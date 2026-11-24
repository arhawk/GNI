"""Persist and query proto-Events (P1-F major-news candidates)."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from gni.events.cluster import ArticleSeed, ProtoCluster, cluster_articles, dominant
from gni.events.geo import centroid
from gni.infrastructure.models import (
    Article,
    Event,
    EventArticle,
    EventLocation,
    EventNarrativeEvidence,
    EventParticipant,
    NarrativeCluster,
    Source,
)
from gni.metrics.definitions import CHINA_INCLUDE_LEVELS
from gni.metrics.service import _latest_analyses


def _seeds_from_db(session: Session) -> list[ArticleSeed]:
    sources = {s.id: s for s in session.scalars(select(Source)).all()}
    articles = list(
        session.scalars(
            select(Article).where(
                Article.exclude_from_metrics.is_(False),
                Article.china_relevance_level.in_(list(CHINA_INCLUDE_LEVELS)),
            )
        ).all()
    )
    analyses = _latest_analyses(session, [a.id for a in articles])
    seeds: list[ArticleSeed] = []
    for a in articles:
        src = sources.get(a.source_id)
        structured = (analyses[a.id].structured_result if a.id in analyses else None) or {}
        framing = structured.get("framing") or {}
        topics = structured.get("topics") or {}
        sentiment = structured.get("sentiment") or {}
        seeds.append(
            ArticleSeed(
                id=a.id,
                title=a.title,
                source_id=a.source_id,
                country_id=src.country_id if src else None,
                published_at=a.published_at or a.first_seen_at,
                china_relevance_level=a.china_relevance_level,
                frame_primary=framing.get("primary"),
                topic_primary=topics.get("primary"),
                sentiment_label=sentiment.get("label"),
            )
        )
    return seeds


def rebuild_proto_events(session: Session, *, min_articles: int = 1, limit: int = 50) -> dict[str, Any]:
    """Replace proto events with freshly clustered candidates. Does not touch non-proto events."""
    seeds = _seeds_from_db(session)
    clusters = [c for c in cluster_articles(seeds) if len(c.article_ids) >= min_articles][:limit]

    # Clear existing proto graph
    proto_ids = list(session.scalars(select(Event.id).where(Event.status == "proto")).all())
    if proto_ids:
        narr_ids = list(
            session.scalars(
                select(NarrativeCluster.id).where(NarrativeCluster.event_id.in_(proto_ids))
            ).all()
        )
        if narr_ids:
            session.execute(
                delete(EventNarrativeEvidence).where(
                    EventNarrativeEvidence.narrative_cluster_id.in_(narr_ids)
                )
            )
            session.execute(delete(NarrativeCluster).where(NarrativeCluster.id.in_(narr_ids)))
        session.execute(delete(EventArticle).where(EventArticle.event_id.in_(proto_ids)))
        session.execute(delete(EventLocation).where(EventLocation.event_id.in_(proto_ids)))
        session.execute(delete(EventParticipant).where(EventParticipant.event_id.in_(proto_ids)))
        session.execute(delete(Event).where(Event.id.in_(proto_ids)))
        session.flush()

    created = 0
    for cl in clusters:
        _persist_cluster(session, cl)
        created += 1
    session.flush()
    return {"created": created, "seed_articles": len(seeds)}


def _persist_cluster(session: Session, cl: ProtoCluster) -> str:
    event_id = str(uuid4())
    topic = dominant(cl.topics)
    frame = dominant(cl.frames)
    # Physical location unknown for title-only clustering — do not invent EVENT_LOCATION coords
    has_phys = False
    event = Event(
        id=event_id,
        title=cl.title,
        summary=f"Proto-event from {len(cl.article_ids)} article(s); "
        f"reporting countries={sorted(cl.country_ids)}. "
        f"No verified physical EVENT_LOCATION (rule cluster).",
        event_type=topic,
        status="proto",
        importance_score=cl.importance_score,
        window_start=cl.window_start,
        window_end=cl.window_end,
        has_physical_location=has_phys,
        schema_version="event_v0.1",
    )
    session.add(event)

    # Participant placeholders from reporting countries are NOT event locations.
    # Optional: ANNOUNCEMENT_LOCATION omitted; PARTICIPANT_LOCATION only if we know actors.
    # For proto: mark china as participant when topic is china-related (always in this pool)
    session.add(
        EventParticipant(
            id=str(uuid4()),
            event_id=event_id,
            participant_id="china",
            participant_name="China",
            role="central_target",
        )
    )

    for aid in cl.article_ids:
        session.add(
            EventArticle(id=str(uuid4()), event_id=event_id, article_id=aid, relation="covers")
        )

    # Narrative cluster from dominant frame (must later attach evidence)
    if frame:
        nid = str(uuid4())
        session.add(
            NarrativeCluster(
                id=nid,
                event_id=event_id,
                label=frame,
                frame_id=frame,
                summary=f"Dominant primary frame among clustered articles: {frame}",
            )
        )
        # Flush so Postgres FK sees narrative_clusters before evidence inserts
        # (no ORM relationship → insert order is not inferred).
        session.flush()
        for aid in cl.article_ids[:5]:
            session.add(
                EventNarrativeEvidence(
                    id=str(uuid4()),
                    narrative_cluster_id=nid,
                    article_id=aid,
                    quote=None,
                )
            )
    return event_id


def list_events(session: Session, *, limit: int = 50) -> list[dict[str, Any]]:
    from sqlalchemy import func

    rows = session.scalars(
        select(Event).order_by(Event.importance_score.desc(), Event.created_at.desc()).limit(limit)
    ).all()
    out: list[dict[str, Any]] = []
    for e in rows:
        art_count = session.scalar(
            select(func.count()).select_from(EventArticle).where(EventArticle.event_id == e.id)
        )
        locs = session.scalars(select(EventLocation).where(EventLocation.event_id == e.id)).all()
        out.append(
            {
                "id": e.id,
                "title": e.title,
                "summary": e.summary,
                "event_type": e.event_type,
                "status": e.status,
                "importance_score": e.importance_score,
                "window_start": e.window_start.isoformat() if e.window_start else None,
                "window_end": e.window_end.isoformat() if e.window_end else None,
                "has_physical_location": e.has_physical_location,
                "article_count": art_count or 0,
                "locations": [
                    {
                        "location_type": loc.location_type,
                        "label": loc.label,
                        "country_id": loc.country_id,
                        "lat": loc.lat,
                        "lon": loc.lon,
                    }
                    for loc in locs
                ],
            }
        )
    return out


def get_event_detail(session: Session, event_id: str) -> dict[str, Any] | None:
    event = session.get(Event, event_id)
    if not event:
        return None
    locs = session.scalars(select(EventLocation).where(EventLocation.event_id == event_id)).all()
    parts = session.scalars(select(EventParticipant).where(EventParticipant.event_id == event_id)).all()
    links = session.scalars(select(EventArticle).where(EventArticle.event_id == event_id)).all()
    article_ids = [l.article_id for l in links]
    articles = {
        a.id: a for a in session.scalars(select(Article).where(Article.id.in_(article_ids))).all()
    } if article_ids else {}
    sources = {s.id: s for s in session.scalars(select(Source)).all()}
    analyses = _latest_analyses(session, article_ids)

    # Who reports: country → media → articles
    by_country: dict[str, dict[str, Any]] = defaultdict(lambda: {"media": defaultdict(list)})
    for link in links:
        art = articles.get(link.article_id)
        if not art:
            continue
        src = sources.get(art.source_id)
        cid = (src.country_id if src else None) or "UNK"
        mid = art.source_id
        mname = src.name if src else mid
        structured = (analyses[art.id].structured_result if art.id in analyses else None) or {}
        by_country[cid]["media"][mid].append(
            {
                "article_id": art.id,
                "title": art.title,
                "url": art.url,
                "source_name": mname,
                "sentiment": (structured.get("sentiment") or {}).get("label"),
                "stance": ((structured.get("stances") or [{}])[0] or {}).get("stance"),
                "frame": (structured.get("framing") or {}).get("primary"),
                "published_at": (art.published_at or art.first_seen_at).isoformat()
                if (art.published_at or art.first_seen_at)
                else None,
            }
        )

    country_view = []
    for cid, blob in by_country.items():
        media_list = []
        for mid, arts in blob["media"].items():
            media_list.append(
                {
                    "source_id": mid,
                    "source_name": arts[0]["source_name"] if arts else mid,
                    "article_count": len(arts),
                    "articles": arts,
                }
            )
        country_view.append(
            {
                "country_id": cid,
                "article_count": sum(m["article_count"] for m in media_list),
                "media": media_list,
            }
        )
    country_view.sort(key=lambda x: -x["article_count"])

    # Reporting distribution map (Who reports) — NOT event geography
    reporting_map = []
    for cv in country_view:
        c = centroid(cv["country_id"])
        if c:
            reporting_map.append(
                {
                    "country_id": cv["country_id"],
                    "lat": c[0],
                    "lon": c[1],
                    "article_count": cv["article_count"],
                    "layer": "reporting_source",
                }
            )

    narrs = session.scalars(
        select(NarrativeCluster).where(NarrativeCluster.event_id == event_id)
    ).all()
    narrative_view = []
    for n in narrs:
        evs = session.scalars(
            select(EventNarrativeEvidence).where(
                EventNarrativeEvidence.narrative_cluster_id == n.id
            )
        ).all()
        narrative_view.append(
            {
                "id": n.id,
                "label": n.label,
                "frame_id": n.frame_id,
                "summary": n.summary,
                "evidence": [
                    {
                        "article_id": e.article_id,
                        "quote": e.quote,
                        "title": articles[e.article_id].title if e.article_id in articles else None,
                    }
                    for e in evs
                ],
            }
        )

    # Timeline from article times
    timeline = []
    for aid, art in articles.items():
        t = art.published_at or art.first_seen_at
        if t:
            timeline.append(
                {
                    "at": t.isoformat(),
                    "kind": "article_published",
                    "article_id": aid,
                    "title": art.title,
                    "country_id": sources[art.source_id].country_id if art.source_id in sources else None,
                }
            )
    timeline.sort(key=lambda x: x["at"])

    return {
        "event": {
            "id": event.id,
            "title": event.title,
            "summary": event.summary,
            "event_type": event.event_type,
            "status": event.status,
            "importance_score": event.importance_score,
            "window_start": event.window_start.isoformat() if event.window_start else None,
            "window_end": event.window_end.isoformat() if event.window_end else None,
            "has_physical_location": event.has_physical_location,
            "schema_version": event.schema_version,
        },
        "views": {
            "where": {
                "locations": [
                    {
                        "location_type": loc.location_type,
                        "label": loc.label,
                        "country_id": loc.country_id,
                        "lat": loc.lat,
                        "lon": loc.lon,
                        "notes": loc.notes,
                    }
                    for loc in locs
                ],
                "note": (
                    "No EVENT_LOCATION pins — proto cluster has no verified physical site."
                    if not event.has_physical_location
                    else None
                ),
            },
            "who_reports": {
                "countries": country_view,
                "reporting_map": reporting_map,
            },
            "how_they_frame": {"narratives": narrative_view},
        },
        "participants": [
            {
                "participant_id": p.participant_id,
                "participant_name": p.participant_name,
                "role": p.role,
            }
            for p in parts
        ],
        "timeline": timeline,
    }


def overview_payload(session: Session, *, days: int = 30) -> dict[str, Any]:
    """Dashboard overview: KPIs + dual map layers + stub trends/topics/anomalies."""
    from gni.dashboard.data import DashboardFilters, compute_dashboard_metrics

    filters = DashboardFilters(days=days)
    metrics = compute_dashboard_metrics(session, filters)
    events = list_events(session, limit=30)

    # Event map pins: only locations with coords and type != reporting
    event_pins = []
    for e in events:
        for loc in e.get("locations") or []:
            if loc.get("lat") is not None and loc.get("lon") is not None:
                event_pins.append(
                    {
                        "event_id": e["id"],
                        "title": e["title"],
                        "location_type": loc["location_type"],
                        "lat": loc["lat"],
                        "lon": loc["lon"],
                        "layer": "event_geography",
                    }
                )

    # Reporting distribution across all proto events' articles
    report_counts: Counter[str] = Counter()
    for e in events:
        detail = get_event_detail(session, e["id"])
        if not detail:
            continue
        for cv in detail["views"]["who_reports"]["countries"]:
            report_counts[cv["country_id"]] += cv["article_count"]
    reporting_pins = []
    for cid, n in report_counts.items():
        c = centroid(cid)
        if c:
            reporting_pins.append(
                {
                    "country_id": cid,
                    "lat": c[0],
                    "lon": c[1],
                    "article_count": n,
                    "layer": "reporting_source",
                }
            )

    research = metrics.get("research") or {}
    weighted = metrics.get("weighted") or {}
    ops = metrics.get("operational") or {}

    return {
        "meta": {
            "days": days,
            "metric_definition_version": metrics.get("metric_definition_version"),
            "relevance_weight_version": metrics.get("relevance_weight_version"),
            "map_modes": ["event_geography", "reporting_source"],
            "map_modes_note": "Mutually exclusive layers — do not mix on one semantic map.",
        },
        "kpis": {
            "total_articles_universe": metrics.get("universe_count"),
            "china_article_count": research.get("article_count", {}).get("value"),
            "weighted_article_volume": weighted.get("weighted_article_volume", {}).get("value"),
            "country_count": ops.get("country_count", {}).get("value"),
            "source_count": ops.get("source_count", {}).get("value"),
            "major_events": len(events),
            "alerts": 0,
        },
        "maps": {
            "event_geography": event_pins,
            "reporting_source": reporting_pins,
        },
        "topics": research.get("topic_share", {}).get("value") or {},
        "sentiment": research.get("sentiment_distribution", {}).get("value") or {},
        "events": events[:15],
        "anomalies": {
            "note": "Rule alerts land in P1-F; listing proto-events by importance for now.",
            "items": [
                {
                    "kind": "major_proto_event",
                    "event_id": e["id"],
                    "title": e["title"],
                    "importance_score": e["importance_score"],
                    "article_count": e["article_count"],
                }
                for e in events[:8]
            ],
        },
        "views_raw_weighted": metrics.get("views"),
    }

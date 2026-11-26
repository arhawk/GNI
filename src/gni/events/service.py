"""Persist and query proto-Events (fingerprint incremental pipeline)."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any
from uuid import NAMESPACE_URL, uuid4, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session

from gni.analysis.stance_util import primary_stance_label
from gni.events.extract import extract_for_articles, load_latest_cards
from gni.events.geo import centroid, location_pin_spec
from gni.events.match import FingerprintCluster, cluster_fingerprints
from gni.events.rollup import (
    attitude_map_rows,
    country_china_attitude_detail,
    rollup_country_china_attitude,
    rollup_event_metrics,
)
from gni.infrastructure.models import (
    Article,
    CountryChinaAttitudeSnapshot,
    Event,
    EventArticle,
    EventLocation,
    EventMetricSnapshot,
    EventNarrativeEvidence,
    EventParticipant,
    EventRevision,
    NarrativeCluster,
    Source,
)
from gni.metrics.definitions import CHINA_INCLUDE_LEVELS
from gni.metrics.service import _latest_analyses


def _primary_stance(structured: dict[str, Any] | None) -> str | None:
    label = primary_stance_label(structured or {})
    return None if label == "unknown" else label


def lock_event(session: Session, event_id: str, *, actor: str = "ui") -> dict[str, Any] | None:
    event = session.get(Event, event_id)
    if not event:
        return None
    event.status = "locked"
    session.add(
        EventRevision(
            id=str(uuid4()),
            event_id=event_id,
            action="lock",
            payload={"status": "locked"},
            actor=actor,
        )
    )
    session.flush()
    return {"id": event.id, "status": event.status}


def merge_events(
    session: Session,
    *,
    keep_id: str,
    merge_id: str,
    actor: str = "ui",
) -> dict[str, Any]:
    keep = session.get(Event, keep_id)
    merge = session.get(Event, merge_id)
    if not keep or not merge:
        raise ValueError("keep_id or merge_id not found")
    if keep_id == merge_id:
        raise ValueError("cannot merge event into itself")
    linked = set(
        session.scalars(select(EventArticle.article_id).where(EventArticle.event_id == keep_id)).all()
    )
    moved = 0
    for link in list(
        session.scalars(select(EventArticle).where(EventArticle.event_id == merge_id)).all()
    ):
        if link.article_id not in linked:
            session.add(
                EventArticle(
                    id=str(uuid4()),
                    event_id=keep_id,
                    article_id=link.article_id,
                    relation=link.relation or "covers",
                )
            )
            moved += 1
        session.delete(link)
    merge.status = "closed"
    session.add(
        EventRevision(
            id=str(uuid4()),
            event_id=keep_id,
            action="merge",
            payload={"merged_from": merge_id, "articles_moved": moved},
            actor=actor,
        )
    )
    session.add(
        EventRevision(
            id=str(uuid4()),
            event_id=merge_id,
            action="merge",
            payload={"merged_into": keep_id},
            actor=actor,
        )
    )
    session.flush()
    return {"keep_id": keep_id, "merge_id": merge_id, "articles_moved": moved, "merge_status": "closed"}


# Never auto-delete or overwrite these during rebuild (manual / terminal states).
_PRESERVE_EVENT_STATUSES = frozenset({"confirmed", "closed", "locked"})


def rebuild_proto_events(
    session: Session,
    *,
    min_articles: int = 1,
    limit: int = 50,
    extract: bool = True,
    use_llm: bool = True,
) -> dict[str, Any]:
    """Rebuild events via fingerprint extract→match→rollup."""
    if extract:
        extract_stats = extract_for_articles(session, limit=500)
    else:
        extract_stats = {"articles": 0, "candidates_written": 0}

    cards = load_latest_cards(session, limit_articles=500)
    clusters = [
        c
        for c in cluster_fingerprints(cards, use_llm=use_llm)
        if len(c.article_ids) >= min_articles
    ][:limit]

    # Incremental upsert by fingerprint_hash — do NOT wipe proto/active graph.
    created = 0
    updated = 0
    event_ids: list[str] = []
    for cl in clusters:
        eid, is_new = _persist_fingerprint_cluster(session, cl)
        event_ids.append(eid)
        if is_new:
            created += 1
        else:
            updated += 1
    session.flush()
    rollup_event_metrics(session, event_ids=event_ids)
    attitude_n = rollup_country_china_attitude(session, window="30d")
    return {
        "created": created,
        "updated": updated,
        "seed_articles": len({c.article_id for c in cards}),
        "candidates_written": extract_stats.get("candidates_written", 0),
        "path": "fingerprint_incremental",
        "attitude_snapshots": attitude_n,
    }


def _stable_event_id(fingerprint: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"gni:event:{fingerprint}"))


def _persist_fingerprint_cluster(session: Session, cl: FingerprintCluster) -> tuple[str, bool]:
    """Upsert by fingerprint_hash / deterministic UUID. Returns (event_id, created_new)."""
    fp = cl.fingerprint_hash
    existing = session.scalar(select(Event).where(Event.fingerprint_hash == fp).limit(1))
    if existing is None:
        eid = _stable_event_id(fp)
        existing = session.get(Event, eid)

    pin = location_pin_spec(
        label=cl.location_label,
        country_id=cl.location_country_id,
        text=cl.location_label,
    )
    loc_label = pin["label"] or cl.location_label
    loc_cid = pin["country_id"]
    coords = (pin["lat"], pin["lon"]) if pin["lat"] is not None and pin["lon"] is not None else None
    has_phys = coords is not None
    # True event time only (may be None); never published_at.
    true_event_time = cl.event_time
    summary = (
        f"Fingerprint event from {len(cl.article_ids)} article(s); "
        f"actor={cl.actor_key} action={cl.action_key}. "
        + (
            f"Location hint: {loc_label} ({loc_cid or 'n/a'}, "
            f"precision={pin.get('geographic_precision')})."
            if loc_label
            else "No verified physical EVENT_LOCATION."
        )
        + (
            " event_time unknown (not filled from published_at)."
            if true_event_time is None
            else ""
        )
    )

    if existing is not None:
        event_id = existing.id
        if existing.status not in _PRESERVE_EVENT_STATUSES:
            existing.title = cl.title
            existing.summary = summary
            existing.event_type = cl.cards[0].event_type
            existing.status = "active" if cl.high_confidence else "proto"
            existing.importance_score = cl.importance_score
            existing.window_start = cl.window_start
            existing.window_end = cl.window_end
            existing.has_physical_location = has_phys or existing.has_physical_location
            existing.actor_key = cl.actor_key
            existing.action_key = cl.action_key
            existing.object_key = cl.object_key
            existing.event_time = true_event_time
            existing.qualifiers = cl.cards[0].qualifiers or {}
            existing.fingerprint_hash = fp
            existing.schema_version = "event_v0.2"
        linked = set(
            session.scalars(
                select(EventArticle.article_id).where(EventArticle.event_id == event_id)
            ).all()
        )
        for aid in cl.article_ids:
            if aid not in linked:
                session.add(
                    EventArticle(
                        id=str(uuid4()), event_id=event_id, article_id=aid, relation="covers"
                    )
                )
        return event_id, False

    event_id = _stable_event_id(fp)
    event = Event(
        id=event_id,
        title=cl.title,
        summary=summary,
        event_type=cl.cards[0].event_type,
        status="active" if cl.high_confidence else "proto",
        importance_score=cl.importance_score,
        window_start=cl.window_start,
        window_end=cl.window_end,
        has_physical_location=has_phys,
        actor_key=cl.actor_key,
        action_key=cl.action_key,
        object_key=cl.object_key,
        event_time=true_event_time,
        qualifiers=cl.cards[0].qualifiers or {},
        fingerprint_hash=fp,
        schema_version="event_v0.2",
    )
    session.add(event)
    session.add(
        EventParticipant(
            id=str(uuid4()),
            event_id=event_id,
            participant_id="china",
            participant_name="China",
            role="central_target",
        )
    )
    if cl.actor_key and cl.actor_key != "china":
        session.add(
            EventParticipant(
                id=str(uuid4()),
                event_id=event_id,
                participant_id=cl.actor_key,
                participant_name=cl.actor_key,
                role="actor",
            )
        )
    if loc_label or pin.get("geographic_precision") not in (None, "unknown"):
        session.add(
            EventLocation(
                id=str(uuid4()),
                event_id=event_id,
                location_type="EVENT_LOCATION",
                label=loc_label,
                country_id=loc_cid,
                lat=coords[0] if coords else None,
                lon=coords[1] if coords else None,
                geographic_precision=pin.get("geographic_precision"),
                confidence=pin.get("confidence"),
                evidence=pin.get("evidence"),
                notes="Heuristic place dictionary — not a geocoder; maritime has no fake coords.",
            )
        )
    for aid in cl.article_ids:
        session.add(
            EventArticle(id=str(uuid4()), event_id=event_id, article_id=aid, relation="covers")
        )
    return event_id, True


def _event_sort_time(e: Event) -> datetime:
    """Newest-first board key: event_time → window_end → window_start → created_at."""
    for t in (e.event_time, e.window_end, e.window_start, e.created_at):
        if t is not None:
            return t if t.tzinfo else t.replace(tzinfo=timezone.utc)
    return datetime.min.replace(tzinfo=timezone.utc)


def list_events(
    session: Session,
    *,
    limit: int = 50,
    window_start: datetime | None = None,
    window_end: datetime | None = None,
) -> list[dict[str, Any]]:
    from sqlalchemy import func

    # Fetch then sort in Python so SQLite/Postgres both honor event_time fallbacks.
    if window_start is not None or window_end is not None:
        all_rows = list(session.scalars(select(Event)).all())
        ws = window_start if (window_start is None or window_start.tzinfo) else window_start.replace(tzinfo=timezone.utc)
        we = window_end if (window_end is None or window_end.tzinfo) else window_end.replace(tzinfo=timezone.utc)
        rows = []
        for e in all_rows:
            t = _event_sort_time(e)
            if ws is not None and t < ws:
                continue
            if we is not None and t >= we:
                continue
            rows.append(e)
    else:
        rows = list(session.scalars(select(Event).limit(max(limit * 3, 80))).all())
    rows.sort(key=_event_sort_time, reverse=True)
    rows = rows[:limit]
    out: list[dict[str, Any]] = []
    for e in rows:
        art_count = session.scalar(
            select(func.count()).select_from(EventArticle).where(EventArticle.event_id == e.id)
        )
        locs = session.scalars(select(EventLocation).where(EventLocation.event_id == e.id)).all()
        sort_t = _event_sort_time(e)
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
                "event_time": e.event_time.isoformat() if e.event_time else None,
                "sort_time": sort_t.isoformat() if sort_t.year > 1 else None,
                "has_physical_location": e.has_physical_location,
                "article_count": art_count or 0,
                "locations": [
                    {
                        "location_type": loc.location_type,
                        "label": loc.label,
                        "country_id": loc.country_id,
                        "lat": loc.lat,
                        "lon": loc.lon,
                        "geographic_precision": getattr(loc, "geographic_precision", None),
                        "confidence": getattr(loc, "confidence", None),
                    }
                    for loc in locs
                ],
                "actor_key": getattr(e, "actor_key", None),
                "action_key": getattr(e, "action_key", None),
                "first_seen_at": e.created_at.isoformat() if getattr(e, "created_at", None) else None,
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
                "stance": _primary_stance(structured),
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

    metric = session.scalar(
        select(EventMetricSnapshot).where(
            EventMetricSnapshot.event_id == event_id,
            EventMetricSnapshot.window == "all",
        )
    )

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
            "actor_key": getattr(event, "actor_key", None),
            "action_key": getattr(event, "action_key", None),
            "object_key": getattr(event, "object_key", None),
            "event_time": event.event_time.isoformat()
            if getattr(event, "event_time", None)
            else None,
            "fingerprint_hash": getattr(event, "fingerprint_hash", None),
        },
        "metrics": {
            "article_count": metric.article_count if metric else len(article_ids),
            "source_count": metric.source_count if metric else None,
            "country_count": metric.country_count if metric else None,
            "sentiment_shares": metric.sentiment_shares if metric else None,
            "stance_shares": metric.stance_shares if metric else None,
            "by_country": metric.by_country if metric else None,
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


def overview_payload(
    session: Session,
    *,
    days: int = 30,
    window_start: datetime | None = None,
    window_end: datetime | None = None,
) -> dict[str, Any]:
    """Dashboard overview: KPIs + dual map layers + stub trends/topics/anomalies."""
    from gni.dashboard.data import (
        DashboardFilters,
        article_data_range,
        compute_dashboard_metrics,
        monitoring_panel_counts,
        resolve_filter_window,
    )

    start_dt = window_start
    end_dt = window_end
    filters = DashboardFilters(days=days, window_start=start_dt, window_end=end_dt)
    start, end = resolve_filter_window(filters)
    span_days = max(1, int(round((end - start).total_seconds() / 86400.0)))
    metrics = compute_dashboard_metrics(session, filters)
    panel = monitoring_panel_counts(session)
    data_min, data_max = article_data_range(session)
    events = list_events(session, limit=30)

    # Event map pins: only locations with coords (no coords → list only, not map)
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
                        "article_count": e.get("article_count"),
                        "importance": e.get("importance_score"),
                        "layer": "event_geography",
                    }
                )

    # Reporting distribution (API retained; UI does not promote)
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

    # Ensure attitude snapshots exist for window label used by UI
    existing_att = session.scalar(select(CountryChinaAttitudeSnapshot.id).limit(1))
    if not existing_att:
        rollup_country_china_attitude(
            session, window="30d", window_start=start, window_end=end
        )
    attitude_rows = attitude_map_rows(session, window="30d")

    research = metrics.get("research") or {}
    weighted = metrics.get("weighted") or {}
    ops = metrics.get("operational") or {}

    return {
        "meta": {
            "days": span_days,
            "preset_days": days if start_dt is None and end_dt is None else None,
            "window_start": start.isoformat(),
            "window_end": end.isoformat(),
            "data_min": data_min.isoformat() if data_min else None,
            "data_max": data_max.isoformat() if data_max else None,
            "metric_definition_version": metrics.get("metric_definition_version"),
            "relevance_weight_version": metrics.get("relevance_weight_version"),
            "map_modes": ["event_time_list", "country_china_attitude"],
            "map_modes_note": (
                "Primary board: events newest-first by event_time. "
                "Attitude map: monitored media sample colors — not official state position."
            ),
            "time_window": metrics.get("time_window"),
        },
        "kpis": {
            "total_articles_universe": metrics.get("universe_count"),
            "china_article_count": research.get("article_count", {}).get("value"),
            "weighted_article_volume": weighted.get("weighted_article_volume", {}).get("value"),
            "monitoring_countries": panel["monitoring_countries"],
            "active_sources_registry": panel["active_sources_registry"],
            "china_reporting_countries": ops.get("country_count", {}).get("value"),
            "china_reporting_sources": ops.get("source_count", {}).get("value"),
            # Backward-compatible aliases (China-set) — prefer renamed fields above
            "country_count": ops.get("country_count", {}).get("value"),
            "source_count": ops.get("source_count", {}).get("value"),
            "major_events": len(events),
            "alerts": 0,
        },
        "maps": {
            "event_geography": event_pins,
            "country_china_attitude": attitude_rows,
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


def get_country_china_attitude(
    session: Session,
    country_id: str,
    *,
    window: str = "30d",
) -> dict[str, Any]:
    return country_china_attitude_detail(session, country_id, window=window)

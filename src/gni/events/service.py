"""Persist and query proto-Events (fingerprint incremental pipeline)."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any
from uuid import NAMESPACE_URL, uuid4, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session

from gni.analysis.budget import llm_allowed, snapshot_budget
from gni.analysis.stance_util import primary_stance_label
from gni.core.config import Settings, get_settings
from gni.events.extract import extract_for_articles, load_latest_cards
from gni.events.geo import centroid, location_pin_spec
from gni.events.llm_grouping import SYSTEM_PROMPT, CallFn, cluster_cards_daily, make_cached_llm_call
from gni.events.lifecycle import HIDDEN_STATUSES, RECENT_TIER_STATUSES, refresh_event_lifecycle
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
    merge.status = "merged"
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
    return {"keep_id": keep_id, "merge_id": merge_id, "articles_moved": moved, "merge_status": "merged"}


def split_event(
    session: Session,
    *,
    source_event_id: str,
    article_ids_to_split: list[str],
    new_title: str | None = None,
    actor: str = "ui",
) -> dict[str, Any]:
    """Split selected articles from an existing Event into a new Event with full EventRevision audit."""
    src = session.get(Event, source_event_id)
    if not src:
        raise ValueError("source_event_id not found")
    split_set = {str(aid).strip() for aid in article_ids_to_split if str(aid).strip()}
    if not split_set:
        raise ValueError("article_ids_to_split must be non-empty")

    links = list(
        session.scalars(select(EventArticle).where(EventArticle.event_id == source_event_id)).all()
    )
    to_move = [lk for lk in links if lk.article_id in split_set]
    if not to_move:
        raise ValueError("no matching EventArticle links to split")

    new_event_id = str(uuid4())
    new_ev = Event(
        id=new_event_id,
        title=(new_title or f"{src.title} (split)")[:280],
        summary=src.summary,
        event_type=src.event_type,
        event_time=None,  # Never fabricate event_time on split
        status="proto",
        importance_score=src.importance_score,
    )
    session.add(new_ev)
    session.flush()

    moved_ids: list[str] = []
    for lk in to_move:
        session.add(
            EventArticle(
                id=str(uuid4()),
                event_id=new_event_id,
                article_id=lk.article_id,
                relation=lk.relation or "covers",
            )
        )
        moved_ids.append(lk.article_id)
        session.delete(lk)

    session.add(
        EventRevision(
            id=str(uuid4()),
            event_id=source_event_id,
            action="split",
            payload={"split_into": new_event_id, "articles_moved": moved_ids},
            actor=actor,
        )
    )
    session.add(
        EventRevision(
            id=str(uuid4()),
            event_id=new_event_id,
            action="split",
            payload={"split_from": source_event_id, "articles_moved": moved_ids},
            actor=actor,
        )
    )
    session.flush()
    return {
        "source_event_id": source_event_id,
        "new_event_id": new_event_id,
        "articles_moved": len(moved_ids),
        "moved_article_ids": moved_ids,
    }


# Never overwrite these during rebuild (manual / merge states).
# dormant / closed are lifecycle states: rebuild may re-link articles, lifecycle recomputes status.
_PRESERVE_EVENT_STATUSES = frozenset({"confirmed", "merged", "locked"})


def _budgeted_grouping_call(session: Session, settings: Settings) -> CallFn | None:
    """LLM grouping call guarded by the same daily budget snapshot as article analysis."""
    # Imported lazily: gni.analysis.deepseek imports gni.events.fingerprint, which initializes
    # this package and would otherwise create a circular import at module load.
    from gni.analysis.deepseek import DeepSeekLLMProvider, estimate_call_cost_usd

    if not settings.llm_api_key:
        return None
    try:
        provider = DeepSeekLLMProvider(settings)
    except RuntimeError:
        return None
    raw_call = make_cached_llm_call(provider=provider, model=settings.llm_model)

    def call(prompt: str) -> dict[str, Any] | None:
        snapshot = snapshot_budget(session, settings)
        est = estimate_call_cost_usd(prompt_chars=len(prompt) + len(SYSTEM_PROMPT))
        if not llm_allowed(snapshot, estimated_cost_usd=est, ignore_article_limit=True):
            return None
        return raw_call(prompt)

    return call


def rebuild_proto_events(
    session: Session,
    *,
    min_articles: int = 1,
    limit: int = 50,
    extract: bool = True,
    use_llm: bool = True,
    grouping: str = "llm_daily",
) -> dict[str, Any]:
    """Rebuild events via fingerprint extract→match→rollup.

    grouping:
      - "llm_daily": one batch LLM grouping call per day; falls back to rules per day on any failure.
      - "rule": pairwise rule/LLM-judge greedy clustering over all cards (legacy path).
    """
    if extract:
        extract_stats = extract_for_articles(session, limit=500)
    else:
        extract_stats = {"articles": 0, "candidates_written": 0}

    cards = load_latest_cards(session, limit_articles=500)
    grouping_stats: dict[str, int] = {}
    if grouping == "llm_daily":
        call = _budgeted_grouping_call(session, get_settings()) if use_llm else None
        all_clusters, grouping_stats = cluster_cards_daily(cards, call=call, use_llm=use_llm)
    elif grouping == "rule":
        all_clusters = cluster_fingerprints(cards, use_llm=use_llm)
    else:
        raise ValueError(f"unknown grouping mode: {grouping!r}")
    all_clusters.sort(key=lambda c: -c.importance_score)
    clusters = [c for c in all_clusters if len(c.article_ids) >= min_articles][:limit]

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
    # Lifecycle covers every event, not just the clusters touched in this rebuild.
    lifecycle_stats = refresh_event_lifecycle(session, settings=get_settings())
    rollup_event_metrics(session, event_ids=event_ids)
    attitude_n = rollup_country_china_attitude(session, window="30d")
    return {
        "created": created,
        "updated": updated,
        "seed_articles": len({c.article_id for c in cards}),
        "candidates_written": extract_stats.get("candidates_written", 0),
        "path": "fingerprint_incremental",
        "grouping": {"mode": grouping, **grouping_stats},
        "attitude_snapshots": attitude_n,
        "lifecycle": lifecycle_stats,
    }


def _min_time(a: datetime | None, b: datetime | None) -> datetime | None:
    if a is None:
        return b
    if b is None:
        return a
    return min(_as_utc(a), _as_utc(b))


def _max_time(a: datetime | None, b: datetime | None) -> datetime | None:
    if a is None:
        return b
    if b is None:
        return a
    return max(_as_utc(a), _as_utc(b))


def _as_utc(t: datetime) -> datetime:
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


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
            # dormant/closed are set by refresh_event_lifecycle, not by clustering.
            if existing.status in RECENT_TIER_STATUSES:
                existing.status = "active" if cl.high_confidence else "proto"
            existing.importance_score = cl.importance_score
            # Widen, never shrink: a later cluster must not erase earlier coverage.
            existing.window_start = _min_time(existing.window_start, cl.window_start)
            existing.window_end = _max_time(existing.window_end, cl.window_end)
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
    include_closed: bool = False,
) -> list[dict[str, Any]]:
    """Events newest-first. closed (archived) and merged rows are hidden unless include_closed."""
    from sqlalchemy import func

    # Fetch then sort in Python so SQLite/Postgres both honor event_time fallbacks.
    base = select(Event)
    if not include_closed:
        base = base.where(Event.status.not_in(sorted(HIDDEN_STATUSES)))
    if window_start is not None or window_end is not None:
        all_rows = list(session.scalars(base).all())
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
        rows = list(session.scalars(base.limit(max(limit * 3, 80))).all())
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
        raw_sent = structured.get("sentiment")
        sent_val = raw_sent.get("label") if isinstance(raw_sent, dict) else (raw_sent if isinstance(raw_sent, str) else None)
        raw_frame = structured.get("framing")
        frame_val = raw_frame.get("primary") if isinstance(raw_frame, dict) else (raw_frame if isinstance(raw_frame, str) else None)
        by_country[cid]["media"][mid].append(
            {
                "article_id": art.id,
                "title": art.title,
                "url": art.url,
                "source_name": mname,
                "sentiment": sent_val,
                "stance": _primary_stance(structured),
                "frame": frame_val,
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


def get_country_china_attitude(
    session: Session,
    country_id: str,
    *,
    window: str = "30d",
) -> dict[str, Any]:
    return country_china_attitude_detail(session, country_id, window=window)

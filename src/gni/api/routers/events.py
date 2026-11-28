"""Events API endpoints: list, enriched detail (event_time timeline + cross-country + assessment), lock/merge/split."""

from __future__ import annotations

from collections import Counter
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

from gni.api.routers.common import (
    extract_verified_evidence,
    load_cached_assessments,
)
from gni.events.service import (
    get_event_detail,
    list_events,
    lock_event,
    merge_events,
    rebuild_proto_events,
    split_event,
)
from gni.infrastructure.db import session_scope
from gni.infrastructure.models import Article, EventArticle, Source
from gni.metrics.service import _latest_analyses

router = APIRouter(tags=["events"])


class EventSplitRequest(BaseModel):
    article_ids: list[str] = Field(..., min_length=1, description="Article IDs to move into new event")
    new_title: str = Field(..., min_length=1, description="Title for split event")


@router.get("/api/events")
def api_events(
    limit: int = Query(50, ge=1, le=200),
    include_closed: bool = Query(False, description="Include archived (closed) events"),
) -> dict[str, Any]:
    with session_scope() as session:
        return {"events": list_events(session, limit=limit, include_closed=include_closed)}


@router.get("/api/events/{event_id}")
def api_event_detail(event_id: str) -> dict[str, Any]:
    with session_scope() as session:
        detail = get_event_detail(session, event_id)
        if not detail:
            raise HTTPException(status_code=404, detail="event not found")

        ev = detail["event"]
        # Strict event_time timeline (never substitute published_at when event_time is None)
        event_timeline: list[dict[str, Any]] = [
            {
                "event_time": ev.get("event_time"),
                "time_status": "known" if ev.get("event_time") else "unknown",
                "label": ev.get("title"),
                "kind": "event_occurrence",
                "note": None
                if ev.get("event_time")
                else "事件发生时间 (event_time) 未知；不以文章发布时间 (published_at) 替代。",
            }
        ]
        # Media coverage publication sequence (explicitly labeled published_at)
        coverage_timeline = [
            {
                "published_at": item.get("at"),
                "kind": item.get("kind") or "article_published",
                "article_id": item.get("article_id"),
                "title": item.get("title"),
                "country_id": item.get("country_id"),
            }
            for item in (detail.get("timeline") or [])
        ]

        # Cross-country interpretation comparison
        cross_country: list[dict[str, Any]] = []
        who_countries = (detail.get("views") or {}).get("who_reports", {}).get("countries") or []
        for c in who_countries:
            sent_c: Counter[str] = Counter()
            stance_c: Counter[str] = Counter()
            frames_c: Counter[str] = Counter()
            rep_articles: list[dict[str, Any]] = []
            for m in c.get("media") or []:
                for a in m.get("articles") or []:
                    sent_c[str(a.get("sentiment") or "unknown")] += 1
                    stance_c[str(a.get("stance") or "Unclassified")] += 1
                    if a.get("frame"):
                        frames_c[str(a["frame"])] += 1
                    if len(rep_articles) < 3:
                        rep_articles.append(
                            {
                                "article_id": a.get("article_id"),
                                "title": a.get("title"),
                                "source_name": m.get("source_name"),
                                "published_at": a.get("published_at"),
                                "stance": a.get("stance"),
                                "sentiment": a.get("sentiment"),
                            }
                        )
            cross_country.append(
                {
                    "country_id": c.get("country_id"),
                    "article_count": c.get("article_count") or 0,
                    "media_count": len(c.get("media") or []),
                    "sentiment_counts": dict(sent_c),
                    "stance_counts": dict(stance_c),
                    "top_frames": [k for k, _ in frames_c.most_common(3)],
                    "sample_warning": (c.get("article_count") or 0) < 3,
                    "representative_articles": rep_articles,
                }
            )

        # Evidence refs from linked articles
        ea_ids = [
            r.article_id
            for r in session.scalars(select(EventArticle).where(EventArticle.event_id == event_id)).all()
        ]
        articles = list(session.scalars(select(Article).where(Article.id.in_(ea_ids))).all()) if ea_ids else []
        sources = {s.id: s for s in session.scalars(select(Source)).all()}
        analyses = _latest_analyses(session, [a.id for a in articles])
        evidence_segments: list[dict[str, Any]] = []
        for a in articles[:15]:
            evs = extract_verified_evidence(a, sources.get(a.source_id), analyses.get(a.id))
            evidence_segments.extend(evs[:2])

        # Cached event_analysis assessment if available
        cached = load_cached_assessments(session, report_type="daily")
        event_assessment = cached.get("event_analysis")

        detail["event_timeline"] = event_timeline
        detail["coverage_timeline"] = coverage_timeline
        detail["cross_country_interpretation"] = cross_country
        detail["evidence_segments"] = evidence_segments[:20]
        detail["event_assessment"] = event_assessment
        return detail


@router.post("/api/events/rebuild")
def api_rebuild_events(
    min_articles: int = Query(1, ge=1, le=20),
) -> dict[str, Any]:
    with session_scope() as session:
        return rebuild_proto_events(session, min_articles=min_articles)


@router.post("/api/events/{event_id}/lock")
def api_event_lock(event_id: str) -> dict[str, Any]:
    with session_scope() as session:
        out = lock_event(session, event_id)
        if not out:
            raise HTTPException(status_code=404, detail="event not found")
        return out


@router.post("/api/events/merge")
def api_events_merge(
    keep_id: str = Query(..., description="Survivor event id"),
    merge_id: str = Query(..., description="Event to close and attach"),
) -> dict[str, Any]:
    with session_scope() as session:
        try:
            return merge_events(session, keep_id=keep_id, merge_id=merge_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/api/events/{event_id}/split")
def api_event_split(event_id: str, body: EventSplitRequest) -> dict[str, Any]:
    with session_scope() as session:
        try:
            return split_event(
                session,
                event_id=event_id,
                article_ids=body.article_ids,
                new_title=body.new_title,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

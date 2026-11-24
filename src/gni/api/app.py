"""FastAPI surface for React dashboard (Event Intelligence + metrics overview)."""

from __future__ import annotations

from datetime import datetime

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from gni import __version__
from gni.dashboard.data import MAX_WINDOW_DAYS
from gni.events.service import (
    get_country_china_attitude,
    get_event_detail,
    list_events,
    overview_payload,
    rebuild_proto_events,
)
from gni.infrastructure.db import ensure_schema, session_scope
from gni.reports.daily import build_daily_report

app = FastAPI(title="GNI API", version=__version__)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    ensure_schema()


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "version": __version__}


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(raw)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"invalid datetime: {value}") from e


@app.get("/api/overview")
def api_overview(
    days: int = Query(30, ge=1, le=MAX_WINDOW_DAYS),
    start: str | None = Query(None, description="ISO UTC window start"),
    end: str | None = Query(None, description="ISO UTC window end (may be before now)"),
) -> dict:
    start_dt = _parse_iso(start)
    end_dt = _parse_iso(end)
    try:
        with session_scope() as session:
            return overview_payload(
                session, days=days, window_start=start_dt, window_end=end_dt
            )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.get("/api/events")
def api_events(limit: int = Query(50, ge=1, le=200)) -> dict:
    with session_scope() as session:
        return {"events": list_events(session, limit=limit)}


@app.get("/api/events/{event_id}")
def api_event_detail(event_id: str) -> dict:
    with session_scope() as session:
        detail = get_event_detail(session, event_id)
        if not detail:
            raise HTTPException(status_code=404, detail="event not found")
        return detail


@app.post("/api/events/rebuild")
def api_rebuild_events(
    min_articles: int = Query(1, ge=1, le=20),
    legacy_title: bool = Query(False, description="Use legacy title Jaccard clustering"),
) -> dict:
    with session_scope() as session:
        return rebuild_proto_events(
            session, min_articles=min_articles, legacy_title=legacy_title
        )


@app.get("/api/countries/{country_id}/china-attitude")
def api_country_china_attitude(
    country_id: str,
    window: str = Query("30d"),
) -> dict:
    with session_scope() as session:
        return get_country_china_attitude(session, country_id.upper(), window=window)


@app.get("/api/reports/daily")
def api_daily_report(
    date: str | None = Query(None, description="YYYY-MM-DD in Asia/Shanghai"),
    polish: bool = Query(False, description="LLM narrative polish only"),
) -> dict:
    try:
        with session_scope() as session:
            return build_daily_report(session, day=date, polish=polish)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.get("/api/search")
def api_search(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(12, ge=1, le=40),
) -> dict:
    """Title search over events (priority) and articles."""
    from sqlalchemy import or_, select

    from gni.infrastructure.models import Article, Event, Source

    term = q.strip()
    if len(term) < 2:
        return {"query": term, "results": []}
    pattern = f"%{term}%"
    with session_scope() as session:
        events = list(
            session.scalars(
                select(Event)
                .where(or_(Event.title.ilike(pattern), Event.summary.ilike(pattern)))
                .order_by(Event.updated_at.desc())
                .limit(limit)
            ).all()
        )
        results: list[dict] = [
            {
                "kind": "event",
                "id": e.id,
                "title": e.title,
                "subtitle": e.status,
                "url": None,
            }
            for e in events
        ]
        remain = max(0, limit - len(results))
        if remain:
            articles = list(
                session.scalars(
                    select(Article)
                    .where(Article.title.ilike(pattern))
                    .order_by(Article.first_seen_at.desc())
                    .limit(remain)
                ).all()
            )
            sources = {
                s.id: s
                for s in session.scalars(
                    select(Source).where(Source.id.in_({a.source_id for a in articles}))
                ).all()
            } if articles else {}
            for a in articles:
                src = sources.get(a.source_id)
                results.append(
                    {
                        "kind": "article",
                        "id": a.id,
                        "title": a.title,
                        "subtitle": (src.country_id if src else None) or a.source_id,
                        "url": a.url,
                    }
                )
        return {"query": term, "results": results}

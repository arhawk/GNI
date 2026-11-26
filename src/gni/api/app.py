"""FastAPI surface for React dashboard (Event Intelligence + metrics overview)."""

from __future__ import annotations

from datetime import datetime

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import select

from gni import __version__
from gni.alerts.service import build_alerts_payload, run_alert_engine, transition_alert
from gni.analysis.stance_util import (
    extract_v1_china_stance,
    extract_v1_stance_evidence,
    extract_v1_topics,
)
from gni.dashboard.data import MAX_WINDOW_DAYS
from gni.dashboard.pages_api import (
    countries_list_payload,
    country_detail_payload,
    system_status_payload,
    trends_payload,
)
from gni.events.service import (
    get_country_china_attitude,
    get_event_detail,
    list_events,
    lock_event,
    merge_events,
    overview_payload,
    rebuild_proto_events,
)
from gni.infrastructure.db import ensure_schema, session_scope
from gni.infrastructure.models import Article, Source
from gni.metrics.service import _latest_analyses
from gni.reports.daily import SCHEMA_VERSION as DAILY_SCHEMA_VERSION
from gni.reports.daily import build_daily_report
from gni.reports.monthly import build_monthly_report
from gni.reports.weekly import build_weekly_report
from gni.search.service import search_all

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
    return {
        "status": "ok",
        "version": __version__,
        "daily_schema": DAILY_SCHEMA_VERSION,
    }


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
) -> dict:
    with session_scope() as session:
        return rebuild_proto_events(session, min_articles=min_articles)


@app.get("/api/countries/{country_id}/china-attitude")
def api_country_china_attitude(
    country_id: str,
    window: str = Query("30d"),
) -> dict:
    with session_scope() as session:
        return get_country_china_attitude(session, country_id.upper(), window=window)


@app.get("/api/reports/daily")
def api_daily_report(
    response: Response,
    date: str | None = Query(None, description="YYYY-MM-DD in Asia/Shanghai"),
    polish: bool = Query(False, description="LLM narrative polish only"),
) -> dict:
    try:
        with session_scope() as session:
            payload = build_daily_report(session, day=date, polish=polish)
        response.headers["X-GNI-Report-Schema"] = str(payload.get("schema_version") or DAILY_SCHEMA_VERSION)
        return payload
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.get("/api/reports/weekly")
def api_weekly_report(
    end: str | None = Query(None, description="Week end YYYY-MM-DD (report TZ)"),
) -> dict:
    try:
        with session_scope() as session:
            return build_weekly_report(session, end_day=end)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.get("/api/reports/monthly")
def api_monthly_report(
    month: str | None = Query(None, description="YYYY-MM"),
) -> dict:
    try:
        with session_scope() as session:
            return build_monthly_report(session, month=month)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


class ReportAnalyzeRequest(BaseModel):
    period: str | None = Field(default=None, description="YYYY-MM-DD (daily/weekly end) or YYYY-MM (monthly)")
    tasks: list[str] | None = Field(default=None, description="Optional subset of task_type names to run/retry")
    force: bool = Field(default=False, description="Bypass cache and regenerate targeted tasks")
    engine: str = Field(default="legacy", description="'legacy' (default 3-task) or 'v2' (unified 9-task assessment engine)")
    save_snapshot: bool = Field(default=False, description="Persist generated daily report into ReportSnapshot")


@app.post("/api/reports/{report_type}/analyze")
def api_analyze_report(report_type: str, body: ReportAnalyzeRequest) -> dict:
    """Explicitly trigger (or retry failed tasks for) the LLM Intelligence Narrative Layer."""
    rt = report_type.strip().lower()
    if rt not in {"daily", "weekly", "monthly"}:
        raise HTTPException(status_code=400, detail=f"unsupported report_type: {report_type}")
    try:
        with session_scope() as session:
            if rt == "daily":
                use_v2 = body.engine.strip().lower() == "v2"
                payload = build_daily_report(
                    session,
                    day=body.period,
                    analyze=not use_v2,
                    analyze_tasks=None if use_v2 else body.tasks,
                    force_analyze=body.force,
                    run_v2_assessments=use_v2,
                    assessment_tasks=body.tasks if use_v2 else None,
                )
                if body.save_snapshot:
                    from gni.reports.daily_package import save_daily_report_snapshot

                    save_daily_report_snapshot(session, payload)
                return payload
            if rt == "weekly":
                return build_weekly_report(
                    session,
                    end_day=body.period,
                    analyze=True,
                    analyze_tasks=body.tasks,
                    force_analyze=body.force,
                )
            return build_monthly_report(
                session,
                month=body.period,
                analyze=True,
                analyze_tasks=body.tasks,
                force_analyze=body.force,
            )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.get("/api/search")
def api_search(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(20, ge=1, le=40),
) -> dict:
    with session_scope() as session:
        return search_all(session, q, limit=limit)


@app.get("/api/trends")
def api_trends(
    days: int = Query(30, ge=1, le=MAX_WINDOW_DAYS),
    country: str | None = Query(None, description="Optional country id"),
) -> dict:
    with session_scope() as session:
        return trends_payload(session, days=days, country_id=country.upper() if country else None)


@app.get("/api/countries")
def api_countries() -> dict:
    with session_scope() as session:
        return countries_list_payload(session)


@app.get("/api/countries/{country_id}")
def api_country_detail(country_id: str) -> dict:
    with session_scope() as session:
        detail = country_detail_payload(session, country_id)
        if not detail:
            raise HTTPException(status_code=404, detail="country not found")
        return detail


@app.get("/api/alerts")
def api_alerts(
    window_start: str | None = Query(None),
    window_end: str | None = Query(None),
    run: bool = Query(False, description="Run rule engine before read"),
) -> dict:
    with session_scope() as session:
        return build_alerts_payload(
            session,
            window_start=_parse_iso(window_start),
            window_end=_parse_iso(window_end),
            run_engine=run,
        )


@app.post("/api/alerts/run")
def api_alerts_run() -> dict:
    with session_scope() as session:
        return run_alert_engine(session)


@app.post("/api/alerts/{alert_id}/acknowledge")
def api_alert_ack(alert_id: str) -> dict:
    with session_scope() as session:
        a = transition_alert(session, alert_id, action="acknowledge")
        if not a:
            raise HTTPException(status_code=404, detail="alert not found")
        return {"id": a.id, "status": a.status}


@app.post("/api/alerts/{alert_id}/resolve")
def api_alert_resolve(alert_id: str) -> dict:
    with session_scope() as session:
        a = transition_alert(session, alert_id, action="resolve")
        if not a:
            raise HTTPException(status_code=404, detail="alert not found")
        return {"id": a.id, "status": a.status}


@app.post("/api/alerts/{alert_id}/close")
def api_alert_close(alert_id: str) -> dict:
    with session_scope() as session:
        a = transition_alert(session, alert_id, action="close")
        if not a:
            raise HTTPException(status_code=404, detail="alert not found")
        return {"id": a.id, "status": a.status}


@app.post("/api/events/{event_id}/lock")
def api_event_lock(event_id: str) -> dict:
    with session_scope() as session:
        out = lock_event(session, event_id)
        if not out:
            raise HTTPException(status_code=404, detail="event not found")
        return out


@app.post("/api/events/merge")
def api_events_merge(
    keep_id: str = Query(..., description="Survivor event id"),
    merge_id: str = Query(..., description="Event to close and attach"),
) -> dict:
    with session_scope() as session:
        try:
            return merge_events(session, keep_id=keep_id, merge_id=merge_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e


@app.get("/api/system/status")
def api_system_status() -> dict:
    with session_scope() as session:
        return system_status_payload(session)


class ArticleTraceRequest(BaseModel):
    article_ids: list[str] = Field(default_factory=list)
    limit: int = Field(default=30, ge=1, le=50)


@app.post("/api/articles/trace")
def api_articles_trace(body: ArticleTraceRequest) -> dict:
    """Return traceable article metadata + V1.0 China stance & stance_evidence for given article_ids."""
    ids = [str(x).strip() for x in body.article_ids if str(x).strip()][: body.limit]
    if not ids:
        return {"articles": []}
    with session_scope() as session:
        articles = list(session.scalars(select(Article).where(Article.id.in_(ids))).all())
        sources = {s.id: s for s in session.scalars(select(Source)).all()}
        analyses = _latest_analyses(session, [a.id for a in articles])
        rows = []
        for a in articles:
            src = sources.get(a.source_id)
            ana = analyses.get(a.id)
            structured = (ana.structured_result if ana else None) or {}
            schema_ver = ana.schema_version if ana else None
            stance = extract_v1_china_stance(structured, schema_version=schema_ver)
            ev = extract_v1_stance_evidence(structured, schema_version=schema_ver)
            cs = structured.get("china_stance") if isinstance(structured.get("china_stance"), dict) else {}
            conf = cs.get("stance_confidence") if schema_ver == "article_analysis_v1.0" else None
            rows.append(
                {
                    "article_id": a.id,
                    "published_at": a.published_at.isoformat() if a.published_at else None,
                    "source_country": src.country_id if src else None,
                    "source_id": a.source_id,
                    "source_name": src.name if src else a.source_id,
                    "title": a.title,
                    "url": a.url,
                    "stance_label": stance,
                    "stance_confidence": conf if isinstance(conf, (int, float)) else None,
                    "stance_evidence": ev,
                    "topics_v1": extract_v1_topics(structured, schema_version=schema_ver),
                }
            )
        rows.sort(key=lambda r: str(r.get("published_at") or ""), reverse=True)
        return {"articles": rows}

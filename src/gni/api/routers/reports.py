"""Reports endpoints: Daily/Weekly/Monthly, ReportPackageContract, Markdown, and ReportSnapshot list."""

from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy import desc, select

from gni.core.config import get_settings
from gni.core.contracts import ReportPackageContract
from gni.infrastructure.db import session_scope
from gni.infrastructure.models import Article, ReportSnapshot
from gni.metrics.definitions import CHINA_INCLUDE_LEVELS
from gni.reports.daily import SCHEMA_VERSION as DAILY_SCHEMA_VERSION
from gni.reports.daily import build_daily_report
from gni.reports.daily_package import (
    get_daily_report_snapshot,
    render_daily_brief_markdown,
    save_daily_report_snapshot,
)
from gni.reports.monthly import build_monthly_report
from gni.reports.weekly import build_weekly_report

router = APIRouter(tags=["reports"])


class ReportAnalyzeRequest(BaseModel):
    period: str | None = Field(default=None, description="YYYY-MM-DD (daily/weekly end) or YYYY-MM (monthly)")
    tasks: list[str] | None = Field(default=None, description="Optional subset of task_type names to run/retry")
    force: bool = Field(default=False, description="Bypass cache and regenerate targeted tasks")
    engine: str = Field(default="legacy", description="'legacy' (default 3-task) or 'v2' (unified 9-task assessment engine)")
    save_snapshot: bool = Field(default=False, description="Persist generated daily report into ReportSnapshot")


@router.get("/api/reports/list")
def api_reports_list(
    report_type: str | None = Query(None, description="Optional filter: daily|weekly|monthly"),
    limit: int = Query(30, ge=1, le=100),
) -> dict[str, Any]:
    with session_scope() as session:
        stmt = select(ReportSnapshot).order_by(desc(ReportSnapshot.period), desc(ReportSnapshot.created_at)).limit(limit)
        if report_type:
            stmt = stmt.where(ReportSnapshot.report_type == report_type.strip().lower())
        rows = list(session.scalars(stmt).all())
        items = []
        for r in rows:
            p = r.payload if isinstance(r.payload, dict) else {}
            pkg = p.get("report_package") if isinstance(p.get("report_package"), dict) else {}
            items.append(
                {
                    "id": r.id,
                    "report_type": r.report_type,
                    "period": r.period,
                    "schema_version": r.schema_version,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "report_id": pkg.get("report_id") or f"{r.report_type}:{r.period}",
                    "generation_status": pkg.get("generation_status"),
                    "validation_status": pkg.get("validation_status"),
                    "article_count": p.get("article_count"),
                }
            )
        return {"reports": items, "total": len(items)}


@router.get("/api/reports/daily")
def api_daily_report(
    response: Response,
    date: str | None = Query(None, description="YYYY-MM-DD in Asia/Shanghai"),
    polish: bool = Query(False, description="LLM narrative polish only"),
    from_snapshot: bool = Query(False, description="Prefer persisted ReportSnapshot if available"),
) -> dict[str, Any]:
    try:
        with session_scope() as session:
            if from_snapshot and date:
                snap = get_daily_report_snapshot(session, date)
                if snap is not None:
                    response.headers["X-GNI-Report-Schema"] = str(snap.get("schema_version") or DAILY_SCHEMA_VERSION)
                    response.headers["X-GNI-Report-Source"] = "snapshot"
                    return snap
            payload = build_daily_report(session, day=date, polish=polish)
        response.headers["X-GNI-Report-Schema"] = str(payload.get("schema_version") or DAILY_SCHEMA_VERSION)
        response.headers["X-GNI-Report-Source"] = "live"
        return payload
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/api/reports/daily/package")
def api_daily_report_package(
    date: str | None = Query(None, description="YYYY-MM-DD in Asia/Shanghai"),
    format: str = Query("json", description="'json' or 'markdown'"),
    from_snapshot: bool = Query(False, description="Prefer persisted ReportSnapshot if available"),
) -> Any:
    try:
        with session_scope() as session:
            payload = None
            if from_snapshot and date:
                payload = get_daily_report_snapshot(session, date)
            if payload is None:
                payload = build_daily_report(session, day=date, analyze=False)
            pkg = payload.get("report_package") or {}
            if format.strip().lower() == "markdown":
                md = render_daily_brief_markdown(ReportPackageContract.model_validate(pkg))
                return PlainTextResponse(md, media_type="text/markdown; charset=utf-8")
            return {
                "report_package": pkg,
                "period": payload.get("period"),
                "schema_version": payload.get("schema_version"),
            }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/api/reports/weekly")
def api_weekly_report(
    end: str | None = Query(None, description="Week end YYYY-MM-DD (report TZ)"),
) -> dict[str, Any]:
    try:
        with session_scope() as session:
            return build_weekly_report(session, end_day=end)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/api/reports/calendar")
def api_reports_calendar(
    month: str | None = Query(None, description="YYYY-MM in report timezone (default current month)"),
) -> dict[str, Any]:
    """Return daily news totals and China-relevant article counts for every day in a month."""
    try:
        tz = ZoneInfo(get_settings().report_timezone or "Asia/Shanghai")
    except Exception:  # noqa: BLE001
        tz = ZoneInfo("Asia/Shanghai")
    if month:
        try:
            y, m = (int(x) for x in month.strip().split("-")[:2])
            if not (1 <= m <= 12):
                raise ValueError("month out of range")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"invalid month: {month}") from e
    else:
        today = datetime.now(tz).date()
        y, m = today.year, today.month

    last_day = monthrange(y, m)[1]
    start_local = datetime(y, m, 1, tzinfo=tz)
    end_local = datetime(y, m, last_day, tzinfo=tz) + timedelta(days=1)
    start_utc = start_local.astimezone(timezone.utc)
    end_utc = end_local.astimezone(timezone.utc)

    totals: dict[str, int] = defaultdict(int)
    chinas: dict[str, int] = defaultdict(int)
    with session_scope() as session:
        rows = session.execute(
            select(Article.published_at, Article.china_relevance_level).where(
                Article.exclude_from_metrics.is_(False),
                Article.published_at.is_not(None),
                Article.published_at >= start_utc,
                Article.published_at < end_utc,
            )
        ).all()
        for pub, rel in rows:
            if pub is None:
                continue
            dt = pub if pub.tzinfo is not None else pub.replace(tzinfo=timezone.utc)
            day_str = dt.astimezone(tz).date().isoformat()
            totals[day_str] += 1
            if rel in CHINA_INCLUDE_LEVELS:
                chinas[day_str] += 1

    days = []
    for d in range(1, last_day + 1):
        ds = date(y, m, d).isoformat()
        days.append(
            {
                "date": ds,
                "total_articles": totals.get(ds, 0),
                "china_articles": chinas.get(ds, 0),
            }
        )
    return {
        "month": f"{y:04d}-{m:02d}",
        "timezone": str(tz),
        "days": days,
    }


@router.get("/api/reports/monthly")
def api_monthly_report(
    month: str | None = Query(None, description="YYYY-MM"),
    end: str | None = Query(None, description="Optional trailing 30-day end date YYYY-MM-DD (report TZ)"),
) -> dict[str, Any]:
    try:
        with session_scope() as session:
            return build_monthly_report(session, month=month, end_day=end)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/api/reports/{report_type}/analyze")
def api_analyze_report(report_type: str, body: ReportAnalyzeRequest) -> dict[str, Any]:
    """Explicitly trigger (or retry failed tasks for) the LLM Intelligence Narrative / Assessment Layer."""
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
            p = (body.period or "").strip()
            use_end_day = p if len(p) == 10 else None
            use_month = None if use_end_day else (p or None)
            return build_monthly_report(
                session,
                month=use_month,
                end_day=use_end_day,
                analyze=True,
                analyze_tasks=body.tasks,
                force_analyze=body.force,
            )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

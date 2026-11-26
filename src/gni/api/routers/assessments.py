"""Unified Assessment Engine API endpoints (Phase 5 -> Phase 7)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from gni.api.routers.common import load_cached_assessments
from gni.infrastructure.db import session_scope
from gni.reports.daily import build_daily_report
from gni.reports.narrative.assessment import (
    get_assessment_task_spec,
    list_assessment_tasks,
    run_assessment_task,
)

router = APIRouter(tags=["assessments"])


class AssessmentRunRequest(BaseModel):
    period: str | None = Field(default=None, description="YYYY-MM-DD (daily)")
    force: bool = Field(default=False, description="Bypass ReportNarrativeTask cache")


@router.get("/api/assessments")
def api_list_assessments(
    report_type: str = Query("daily"),
    period: str | None = Query(None, description="Optional YYYY-MM-DD period"),
) -> dict[str, Any]:
    with session_scope() as session:
        cached = load_cached_assessments(session, report_type=report_type, period=period)
        catalog = list_assessment_tasks()
        items = []
        for spec in catalog:
            tt = spec.task_type
            res = cached.get(tt)
            items.append(
                {
                    "task_type": tt,
                    "title_zh": spec.title_zh,
                    "prompt_version": spec.prompt_version,
                    "status": res.get("status") if res else "not_run",
                    "result": res,
                }
            )
        return {
            "report_type": report_type,
            "period": period,
            "tasks": items,
            "completed_count": sum(1 for i in items if i["status"] == "completed"),
            "total_tasks": len(items),
        }


@router.get("/api/assessments/{task_type}")
def api_get_assessment(
    task_type: str,
    report_type: str = Query("daily"),
    period: str | None = Query(None),
) -> dict[str, Any]:
    try:
        spec = get_assessment_task_spec(task_type)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=f"unknown assessment task_type: {task_type}") from e
    with session_scope() as session:
        cached = load_cached_assessments(session, report_type=report_type, period=period)
        res = cached.get(spec.task_type)
        return {
            "task_type": spec.task_type,
            "title_zh": spec.title_zh,
            "prompt_version": spec.prompt_version,
            "status": res.get("status") if res else "not_run",
            "result": res,
        }


@router.post("/api/assessments/{task_type}/run")
def api_run_assessment(task_type: str, body: AssessmentRunRequest) -> dict[str, Any]:
    try:
        spec = get_assessment_task_spec(task_type)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=f"unknown assessment task_type: {task_type}") from e
    try:
        with session_scope() as session:
            daily = build_daily_report(session, day=body.period, analyze=False)
            result = run_assessment_task(
                session,
                task_type=spec.task_type,
                report_type="daily",
                report_payload=daily,
                force=body.force,
            )
            return {
                "task_type": spec.task_type,
                "period": daily.get("period"),
                "status": result.status,
                "result": result.model_dump(mode="json"),
            }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

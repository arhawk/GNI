"""Alerts, Search, Trends, and System Status endpoints (preserved backward-compatibly)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from gni.alerts.service import build_alerts_payload, run_alert_engine, transition_alert
from gni.api.routers.common import parse_iso
from gni.dashboard.data import MAX_WINDOW_DAYS
from gni.dashboard.pages_api import system_status_payload, trends_payload
from gni.infrastructure.db import session_scope
from gni.search.service import search_all

router = APIRouter(tags=["alerts-system"])


@router.get("/api/search")
def api_search(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(20, ge=1, le=40),
) -> dict[str, Any]:
    with session_scope() as session:
        return search_all(session, q, limit=limit)


@router.get("/api/trends")
def api_trends(
    days: int = Query(30, ge=1, le=MAX_WINDOW_DAYS),
    country: str | None = Query(None, description="Optional country id"),
) -> dict[str, Any]:
    with session_scope() as session:
        return trends_payload(session, days=days, country_id=country.upper() if country else None)


@router.get("/api/alerts")
def api_alerts(
    window_start: str | None = Query(None),
    window_end: str | None = Query(None),
    run: bool = Query(False, description="Run rule engine before read"),
) -> dict[str, Any]:
    with session_scope() as session:
        return build_alerts_payload(
            session,
            window_start=parse_iso(window_start),
            window_end=parse_iso(window_end),
            run_engine=run,
        )


@router.post("/api/alerts/run")
def api_alerts_run() -> dict[str, Any]:
    with session_scope() as session:
        return run_alert_engine(session)


@router.post("/api/alerts/{alert_id}/acknowledge")
def api_alert_ack(alert_id: str) -> dict[str, Any]:
    with session_scope() as session:
        a = transition_alert(session, alert_id, action="acknowledge")
        if not a:
            raise HTTPException(status_code=404, detail="alert not found")
        return {"id": a.id, "status": a.status}


@router.post("/api/alerts/{alert_id}/resolve")
def api_alert_resolve(alert_id: str) -> dict[str, Any]:
    with session_scope() as session:
        a = transition_alert(session, alert_id, action="resolve")
        if not a:
            raise HTTPException(status_code=404, detail="alert not found")
        return {"id": a.id, "status": a.status}


@router.post("/api/alerts/{alert_id}/close")
def api_alert_close(alert_id: str) -> dict[str, Any]:
    with session_scope() as session:
        a = transition_alert(session, alert_id, action="close")
        if not a:
            raise HTTPException(status_code=404, detail="alert not found")
        return {"id": a.id, "status": a.status}


@router.get("/api/system/status")
def api_system_status() -> dict[str, Any]:
    with session_scope() as session:
        return system_status_payload(session)

"""Persist and serve A/B alert center (upsert by deduplication_key)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from gni.alerts.rules import generate_intelligence_alerts, generate_system_alerts
from gni.infrastructure.models import Alert, AlertEvent, AlertEvidence


def _aware(t: datetime | None) -> datetime | None:
    if t is None:
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _alert_to_dict(a: Alert) -> dict[str, Any]:
    return {
        "id": a.id,
        "category": a.category,
        "subcategory": a.subcategory,
        "severity": a.severity,
        "status": a.status,
        "title": a.title,
        "summary": a.summary,
        "detected_at": a.last_triggered_at.isoformat() if a.last_triggered_at else None,
        "first_triggered_at": a.first_triggered_at.isoformat() if a.first_triggered_at else None,
        "last_triggered_at": a.last_triggered_at.isoformat() if a.last_triggered_at else None,
        "trigger_count": a.trigger_count,
        "deduplication_key": a.deduplication_key,
        "evidence": a.evidence_snapshot or {},
    }


def upsert_alerts_from_candidates(
    session: Session,
    candidates: list[dict[str, Any]],
    *,
    window_start: datetime | None = None,
    window_end: datetime | None = None,
) -> dict[str, int]:
    """Upsert rule candidates by deduplication_key. Returns created/updated counts."""
    created = updated = 0
    now = _now()
    for cand in candidates:
        key = cand.get("deduplication_key") or f"{cand.get('category')}:{cand.get('subcategory')}:global"
        existing = session.scalar(select(Alert).where(Alert.deduplication_key == key).limit(1))
        evidence = cand.get("evidence") or {}
        if existing:
            existing.title = cand.get("title") or existing.title
            existing.summary = cand.get("summary")
            existing.severity = cand.get("severity") or existing.severity
            existing.last_triggered_at = now
            existing.trigger_count = int(existing.trigger_count or 0) + 1
            existing.evidence_snapshot = evidence
            existing.window_start = window_start or existing.window_start
            existing.window_end = window_end or existing.window_end
            if existing.status == "CLOSED":
                existing.status = "OPEN"
            session.add(
                AlertEvent(
                    id=str(uuid4()),
                    alert_id=existing.id,
                    action="trigger",
                    actor="rules",
                    payload={"trigger_count": existing.trigger_count},
                )
            )
            updated += 1
        else:
            aid = str(uuid4())
            alert = Alert(
                id=aid,
                category=cand.get("category") or "intelligence",
                subcategory=cand.get("subcategory") or "unknown",
                severity=cand.get("severity") or "medium",
                status="OPEN",
                deduplication_key=key,
                title=cand.get("title") or key,
                summary=cand.get("summary"),
                first_triggered_at=now,
                last_triggered_at=now,
                trigger_count=1,
                window_start=window_start,
                window_end=window_end,
                evidence_snapshot=evidence,
            )
            session.add(alert)
            session.add(
                AlertEvent(
                    id=str(uuid4()),
                    alert_id=aid,
                    action="create",
                    actor="rules",
                    payload=None,
                )
            )
            ev_id = evidence.get("event_id")
            art_id = evidence.get("article_id")
            if ev_id or art_id or evidence:
                session.add(
                    AlertEvidence(
                        id=str(uuid4()),
                        alert_id=aid,
                        article_id=art_id if isinstance(art_id, str) else None,
                        event_id=ev_id if isinstance(ev_id, str) else None,
                        snapshot=evidence,
                    )
                )
            created += 1
    session.flush()
    return {"created": created, "updated": updated}


def run_alert_engine(
    session: Session,
    *,
    window_start: datetime | None = None,
    window_end: datetime | None = None,
) -> dict[str, Any]:
    intel = generate_intelligence_alerts(session)
    system = generate_system_alerts(session)
    stats = upsert_alerts_from_candidates(
        session, intel + system, window_start=window_start, window_end=window_end
    )
    return {"ok": True, **stats, "candidates": len(intel) + len(system)}


def transition_alert(
    session: Session,
    alert_id: str,
    *,
    action: str,
    actor: str = "ui",
) -> Alert | None:
    alert = session.get(Alert, alert_id)
    if not alert:
        return None
    action = action.lower()
    status_map = {
        "acknowledge": "ACKNOWLEDGED",
        "ack": "ACKNOWLEDGED",
        "resolve": "RESOLVED",
        "close": "CLOSED",
        "reopen": "OPEN",
    }
    if action not in status_map:
        raise ValueError(f"unsupported action: {action}")
    alert.status = status_map[action]
    session.add(
        AlertEvent(
            id=str(uuid4()),
            alert_id=alert.id,
            action=action,
            actor=actor,
            payload={"status": alert.status},
        )
    )
    session.flush()
    return alert


def build_alerts_payload(
    session: Session,
    *,
    window_start: datetime | str | None = None,
    window_end: datetime | str | None = None,
    run_engine: bool = False,
) -> dict[str, Any]:
    """Read persisted alerts; optionally run engine first. Filter by last_triggered window."""
    ws = _parse_dt(window_start)
    we = _parse_dt(window_end)
    if run_engine or session.scalar(select(Alert.id).limit(1)) is None:
        run_alert_engine(session, window_start=ws, window_end=we)

    q = select(Alert).where(Alert.status != "CLOSED")
    if ws is not None:
        q = q.where(Alert.last_triggered_at >= ws)
    if we is not None:
        q = q.where(Alert.last_triggered_at < we)
    rows = list(session.scalars(q.order_by(Alert.last_triggered_at.desc()).limit(200)).all())

    intelligence = [_alert_to_dict(a) for a in rows if a.category == "intelligence"]
    system = [_alert_to_dict(a) for a in rows if a.category == "system"]

    def sev_rank(a: dict[str, Any]) -> int:
        return {"high": 0, "medium": 1, "low": 2}.get(a.get("severity") or "low", 3)

    intelligence.sort(key=sev_rank)
    system.sort(key=sev_rank)
    return {
        "disclaimer": (
            "预警为规则监测信号，分「舆情情报」与「系统运行」两类；"
            "情报预警基于被监测官媒样本，不等于国家立场或民意。"
            "列表来自持久化 Alerts（同 dedupe_key 稳定 ID）。"
        ),
        "intelligence": intelligence,
        "system": system,
        "counts": {
            "intelligence": len(intelligence),
            "system": len(system),
            "high": sum(1 for a in intelligence + system if a.get("severity") == "high"),
        },
    }


def _parse_dt(value: datetime | str | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return _aware(value)
    try:
        return _aware(datetime.fromisoformat(str(value).replace("Z", "+00:00")))
    except ValueError:
        return None

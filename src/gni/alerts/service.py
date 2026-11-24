"""Assemble A/B alert center payload."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from gni.alerts.rules import generate_intelligence_alerts, generate_system_alerts


def build_alerts_payload(session: Session) -> dict[str, Any]:
    intelligence = generate_intelligence_alerts(session)
    system = generate_system_alerts(session)

    def sev_rank(a: dict[str, Any]) -> int:
        return {"high": 0, "medium": 1, "low": 2}.get(a.get("severity") or "low", 3)

    intelligence.sort(key=sev_rank)
    system.sort(key=sev_rank)
    return {
        "disclaimer": (
            "预警为规则监测信号，分「舆情情报」与「系统运行」两类；"
            "情报预警基于被监测官媒样本，不等于国家立场或民意。"
        ),
        "intelligence": intelligence,
        "system": system,
        "counts": {
            "intelligence": len(intelligence),
            "system": len(system),
            "high": sum(
                1
                for a in intelligence + system
                if a.get("severity") == "high"
            ),
        },
    }

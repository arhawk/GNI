"""Rule MVP: sector + risk_level tagging from configs/risk_sectors.yaml."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

CONFIG_PATH = Path(__file__).resolve().parents[3] / "configs" / "risk_sectors.yaml"


@lru_cache(maxsize=1)
def _cfg() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}


def media_type_bucket(src: Any | None) -> str:
    """government_agency | state_media | public_broadcaster | private_mainstream | other."""
    if src is None:
        return "other"
    scope = (getattr(src, "feed_scope", None) or "").upper()
    st = (getattr(src, "source_type", None) or "").lower()
    ownership = (getattr(src, "ownership_type", None) or "").lower()
    ctrl = (getattr(src, "government_control_level", None) or "").lower()
    if scope == "GOVERNMENT_RELEASES" or st in {"gov_comms", "government", "government_release"}:
        return "government_agency"
    if ownership in {"public", "public_law"}:
        return "public_broadcaster"
    if ownership in {"private", "commercial"} or st in {"private", "commercial"}:
        return "private_mainstream"
    if ownership in {"state", "government"} or ctrl in {"high", "medium"} or "state" in st:
        return "state_media"
    return "other"


MEDIA_TYPE_ZH = {
    "government_agency": "政府机构",
    "state_media": "国有官媒",
    "public_broadcaster": "公共广播",
    "private_mainstream": "私营主流",
    "other": "其他",
}


def tag_text(*parts: str | None) -> dict[str, Any]:
    """Return sectors[], risk_level, matched_triggers from free text."""
    cfg = _cfg()
    hay = " ".join(p for p in parts if p).lower()
    sectors: list[dict[str, str]] = []
    for sid, meta in (cfg.get("sectors") or {}).items():
        kws = [str(k).lower() for k in (meta.get("keywords") or [])]
        if any(k in hay for k in kws):
            sectors.append({"id": sid, "label": str(meta.get("label") or sid)})

    risk_level = "unmapped"
    matched: list[str] = []
    triggers = cfg.get("risk_triggers") or {}
    for level in ("high", "medium", "watch"):
        for kw in triggers.get(level) or []:
            if str(kw).lower() in hay:
                matched.append(str(kw))
                if risk_level == "unmapped":
                    risk_level = level
                elif _rank(level) < _rank(risk_level):
                    risk_level = level

    return {
        "sectors": sectors or [{"id": "unmapped", "label": "未映射"}],
        "sector_ids": [s["id"] for s in sectors] if sectors else ["unmapped"],
        "risk_level": risk_level,
        "matched_triggers": matched[:8],
    }


def elevate_risk(current: str, candidate: str) -> str:
    if _rank(candidate) < _rank(current):
        return candidate
    return current


def risk_from_alert_severity(severity: str | None) -> str:
    m = (_cfg().get("alert_severity_to_risk") or {})
    if not severity:
        return "unmapped"
    return str(m.get(severity) or severity)


def _rank(level: str) -> int:
    order = {"high": 0, "medium": 1, "watch": 2, "unmapped": 3}
    return order.get(level, 9)

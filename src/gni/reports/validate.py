"""Deterministic daily-report validator (MVP)."""

from __future__ import annotations

from typing import Any

# Affirmative misuse only — disclaimer may contain negated forms of similar words.
FORBIDDEN_PHRASES = (
    "对华总分",
    "综合舆情指数",
    "代表民意",
    "全民舆论",
)


def validate_daily_report(payload: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    errors: list[str] = []

    def ok(name: str, passed: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": passed, "detail": detail})
        if not passed:
            errors.append(f"{name}: {detail or 'failed'}")

    ok("schema_version", payload.get("schema_version") == "daily_report_schema_v2")
    ok("report_type", payload.get("report_type") == "daily")
    ok("has_disclaimer", bool(payload.get("disclaimer")))
    ok("has_period", bool(payload.get("period")))

    sections = payload.get("sections") or {}
    for key in ("summary", "major_events", "coverage", "tone", "signals", "quality"):
        present = key in sections
        ok(f"section_{key}", present, "" if present else "missing section")

    summary = sections.get("summary") or {}
    kpis = summary.get("kpis") or {}
    ok("kpi_china_articles", isinstance(kpis.get("china_articles"), int))

    events = sections.get("major_events") or []
    ids = [e.get("event_id") for e in events if e.get("event_id")]
    ok("events_unique", len(ids) == len(set(ids)), f"dupes={len(ids) - len(set(ids))}")

    fact_ok = True
    for e in events:
        if not e.get("event_id"):
            fact_ok = False
            break
        for ev in e.get("evidence") or []:
            if not ev.get("article_id"):
                fact_ok = False
                break
    ok("event_facts_bound", fact_ok, "event or evidence missing id")

    # No composite score field
    blob = str(payload)
    ok("no_composite_score_field", "china_sentiment_score" not in blob and "composite_score" not in blob)

    narr = payload.get("narratives") or {}
    text_join = " ".join(str(v) for v in narr.values() if isinstance(v, str))
    overview = (summary.get("overview_text") or "") + " " + text_join
    for e in events:
        overview += " " + str(e.get("overview_text") or "")
    # disclaimer may mention 官方立场 negatively — only flag affirmative misuse outside it
    body_wo_disclaimer = overview.replace(str(payload.get("disclaimer") or ""), "")
    banned_hit = next((p for p in FORBIDDEN_PHRASES if p in body_wo_disclaimer), None)
    ok("no_forbidden_claims", banned_hit is None, banned_hit or "")

    return {"ok": len(errors) == 0, "checks": checks, "errors": errors}

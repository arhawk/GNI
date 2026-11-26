"""Deterministic report validators for Daily, Weekly, and Monthly GNI reports."""

from __future__ import annotations

from typing import Any

# Affirmative misuse only — disclaimer may contain negated forms of similar words.
FORBIDDEN_PHRASES = (
    "对华总分",
    "综合舆情指数",
    "代表民意",
    "全民舆论",
)


def _check_intelligence_block(
    payload: dict[str, Any],
    ok_fn: Any,
) -> None:
    intel = payload.get("intelligence")
    if not isinstance(intel, dict):
        return
    status = intel.get("status")
    ok_fn(
        "intelligence_status",
        status in {"rule_only", "completed", "partial", "needs_review", "failed"},
        str(status),
    )
    tasks = intel.get("tasks") or {}
    if not isinstance(tasks, dict):
        ok_fn("intelligence_tasks_dict", False, "tasks must be dict")
        return

    # Verify every Fact finding inside intelligence tasks still carries >= 1 evidence_ref
    fact_bound = True
    for tname, tout in tasks.items():
        if not isinstance(tout, dict):
            continue
        for f in tout.get("findings") or []:
            if isinstance(f, dict) and f.get("classification") == "Fact":
                if not (f.get("evidence_refs") or []):
                    fact_bound = False
                    break
        if not fact_bound:
            break
    ok_fn("intelligence_facts_evidenced", fact_bound, "Fact finding missing evidence_refs")


def validate_daily_report(payload: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    errors: list[str] = []

    def ok(name: str, passed: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": passed, "detail": detail})
        if not passed:
            errors.append(f"{name}: {detail or 'failed'}")

    schema = payload.get("schema_version")
    ok(
        "schema_version",
        schema in {"daily_report_schema_v2", "daily_report_schema_v4"},
        str(schema),
    )
    ok("report_type", payload.get("report_type") == "daily")
    ok("has_disclaimer", bool(payload.get("disclaimer")))
    ok("has_period", bool(payload.get("period")))

    sections = payload.get("sections") or {}
    required = ["summary", "major_events", "coverage", "tone", "signals", "quality"]
    if schema == "daily_report_schema_v4":
        required.extend(["overview_stats", "anomalies", "ops"])
    for key in required:
        present = key in sections
        ok(f"section_{key}", present, "" if present else "missing section")

    if payload.get("methodology_version") == "methodology_v1.0":
        v1 = sections.get("v1_stats")
        ok(
            "v1_stats_structure",
            isinstance(v1, dict)
            and all(k in v1 for k in ("global", "countries", "boards", "topics")),
            "missing v1_stats scope keys",
        )

    summary = sections.get("summary") or {}
    kpis = summary.get("kpis") or {}
    ok("kpi_china_articles", isinstance(kpis.get("china_articles"), int))
    if schema == "daily_report_schema_v4":
        ok(
            "judgment_text",
            isinstance(summary.get("judgment_text"), str) and bool(summary.get("judgment_text")),
            "missing judgment_text",
        )
        ok(
            "confidence",
            summary.get("confidence") in {"high", "medium", "low", "unavailable"},
            str(summary.get("confidence")),
        )
        ok("risk_banner", isinstance(summary.get("risk_banner"), dict))

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

    # No composite score field (exclude self-referential validation block for idempotency)
    blob = str({k: v for k, v in payload.items() if k != "validation"})
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

    _check_intelligence_block(payload, ok)

    return {"ok": len(errors) == 0, "checks": checks, "errors": errors}


def validate_weekly_report(payload: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    errors: list[str] = []

    def ok(name: str, passed: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": passed, "detail": detail})
        if not passed:
            errors.append(f"{name}: {detail or 'failed'}")

    ok("report_type", payload.get("report_type") == "weekly")
    ok("has_disclaimer", bool(payload.get("disclaimer")))
    ok("has_period", bool(payload.get("period")))

    sections = payload.get("sections") or {}
    for key in (
        "summary",
        "major_events",
        "event_evolution",
        "cross_country_narrative",
        "topic_trends",
        "sentiment_stance",
        "signals",
        "quality",
    ):
        ok(f"section_{key}", key in sections, "" if key in sections else "missing section")

    if payload.get("methodology_version") == "methodology_v1.0":
        v1 = sections.get("v1_stats")
        v1_prev = sections.get("v1_stats_prev")
        ok(
            "v1_stats_structure",
            isinstance(v1, dict)
            and all(k in v1 for k in ("global", "countries", "boards", "topics"))
            and isinstance(v1_prev, dict),
            "missing v1_stats or v1_stats_prev",
        )

    blob = str({k: v for k, v in payload.items() if k != "validation"})
    ok("no_composite_score_field", "china_sentiment_score" not in blob and "composite_score" not in blob)

    events = sections.get("major_events") or []
    ev_ids = [e.get("event_id") or e.get("id") for e in events if isinstance(e, dict) and (e.get("event_id") or e.get("id"))]
    ok("events_unique", len(ev_ids) == len(set(ev_ids)), f"dupes={len(ev_ids) - len(set(ev_ids))}")

    narr = payload.get("narratives") or {}
    text_join = " ".join(str(v) for v in narr.values() if isinstance(v, str))
    overview = str((sections.get("summary") or {}).get("overview_text") or "") + " " + text_join
    body_wo_disclaimer = overview.replace(str(payload.get("disclaimer") or ""), "")
    banned_hit = next((p for p in FORBIDDEN_PHRASES if p in body_wo_disclaimer), None)
    ok("no_forbidden_claims", banned_hit is None, banned_hit or "")

    _check_intelligence_block(payload, ok)
    return {"ok": len(errors) == 0, "checks": checks, "errors": errors}


def validate_monthly_report(payload: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    errors: list[str] = []

    def ok(name: str, passed: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": passed, "detail": detail})
        if not passed:
            errors.append(f"{name}: {detail or 'failed'}")

    ok("report_type", payload.get("report_type") == "monthly")
    ok("has_disclaimer", bool(payload.get("disclaimer")))
    ok("has_period", bool(payload.get("period")))

    sections = payload.get("sections") or {}
    for key in (
        "summary",
        "major_events",
        "topic_trends",
        "cross_country_narrative",
        "sentiment_stance",
        "signals",
        "quality",
    ):
        ok(f"section_{key}", key in sections, "" if key in sections else "missing section")

    if payload.get("methodology_version") == "methodology_v1.0":
        v1 = sections.get("v1_stats")
        v1_prev = sections.get("v1_stats_prev")
        ok(
            "v1_stats_structure",
            isinstance(v1, dict)
            and all(k in v1 for k in ("global", "countries", "boards", "topics"))
            and isinstance(v1_prev, dict),
            "missing v1_stats or v1_stats_prev",
        )

    blob = str({k: v for k, v in payload.items() if k != "validation"})
    ok("no_composite_score_field", "china_sentiment_score" not in blob and "composite_score" not in blob)

    events = sections.get("major_events") or []
    ev_ids = [e.get("event_id") or e.get("id") for e in events if isinstance(e, dict) and (e.get("event_id") or e.get("id"))]
    ok("events_unique", len(ev_ids) == len(set(ev_ids)), f"dupes={len(ev_ids) - len(set(ev_ids))}")

    narr = payload.get("narratives") or {}
    text_join = " ".join(str(v) for v in narr.values() if isinstance(v, str))
    overview = str((sections.get("summary") or {}).get("overview_text") or "") + " " + text_join
    body_wo_disclaimer = overview.replace(str(payload.get("disclaimer") or ""), "")
    banned_hit = next((p for p in FORBIDDEN_PHRASES if p in body_wo_disclaimer), None)
    ok("no_forbidden_claims", banned_hit is None, banned_hit or "")

    _check_intelligence_block(payload, ok)
    return {"ok": len(errors) == 0, "checks": checks, "errors": errors}

"""Three-State Report Quality Gate (Task 3C): passed | passed_with_warnings | blocked."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class QualityGateResult:
    status: str  # passed | passed_with_warnings | blocked
    blocking_issues: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)
    checks_run: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "blocking_issues": self.blocking_issues,
            "warnings": self.warnings,
            "checks_run": self.checks_run,
        }


def evaluate_report_quality_gate(payload: dict[str, Any]) -> dict[str, Any]:
    """Evaluate deterministic + LLM report payload against blocking and warning gates."""
    blocking: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    checks: list[str] = []

    # 1. Required top-level schema & period consistency
    checks.append("schema_and_period_consistency")
    for req in ("report_type", "period", "schema_version", "sections"):
        if not payload.get(req):
            blocking.append({"code": "missing_required_field", "field": req, "detail": f"Missing {req}"})

    p_start = payload.get("period_start")
    p_end = payload.get("period_end")
    if p_start and p_end and str(p_start) >= str(p_end):
        blocking.append(
            {
                "code": "invalid_period_bounds",
                "detail": f"period_start ({p_start}) must be strictly before period_end ({p_end})",
            }
        )

    sections = payload.get("sections") if isinstance(payload.get("sections"), dict) else {}

    # 2. V1.0 statistical denominator & Unclassified isolation check
    checks.append("v1_stance_denominator_and_coverage")
    v1 = sections.get("v1_stats") if isinstance(sections.get("v1_stats"), dict) else {}
    g = v1.get("global") if isinstance(v1.get("global"), dict) else None
    if g is not None:
        total = int(g.get("article_count") or 0)
        pos = int(g.get("positive_count") or 0)
        neu = int(g.get("neutral_count") or 0)
        neg = int(g.get("negative_count") or 0)
        unc = int(g.get("unclassified_count") or 0)
        classified = pos + neu + neg
        if classified + unc != total and total > 0:
            blocking.append(
                {
                    "code": "stance_count_mismatch",
                    "detail": f"pos({pos})+neu({neu})+neg({neg})+unc({unc}) != article_count({total})",
                }
            )
        if classified > 0:
            for rate_key, cnt in (("positive_rate", pos), ("neutral_rate", neu), ("negative_rate", neg)):
                r = g.get(rate_key)
                if isinstance(r, (int, float)):
                    expected = cnt / classified
                    if abs(float(r) - expected) > 0.02:
                        blocking.append(
                            {
                                "code": "unclassified_leaked_into_denominator",
                                "field": rate_key,
                                "detail": f"{rate_key}={r} does not match {cnt}/{classified}={expected:.4f}",
                            }
                        )
        if total > 0 and g.get("stance_coverage_rate") is None:
            blocking.append(
                {
                    "code": "missing_stance_coverage_rate",
                    "detail": "stance_coverage_rate must be present whenever article_count > 0",
                }
            )
        if total < 5:
            warnings.append(
                {
                    "code": "low_sample_size",
                    "detail": f"涉华有效文章样本偏少（{total} 篇），结论强度需保持谨慎。",
                }
            )

    # 3. Partial period disclosure check
    checks.append("partial_period_disclosure")
    win = payload.get("window_spec") if isinstance(payload.get("window_spec"), dict) else {}
    if win.get("is_partial_period"):
        warnings.append(
            {
                "code": "partial_period_provisional",
                "detail": str(win.get("comparison_note") or "当前周期尚未结束，属于暂定统计窗口。"),
            }
        )

    # 4. Event time integrity check (must not fabricate event_time from published_at)
    checks.append("event_time_integrity")
    for ev in sections.get("major_events") or []:
        if isinstance(ev, dict) and ev.get("event_time_fabricated"):
            blocking.append(
                {
                    "code": "fabricated_event_time",
                    "event_id": ev.get("event_id"),
                    "detail": "event_time must remain NULL when unknown rather than copying published_at",
                }
            )

    # 5. Intelligence / LLM task health check (non-blocking warnings for partial/needs_review)
    checks.append("intelligence_layer_status")
    intel = payload.get("intelligence") if isinstance(payload.get("intelligence"), dict) else {}
    ist = str(intel.get("status") or "")
    if ist in {"partial", "needs_review", "failed"}:
        warnings.append(
            {
                "code": f"intelligence_{ist}",
                "detail": f"智能研判层状态为 {ist}，部分任务需要复核或重试。",
            }
        )
    if intel.get("stale"):
        warnings.append(
            {
                "code": "stale_intelligence_cache",
                "detail": "缓存研判对应的证据指纹已变化，建议刷新研判。",
            }
        )

    if blocking:
        status = "blocked"
    elif warnings:
        status = "passed_with_warnings"
    else:
        status = "passed"
    return QualityGateResult(
        status=status,
        blocking_issues=blocking,
        warnings=warnings,
        checks_run=checks,
    ).to_dict()

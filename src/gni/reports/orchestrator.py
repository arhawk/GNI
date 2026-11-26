"""Unified Report Orchestrator (Task 2).

Single execution coordinator for Daily, Weekly, and Monthly intelligence reports:
- Explicit ReportTaskProfile registry (no ad-hoc if/else task scattering).
- Shares one deterministic EvidenceBundle per report run.
- Executes Canonical Assessment Engine tasks in dependency order (analysts -> synthesis).
- Supports cache lookup, force refresh, partial failed-task retry, and graceful degradation.
- Projects Canonical AssessmentResultContract outputs into backward-compatible legacy
  `payload["intelligence"]` shape so existing UI and consumers keep working seamlessly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from gni.core.config import Settings
from gni.core.contracts import AssessmentResultContract
from gni.infrastructure.models import ReportNarrativeTask
from gni.reports.narrative.assessment import (
    effective_prompt_version,
    get_assessment_task_spec,
    resolve_task_type,
    run_assessment_task,
)
from gni.reports.narrative.evidence import compute_payload_fingerprint, prepare_evidence_bundle
from gni.reports.narrative.runner import JsonLLMClient, load_cached_intelligence

ORCHESTRATOR_VERSION = "orchestrator_v1.0"


@dataclass(frozen=True)
class ReportTaskProfile:
    report_type: str
    profile_version: str
    core_tasks: tuple[str, ...]
    optional_tasks: tuple[str, ...]
    # Analyst tasks run first; synthesis tasks (overall, risk, outlook) run after.
    execution_order: tuple[str, ...]


REPORT_TASK_PROFILES: dict[str, ReportTaskProfile] = {
    "daily": ReportTaskProfile(
        report_type="daily",
        profile_version="daily_profile_v1.0",
        core_tasks=(
            "event_analysis",
            "change_detection_assessment",
            "overall_situation_assessment",
            "risk_signal_assessment",
            "outlook_assessment",
        ),
        optional_tasks=(
            "topic_analysis",
            "country_comparison",
            "narrative_analysis",
            "sentiment_stance_analysis",
        ),
        execution_order=(
            "event_analysis",
            "topic_analysis",
            "country_comparison",
            "narrative_analysis",
            "sentiment_stance_analysis",
            "change_detection_assessment",
            "overall_situation_assessment",
            "risk_signal_assessment",
            "outlook_assessment",
        ),
    ),
    "weekly": ReportTaskProfile(
        report_type="weekly",
        profile_version="weekly_profile_v1.0",
        core_tasks=(
            "event_analysis",
            "topic_analysis",
            "country_comparison",
            "sentiment_stance_analysis",
            "change_detection_assessment",
            "overall_situation_assessment",
            "risk_signal_assessment",
            "outlook_assessment",
        ),
        optional_tasks=("narrative_analysis",),
        execution_order=(
            "event_analysis",
            "topic_analysis",
            "country_comparison",
            "narrative_analysis",
            "sentiment_stance_analysis",
            "change_detection_assessment",
            "overall_situation_assessment",
            "risk_signal_assessment",
            "outlook_assessment",
        ),
    ),
    "monthly": ReportTaskProfile(
        report_type="monthly",
        profile_version="monthly_profile_v1.0",
        core_tasks=(
            "event_analysis",
            "topic_analysis",
            "country_comparison",
            "narrative_analysis",
            "sentiment_stance_analysis",
            "change_detection_assessment",
            "overall_situation_assessment",
            "risk_signal_assessment",
            "outlook_assessment",
        ),
        optional_tasks=(),
        execution_order=(
            "event_analysis",
            "topic_analysis",
            "country_comparison",
            "narrative_analysis",
            "sentiment_stance_analysis",
            "change_detection_assessment",
            "overall_situation_assessment",
            "risk_signal_assessment",
            "outlook_assessment",
        ),
    ),
}

# Mapping from canonical task types to legacy frontend/API intelligence.tasks keys
_CANONICAL_TO_LEGACY_KEY: dict[str, str] = {
    "overall_situation_assessment": "executive_analysis",
    "event_analysis": "event_analysis",
    "topic_analysis": "topic_trend_analysis",
    "country_comparison": "cross_country_analysis",
    "sentiment_stance_analysis": "stance_analysis",
    "outlook_assessment": "emerging_signals",
}

_LEGACY_TO_CANONICAL_KEY: dict[str, str] = {
    "executive_analysis": "overall_situation_assessment",
    "event_analysis": "event_analysis",
    "topic_trend_analysis": "topic_analysis",
    "cross_country_analysis": "country_comparison",
    "stance_analysis": "sentiment_stance_analysis",
    "emerging_signals": "outlook_assessment",
}


def get_report_task_profile(report_type: str) -> ReportTaskProfile:
    rt = (report_type or "").strip().lower()
    if rt not in REPORT_TASK_PROFILES:
        raise ValueError(f"Unsupported report_type for orchestrator: {report_type}")
    return REPORT_TASK_PROFILES[rt]


def resolve_profile_tasks(
    report_type: str,
    *,
    profile: str = "core",
    requested_tasks: list[str] | tuple[str, ...] | None = None,
) -> list[str]:
    """Resolve ordered list of canonical task types for a report run."""
    prof = get_report_task_profile(report_type)
    if requested_tasks is not None:
        wanted = {resolve_task_type(_LEGACY_TO_CANONICAL_KEY.get(t, t)) for t in requested_tasks}
        return [t for t in prof.execution_order if t in wanted] + [
            t for t in wanted if t not in prof.execution_order
        ]
    if profile == "full":
        return list(prof.execution_order)
    allowed = set(prof.core_tasks)
    return [t for t in prof.execution_order if t in allowed]


def _canonical_to_legacy_task_payload(res: AssessmentResultContract) -> dict[str, Any]:
    """Project an AssessmentResultContract into the legacy NarrativeTaskOutput dict shape."""
    details = res.details or {}
    out: dict[str, Any] = {
        "task_type": _CANONICAL_TO_LEGACY_KEY.get(res.task_type, res.task_type),
        "summary": res.executive_summary,
        "findings": list(res.key_findings or []),
        "uncertainties": list(res.limitations or []),
        "follow_up_questions": [
            str(w.get("signal") or "")
            for w in (res.watch_items or [])
            if isinstance(w, dict) and w.get("kind") == "follow_up_question"
        ],
    }
    if details.get("important_changes"):
        out["important_changes"] = list(details["important_changes"])
    if details.get("main_drivers"):
        out["main_drivers"] = list(details["main_drivers"])
    if details.get("event_interpretations"):
        out["event_interpretations"] = list(details["event_interpretations"])
    if details.get("topic_deep_dives"):
        out["topic_trends"] = list(details["topic_deep_dives"])
    if details.get("cross_country_comparisons"):
        out["cross_country"] = list(details["cross_country_comparisons"])
    if details.get("outlook_signals"):
        out["outlook_signals"] = list(details["outlook_signals"])
    elif res.watch_items:
        sigs = [w for w in res.watch_items if isinstance(w, dict) and w.get("kind") != "follow_up_question"]
        if sigs:
            out["outlook_signals"] = sigs
    return out


def project_canonical_to_legacy_intelligence(
    *,
    report_type: str,
    period: str,
    evidence_hash: str,
    assessments: dict[str, AssessmentResultContract],
    profile_version: str,
) -> dict[str, Any]:
    """Build backward-compatible `payload['intelligence']` block from canonical assessments."""
    tasks_payload: dict[str, Any] = {}
    task_statuses: dict[str, dict[str, Any]] = {}
    completed = 0
    needs_review = 0
    failed = 0
    models: set[str] = set()
    prompt_versions: dict[str, str] = {}

    for tt, res in assessments.items():
        spec = get_assessment_task_spec(tt)
        pv = res.prompt_version or effective_prompt_version(spec, report_type)
        prompt_versions[tt] = pv
        if res.model_version:
            models.add(res.model_version)
        task_statuses[tt] = {
            "title_zh": spec.title_zh,
            "prompt_version": pv,
            "model_version": res.model_version,
            "status": res.status,
            "stale": bool(evidence_hash and res.evidence_hash and res.evidence_hash != evidence_hash),
            "validation": res.validation_result,
            "updated_at": res.generated_at,
        }
        if res.status == "failed":
            failed += 1
            continue
        if res.status in {"completed", "needs_review", "degraded", "insufficient_data"}:
            completed += 1
            if res.status == "needs_review":
                needs_review += 1
            legacy_key = _CANONICAL_TO_LEGACY_KEY.get(tt)
            if legacy_key:
                tasks_payload[legacy_key] = _canonical_to_legacy_task_payload(res)

    total_expected = len(assessments)
    if completed == 0 and failed == 0:
        overall_status = "rule_only"
    elif completed == 0 and failed > 0:
        overall_status = "failed"
    elif completed < total_expected or failed > 0:
        overall_status = "partial"
    elif needs_review > 0:
        overall_status = "needs_review"
    else:
        overall_status = "completed"

    return {
        "status": overall_status,
        "engine": "canonical_orchestrator",
        "orchestrator_version": ORCHESTRATOR_VERSION,
        "profile_version": profile_version,
        "report_type": report_type,
        "period": period,
        "evidence_hash": evidence_hash,
        "stale": False,
        "tasks": tasks_payload,
        "canonical_tasks": {k: v.model_dump() for k, v in assessments.items()},
        "task_statuses": task_statuses,
        "meta": {
            "completed_tasks": completed,
            "failed_tasks": failed,
            "needs_review_tasks": needs_review,
            "total_tasks": total_expected,
            "model_versions": sorted(models),
            "prompt_versions": prompt_versions,
        },
    }


@dataclass
class OrchestratorRunResult:
    report_type: str
    period: str
    profile_version: str
    evidence_hash: str
    assessments: dict[str, AssessmentResultContract] = field(default_factory=dict)
    intelligence: dict[str, Any] = field(default_factory=dict)
    executed_tasks: list[str] = field(default_factory=list)


class ReportOrchestrator:
    """Unified orchestrator scheduling Canonical Assessment tasks across Daily/Weekly/Monthly."""

    def run(
        self,
        session: Session,
        *,
        report_type: str,
        payload: dict[str, Any],
        profile: str = "core",
        tasks: list[str] | tuple[str, ...] | None = None,
        force: bool = False,
        llm_client: JsonLLMClient | None = None,
        settings: Settings | None = None,
        allow_fallback: bool = True,
    ) -> OrchestratorRunResult:
        prof = get_report_task_profile(report_type)
        period = str(payload.get("period") or "")
        ordered_tasks = resolve_profile_tasks(
            report_type,
            profile=profile,
            requested_tasks=tasks,
        )
        shared_bundle = prepare_evidence_bundle(session, report_type=report_type, payload=payload)

        # Load already-cached tasks first so partial retries preserve unaffected completed tasks
        assessments: dict[str, AssessmentResultContract] = self.load_cached_assessments(
            session,
            report_type=report_type,
            period=period,
        )

        for tt in ordered_tasks:
            assessments[tt] = run_assessment_task(
                session,
                task_type=tt,
                report_type=report_type,
                payload=payload,
                bundle=shared_bundle,
                client=llm_client,
                settings=settings,
                force=force,
                allow_fallback=allow_fallback,
            )

        intelligence = project_canonical_to_legacy_intelligence(
            report_type=report_type,
            period=period,
            evidence_hash=shared_bundle.evidence_hash,
            assessments=assessments,
            profile_version=prof.profile_version,
        )
        return OrchestratorRunResult(
            report_type=report_type,
            period=period,
            profile_version=prof.profile_version,
            evidence_hash=shared_bundle.evidence_hash,
            assessments=assessments,
            intelligence=intelligence,
            executed_tasks=ordered_tasks,
        )

    def load_cached_assessments(
        self,
        session: Session,
        *,
        report_type: str,
        period: str,
    ) -> dict[str, AssessmentResultContract]:
        prof = get_report_task_profile(report_type)
        expected_pvs = {
            tt: effective_prompt_version(get_assessment_task_spec(tt), report_type)
            for tt in prof.execution_order
        }
        rows = list(
            session.scalars(
                select(ReportNarrativeTask)
                .where(
                    ReportNarrativeTask.report_type == report_type,
                    ReportNarrativeTask.period == period,
                    ReportNarrativeTask.task_type.in_(list(prof.execution_order)),
                )
                .order_by(ReportNarrativeTask.updated_at.desc())
            ).all()
        )
        out: dict[str, AssessmentResultContract] = {}
        for r in rows:
            if r.task_type in out or not isinstance(r.validated_output, dict):
                continue
            if expected_pvs.get(r.task_type) != r.prompt_version:
                continue
            try:
                out[r.task_type] = AssessmentResultContract.model_validate(r.validated_output)
            except Exception:
                continue
        return out

    def load_cached_intelligence(
        self,
        session: Session,
        *,
        report_type: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Cache-only lookup preferring canonical assessments, falling back to legacy cache."""
        prof = get_report_task_profile(report_type)
        period = str(payload.get("period") or "")
        cached_canonical = self.load_cached_assessments(
            session,
            report_type=report_type,
            period=period,
        )
        if cached_canonical:
            ev_hash = compute_payload_fingerprint(payload)
            return project_canonical_to_legacy_intelligence(
                report_type=report_type,
                period=period,
                evidence_hash=ev_hash,
                assessments=cached_canonical,
                profile_version=prof.profile_version,
            )
        return load_cached_intelligence(
            session,
            report_type=report_type,
            period=period,
            payload=payload,
        )

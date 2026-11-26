"""Canonical Report Orchestrator — single execution entrypoint for Daily, Weekly, and Monthly reports.

Design invariants:
- Single task registry: ASSESSMENT_TASK_SPECS in src/gni/reports/narrative/assessment.py.
- Single task execution entrypoint: run_assessment_task().
- Single output contract: AssessmentResultContract (exposed via payload["assessments"] & payload["assessments_meta"]).
- Daily / Weekly / Monthly reuse the exact same orchestrator through declarative ReportTaskProfile configs.
- Zero legacy engine fallback or legacy intelligence projection shims.
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
from gni.reports.narrative.llm_client import JsonLLMClient

ORCHESTRATOR_VERSION = "orchestrator_v2.0"


@dataclass(frozen=True)
class ReportTaskProfile:
    report_type: str
    profile_version: str
    core_tasks: tuple[str, ...]
    optional_tasks: tuple[str, ...]
    execution_order: tuple[str, ...]


REPORT_TASK_PROFILES: dict[str, ReportTaskProfile] = {
    "daily": ReportTaskProfile(
        report_type="daily",
        profile_version="daily_profile_v2.0",
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
        profile_version="weekly_profile_v2.0",
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
        profile_version="monthly_profile_v2.0",
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
        wanted = {resolve_task_type(t) for t in requested_tasks}
        return [t for t in prof.execution_order if t in wanted] + [
            t for t in wanted if t not in prof.execution_order
        ]
    if profile == "full":
        return list(prof.execution_order)
    allowed = set(prof.core_tasks)
    return [t for t in prof.execution_order if t in allowed]


def build_assessments_meta(
    *,
    report_type: str,
    period: str,
    evidence_hash: str,
    assessments: dict[str, AssessmentResultContract],
    profile: ReportTaskProfile,
) -> dict[str, Any]:
    """Build canonical telemetry & status summary for a report's assessments."""
    task_statuses: dict[str, dict[str, Any]] = {}
    completed = 0
    needs_review = 0
    failed = 0
    models: set[str] = set()
    prompt_versions: dict[str, str] = {}
    stale = False

    for tt in profile.core_tasks:
        spec = get_assessment_task_spec(tt)
        pv = effective_prompt_version(spec, report_type)
        prompt_versions[tt] = pv
        res = assessments.get(tt)
        if res is None:
            task_statuses[tt] = {
                "title_zh": spec.title_zh,
                "prompt_version": pv,
                "status": "pending",
                "cached": False,
            }
            continue
        if res.model_version:
            models.add(res.model_version)
        row_stale = bool(evidence_hash and res.evidence_hash and res.evidence_hash != evidence_hash)
        if row_stale:
            stale = True
        task_statuses[tt] = {
            "title_zh": spec.title_zh,
            "prompt_version": res.prompt_version or pv,
            "model_version": res.model_version,
            "status": res.status,
            "stale": row_stale,
            "cached": bool((res.metadata or {}).get("cache_hit", True)),
            "validation": res.validation_result,
            "generated_at": res.generated_at,
        }
        if res.status == "failed":
            failed += 1
        elif res.status in {"completed", "needs_review", "degraded", "insufficient_data"}:
            if res.status == "needs_review":
                needs_review += 1
            completed += 1

    # Also record any optional tasks that were executed/cached
    for tt, res in assessments.items():
        if tt in task_statuses:
            continue
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
            "cached": bool((res.metadata or {}).get("cache_hit", True)),
            "validation": res.validation_result,
            "generated_at": res.generated_at,
        }
        if res.status == "failed":
            failed += 1
        elif res.status in {"completed", "needs_review", "degraded", "insufficient_data"}:
            if res.status == "needs_review":
                needs_review += 1
            completed += 1

    total_tasks = len(task_statuses)
    if completed == 0 and failed == 0:
        overall_status = "rule_only"
    elif completed == 0 and failed > 0:
        overall_status = "failed"
    elif completed < total_tasks or failed > 0:
        overall_status = "partial"
    elif needs_review > 0:
        overall_status = "needs_review"
    else:
        overall_status = "completed"

    return {
        "status": overall_status,
        "engine": "canonical_orchestrator",
        "orchestrator_version": ORCHESTRATOR_VERSION,
        "profile_version": profile.profile_version,
        "report_type": report_type,
        "period": period,
        "evidence_hash": evidence_hash,
        "stale": stale,
        "task_statuses": task_statuses,
        "meta": {
            "completed_tasks": completed,
            "failed_tasks": failed,
            "needs_review_tasks": needs_review,
            "total_tasks": total_tasks,
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
    assessments_meta: dict[str, Any] = field(default_factory=dict)
    executed_tasks: list[str] = field(default_factory=list)

    def serialized_assessments(self) -> dict[str, dict[str, Any]]:
        return {k: v.model_dump(mode="json") for k, v in self.assessments.items()}


class ReportOrchestrator:
    """Single canonical orchestrator scheduling Assessment Engine tasks across Daily/Weekly/Monthly."""

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

        # Load already-cached canonical tasks first so partial retries preserve unaffected completed tasks
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

        meta = build_assessments_meta(
            report_type=report_type,
            period=period,
            evidence_hash=shared_bundle.evidence_hash,
            assessments=assessments,
            profile=prof,
        )
        return OrchestratorRunResult(
            report_type=report_type,
            period=period,
            profile_version=prof.profile_version,
            evidence_hash=shared_bundle.evidence_hash,
            assessments=assessments,
            assessments_meta=meta,
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

    def load_cached(
        self,
        session: Session,
        *,
        report_type: str,
        payload: dict[str, Any],
    ) -> OrchestratorRunResult:
        """Cache-only lookup reading strictly canonical AssessmentResultContract rows."""
        prof = get_report_task_profile(report_type)
        period = str(payload.get("period") or "")
        assessments = self.load_cached_assessments(
            session,
            report_type=report_type,
            period=period,
        )
        ev_hash = compute_payload_fingerprint(payload)
        meta = build_assessments_meta(
            report_type=report_type,
            period=period,
            evidence_hash=ev_hash,
            assessments=assessments,
            profile=prof,
        )
        return OrchestratorRunResult(
            report_type=report_type,
            period=period,
            profile_version=prof.profile_version,
            evidence_hash=ev_hash,
            assessments=assessments,
            assessments_meta=meta,
            executed_tasks=[],
        )

"""One-time idempotent migration script: Legacy report_narrative_tasks -> Canonical AssessmentResultContract.

Converts historical legacy rows (executive_analysis, event_analysis with legacy prompt_version,
topic_trend_analysis, cross_country_analysis, stance_analysis, emerging_signals) into Canonical
AssessmentResultContract rows so historical reports keep their previously analyzed conclusions
with zero legacy runtime code or fallback branches.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select

from gni.core.contracts import ASSESSMENT_SCHEMA_VERSION, AssessmentResultContract
from gni.infrastructure.db import session_scope
from gni.infrastructure.models import ReportNarrativeTask
from gni.metrics.definitions import METHODOLOGY_VERSION, TAXONOMY_V1_VERSION
from gni.reports.narrative.assessment import (
    ASSESSMENT_TASK_SPECS,
    effective_prompt_version,
)

LEGACY_TO_CANONICAL_MAP: dict[str, list[str]] = {
    "executive_analysis": ["overall_situation_assessment"],
    "event_analysis": ["event_analysis"],
    "topic_trend_analysis": ["topic_analysis"],
    "cross_country_analysis": ["country_comparison"],
    "stance_analysis": ["sentiment_stance_analysis"],
    "emerging_signals": ["risk_signal_assessment", "outlook_assessment"],
}


def _convert_legacy_output_to_canonical(
    row: ReportNarrativeTask,
    canonical_task_type: str,
    prompt_version: str,
) -> AssessmentResultContract:
    raw: dict[str, Any] = row.validated_output if isinstance(row.validated_output, dict) else {}
    findings = [f for f in (raw.get("findings") or []) if isinstance(f, dict)]
    obs = [f for f in findings if f.get("classification") == "Fact"]
    interps = [f for f in findings if f.get("classification") == "Inference"]
    hyps = [f for f in findings if f.get("classification") in {"Hypothesis", "Outlook"}]
    ev_refs: list[dict[str, Any]] = []
    for f in findings:
        for r in f.get("evidence_refs") or []:
            if isinstance(r, dict):
                ev_refs.append(r)
    for ei in raw.get("event_interpretations") or []:
        if isinstance(ei, dict):
            for r in ei.get("evidence_refs") or []:
                if isinstance(r, dict):
                    ev_refs.append(r)
    watch = [s for s in (raw.get("outlook_signals") or []) if isinstance(s, dict)]
    details = {
        k: v
        for k, v in raw.items()
        if k
        in {
            "event_interpretations",
            "topic_shifts",
            "country_differences",
            "stance_observations",
            "outlook_signals",
            "follow_up_questions",
        }
        and v
    }
    now_iso = (row.updated_at or datetime.now(timezone.utc)).isoformat()
    return AssessmentResultContract(
        task_type=canonical_task_type,
        task_version=prompt_version,
        report_type=row.report_type,
        period=row.period,
        evidence_hash=row.evidence_hash,
        generated_at=now_iso,
        model_version=row.model_version or "migrated-legacy",
        prompt_version=prompt_version,
        schema_version=ASSESSMENT_SCHEMA_VERSION,
        methodology_version=METHODOLOGY_VERSION,
        taxonomy_version=TAXONOMY_V1_VERSION,
        executive_summary=str(raw.get("summary") or ""),
        key_findings=findings,
        observations=obs,
        interpretations=interps,
        hypotheses=hyps,
        evidence_refs=ev_refs,
        limitations=[str(u) for u in (raw.get("uncertainties") or []) if str(u).strip()],
        watch_items=watch,
        details=details,
        status=row.status if row.status in {"completed", "needs_review", "insufficient_data", "degraded", "failed"} else "completed",  # type: ignore[arg-type]
        validation_result=row.validation_result if isinstance(row.validation_result, dict) else {"ok": True},
        metadata={
            "model_version": row.model_version or "migrated-legacy",
            "prompt_version": prompt_version,
            "migrated_from_legacy": True,
            "legacy_task_type": row.task_type,
            "legacy_prompt_version": row.prompt_version,
        },
    )


def migrate_legacy_report_cache() -> dict[str, int]:
    migrated = 0
    skipped_existing = 0
    skipped_non_legacy = 0
    canonical_pvs = {
        effective_prompt_version(spec, rt)
        for spec in ASSESSMENT_TASK_SPECS.values()
        for rt in ("daily", "weekly", "monthly")
    }
    with session_scope() as session:
        rows = list(session.scalars(select(ReportNarrativeTask)).all())
        for row in rows:
            if row.prompt_version in canonical_pvs:
                skipped_non_legacy += 1
                continue
            targets = LEGACY_TO_CANONICAL_MAP.get(row.task_type)
            if not targets or not isinstance(row.validated_output, dict):
                skipped_non_legacy += 1
                continue
            for canonical_task in targets:
                spec = ASSESSMENT_TASK_SPECS[canonical_task]
                pv = effective_prompt_version(spec, row.report_type)
                exists = session.scalar(
                    select(ReportNarrativeTask).where(
                        ReportNarrativeTask.report_type == row.report_type,
                        ReportNarrativeTask.period == row.period,
                        ReportNarrativeTask.task_type == canonical_task,
                        ReportNarrativeTask.prompt_version == pv,
                    )
                )
                if exists is not None:
                    skipped_existing += 1
                    continue
                contract = _convert_legacy_output_to_canonical(row, canonical_task, pv)
                session.add(
                    ReportNarrativeTask(
                        id=str(uuid4()),
                        report_type=row.report_type,
                        period=row.period,
                        task_type=canonical_task,
                        prompt_version=pv,
                        evidence_hash=row.evidence_hash,
                        model_version=row.model_version,
                        status=contract.status,
                        raw_output=row.raw_output,
                        validated_output=contract.model_dump(mode="json"),
                        validation_result=contract.validation_result,
                        prompt_tokens=row.prompt_tokens,
                        completion_tokens=row.completion_tokens,
                        total_tokens=row.total_tokens,
                        latency_ms=row.latency_ms,
                        estimated_cost_usd=row.estimated_cost_usd,
                        error_message=row.error_message,
                        created_at=row.created_at,
                        updated_at=row.updated_at,
                    )
                )
                migrated += 1
        session.flush()
    return {
        "migrated": migrated,
        "skipped_existing": skipped_existing,
        "skipped_non_legacy": skipped_non_legacy,
    }


if __name__ == "__main__":
    stats = migrate_legacy_report_cache()
    print("Legacy report cache migration complete:", stats)

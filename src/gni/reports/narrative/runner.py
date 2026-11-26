"""Task orchestrator, DB cache, partial-retry runner, and graceful fallback for Report Narrative Layer."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from gni.analysis.budget import llm_allowed, snapshot_budget
from gni.analysis.deepseek import DeepSeekLLMProvider, LLMCallResult
from gni.core.config import Settings, get_settings
from gni.infrastructure.models import ReportNarrativeTask
from gni.reports.narrative.evidence import (
    EvidenceBundle,
    compute_payload_fingerprint,
    prepare_evidence_bundle,
)
from gni.reports.narrative.prompts import TaskPromptSpec, list_report_tasks
from gni.reports.narrative.schemas import NarrativeTaskOutput
from gni.reports.narrative.validator import validate_task_output

logger = logging.getLogger(__name__)


class JsonLLMClient(Protocol):
    def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 2500,
        timeout: float = 75.0,
        max_retries: int = 2,
    ) -> LLMCallResult: ...


def _assemble_intelligence_block(
    report_type: str,
    period: str,
    evidence_hash: str,
    specs: list[TaskPromptSpec],
    rows_by_task: dict[str, ReportNarrativeTask],
) -> dict[str, Any]:
    tasks_payload: dict[str, Any] = {}
    task_statuses: dict[str, dict[str, Any]] = {}
    completed = 0
    needs_review = 0
    failed = 0
    total_tokens = 0
    total_latency_ms = 0
    total_cost = 0.0
    models: set[str] = set()
    stale = False

    for spec in specs:
        row = rows_by_task.get(spec.task_type)
        if row is None:
            task_statuses[spec.task_type] = {
                "title_zh": spec.title_zh,
                "prompt_version": spec.prompt_version,
                "status": "pending",
                "cached": False,
            }
            continue

        row_stale = bool(evidence_hash and row.evidence_hash and row.evidence_hash != evidence_hash)
        if row_stale:
            stale = True

        if row.model_version:
            models.add(row.model_version)
        total_tokens += int(row.total_tokens or 0)
        total_latency_ms += int(row.latency_ms or 0)
        total_cost += float(row.estimated_cost_usd or 0.0)

        task_statuses[spec.task_type] = {
            "title_zh": spec.title_zh,
            "prompt_version": row.prompt_version,
            "model_version": row.model_version,
            "status": row.status,
            "stale": row_stale,
            "total_tokens": row.total_tokens,
            "latency_ms": row.latency_ms,
            "error_message": row.error_message,
            "validation": row.validation_result,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }

        if row.status == "failed":
            failed += 1
        elif row.status in {"completed", "needs_review", "degraded", "insufficient_data"}:
            if row.status == "needs_review":
                needs_review += 1
            completed += 1
            if isinstance(row.validated_output, dict):
                tasks_payload[spec.task_type] = row.validated_output

    total_expected = len(specs)
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
        "report_type": report_type,
        "period": period,
        "evidence_hash": evidence_hash,
        "stale": stale,
        "tasks": tasks_payload,
        "task_statuses": task_statuses,
        "meta": {
            "completed_tasks": completed,
            "failed_tasks": failed,
            "needs_review_tasks": needs_review,
            "total_tasks": total_expected,
            "model_versions": sorted(models),
            "prompt_versions": {s.task_type: s.prompt_version for s in specs},
            "total_tokens": total_tokens,
            "total_latency_ms": total_latency_ms,
            "estimated_cost_usd": round(total_cost, 6),
        },
    }


def load_cached_intelligence(
    session: Session,
    *,
    report_type: str,
    period: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Fast cache-only lookup for GET /api/reports/* — never invokes external LLM."""
    specs = list_report_tasks(report_type)
    prompt_versions = {s.task_type: s.prompt_version for s in specs}
    ev_hash = compute_payload_fingerprint(payload)

    rows = list(
        session.scalars(
            select(ReportNarrativeTask).where(
                ReportNarrativeTask.report_type == report_type,
                ReportNarrativeTask.period == period,
            )
        ).all()
    )
    rows_by_task: dict[str, ReportNarrativeTask] = {}
    for row in rows:
        if prompt_versions.get(row.task_type) == row.prompt_version:
            rows_by_task[row.task_type] = row
    return _assemble_intelligence_block(report_type, period, ev_hash, specs, rows_by_task)


def _upsert_task_row(
    session: Session,
    *,
    report_type: str,
    period: str,
    task_type: str,
    prompt_version: str,
    evidence_hash: str,
    status: str,
    provider: str | None = None,
    model_version: str | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    total_tokens: int | None = None,
    latency_ms: int | None = None,
    estimated_cost_usd: float | None = None,
    error_message: str | None = None,
    raw_output: dict[str, Any] | None = None,
    validated_output: dict[str, Any] | None = None,
    validation_result: dict[str, Any] | None = None,
) -> ReportNarrativeTask:
    existing = session.scalar(
        select(ReportNarrativeTask)
        .where(
            ReportNarrativeTask.report_type == report_type,
            ReportNarrativeTask.period == period,
            ReportNarrativeTask.task_type == task_type,
            ReportNarrativeTask.prompt_version == prompt_version,
        )
        .limit(1)
    )
    now = datetime.now(timezone.utc)
    if existing:
        existing.evidence_hash = evidence_hash
        existing.status = status
        existing.provider = provider
        existing.model_version = model_version
        existing.prompt_tokens = prompt_tokens
        existing.completion_tokens = completion_tokens
        existing.total_tokens = total_tokens
        existing.latency_ms = latency_ms
        existing.estimated_cost_usd = estimated_cost_usd
        existing.error_message = error_message
        existing.raw_output = raw_output
        existing.validated_output = validated_output
        existing.validation_result = validation_result
        existing.updated_at = now
        session.flush()
        return existing

    row = ReportNarrativeTask(
        id=str(uuid4()),
        report_type=report_type,
        period=period,
        task_type=task_type,
        evidence_hash=evidence_hash,
        prompt_version=prompt_version,
        provider=provider,
        model_version=model_version,
        status=status,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        latency_ms=latency_ms,
        estimated_cost_usd=estimated_cost_usd,
        error_message=error_message,
        raw_output=raw_output,
        validated_output=validated_output,
        validation_result=validation_result,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    session.flush()
    return row


def _build_user_prompt(spec: TaskPromptSpec, bundle: EvidenceBundle) -> str:
    ev_slice = bundle.for_task(spec.task_type)
    ev_json = json.dumps(ev_slice, ensure_ascii=False, default=str)
    # Trim cleanly if oversized while preserving valid JSON
    if len(ev_json) > 22000:
        ev_slice = dict(ev_slice)
        if isinstance(ev_slice.get("articles"), list):
            ev_slice["articles"] = ev_slice["articles"][:10]
        if isinstance(ev_slice.get("events"), list):
            ev_slice["events"] = ev_slice["events"][:5]
        ev_json = json.dumps(ev_slice, ensure_ascii=False, default=str)[:22000]

    return (
        f"report_type={spec.report_type} task_type={spec.task_type} "
        f"prompt_version={spec.prompt_version}\n\n"
        f"{spec.task_instructions}\n\n"
        f"EVIDENCE JSON:\n{ev_json}"
    )


def run_report_intelligence(
    session: Session,
    *,
    report_type: str,
    period: str,
    payload: dict[str, Any],
    tasks: list[str] | None = None,
    force: bool = False,
    llm_client: JsonLLMClient | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Execute (with per-task DB caching & partial retry) the LLM Intelligence Narrative Layer.

    Never raises on LLM unavailability or single-task failure so statistical reports always succeed.
    """
    cfg = settings or get_settings()
    all_specs = list_report_tasks(report_type)
    target_set = set(tasks) if tasks else {s.task_type for s in all_specs}
    bundle = prepare_evidence_bundle(session, report_type=report_type, payload=payload)

    # Load existing cache rows for this (report_type, period)
    existing_rows = {
        r.task_type: r
        for r in session.scalars(
            select(ReportNarrativeTask).where(
                ReportNarrativeTask.report_type == report_type,
                ReportNarrativeTask.period == period,
            )
        ).all()
    }

    # Resolve LLM client lazily only when needed
    client = llm_client
    llm_unavailable_reason: str | None = None
    if client is None:
        if not cfg.llm_api_key:
            llm_unavailable_reason = "GNI_LLM_API_KEY not configured; fallback to rule report"
        else:
            budget = snapshot_budget(session, cfg)
            if not llm_allowed(budget, estimated_cost_usd=0.01):
                llm_unavailable_reason = f"LLM daily budget/limit exhausted ({budget.reason or 'budget'})"
            else:
                try:
                    client = DeepSeekLLMProvider(cfg)
                except Exception as exc:  # noqa: BLE001
                    llm_unavailable_reason = f"LLM provider init failed: {exc}"

    rows_by_task: dict[str, ReportNarrativeTask] = {}
    for spec in all_specs:
        cached = existing_rows.get(spec.task_type)
        same_version = cached is not None and cached.prompt_version == spec.prompt_version
        if same_version:
            rows_by_task[spec.task_type] = cached  # type: ignore[assignment]

        if spec.task_type not in target_set:
            continue

        # Cache hit check
        if (
            not force
            and same_version
            and cached is not None
            and cached.evidence_hash == bundle.evidence_hash
            and cached.status in {"completed", "needs_review", "insufficient_data"}
            and isinstance(cached.validated_output, dict)
        ):
            continue

        if client is None:
            row = _upsert_task_row(
                session,
                report_type=report_type,
                period=period,
                task_type=spec.task_type,
                prompt_version=spec.prompt_version,
                evidence_hash=bundle.evidence_hash,
                status="failed",
                provider=cfg.llm_provider,
                model_version=cfg.llm_model,
                error_message=llm_unavailable_reason or "llm_unavailable",
            )
            rows_by_task[spec.task_type] = row
            continue

        # Run single LLM task independently so one failure never blocks others
        user_prompt = _build_user_prompt(spec, bundle)
        try:
            call_res = client.generate_json(
                system_prompt=spec.system_prompt,
                user_prompt=user_prompt,
                model=cfg.llm_model,
                temperature=0.2,
                max_tokens=spec.max_tokens,
            )
            raw_dict = dict(call_res.parsed)
            raw_dict["task_type"] = spec.task_type
            raw_dict["report_type"] = report_type
            parsed_model = NarrativeTaskOutput.model_validate(raw_dict)
            parsed_model.meta.update(
                {
                    "provider": call_res.provider,
                    "model_version": call_res.model_version,
                    "prompt_version": spec.prompt_version,
                    "evidence_hash": bundle.evidence_hash,
                    "total_tokens": call_res.total_tokens,
                    "latency_ms": call_res.latency_ms,
                }
            )
            validated_model, val_summary = validate_task_output(parsed_model, bundle)
            row = _upsert_task_row(
                session,
                report_type=report_type,
                period=period,
                task_type=spec.task_type,
                prompt_version=spec.prompt_version,
                evidence_hash=bundle.evidence_hash,
                status=validated_model.status,
                provider=call_res.provider,
                model_version=call_res.model_version,
                prompt_tokens=call_res.prompt_tokens,
                completion_tokens=call_res.completion_tokens,
                total_tokens=call_res.total_tokens,
                latency_ms=call_res.latency_ms,
                estimated_cost_usd=call_res.estimated_cost_usd,
                error_message=None,
                raw_output=call_res.parsed,
                validated_output=validated_model.model_dump(mode="json"),
                validation_result=val_summary,
            )
            rows_by_task[spec.task_type] = row
        except Exception as exc:  # noqa: BLE001
            logger.exception("Report narrative task %s/%s failed", report_type, spec.task_type)
            row = _upsert_task_row(
                session,
                report_type=report_type,
                period=period,
                task_type=spec.task_type,
                prompt_version=spec.prompt_version,
                evidence_hash=bundle.evidence_hash,
                status="failed",
                provider=cfg.llm_provider,
                model_version=cfg.llm_model,
                error_message=str(exc)[:400],
            )
            rows_by_task[spec.task_type] = row

    result = _assemble_intelligence_block(
        report_type, period, bundle.evidence_hash, all_specs, rows_by_task
    )
    if llm_unavailable_reason:
        result["fallback_reason"] = llm_unavailable_reason
    return result

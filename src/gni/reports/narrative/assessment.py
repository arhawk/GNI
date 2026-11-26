"""Unified Assessment Engine (Phase 5): single execution framework for all 9 V2.0 assessment tasks.

Design invariants:
- Reuses existing EvidencePackage builder (evidence.py), 3-layer Validator (validator.py),
  DeepSeek JSON client (deepseek.py), budget guard (budget.py), and ReportNarrativeTask DB cache.
- Never builds 9 separate ad-hoc agents; all 9 task types execute through one unified runner.
- Strictly separates Observations (Fact), Interpretations (Inference), and Hypotheses (Hypothesis).
- Handles zero-data / insufficient_data, LLM timeout, JSON failure, and budget exhaustion cleanly.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from gni.analysis.budget import llm_allowed, snapshot_budget
from gni.analysis.deepseek import DeepSeekLLMProvider, _extract_json
from gni.core.config import Settings, get_settings
from gni.core.contracts import (
    ASSESSMENT_SCHEMA_VERSION,
    AssessmentResultContract,
    EvidencePackageContract,
)
from gni.infrastructure.models import ReportNarrativeTask
from gni.reports.narrative.evidence import (
    EvidenceBundle,
    build_task_evidence_package,
    prepare_evidence_bundle,
)
from gni.reports.narrative.prompts import _COMMON_HARD_RULES, _FINDING_SCHEMA_HINT
from gni.reports.narrative.runner import JsonLLMClient
from gni.reports.narrative.schemas import NarrativeTaskOutput
from gni.reports.narrative.validator import validate_task_output

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AssessmentTaskSpec:
    task_type: str
    title_zh: str
    prompt_version: str
    required_metrics: tuple[str, ...]
    required_evidence_kinds: tuple[str, ...]
    system_prompt: str
    task_instructions: str
    max_tokens: int = 3600
    legacy_alias: str | None = None


_UNIFIED_OUTPUT_HINT = (
    "输出 JSON 必须包含：\n"
    "- summary: string（简明执行摘要，禁止编造数字）\n"
    "- findings: list（严格区分 classification='Fact'|'Inference'|'Hypothesis'|'Outlook'，每条 Fact 必须附 >=1 条输入真实 evidence_refs，可附 supporting_metrics 与 counter_evidence）\n"
    "- uncertainties: list[string]（样本、覆盖度或归因局限）\n"
    "- follow_up_questions: list[string]（待核查/持续跟踪问题）\n"
    + _FINDING_SCHEMA_HINT
)


def _build_assessment_registry() -> dict[str, AssessmentTaskSpec]:
    specs = [
        AssessmentTaskSpec(
            task_type="overall_situation_assessment",
            title_zh="全局涉华态势综合研判",
            prompt_version="assess_overall_v2.0",
            required_metrics=("GLOBAL", "COUNTRY", "BOARD", "TOPIC"),
            required_evidence_kinds=("metrics", "events", "representative_evidence", "counter_evidence"),
            system_prompt=_COMMON_HARD_RULES
            + "\n\n【任务1：Overall Situation Assessment】不得简单拼接文章数、负面比例和议题排名；必须综合解释整体关注格局、主要变化、核心驱动与反证。",
            task_instructions=(
                "基于 EVIDENCE_PACKAGE 输出当日全局涉华态势研判：\n"
                "1) 整体关注格局与核心议题板块；2) 核心变化及其事件/议题驱动；3) 反例（counter_evidence）与数据覆盖局限。\n"
                "额外字段：important_changes (list[str]), main_drivers (list[str])。\n"
                + _UNIFIED_OUTPUT_HINT
            ),
            legacy_alias="executive_analysis",
        ),
        AssessmentTaskSpec(
            task_type="change_detection_assessment",
            title_zh="周期变化与异常检测研判",
            prompt_version="assess_change_v2.0",
            required_metrics=("GLOBAL", "COUNTRY", "TOPIC"),
            required_evidence_kinds=("metrics", "historical_comparison", "representative_evidence"),
            system_prompt=_COMMON_HARD_RULES
            + "\n\n【任务2：Change Detection】必须对比当前周期与基准周期，严格区分真实变化与小样本波动，禁止仅凭百分比变化判定重大异常。",
            task_instructions=(
                "基于 EVIDENCE_PACKAGE 中的当前周期指标、历史基线对比与多因素变化信号（change_signals），识别并解释关键变化与异常：\n"
                "说明绝对增量、基线水平、样本量与信源覆盖度；对小样本维度必须显式标注不确定性。\n"
                "额外字段：important_changes (list[str]), main_drivers (list[str])。\n"
                + _UNIFIED_OUTPUT_HINT
            ),
        ),
        AssessmentTaskSpec(
            task_type="event_analysis",
            title_zh="重点事件七维深度研判",
            prompt_version="assess_event_v2.0",
            required_metrics=("GLOBAL", "COUNTRY"),
            required_evidence_kinds=("events", "representative_evidence", "counter_evidence"),
            system_prompt=_COMMON_HARD_RULES
            + "\n\n【任务3：Event Analysis】每个重点事件必须按七个维度组织：1) 背景 2) 发生了什么 3) 关键进展 4) 媒体报道 5) 跨国差异 6) 可能影响 7) 后续观察。严禁混淆 event_time 与 published_at。",
            task_instructions=(
                "针对 EVIDENCE_PACKAGE.events 中的重点事件（最多 5 件），输出 event_interpretations 数组，每项包含：\n"
                "event_id, title, background（背景）, what_happened（发生了什么）, event_actual_changes（关键进展）, "
                "coverage_attention_changes（媒体报道关注度）, country_differences（跨国差异）, media_viewpoints (list[str]), "
                "why_it_matters（可能影响）, what_to_monitor (list[str] 后续观察), evidence_refs, confidence, limitations。\n"
                + _UNIFIED_OUTPUT_HINT
            ),
            max_tokens=4400,
            legacy_alias="event_analysis",
        ),
        AssessmentTaskSpec(
            task_type="topic_analysis",
            title_zh="议题格局与持续性研判",
            prompt_version="assess_topic_v2.0",
            required_metrics=("BOARD", "TOPIC"),
            required_evidence_kinds=("metrics", "representative_evidence", "events"),
            system_prompt=_COMMON_HARD_RULES
            + "\n\n【任务4：Topic Analysis】严格沿用 4 大板块 × 15 议题体系，分析关注度、变化趋势、持续性与核心驱动，注意多议题重叠统计口径。",
            task_instructions=(
                "分析当日/当期活跃议题的关注度分布、趋势变化、跨板块交叉情况及主要驱动事件。\n"
                "额外字段：topic_deep_dives (list of {topic_id, topic_name, article_count, trend_interpretation, drivers, dominant_frames, stance_pattern, evidence_refs, confidence, limitations})。\n"
                + _UNIFIED_OUTPUT_HINT
            ),
        ),
        AssessmentTaskSpec(
            task_type="country_comparison",
            title_zh="国别媒体报道对比研判",
            prompt_version="assess_country_v2.0",
            required_metrics=("COUNTRY",),
            required_evidence_kinds=("metrics", "current_articles", "representative_evidence", "counter_evidence"),
            system_prompt=_COMMON_HARD_RULES
            + "\n\n【任务5：Country Comparison】按信源所属国家比较报道量、议题结构、立场分布与叙事差异，必须同步披露各国样本量与立场覆盖率限制。",
            task_instructions=(
                "对比主要报道国家的涉华关注重点、立场分布与叙事差异，输出 country_comparisons 数组：\n"
                "{country_id, article_count, stance_coverage_rate, focus_topics, attitude_summary, key_narratives, difference_vs_global, sample_warning, evidence_refs, confidence}。\n"
                + _UNIFIED_OUTPUT_HINT
            ),
        ),
        AssessmentTaskSpec(
            task_type="narrative_analysis",
            title_zh="叙事结构与演化扩散研判",
            prompt_version="assess_narrative_v2.0",
            required_metrics=("GLOBAL", "COUNTRY", "TOPIC"),
            required_evidence_kinds=("narratives", "representative_evidence", "counter_evidence"),
            system_prompt=_COMMON_HARD_RULES
            + "\n\n【任务6：Narrative Analysis】识别主导叙事、新兴叙事、衰退叙事、叙事分化与跨国扩散；严禁仅凭多国叙事相似推断协调传播。",
            task_instructions=(
                "基于 EVIDENCE_PACKAGE.narratives 与正反例证据，分析主导叙事、新兴/分化叙事与反证声音。\n"
                "额外字段：narrative_shifts (list of {narrative_theme, direction, countries, summary, evidence_refs, confidence, limitations})。\n"
                + _UNIFIED_OUTPUT_HINT
            ),
        ),
        AssessmentTaskSpec(
            task_type="sentiment_stance_analysis",
            title_zh="情感与对华立场独立研判",
            prompt_version="assess_sentiment_stance_v2.0",
            required_metrics=("GLOBAL", "COUNTRY"),
            required_evidence_kinds=("metrics", "current_articles", "representative_evidence", "counter_evidence"),
            system_prompt=_COMMON_HARD_RULES
            + "\n\n【任务7：Sentiment & Stance Analysis】严格区分情感（Sentiment）与对华立场（Stance, target='china_mainland'）；必须区分媒体自身观点（media）与引述对象观点（quoted_actor），Unclassified 不进入正中负分母。",
            task_instructions=(
                "分别评估媒体样本的情感基调与对中国大陆的媒体自身立场分布，明确指出 Unclassified 比例、立场覆盖率与引述观点占比。\n"
                + _UNIFIED_OUTPUT_HINT
            ),
        ),
        AssessmentTaskSpec(
            task_type="risk_signal_assessment",
            title_zh="风险信号与关注度分离研判",
            prompt_version="assess_risk_signal_v2.0",
            required_metrics=("GLOBAL", "COUNTRY", "TOPIC"),
            required_evidence_kinds=("historical_comparison", "events", "narratives", "representative_evidence"),
            system_prompt=_COMMON_HARD_RULES
            + "\n\n【任务8：Risk & Signal Assessment】必须严格区分三者：1) 报道量变化 2) 媒体表达变化 3) 现实世界风险。禁止将负面报道数量增加直接等同于实际风险上升。",
            task_instructions=(
                "评估当日潜在风险信号、持续性议题与跨国传播现象，并逐条给出替代解释（alternative_explanation）。\n"
                "额外字段：outlook_signals (list of {signal, observation_object, evidence_refs, trigger_metrics, reasoning, confidence, what_to_monitor, potential_trigger, alternative_explanation, uncertainty})。\n"
                + _UNIFIED_OUTPUT_HINT
            ),
        ),
        AssessmentTaskSpec(
            task_type="outlook_assessment",
            title_zh="条件性展望与观察清单",
            prompt_version="assess_outlook_v2.0",
            required_metrics=("GLOBAL", "TOPIC"),
            required_evidence_kinds=("events", "narratives", "historical_comparison", "representative_evidence"),
            system_prompt=_COMMON_HARD_RULES
            + "\n\n【任务9：Outlook】必须采用条件性展望，逐项给出 Observation Object、Current Evidence、Possible Development、Trigger Condition、Alternative Scenario 与 Uncertainty，严禁无证据断言必然发生。",
            task_instructions=(
                "输出条件性展望与后续监测清单（outlook_signals），每项必须包含：\n"
                "signal（可能演变）, observation_object（观察对象）, evidence_refs（当前证据）, reasoning（推演依据）, "
                "potential_trigger（触发条件）, alternative_scenario（替代情景）, uncertainty（不确定性）, what_to_monitor (list[str]), confidence。\n"
                + _UNIFIED_OUTPUT_HINT
            ),
            legacy_alias="emerging_signals",
        ),
    ]
    return {s.task_type: s for s in specs}


ASSESSMENT_TASK_SPECS: dict[str, AssessmentTaskSpec] = _build_assessment_registry()

CANONICAL_ASSESSMENT_TASKS: tuple[str, ...] = tuple(ASSESSMENT_TASK_SPECS.keys())

_ALIAS_TO_CANONICAL: dict[str, str] = {
    "executive_analysis": "overall_situation_assessment",
    "emerging_signals": "outlook_assessment",
}


def resolve_task_type(task_type: str) -> str:
    return _ALIAS_TO_CANONICAL.get(task_type, task_type)


def list_assessment_tasks() -> list[AssessmentTaskSpec]:
    return list(ASSESSMENT_TASK_SPECS.values())


def get_assessment_task_spec(task_type: str) -> AssessmentTaskSpec:
    canonical = resolve_task_type(task_type)
    if canonical not in ASSESSMENT_TASK_SPECS:
        raise ValueError(f"Unknown assessment task_type: {task_type}")
    return ASSESSMENT_TASK_SPECS[canonical]


def _build_assessment_user_prompt(
    spec: AssessmentTaskSpec,
    pkg: EvidencePackageContract,
) -> str:
    compact = pkg.model_dump(mode="json")
    raw_json = json.dumps(compact, ensure_ascii=False, separators=(",", ":"))
    if len(raw_json) > 15000:
        compact["current_articles"] = compact["current_articles"][:8]
        compact["representative_evidence"] = compact["representative_evidence"][:8]
        compact["counter_evidence"] = compact["counter_evidence"][:4]
        raw_json = json.dumps(compact, ensure_ascii=False, separators=(",", ":"))
    return (
        f"TASK_TYPE: {spec.task_type} ({spec.title_zh})\n"
        f"PROMPT_VERSION: {spec.prompt_version}\n"
        f"EVIDENCE_PACKAGE_ID: {pkg.package_id}\n\n"
        f"{spec.task_instructions}\n\n"
        f"=== EVIDENCE_PACKAGE (ONLY ALLOWED FACTS, METRICS & REF_IDS) ===\n"
        f"{raw_json}\n"
    )


def _overall_confidence(output: NarrativeTaskOutput, coverage: dict[str, Any]) -> str:
    if coverage.get("is_insufficient_data") or int(coverage.get("global_article_count") or 0) < 3:
        return "low"
    confs = [f.confidence for f in output.findings]
    if not confs:
        return "low"
    if all(c == "high" for c in confs) and not coverage.get("low_sample_scopes"):
        return "high"
    if any(c in {"high", "medium"} for c in confs):
        return "medium"
    return "low"


def to_unified_assessment_result(
    *,
    task_type: str,
    validated: NarrativeTaskOutput,
    evidence_package: EvidencePackageContract,
    validation_result: dict[str, Any],
    status: str,
    model_version: str,
    prompt_version: str,
) -> AssessmentResultContract:
    """Project validated NarrativeTaskOutput into canonical AssessmentResultContract."""
    observations: list[dict[str, Any]] = []
    interpretations: list[dict[str, Any]] = []
    hypotheses: list[dict[str, Any]] = []
    key_findings: list[dict[str, Any]] = []
    all_ev_refs: list[dict[str, Any]] = []
    supporting_metrics: list[str] = []
    counter_ev: list[dict[str, Any]] = []

    seen_ref_keys: set[tuple[str, str]] = set()
    for f in validated.findings:
        fd = f.model_dump()
        key_findings.append(fd)
        if f.classification == "Fact":
            observations.append(fd)
        elif f.classification in {"Hypothesis", "Outlook"}:
            hypotheses.append(fd)
        else:
            interpretations.append(fd)
        for m in f.supporting_metrics:
            if m not in supporting_metrics:
                supporting_metrics.append(m)
        for ref in f.evidence_refs:
            rd = ref.model_dump()
            k = (rd["type"], rd["ref_id"])
            if k not in seen_ref_keys:
                seen_ref_keys.add(k)
                all_ev_refs.append(rd)
        for cref in f.counter_evidence:
            counter_ev.append(cref.model_dump())

    # Include event/country/signal-level evidence_refs & watch_items
    watch_items: list[dict[str, Any]] = []
    for sig in validated.outlook_signals:
        sd = sig.model_dump()
        watch_items.append(sd)
        for ref in sig.evidence_refs:
            rd = ref.model_dump()
            k = (rd["type"], rd["ref_id"])
            if k not in seen_ref_keys:
                seen_ref_keys.add(k)
                all_ev_refs.append(rd)
    for q in validated.follow_up_questions:
        watch_items.append({"signal": q, "kind": "follow_up_question"})

    # Attach package-level counter_evidence if model did not explicitly cite them
    if not counter_ev and evidence_package.counter_evidence:
        counter_ev = [
            {
                "type": "article",
                "ref_id": c.get("article_id", ""),
                "evidence_id": c.get("evidence_id"),
                "label": str(c.get("text_span") or "")[:140],
            }
            for c in evidence_package.counter_evidence[:3]
            if c.get("article_id")
        ]

    if not supporting_metrics:
        for m in evidence_package.metrics[:5]:
            if m.get("metric_ref_id"):
                supporting_metrics.append(str(m["metric_ref_id"]))

    limitations = list(dict.fromkeys(list(evidence_package.limitations) + list(validated.uncertainties)))
    details: dict[str, Any] = {}
    for attr_name in (
        "event_interpretations",
        "cross_country_comparisons",
        "topic_deep_dives",
        "narrative_shifts",
        "outlook_signals",
    ):
        val = getattr(validated, attr_name, None)
        if val:
            details[attr_name] = [
                x.model_dump() if hasattr(x, "model_dump") else x for x in val
            ]
    if getattr(validated, "important_changes", None):
        details["important_changes"] = list(validated.important_changes)
    if getattr(validated, "main_drivers", None):
        details["main_drivers"] = list(validated.main_drivers)

    valid_status = status if status in {"completed", "needs_review", "insufficient_data", "degraded", "failed"} else "needs_review"
    return AssessmentResultContract(
        task_type=task_type,
        executive_summary=validated.summary,
        key_findings=key_findings,
        observations=observations,
        interpretations=interpretations,
        hypotheses=hypotheses,
        evidence_refs=all_ev_refs,
        supporting_metrics=supporting_metrics,
        counter_evidence=counter_ev,
        confidence=_overall_confidence(validated, evidence_package.coverage),  # type: ignore[arg-type]
        limitations=limitations,
        watch_items=watch_items,
        details=details,
        status=valid_status,  # type: ignore[arg-type]
        validation_result=validation_result,
        metadata={
            "schema_version": ASSESSMENT_SCHEMA_VERSION,
            "evidence_package_id": evidence_package.package_id,
            "prompt_version": prompt_version,
            "model_version": model_version,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    )


def _insufficient_data_result(
    spec: AssessmentTaskSpec,
    pkg: EvidencePackageContract,
) -> AssessmentResultContract:
    return AssessmentResultContract(
        task_type=spec.task_type,
        executive_summary="当前统计窗口内无足够涉华监测证据，暂不生成推测性研判结论。",
        key_findings=[],
        observations=[],
        interpretations=[],
        hypotheses=[],
        evidence_refs=[],
        supporting_metrics=[str(m["metric_ref_id"]) for m in pkg.metrics[:3] if m.get("metric_ref_id")],
        counter_evidence=[],
        confidence="low",
        limitations=list(pkg.limitations) or ["当前窗口无涉华报道，证据不足。"],
        watch_items=[],
        status="insufficient_data",
        validation_result={"passed": True, "errors": [], "warnings": ["insufficient_data_short_circuit"]},
        metadata={
            "schema_version": ASSESSMENT_SCHEMA_VERSION,
            "evidence_package_id": pkg.package_id,
            "prompt_version": spec.prompt_version,
            "model_version": "deterministic_gate",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    )


def _deterministic_degraded_result(
    spec: AssessmentTaskSpec,
    pkg: EvidencePackageContract,
    *,
    reason: str,
) -> AssessmentResultContract:
    """Grounded deterministic fallback when LLM is unavailable/times out (no fabricated prose)."""
    g = next((m for m in pkg.metrics if m.get("metric_ref_id") == "metric:GLOBAL:ALL"), None)
    obs: list[dict[str, Any]] = []
    ev_refs: list[dict[str, Any]] = []
    metrics_refs: list[str] = []
    if g:
        mref = str(g["metric_ref_id"])
        metrics_refs.append(mref)
        ev_refs.append({"type": "metric", "ref_id": mref, "label": "全球涉华统计快照"})
        obs.append(
            {
                "title": "确定性统计快照摘要",
                "conclusion": (
                    f"当期涉华去重文章 {g.get('article_count', 0)} 篇，"
                    f"立场覆盖率 {float(g.get('stance_coverage_rate') or 0.0):.0%}。"
                ),
                "classification": "Fact",
                "evidence_refs": [{"type": "metric", "ref_id": mref, "label": "全球涉华统计快照"}],
                "supporting_metrics": [mref],
                "confidence": "low",
                "limitations": [f"LLM 研判不可用已降级：{reason}"],
            }
        )
    for rep in pkg.representative_evidence[:3]:
        if rep.get("article_id"):
            ev_refs.append(
                {
                    "type": "article",
                    "ref_id": rep["article_id"],
                    "evidence_id": rep.get("evidence_id"),
                    "label": str(rep.get("text_span") or "")[:120],
                }
            )
    return AssessmentResultContract(
        task_type=spec.task_type,
        executive_summary=f"LLM 研判暂不可用（{reason}），已保留确定性统计与原文证据引用。",
        key_findings=obs,
        observations=obs,
        interpretations=[],
        hypotheses=[],
        evidence_refs=ev_refs,
        supporting_metrics=metrics_refs,
        counter_evidence=[
            {
                "type": "article",
                "ref_id": c["article_id"],
                "evidence_id": c.get("evidence_id"),
                "label": str(c.get("text_span") or "")[:120],
            }
            for c in pkg.counter_evidence[:3]
            if c.get("article_id")
        ],
        confidence="low",
        limitations=list(dict.fromkeys(list(pkg.limitations) + [f"降级原因：{reason}"])),
        watch_items=[],
        status="degraded",
        validation_result={"passed": True, "errors": [], "warnings": [f"degraded:{reason}"]},
        metadata={
            "schema_version": ASSESSMENT_SCHEMA_VERSION,
            "evidence_package_id": pkg.package_id,
            "prompt_version": spec.prompt_version,
            "model_version": "deterministic_fallback",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    )


def _persist_assessment_task(
    session: Session,
    *,
    report_type: str,
    period: str,
    spec: AssessmentTaskSpec,
    evidence_hash: str,
    result: AssessmentResultContract,
    raw_output: str | None = None,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    latency_ms: int = 0,
    cost_usd: float = 0.0,
    error_message: str | None = None,
) -> ReportNarrativeTask:
    existing = session.scalar(
        select(ReportNarrativeTask).where(
            ReportNarrativeTask.report_type == report_type,
            ReportNarrativeTask.period == period,
            ReportNarrativeTask.task_type == spec.task_type,
            ReportNarrativeTask.prompt_version == spec.prompt_version,
        )
    )
    now = datetime.now(timezone.utc)
    if existing is None:
        existing = ReportNarrativeTask(
            id=str(uuid4()),
            report_type=report_type,
            period=period,
            task_type=spec.task_type,
            prompt_version=spec.prompt_version,
            created_at=now,
        )
        session.add(existing)
    existing.evidence_hash = evidence_hash
    existing.model_version = str(result.metadata.get("model_version") or "")
    existing.status = result.status
    existing.raw_output = raw_output
    existing.validated_output = result.model_dump(mode="json")
    existing.validation_result = result.validation_result
    existing.prompt_tokens = prompt_tokens
    existing.completion_tokens = completion_tokens
    existing.total_tokens = total_tokens
    existing.latency_ms = latency_ms
    existing.estimated_cost_usd = cost_usd
    existing.error_message = error_message
    existing.updated_at = now
    session.flush()
    return existing


def run_assessment_task(
    session: Session,
    *,
    task_type: str,
    report_type: str,
    payload: dict[str, Any],
    bundle: EvidenceBundle | None = None,
    client: JsonLLMClient | None = None,
    settings: Settings | None = None,
    force: bool = False,
    allow_fallback: bool = True,
) -> AssessmentResultContract:
    """Unified execution entrypoint for any of the 9 V2.0 assessment tasks."""
    spec = get_assessment_task_spec(task_type)
    period = str(payload.get("period") or "")
    pkg, ev_bundle = build_task_evidence_package(
        session,
        task_type=spec.task_type,
        report_type=report_type,
        payload=payload,
        bundle=bundle,
    )

    # 1. Cache lookup in ReportNarrativeTask
    if not force:
        cached = session.scalar(
            select(ReportNarrativeTask).where(
                ReportNarrativeTask.report_type == report_type,
                ReportNarrativeTask.period == period,
                ReportNarrativeTask.task_type == spec.task_type,
                ReportNarrativeTask.prompt_version == spec.prompt_version,
                ReportNarrativeTask.evidence_hash == ev_bundle.evidence_hash,
                ReportNarrativeTask.status.in_(["completed", "needs_review", "insufficient_data"]),
            )
        )
        if cached and isinstance(cached.validated_output, dict):
            try:
                return AssessmentResultContract.model_validate(cached.validated_output)
            except Exception:
                pass

    # 2. Insufficient data short-circuit (zero articles -> never hallucinate)
    if pkg.coverage.get("is_insufficient_data"):
        res = _insufficient_data_result(spec, pkg)
        _persist_assessment_task(
            session,
            report_type=report_type,
            period=period,
            spec=spec,
            evidence_hash=ev_bundle.evidence_hash,
            result=res,
        )
        return res

    # 3. Resolve LLM client & budget gate
    cfg = settings or get_settings()
    llm_client = client
    if llm_client is None:
        if not cfg.llm_api_key:
            if allow_fallback:
                res = _deterministic_degraded_result(spec, pkg, reason="no_llm_api_key")
                _persist_assessment_task(
                    session,
                    report_type=report_type,
                    period=period,
                    spec=spec,
                    evidence_hash=ev_bundle.evidence_hash,
                    result=res,
                    error_message="GNI_LLM_API_KEY not configured",
                )
                return res
            raise RuntimeError("GNI_LLM_API_KEY not configured")
        budget = snapshot_budget(session, cfg)
        if not llm_allowed(budget, estimated_cost_usd=0.01, ignore_article_limit=True):
            res = _deterministic_degraded_result(spec, pkg, reason="daily_budget_exhausted")
            _persist_assessment_task(
                session,
                report_type=report_type,
                period=period,
                spec=spec,
                evidence_hash=ev_bundle.evidence_hash,
                result=res,
                error_message="Daily LLM budget exhausted",
            )
            return res
        llm_client = DeepSeekLLMProvider(cfg)

    # 4. Call LLM + Schema Validation + 3-Layer Fact/Evidence/Reasoning Validator
    user_prompt = _build_assessment_user_prompt(spec, pkg)
    try:
        call = llm_client.generate_json(
            system_prompt=spec.system_prompt,
            user_prompt=user_prompt,
            model=cfg.llm_model,
            temperature=0.2,
            max_tokens=spec.max_tokens,
            timeout=75.0,
            max_retries=2,
        )
        raw_text = call.raw_text or ""
        parsed = dict(call.parsed) if isinstance(call.parsed, dict) and call.parsed else _extract_json(raw_text)
        if not isinstance(parsed, dict):
            raise ValueError("LLM response was not valid JSON")
        parsed.setdefault("task_type", spec.task_type)
        model_out = NarrativeTaskOutput.model_validate(parsed)
        validated, val_report = validate_task_output(model_out, ev_bundle)
        status = str(val_report.get("status") or ("needs_review" if val_report.get("needs_review") else "completed"))
        res = to_unified_assessment_result(
            task_type=spec.task_type,
            validated=validated,
            evidence_package=pkg,
            validation_result=val_report,
            status=status,
            model_version=call.model_version or cfg.llm_model,
            prompt_version=spec.prompt_version,
        )
        _persist_assessment_task(
            session,
            report_type=report_type,
            period=period,
            spec=spec,
            evidence_hash=ev_bundle.evidence_hash,
            result=res,
            raw_output=raw_text[:20000],
            prompt_tokens=call.prompt_tokens,
            completion_tokens=call.completion_tokens,
            total_tokens=call.total_tokens,
            latency_ms=call.latency_ms,
            cost_usd=call.estimated_cost_usd,
        )
        return res
    except Exception as exc:  # noqa: BLE001
        logger.warning("Assessment task %s failed: %s", spec.task_type, exc)
        if allow_fallback:
            res = _deterministic_degraded_result(spec, pkg, reason=str(exc)[:180])
            res.status = "failed"
            _persist_assessment_task(
                session,
                report_type=report_type,
                period=period,
                spec=spec,
                evidence_hash=ev_bundle.evidence_hash,
                result=res,
                error_message=str(exc)[:500],
            )
            return res
        raise


def run_assessment_suite(
    session: Session,
    *,
    task_types: list[str] | tuple[str, ...] | None = None,
    report_type: str = "daily",
    payload: dict[str, Any],
    client: JsonLLMClient | None = None,
    settings: Settings | None = None,
    force: bool = False,
    allow_fallback: bool = True,
) -> dict[str, AssessmentResultContract]:
    """Run a batch of assessment tasks sharing one DB-backed EvidenceBundle."""
    tasks = list(task_types) if task_types is not None else list(CANONICAL_ASSESSMENT_TASKS)
    shared_bundle = prepare_evidence_bundle(session, report_type=report_type, payload=payload)
    out: dict[str, AssessmentResultContract] = {}
    for tt in tasks:
        canonical = resolve_task_type(tt)
        out[canonical] = run_assessment_task(
            session,
            task_type=canonical,
            report_type=report_type,
            payload=payload,
            bundle=shared_bundle,
            client=client,
            settings=settings,
            force=force,
            allow_fallback=allow_fallback,
        )
    return out

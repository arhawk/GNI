"""Phase 6: Unified Report Package assembler & validator for Daily Intelligence Brief (6 Chapters + Appendix).

Reuses:
- ReportPackageContract & ReportSectionContract (src/gni/core/contracts.py)
- Assessment Engine (src/gni/reports/narrative/assessment.py)
- Deterministic V1.0 metrics (v1_stats), multi-factor changes (metrics/changes.py),
  Events & Narratives (events/narratives.py), and ReportSnapshot persistence.

Strictly enforces deterministic vs LLM responsibility boundaries:
- Deterministic code owns ALL counts, rates, rankings, period comparisons, and coverage stats.
- LLM assessments own interpretation, narrative synthesis, cross-country explanation, and conditional outlook.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from gni.core.contracts import (
    REPORT_PACKAGE_VERSION,
    AssessmentResultContract,
    ReportPackageContract,
    ReportSectionContract,
)
from gni.infrastructure.models import ReportNarrativeTask, ReportSnapshot
from gni.metrics.definitions import METHODOLOGY_VERSION, TAXONOMY_V1_VERSION, V1_ANALYSIS_VERSION
from gni.reports.narrative.assessment import (
    CANONICAL_ASSESSMENT_TASKS,
    run_assessment_suite,
)
from gni.reports.narrative.evidence import (
    _collect_narratives_for_package,
    _compute_change_signals_for_package,
    prepare_evidence_bundle,
)
from gni.reports.narrative.runner import JsonLLMClient

REQUIRED_DAILY_CHAPTER_IDS: tuple[str, ...] = (
    "chapter_1_executive_judgment",
    "chapter_2_key_developments",
    "chapter_3_global_situation",
    "chapter_4_key_changes_anomalies",
    "chapter_5_emerging_signals",
    "chapter_6_outlook_watchlist",
    "appendix",
)

# Maps each chapter to its canonical Phase 5 assessment task types (and legacy fallback keys)
_CHAPTER_TASK_MAP: dict[str, tuple[str, ...]] = {
    "chapter_1_executive_judgment": ("overall_situation_assessment", "executive_analysis"),
    "chapter_2_key_developments": ("event_analysis",),
    "chapter_3_global_situation": ("topic_analysis", "country_comparison"),
    "chapter_4_key_changes_anomalies": ("change_detection_assessment", "sentiment_stance_analysis"),
    "chapter_5_emerging_signals": ("narrative_analysis", "risk_signal_assessment"),
    "chapter_6_outlook_watchlist": ("outlook_assessment", "emerging_signals"),
}


def _load_cached_v2_assessments(
    session: Session,
    *,
    report_type: str,
    period: str,
) -> dict[str, AssessmentResultContract]:
    rows = list(
        session.scalars(
            select(ReportNarrativeTask)
            .where(
                ReportNarrativeTask.report_type == report_type,
                ReportNarrativeTask.period == period,
                ReportNarrativeTask.task_type.in_(list(CANONICAL_ASSESSMENT_TASKS)),
            )
            .order_by(ReportNarrativeTask.updated_at.desc())
        ).all()
    )
    out: dict[str, AssessmentResultContract] = {}
    for r in rows:
        if r.task_type in out or not isinstance(r.validated_output, dict):
            continue
        try:
            out[r.task_type] = AssessmentResultContract.model_validate(r.validated_output)
        except Exception:
            continue
    return out


def _adapt_legacy_intelligence_task(
    task_type: str,
    raw: dict[str, Any],
) -> AssessmentResultContract:
    """Adapt existing daily intelligence task output (executive_analysis/event_analysis/emerging_signals)."""
    findings = [f for f in (raw.get("findings") or []) if isinstance(f, dict)]
    obs = [f for f in findings if f.get("classification") == "Fact"]
    interps = [f for f in findings if f.get("classification") == "Inference"]
    hyps = [f for f in findings if f.get("classification") in {"Hypothesis", "Outlook"}]
    ev_refs: list[dict[str, Any]] = []
    for f in findings:
        for ref in f.get("evidence_refs") or []:
            if isinstance(ref, dict):
                ev_refs.append(ref)
    for ev_i in raw.get("event_interpretations") or []:
        if isinstance(ev_i, dict):
            for ref in ev_i.get("evidence_refs") or []:
                if isinstance(ref, dict):
                    ev_refs.append(ref)
    watch = [s for s in (raw.get("outlook_signals") or []) if isinstance(s, dict)]
    return AssessmentResultContract(
        task_type=task_type,
        executive_summary=str(raw.get("summary") or ""),
        key_findings=findings,
        observations=obs,
        interpretations=interps,
        hypotheses=hyps,
        evidence_refs=ev_refs,
        limitations=[str(u) for u in (raw.get("uncertainties") or []) if str(u).strip()],
        watch_items=watch,
        details={
            k: raw[k]
            for k in (
                "event_interpretations",
                "country_comparisons",
                "topic_deep_dives",
                "narrative_shifts",
                "outlook_signals",
                "important_changes",
                "main_drivers",
            )
            if raw.get(k)
        },
        status="completed",
    )


def _pick_assessments(
    chapter_id: str,
    assessments: dict[str, AssessmentResultContract],
    legacy_tasks: dict[str, Any],
) -> list[AssessmentResultContract]:
    picked: list[AssessmentResultContract] = []
    seen_canonical: set[str] = set()
    for key in _CHAPTER_TASK_MAP.get(chapter_id, ()):
        if key in assessments and key not in seen_canonical:
            picked.append(assessments[key])
            seen_canonical.add(key)
        elif key in legacy_tasks and isinstance(legacy_tasks[key], dict) and not picked:
            picked.append(_adapt_legacy_intelligence_task(key, legacy_tasks[key]))
    return picked


def _merge_section_from_assessments(
    *,
    section_id: str,
    title: str,
    source_kind: str,
    picked: list[AssessmentResultContract],
    deterministic_summary: str,
    deterministic_metrics: list[dict[str, Any]],
    deterministic_evidence: list[dict[str, Any]],
    visualizations: list[dict[str, Any]] | None = None,
    extra_limitations: list[str] | None = None,
) -> ReportSectionContract:
    summaries = [a.executive_summary for a in picked if a.executive_summary]
    summary = " ".join(summaries).strip() if summaries else deterministic_summary
    findings: list[dict[str, Any]] = []
    ev_refs: list[dict[str, Any]] = list(deterministic_evidence)
    limitations: list[str] = list(extra_limitations or [])
    statuses = [a.status for a in picked]

    for a in picked:
        findings.extend(a.key_findings)
        ev_refs.extend(a.evidence_refs)
        limitations.extend(a.limitations)
        if a.details.get("event_interpretations"):
            for ev_i in a.details["event_interpretations"]:
                if isinstance(ev_i, dict):
                    findings.append(
                        {
                            "title": ev_i.get("title") or ev_i.get("event_id") or "Event",
                            "conclusion": ev_i.get("what_happened") or ev_i.get("why_it_matters") or "",
                            "classification": "Inference",
                            "evidence_refs": ev_i.get("evidence_refs") or [],
                            "confidence": ev_i.get("confidence") or "medium",
                            "event_detail": ev_i,
                        }
                    )
        if a.watch_items and section_id == "chapter_6_outlook_watchlist":
            for wi in a.watch_items:
                if isinstance(wi, dict):
                    findings.append(
                        {
                            "title": wi.get("observation_object") or wi.get("signal") or "Watch item",
                            "conclusion": wi.get("signal") or "",
                            "classification": "Outlook",
                            "evidence_refs": wi.get("evidence_refs") or [],
                            "confidence": wi.get("confidence") or "low",
                            "watch_detail": wi,
                        }
                    )

    # Deduplicate evidence_refs & limitations
    dedup_refs: list[dict[str, Any]] = []
    seen_r: set[tuple[str, str]] = set()
    for r in ev_refs:
        if not isinstance(r, dict):
            continue
        k = (str(r.get("type") or ""), str(r.get("ref_id") or r.get("article_id") or r.get("event_id") or ""))
        if k[1] and k not in seen_r:
            seen_r.add(k)
            dedup_refs.append(r)

    if not picked:
        sec_status = "rule_only" if source_kind != "llm_assessment" else "insufficient_data"
    elif any(s == "failed" for s in statuses):
        sec_status = "partial" if any(s in {"completed", "needs_review"} for s in statuses) else "failed"
    elif any(s == "insufficient_data" for s in statuses):
        sec_status = "insufficient_data"
    elif any(s == "needs_review" for s in statuses):
        sec_status = "needs_review"
    elif all(s == "degraded" for s in statuses):
        sec_status = "rule_only"
    else:
        sec_status = "completed"

    return ReportSectionContract(
        section_id=section_id,
        title=title,
        source_kind=source_kind,  # type: ignore[arg-type]
        summary=summary,
        findings=findings,
        evidence_refs=dedup_refs[:30],
        metrics=deterministic_metrics,
        visualizations=list(visualizations or []),
        limitations=list(dict.fromkeys(limitations)),
        assessment_task_types=[a.task_type for a in picked],
        status=sec_status,  # type: ignore[arg-type]
    )


def validate_report_package(
    pkg: ReportPackageContract,
    payload: dict[str, Any],
) -> tuple[str, list[str]]:
    """Deterministic report-level validation: chapter completeness, metric alignment, evidence grounding."""
    notes: list[str] = []
    hard_fail = False

    # 1. All 6 required chapters + appendix present
    present_ids = {s.section_id for s in pkg.sections}
    missing = [cid for cid in REQUIRED_DAILY_CHAPTER_IDS if cid not in present_ids]
    if missing:
        notes.append(f"missing_chapters:{','.join(missing)}")
        hard_fail = True

    # 2. Deterministic metric consistency check against v1_stats.global
    v1_global = ((payload.get("sections") or {}).get("v1_stats") or {}).get("global") or {}
    expected_n = v1_global.get("article_count")
    ch3 = next((s for s in pkg.sections if s.section_id == "chapter_3_global_situation"), None)
    if ch3 and expected_n is not None:
        g_met = next((m for m in ch3.metrics if m.get("scope_type") == "GLOBAL"), None)
        if g_met and g_met.get("article_count") != expected_n:
            notes.append(
                f"metric_mismatch:chapter_3({g_met.get('article_count')})!=v1_global({expected_n})"
            )
            hard_fail = True

    # 3. Every Fact finding must carry >= 1 evidence_ref
    ungrounded_facts = 0
    for sec in pkg.sections:
        for f in sec.findings:
            if isinstance(f, dict) and f.get("classification") == "Fact":
                if not (f.get("evidence_refs") or []):
                    ungrounded_facts += 1
    if ungrounded_facts > 0:
        notes.append(f"ungrounded_fact_findings:{ungrounded_facts}")

    if any(s.status in {"failed", "needs_review"} for s in pkg.sections):
        notes.append("section_requires_review_or_partial")

    if hard_fail:
        return "failed", notes
    if notes:
        return "needs_review", notes
    return "passed", notes


def assemble_daily_report_package(
    session: Session,
    *,
    payload: dict[str, Any],
    assessments: dict[str, AssessmentResultContract] | None = None,
    run_assessments: bool = False,
    assessment_tasks: list[str] | tuple[str, ...] | None = None,
    llm_client: JsonLLMClient | None = None,
    force: bool = False,
) -> ReportPackageContract:
    """Assemble the canonical 6-Chapter + Appendix Daily Intelligence Brief ReportPackageContract."""
    period = str(payload.get("period") or "")
    sections_raw = payload.get("sections") or {}
    v1_stats = sections_raw.get("v1_stats") or {}
    summary_raw = sections_raw.get("summary") or {}
    kpis = summary_raw.get("kpis") or {}
    major_events = sections_raw.get("major_events") or []
    coverage_raw = sections_raw.get("coverage") or {}

    # Shared DB-backed evidence bundle + Phase 4 change signals & narratives
    bundle = prepare_evidence_bundle(session, report_type="daily", payload=payload)
    change_signals = _compute_change_signals_for_package(bundle)
    narratives = _collect_narratives_for_package(session, bundle, limit=8)

    # Assessments: provided > freshly run > cached V2.0 > legacy intelligence fallback
    resolved_assessments: dict[str, AssessmentResultContract] = dict(assessments or {})
    if run_assessments:
        ran = run_assessment_suite(
            session,
            task_types=assessment_tasks,
            report_type="daily",
            payload=payload,
            client=llm_client,
            force=force,
        )
        resolved_assessments.update(ran)
    elif not resolved_assessments:
        resolved_assessments = _load_cached_v2_assessments(
            session, report_type="daily", period=period
        )

    legacy_tasks = (payload.get("intelligence") or {}).get("tasks") or {}

    # Deterministic metrics list + refs
    v1_global = v1_stats.get("global") if isinstance(v1_stats.get("global"), dict) else {}
    v1_countries = [c for c in (v1_stats.get("countries") or []) if isinstance(c, dict)]
    v1_boards = [b for b in (v1_stats.get("boards") or []) if isinstance(b, dict)]
    v1_topics = [t for t in (v1_stats.get("topics") or []) if isinstance(t, dict)]

    metric_refs: list[str] = []
    if v1_global:
        metric_refs.append("metric:GLOBAL:ALL")
    for c in v1_countries:
        if c.get("scope_id"):
            metric_refs.append(f"metric:COUNTRY:{c['scope_id']}")
    for b in v1_boards:
        if b.get("scope_id"):
            metric_refs.append(f"metric:BOARD:{b['scope_id']}")
    for t in v1_topics:
        if t.get("scope_id"):
            metric_refs.append(f"metric:TOPIC:{t['scope_id']}")

    global_article_n = int(v1_global.get("article_count") or kpis.get("china_articles") or 0)
    stance_cov = v1_global.get("stance_coverage_rate")
    global_ev_refs = [
        {"type": "metric", "ref_id": "metric:GLOBAL:ALL", "label": f"全球涉华 {global_article_n} 篇"}
    ]
    event_ev_refs = [
        {"type": "event", "ref_id": str(e.get("event_id") or e.get("id")), "label": str(e.get("title") or "")[:100]}
        for e in major_events[:6]
        if (e.get("event_id") or e.get("id"))
    ]
    article_ev_refs = [
        {
            "type": "article",
            "ref_id": a["article_id"],
            "article_version_id": a.get("article_version_id"),
            "label": str(a.get("title") or "")[:100],
            "source_country": a.get("source_country"),
            "published_at": a.get("published_at"),
        }
        for a in bundle.articles[:12]
    ]

    # Chapter 1 — Executive Judgment
    ch1 = _merge_section_from_assessments(
        section_id="chapter_1_executive_judgment",
        title="Chapter 1 — Executive Judgment",
        source_kind="hybrid",
        picked=_pick_assessments("chapter_1_executive_judgment", resolved_assessments, legacy_tasks),
        deterministic_summary=(
            summary_raw.get("judgment_text")
            or summary_raw.get("overview_text")
            or f"当期监测到涉华去重文章 {global_article_n} 篇。"
        ),
        deterministic_metrics=[v1_global] if v1_global else [],
        deterministic_evidence=global_ev_refs + event_ev_refs[:3],
    )

    # Chapter 2 — Key Developments
    ch2 = _merge_section_from_assessments(
        section_id="chapter_2_key_developments",
        title="Chapter 2 — Key Developments",
        source_kind="hybrid",
        picked=_pick_assessments("chapter_2_key_developments", resolved_assessments, legacy_tasks),
        deterministic_summary=(
            f"当期识别重点涉华事件 {len(major_events)} 件。"
            if major_events
            else "当期暂无达到聚簇阈值的重点涉华事件。"
        ),
        deterministic_metrics=[
            {"metric": "major_events_count", "value": len(major_events)},
            {"metric": "new_events_count", "value": kpis.get("new_events", 0)},
        ],
        deterministic_evidence=event_ev_refs + article_ev_refs[:5],
    )

    # Chapter 3 — Global Situation (deterministic metrics anchor + topic/country interpretation)
    ch3_metrics = ([v1_global] if v1_global else []) + v1_countries[:10] + v1_boards + v1_topics[:15]
    ch3 = _merge_section_from_assessments(
        section_id="chapter_3_global_situation",
        title="Chapter 3 — Global Situation",
        source_kind="deterministic_metrics",
        picked=_pick_assessments("chapter_3_global_situation", resolved_assessments, legacy_tasks),
        deterministic_summary=(
            f"全球涉华去重文章 {global_article_n} 篇，覆盖 {kpis.get('reporting_countries', len(v1_countries))} 国、"
            f"{kpis.get('reporting_sources', 0)} 个信源，立场判定覆盖率 "
            f"{(f'{float(stance_cov) * 100:.1f}%' if isinstance(stance_cov, (int, float)) else '—')}。"
        ),
        deterministic_metrics=ch3_metrics,
        deterministic_evidence=global_ev_refs + article_ev_refs[:6],
        visualizations=[
            {"chart_id": "global_country_distribution", "data": v1_countries[:12]},
            {"chart_id": "four_boards_distribution", "data": v1_boards},
            {"chart_id": "fifteen_topics_distribution", "data": v1_topics},
        ],
    )

    # Chapter 4 — Key Changes & Anomalies
    ch4 = _merge_section_from_assessments(
        section_id="chapter_4_key_changes_anomalies",
        title="Chapter 4 — Key Changes & Anomalies",
        source_kind="hybrid",
        picked=_pick_assessments("chapter_4_key_changes_anomalies", resolved_assessments, legacy_tasks),
        deterministic_summary=(
            f"确定性多因素变化检测识别 {len(change_signals)} 条异常信号，规则告警 {len(bundle.alerts)} 条。"
        ),
        deterministic_metrics=[
            {"metric": "comparisons", "value": summary_raw.get("comparisons") or {}},
            {"metric": "change_signals", "value": change_signals},
            {"metric": "alerts_count", "value": len(bundle.alerts)},
        ],
        deterministic_evidence=global_ev_refs,
    )

    # Chapter 5 — Emerging Signals (Narratives + Risk Signals)
    ch5 = _merge_section_from_assessments(
        section_id="chapter_5_emerging_signals",
        title="Chapter 5 — Emerging Signals",
        source_kind="hybrid",
        picked=_pick_assessments("chapter_5_emerging_signals", resolved_assessments, legacy_tasks),
        deterministic_summary=(
            f"当期聚合涉华叙事簇 {len(narratives)} 个（含正反证分离，不推断协调传播）。"
            if narratives
            else "当期未形成跨文章稳定叙事簇，持续监测中。"
        ),
        deterministic_metrics=[
            {"metric": "narrative_clusters_count", "value": len(narratives)},
            {"metric": "narratives", "value": narratives[:6]},
        ],
        deterministic_evidence=article_ev_refs[:4],
    )

    # Chapter 6 — Outlook & Watchlist
    ch6 = _merge_section_from_assessments(
        section_id="chapter_6_outlook_watchlist",
        title="Chapter 6 — Outlook & Watchlist",
        source_kind="llm_assessment",
        picked=_pick_assessments("chapter_6_outlook_watchlist", resolved_assessments, legacy_tasks),
        deterministic_summary="条件性展望与次日观察清单需基于已完成研判任务生成；样本不足时不作无依据预测。",
        deterministic_metrics=[],
        deterministic_evidence=event_ev_refs[:3],
    )

    # Appendix — Statistics, Representative Articles, Coverage & Methodology
    limitations = list(
        dict.fromkeys(
            [
                str(payload.get("disclaimer") or ""),
                "官方媒体报道不能直接等同于政府正式政策立场。",
                "Unclassified 保留在总文章量中，不进入正中负比例分母。",
                "事件时间线仅使用明确 event_time，未知保持 NULL，绝不以 published_at 替代。",
            ]
            + [l for a in resolved_assessments.values() for l in a.limitations]
        )
    )
    limitations = [x for x in limitations if x]

    appendix = ReportSectionContract(
        section_id="appendix",
        title="Appendix — Statistics, Representative Articles, Coverage & Methodology",
        source_kind="deterministic_metrics",
        summary="附录提供 V1.0 统计口径声明、数据覆盖率、代表文章列表与样本局限。",
        findings=[],
        evidence_refs=article_ev_refs,
        metrics=[
            {"metric": "v1_global", "value": v1_global},
            {"metric": "coverage_by_source", "value": (coverage_raw.get("by_source") or [])[:15]},
            {"metric": "representative_articles", "value": bundle.articles[:12]},
        ],
        limitations=limitations,
        status="completed",
    )

    sections = [ch1, ch2, ch3, ch4, ch5, ch6, appendix]

    # Overall generation status
    all_ev_refs: list[dict[str, Any]] = []
    seen_all: set[tuple[str, str]] = set()
    for sec in sections:
        for r in sec.evidence_refs:
            k = (str(r.get("type") or ""), str(r.get("ref_id") or ""))
            if k[1] and k not in seen_all:
                seen_all.add(k)
                all_ev_refs.append(r)

    if global_article_n == 0:
        gen_status = "insufficient_data"
    elif not resolved_assessments and not legacy_tasks:
        gen_status = "rule_only"
    elif any(a.status == "failed" for a in resolved_assessments.values()):
        gen_status = "partial"
    elif any(a.status == "needs_review" for a in resolved_assessments.values()):
        gen_status = "needs_review"
    else:
        gen_status = "completed"

    pkg = ReportPackageContract(
        report_id=f"daily:{period}",
        report_type="daily",
        period={"label": period, "timezone": payload.get("timezone")},
        period_start=payload.get("period_start"),
        period_end=payload.get("period_end"),
        generated_at=datetime.now(timezone.utc).isoformat(),
        metric_snapshot_refs=metric_refs,
        assessment_refs=[
            {
                "task_type": a.task_type,
                "status": a.status,
                "prompt_version": a.metadata.get("prompt_version"),
                "model_version": a.metadata.get("model_version"),
                "evidence_package_id": a.metadata.get("evidence_package_id"),
            }
            for a in resolved_assessments.values()
        ],
        assessment_results=[a.model_dump(mode="json") for a in resolved_assessments.values()],
        sections=sections,
        evidence_refs=all_ev_refs[:50],
        methodology={
            "methodology_version": METHODOLOGY_VERSION,
            "taxonomy_version": TAXONOMY_V1_VERSION,
            "analysis_version": V1_ANALYSIS_VERSION,
            "core_kpi": "deduplicated_article_count",
            "time_basis_articles": "published_at",
            "time_basis_events": "event_time_nullable",
            "country_attribution": "source.country_id",
            "stance_denominator": "classified_only_excluding_unclassified",
        },
        coverage={
            "global_article_count": global_article_n,
            "reporting_countries": kpis.get("reporting_countries", len(v1_countries)),
            "reporting_sources": kpis.get("reporting_sources", 0),
            "stance_coverage_rate": stance_cov,
            "low_sample_scopes": list(bundle.low_sample_scopes),
        },
        limitations=limitations,
        generation_status=gen_status,  # type: ignore[arg-type]
        generation_metadata={
            "report_schema_version": REPORT_PACKAGE_VERSION,
            "generator": payload.get("generator"),
            "evidence_hash": bundle.evidence_hash,
        },
    )

    val_status, val_notes = validate_report_package(pkg, payload)
    pkg.validation_status = val_status  # type: ignore[arg-type]
    pkg.validation_notes = val_notes
    return pkg


def render_daily_brief_markdown(pkg: ReportPackageContract) -> str:
    """Render concise 3-5 minute 6-Chapter Daily Intelligence Brief + Appendix in Markdown."""
    lines: list[str] = [
        f"# GNI Daily Intelligence Brief ({pkg.period.get('label', '')})",
        "",
        f"- **Report ID**: `{pkg.report_id}` · **Window**: `{pkg.period_start}` -> `{pkg.period_end}`",
        f"- **Generation Status**: `{pkg.generation_status}` · **Validation**: `{pkg.validation_status}`",
        f"- **Methodology**: `{pkg.methodology.get('methodology_version')}` (`{pkg.methodology.get('taxonomy_version')}`)",
        "",
    ]
    for sec in pkg.sections:
        lines.append(f"## {sec.title}")
        lines.append("")
        lines.append(f"_source: `{sec.source_kind}` · status: `{sec.status}`_")
        lines.append("")
        if sec.summary:
            lines.append(sec.summary)
            lines.append("")
        for f in sec.findings[:6]:
            cls_tag = f.get("classification") or "Inference"
            refs = ", ".join(
                f"{r.get('type')}:{r.get('ref_id')}"
                for r in (f.get("evidence_refs") or [])[:3]
                if isinstance(r, dict) and r.get("ref_id")
            )
            ref_suffix = f" _(refs: {refs})_" if refs else ""
            lines.append(f"- **[{cls_tag}] {f.get('title', '')}**: {f.get('conclusion', '')}{ref_suffix}")
        if sec.findings:
            lines.append("")
        if sec.limitations and sec.section_id == "appendix":
            lines.append("### Data Coverage & Limitations")
            lines.append("")
            for lim in sec.limitations[:8]:
                lines.append(f"- {lim}")
            lines.append("")
    return "\n".join(lines).strip() + "\n"


def save_daily_report_snapshot(
    session: Session,
    payload: dict[str, Any],
) -> ReportSnapshot:
    """Persist a Daily Intelligence Brief payload (including report_package) in ReportSnapshot."""
    from uuid import uuid4

    period = str(payload.get("period") or "")
    schema_version = str(
        (payload.get("report_package") or {}).get("generation_metadata", {}).get("report_schema_version")
        or payload.get("schema_version")
        or REPORT_PACKAGE_VERSION
    )
    existing = session.scalar(
        select(ReportSnapshot)
        .where(ReportSnapshot.report_type == "daily", ReportSnapshot.period == period)
        .order_by(ReportSnapshot.created_at.desc())
        .limit(1)
    )
    if existing:
        existing.payload = payload
        existing.schema_version = schema_version
        session.flush()
        return existing

    snap = ReportSnapshot(
        id=str(uuid4()),
        report_type="daily",
        period=period,
        schema_version=schema_version,
        payload=payload,
    )
    session.add(snap)
    session.flush()
    return snap


def get_daily_report_snapshot(
    session: Session,
    period: str,
) -> dict[str, Any] | None:
    """Query the saved Daily Intelligence Brief snapshot for a given YYYY-MM-DD period."""
    row = session.scalar(
        select(ReportSnapshot)
        .where(ReportSnapshot.report_type == "daily", ReportSnapshot.period == period)
        .order_by(ReportSnapshot.created_at.desc())
        .limit(1)
    )
    return dict(row.payload) if row and isinstance(row.payload, dict) else None


def regenerate_daily_report(
    session: Session,
    *,
    day: Any = None,
    run_v2_assessments: bool = True,
    assessment_tasks: list[str] | None = None,
    llm_client: JsonLLMClient | None = None,
) -> dict[str, Any]:
    """Regenerate Daily Intelligence Brief with force_analyze=True and persist ReportSnapshot."""
    from gni.reports.daily import build_daily_report

    payload = build_daily_report(
        session,
        day=day,
        analyze=False,
        force_analyze=True,
        llm_client=llm_client,
        run_v2_assessments=run_v2_assessments,
        assessment_tasks=assessment_tasks,
    )
    save_daily_report_snapshot(session, payload)
    return payload

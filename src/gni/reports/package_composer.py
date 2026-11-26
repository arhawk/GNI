"""Task 4: Unified ReportPackage Composer for Daily (6ch), Weekly (8ch), and Monthly (8ch).

Builds structured, evidence-curated, visualization-ready ReportPackageContract objects
and renders clean Markdown for all three report cadences without modifying V1.0 statistical definitions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from gni.core.contracts import (
    REPORT_PACKAGE_VERSION,
    ReportPackageContract,
    ReportSectionContract,
)
from gni.metrics.definitions import METHODOLOGY_VERSION, TAXONOMY_V1_VERSION, V1_ANALYSIS_VERSION
from gni.reports.narrative.evidence import curate_finding_evidence

WEEKLY_CHAPTER_DEFS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("chapter_1_weekly_executive", "1. Weekly Executive Assessment", ("overall_situation_assessment", "executive_analysis")),
    ("chapter_2_attention_changes", "2. Global Attention Changes", ("change_detection_assessment",)),
    ("chapter_3_event_evolution", "3. Major Event Evolution", ("event_analysis",)),
    ("chapter_4_country_comparison", "4. Cross-country Comparison", ("country_comparison", "cross_country_analysis")),
    ("chapter_5_topic_narrative_trends", "5. Topic & Narrative Trends", ("topic_analysis", "narrative_analysis", "topic_trend_analysis")),
    ("chapter_6_stance_changes", "6. Sentiment & Stance Changes", ("sentiment_stance_analysis", "stance_analysis")),
    ("chapter_7_emerging_risks", "7. Emerging Risks & Signals", ("risk_signal_assessment", "emerging_signals")),
    ("chapter_8_outlook_priorities", "8. Outlook & Next Week Priorities", ("outlook_assessment",)),
    ("appendix", "9. Data Coverage & Methodology", ()),
)

MONTHLY_CHAPTER_DEFS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("chapter_1_monthly_executive", "1. Monthly Executive Assessment", ("overall_situation_assessment", "executive_analysis")),
    ("chapter_2_attention_landscape", "2. Global Attention Landscape", ("change_detection_assessment",)),
    ("chapter_3_event_retrospective", "3. Major Event Retrospective", ("event_analysis",)),
    ("chapter_4_country_analysis", "4. Country-Level Analysis", ("country_comparison", "cross_country_analysis")),
    ("chapter_5_narrative_landscape", "5. Narrative Landscape", ("narrative_analysis",)),
    ("chapter_6_topic_structural", "6. Topic Structural Changes", ("topic_analysis", "topic_trend_analysis")),
    ("chapter_7_stance_trends", "7. Sentiment & Stance Trends", ("sentiment_stance_analysis", "stance_analysis")),
    ("chapter_8_strategic_outlook", "8. Strategic Signals & Outlook", ("risk_signal_assessment", "outlook_assessment", "emerging_signals")),
    ("appendix", "9. Methodology & Limitations", ()),
)


def extract_report_visualizations(payload: dict[str, Any]) -> dict[str, Any]:
    """Build deterministic visualization payloads strictly from V1.0 stats & event_time."""
    sections = payload.get("sections") or {}
    v1 = sections.get("v1_stats") or {}
    g = v1.get("global") or {}

    # 1. Trend line (daily_volume_trend or monthly/weekly historical_v1_stats)
    trend_series: list[dict[str, Any]] = []
    if isinstance(sections.get("daily_volume_trend"), list) and sections["daily_volume_trend"]:
        for row in sections["daily_volume_trend"]:
            if isinstance(row, dict):
                trend_series.append(
                    {
                        "label": str(row.get("day") or row.get("period") or row.get("label") or ""),
                        "article_count": int(row.get("articles") or row.get("article_count") or 0),
                    }
                )
    elif isinstance(sections.get("historical_v1_stats"), list):
        for row in sections["historical_v1_stats"]:
            if isinstance(row, dict):
                gl = (row.get("v1_stats") or {}).get("global") or {}
                cnt = row.get("article_count")
                if cnt is None:
                    cnt = gl.get("article_count") or 0
                trend_series.append(
                    {
                        "label": str(row.get("month") or row.get("label") or row.get("period") or ""),
                        "article_count": int(cnt),
                        "is_partial": bool(row.get("is_partial")),
                    }
                )

    # 2. Country horizontal bar (by source country)
    by_country = v1.get("countries") or v1.get("by_country") or []
    country_bar = [
        {
            "country_code": str(c.get("scope_id") or c.get("country_code") or c.get("country") or ""),
            "country_name": str(c.get("label_zh") or c.get("country_name") or c.get("scope_id") or c.get("country_code") or ""),
            "article_count": int(c.get("article_count") or 0),
            "positive_count": int(c.get("positive_count") or 0),
            "neutral_count": int(c.get("neutral_count") or 0),
            "negative_count": int(c.get("negative_count") or 0),
            "unclassified_count": int(c.get("unclassified_count") or 0),
            "stance_coverage_rate": c.get("stance_coverage_rate"),
        }
        for c in by_country[:12]
        if isinstance(c, dict)
    ]

    # 3. Topic distribution / delta
    by_topic = v1.get("topics") or v1.get("by_topic") or []
    prev_v1 = sections.get("v1_stats_prev") or sections.get("prev_v1_stats") or {}
    prev_topics = {
        str(t.get("scope_id") or t.get("topic") or t.get("name") or ""): int(t.get("article_count") or 0)
        for t in (prev_v1.get("topics") or prev_v1.get("by_topic") or [])
        if isinstance(t, dict)
    }
    topic_delta = [
        {
            "topic": str(t.get("label_zh") or t.get("scope_id") or t.get("topic") or t.get("name") or ""),
            "article_count": int(t.get("article_count") or 0),
            "prev_article_count": prev_topics.get(str(t.get("scope_id") or t.get("topic") or t.get("name") or ""), 0),
            "delta": int(t.get("article_count") or 0) - prev_topics.get(str(t.get("scope_id") or t.get("topic") or t.get("name") or ""), 0),
        }
        for t in by_topic[:10]
        if isinstance(t, dict)
    ]

    # 4. Stance stacked breakdown (Unclassified preserved & excluded from ratio denominator)
    stance_stacked = {
        "article_count": int(g.get("article_count") or 0),
        "positive_count": int(g.get("positive_count") or 0),
        "neutral_count": int(g.get("neutral_count") or 0),
        "negative_count": int(g.get("negative_count") or 0),
        "unclassified_count": int(g.get("unclassified_count") or 0),
        "positive_rate": g.get("positive_rate"),
        "neutral_rate": g.get("neutral_rate"),
        "negative_rate": g.get("negative_rate"),
        "stance_coverage_rate": g.get("stance_coverage_rate"),
    }

    # 5. Event timeline (strictly event_time, NEVER fabricated from published_at)
    raw_events = (
        sections.get("major_events")
        or sections.get("top_events")
        or (sections.get("events") if isinstance(sections.get("events"), list) else [])
        or []
    )
    event_timeline = [
        {
            "event_id": str(ev.get("event_id") or ev.get("id") or ""),
            "title": str(ev.get("title") or ev.get("canonical_title") or ""),
            "event_time": ev.get("event_time"),  # NULL if unknown; never substituted with published_at
            "article_count": int(ev.get("article_count") or 0),
            "countries": ev.get("countries") or [],
        }
        for ev in raw_events[:10]
        if isinstance(ev, dict)
    ]

    return {
        "trend_line": {
            "type": "trend_line",
            "title": "涉华报道量趋势",
            "series": trend_series,
            "caption": "基于信源去重文章数（Article Count）与 published_at 统计。",
        },
        "country_bar": {
            "type": "country_bar",
            "title": "国家分布（按信源国家）",
            "items": country_bar,
            "caption": "按信源所属国家聚合，包含各国立场覆盖率。",
        },
        "topic_delta": {
            "type": "topic_delta",
            "title": "议题分布与环比变化（跨议题允许重叠）",
            "items": topic_delta,
            "caption": "同一篇文章可归属多个议题，议题数之和不等于全球去重总量。",
        },
        "stance_stacked": {
            "type": "stance_stacked",
            "title": "涉华立场分布（Unclassified 不计入比例分母）",
            "data": stance_stacked,
            "caption": "正/中/负比例分母仅为已分类文章数，Unclassified 与 stance_coverage_rate 单独展示。",
        },
        "event_timeline": {
            "type": "event_timeline",
            "title": "重点事件时间线（严格使用 event_time）",
            "items": event_timeline,
            "caption": "事件时间取自 event_time；发生时间不明确时保留为空，不用 published_at 替代。",
        },
    }


def _normalize_finding(
    raw: dict[str, Any],
    *,
    curated: dict[str, list[dict[str, Any]]],
    supporting_metrics: dict[str, Any],
) -> dict[str, Any]:
    """Normalize any LLM or deterministic finding to Task 4 unified Key Finding structure."""
    title = str(raw.get("title") or raw.get("statement") or "关键发现").strip()[:160]
    summary = str(raw.get("finding_summary") or raw.get("statement") or raw.get("summary") or "").strip()
    existing_refs = [r for r in (raw.get("evidence_refs") or []) if isinstance(r, dict)]
    refs = existing_refs[:3] if existing_refs else curated["evidence_refs"]
    counter = [c for c in (raw.get("counter_evidence") or []) if isinstance(c, dict)] or curated["counter_evidence"]
    return {
        "title": title,
        "finding_summary": summary,
        "observed_change": str(raw.get("observed_change") or ""),
        "interpretation": str(raw.get("interpretation") or raw.get("reasoning") or ""),
        "why_it_matters": str(raw.get("why_it_matters") or ""),
        "evidence_refs": refs,
        "supporting_metrics": raw.get("supporting_metrics") or supporting_metrics,
        "counter_evidence": counter,
        "confidence": str(raw.get("confidence") or "medium"),
        "limitations": list(raw.get("limitations") or []),
        "watch_items": list(raw.get("watch_items") or []),
    }


def _collect_pool_articles(session: Session | None, payload: dict[str, Any]) -> list[dict[str, Any]]:
    sections = payload.get("sections") or {}
    pool: list[dict[str, Any]] = []
    for key in ("representative_articles", "top_articles", "articles"):
        items = sections.get(key)
        if isinstance(items, list):
            pool.extend([a for a in items if isinstance(a, dict)])
    for ev_key in ("major_events", "top_events"):
        for ev in sections.get(ev_key) or []:
            if isinstance(ev, dict):
                for a in (
                    ev.get("articles")
                    or ev.get("representative_articles")
                    or ev.get("sample_articles")
                    or []
                ):
                    if isinstance(a, dict):
                        pool.append({**a, "event_id": ev.get("event_id") or ev.get("id")})
    if not pool and session is not None:
        from sqlalchemy import select
        from gni.infrastructure.models import Article, Source

        p_start = payload.get("period_start")
        p_end = payload.get("period_end")
        try:
            dt_start = datetime.fromisoformat(str(p_start).replace("Z", "+00:00")) if p_start else None
            dt_end = datetime.fromisoformat(str(p_end).replace("Z", "+00:00")) if p_end else None
        except Exception:
            dt_start = dt_end = None
        if dt_start and dt_end:
            stmt = (
                select(Article, Source)
                .join(Source, Source.id == Article.source_id, isouter=True)
                .where(
                    Article.published_at >= dt_start.astimezone(timezone.utc),
                    Article.published_at < dt_end.astimezone(timezone.utc),
                    Article.china_relevance_level.in_(["core", "high", "medium"]),
                )
                .order_by(Article.published_at.desc())
                .limit(60)
            )
            for art, src in session.execute(stmt).all():
                pool.append(
                    {
                        "article_id": art.id,
                        "title": art.title,
                        "source_name": src.name if src else "Unknown",
                        "country_code": src.country_id if src else "",
                        "china_stance": "Unclassified",
                        "published_at": art.published_at.isoformat() if art.published_at else None,
                        "url": art.url,
                        "excerpt": str(getattr(art, "cleaned_text", None) or getattr(art, "content", None) or "")[:240],
                    }
                )
    return pool


def build_unified_report_package(
    session: Session | None,
    *,
    report_type: str,
    payload: dict[str, Any],
) -> ReportPackageContract:
    """Compose unified ReportPackageContract for Weekly (8ch+appendix) or Monthly (8ch+appendix)."""
    rt = report_type.lower().strip()
    chapter_defs = WEEKLY_CHAPTER_DEFS if rt == "weekly" else MONTHLY_CHAPTER_DEFS
    sections_raw = payload.get("sections") or {}
    v1 = sections_raw.get("v1_stats") or {}
    g = v1.get("global") or {}
    summary_kpis = (sections_raw.get("summary") or {}).get("kpis") or {}
    intel_tasks = (payload.get("intelligence") or {}).get("tasks") or {}
    visualizations = extract_report_visualizations(payload)
    article_pool = _collect_pool_articles(session, payload)
    curated_global = curate_finding_evidence(article_pool, max_refs=3, include_counter=True)

    # Map chapter IDs to relevant deterministic visualizations
    chapter_viz_map: dict[str, list[dict[str, Any]]] = {
        "chapter_2_attention_changes": [visualizations["trend_line"]],
        "chapter_2_attention_landscape": [visualizations["trend_line"]],
        "chapter_3_event_evolution": [visualizations["event_timeline"]],
        "chapter_3_event_retrospective": [visualizations["event_timeline"]],
        "chapter_4_country_comparison": [visualizations["country_bar"]],
        "chapter_4_country_analysis": [visualizations["country_bar"]],
        "chapter_5_topic_narrative_trends": [visualizations["topic_delta"]],
        "chapter_6_topic_structural": [visualizations["topic_delta"]],
        "chapter_6_stance_changes": [visualizations["stance_stacked"]],
        "chapter_7_stance_trends": [visualizations["stance_stacked"]],
    }

    built_sections: list[ReportSectionContract] = []
    for ch_id, ch_title, task_keys in chapter_defs:
        matched_task: dict[str, Any] | None = None
        for tk in task_keys:
            if isinstance(intel_tasks.get(tk), dict):
                matched_task = intel_tasks[tk]
                break

        raw_findings = (matched_task or {}).get("findings") or (matched_task or {}).get("key_findings") or []
        norm_findings = [
            _normalize_finding(
                f,
                curated=curated_global,
                supporting_metrics={"global_article_count": int(g.get("article_count") or 0)},
            )
            for f in raw_findings[:5]
            if isinstance(f, dict)
        ]

        # Deterministic fallback finding when LLM intelligence hasn't been triggered yet
        if not norm_findings and ch_id != "appendix":
            if ch_id.startswith("chapter_1_"):
                art_cnt = int(g.get("article_count") or summary_kpis.get("china_articles") or 0)
                delta = summary_kpis.get("delta")
                cov = g.get("stance_coverage_rate")
                norm_findings = [
                    _normalize_finding(
                        {
                            "title": f"{'本周' if rt == 'weekly' else '本月'}涉华报道总量 {art_cnt} 篇",
                            "finding_summary": (
                                f"统计窗口内共监测去重涉华报道 {art_cnt} 篇"
                                + (f"（环比变化 {delta:+d} 篇）" if isinstance(delta, int) else "")
                                + (f"，立场覆盖率 {cov * 100:.1f}%。" if isinstance(cov, (int, float)) else "。")
                            ),
                            "observed_change": f"delta={delta}" if delta is not None else "",
                            "interpretation": "该结论由 V1.0 确定性指标层生成；运行研判引擎后将补充深度归因。",
                            "confidence": "high" if art_cnt >= 5 else "low",
                        },
                        curated=curated_global,
                        supporting_metrics={"article_count": art_cnt, "delta": delta, "stance_coverage_rate": cov},
                    )
                ]

        limitations: list[str] = []
        if ch_id == "appendix":
            ws = payload.get("window_spec") or {}
            if ws.get("is_partial_period"):
                limitations.append(str(ws.get("comparison_note") or "当前为月中未完整周期，已采用同天数 MTD 公平环比。"))
            if rt == "monthly":
                hist = sections_raw.get("historical_v1_stats") or []
                months_with_data = sum(1 for row in hist if isinstance(row, dict) and int(row.get("article_count") or 0) > 0)
                if months_with_data < 6:
                    limitations.append(f"当前有效历史月度基线仅 {months_with_data} 个月（不足 6 个月），长期结构性趋势需谨慎外推。")
            limitations.append("跨议题与跨板块文章允许重叠，不得将各议题文章数直接相加替代全球去重总量。")
            limitations.append("立场比例分母仅含已分类文章（Positive/Neutral/Negative），Unclassified 独立统计并展示覆盖率。")

        built_sections.append(
            ReportSectionContract(
                section_id=ch_id,
                title=ch_title,
                summary=str((matched_task or {}).get("summary") or (matched_task or {}).get("executive_summary") or ""),
                key_findings=norm_findings,
                evidence_refs=curated_global["evidence_refs"] if ch_id in {"chapter_1_weekly_executive", "chapter_1_monthly_executive", "appendix"} else [],
                metrics=[
                    {
                        "global": g,
                        "kpis": summary_kpis,
                        "window_spec": payload.get("window_spec") or {},
                    }
                ]
                if ch_id.startswith("chapter_1_") or ch_id == "appendix"
                else [],
                visualizations=chapter_viz_map.get(ch_id, []),
                limitations=limitations,
                status="completed" if matched_task else "rule_only",
            )
        )

    period_label = str(payload.get("period") or "")
    qg = payload.get("quality_gate") or {}
    qg_status = qg.get("status")
    val_status = "failed" if qg_status == "blocked" else ("needs_review" if qg_status == "passed_with_warnings" else "passed")
    has_llm = bool((payload.get("intelligence") or {}).get("meta", {}).get("completed_tasks", 0))
    gen_status = "completed" if has_llm else ("insufficient_data" if int(g.get("article_count") or 0) == 0 else "rule_only")

    return ReportPackageContract(
        report_id=f"{rt}:{period_label}",
        report_type=rt,  # type: ignore[arg-type]
        period={
            "label": period_label,
            "start": payload.get("period_start"),
            "end": payload.get("period_end"),
            "window_mode": (payload.get("window_spec") or {}).get("window_mode"),
            "is_partial_period": bool((payload.get("window_spec") or {}).get("is_partial_period")),
        },
        period_start=payload.get("period_start"),
        period_end=payload.get("period_end"),
        generated_at=datetime.now(timezone.utc).isoformat(),
        sections=built_sections,
        evidence_refs=curated_global["evidence_refs"],
        methodology={
            "methodology_version": METHODOLOGY_VERSION,
            "taxonomy_version": TAXONOMY_V1_VERSION,
            "analysis_version": V1_ANALYSIS_VERSION,
            "package_version": REPORT_PACKAGE_VERSION,
        },
        coverage={
            "global_article_count": int(g.get("article_count") or 0),
            "stance_coverage_rate": g.get("stance_coverage_rate"),
            "countries_reporting": len(v1.get("by_country") or []),
            "quality_gate": qg,
            "window_spec": payload.get("window_spec") or {},
        },
        limitations=built_sections[-1].limitations if built_sections else [],
        generation_status=gen_status,  # type: ignore[arg-type]
        validation_status=val_status,  # type: ignore[arg-type]
        validation_notes=[str(w.get("message") or "") for w in (qg.get("warnings") or []) if isinstance(w, dict)],
        generation_metadata={
            "report_schema_version": REPORT_PACKAGE_VERSION,
            "quality_gate_status": qg_status,
        },
    )


def render_report_package_markdown(package: ReportPackageContract | dict[str, Any]) -> str:
    """Render any Daily/Weekly/Monthly ReportPackageContract to structured Markdown."""
    data = package.model_dump(mode="json") if isinstance(package, ReportPackageContract) else dict(package)
    period_obj = data.get("period")
    period_label = period_obj.get("label") if isinstance(period_obj, dict) else str(period_obj or "")
    meth = data.get("methodology") or {}
    lines: list[str] = [
        f"# GNI {str(data.get('report_type') or '').upper()} Intelligence Report — {period_label}",
        "",
        f"- **周期窗口**: `{data.get('period_start')}` → `{data.get('period_end')}`",
        f"- **方法论版本**: `{meth.get('methodology_version', METHODOLOGY_VERSION)}` / `{meth.get('taxonomy_version', TAXONOMY_V1_VERSION)}`",
        f"- **质量门禁**: `{data.get('validation_status', 'unknown')}`",
        "",
    ]
    for sec in data.get("sections") or []:
        lines.append(f"## {sec.get('title')}")
        lines.append("")
        if sec.get("summary"):
            lines.append(str(sec["summary"]))
            lines.append("")
        for idx, f in enumerate(sec.get("key_findings") or [], start=1):
            lines.append(f"### {idx}. {f.get('title') or '关键发现'}")
            if f.get("finding_summary"):
                lines.append(f"- **发现**：{f['finding_summary']}")
            if f.get("interpretation"):
                lines.append(f"- **解释**：{f['interpretation']}")
            refs = f.get("evidence_refs") or []
            if refs:
                ref_str = "；".join(
                    f"[{r.get('source_name') or '源'}/{r.get('country_code') or '-'}] {r.get('title') or ''}"
                    for r in refs[:3]
                )
                lines.append(f"- **代表证据**：{ref_str}")
            counter = f.get("counter_evidence") or []
            if counter:
                c_str = "；".join(
                    f"[{r.get('source_name') or '源'}/{r.get('china_stance')}] {r.get('title') or ''}"
                    for r in counter[:2]
                )
                lines.append(f"- **反证/对照视角**：{c_str}")
            lines.append("")
        for lim in sec.get("limitations") or []:
            lines.append(f"- *口径与局限*：{lim}")
        if sec.get("limitations"):
            lines.append("")
    return "\n".join(lines).strip() + "\n"

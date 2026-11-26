"""Comprehensive tests for GNI Report Intelligence Narrative Layer (Daily / Weekly / Monthly)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from gni.analysis.deepseek import LLMCallResult
from gni.core.config import Settings
from gni.infrastructure.models import (
    Article,
    ArticleAnalysis,
    Base,
    Country,
    Event,
    EventArticle,
    Organization,
    ReportNarrativeTask,
    Source,
)
from gni.reports.daily import build_daily_report, render_daily_markdown
from gni.reports.monthly import build_monthly_report
from gni.reports.narrative.evidence import prepare_evidence_bundle
from gni.reports.narrative.prompts import get_task_prompt_spec, list_report_tasks
from gni.reports.narrative.schemas import EvidenceRef, Finding, NarrativeTaskOutput, OutlookSignal, TopicTrendItem
from gni.reports.narrative.validator import validate_task_output
from gni.reports.weekly import build_weekly_report


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _seed_corpus(session: Session) -> dict[str, Any]:
    """Seed multi-country, multi-stance V1.0 corpus spanning today, last week, and last month."""
    now = datetime(2026, 11, 26, 6, 0, tzinfo=timezone.utc)
    for code, name in [("US", "United States"), ("DE", "Germany"), ("RU", "Russia")]:
        session.add(Country(id=code, code=code, name=name))
        session.add(Organization(id=f"org_{code.lower()}", country_id=code, name=f"Org {code}"))
        session.add(
            Source(
                id=f"src_{code.lower()}",
                organization_id=f"org_{code.lower()}",
                country_id=code,
                name=f"Media {code}",
                source_type="news_agency",
                active_status="active",
                feed_scope="INTERNATIONAL_NEWS",
            )
        )

    articles_info: list[dict[str, Any]] = [
        # Today (2026-11-26) — 4 articles across US/DE/RU with Positive/Neutral/Negative
        {
            "id": "art-us-neg-1",
            "src": "src_us",
            "title": "US tightens semiconductor export controls targeting China AI chips",
            "url": "https://example.us/semi-controls-1",
            "pub": now - timedelta(hours=2),
            "stance": "Negative",
            "topics": ["tech_competition", "trade_tariffs"],
            "frame": "security_threat",
            "quote": "Officials warned China's AI chip acquisition poses national security risks.",
        },
        {
            "id": "art-de-neu-1",
            "src": "src_de",
            "title": "German industry weighs China semiconductor supply chain adjustments",
            "url": "https://example.de/semi-supply-1",
            "pub": now - timedelta(hours=1),
            "stance": "Neutral",
            "topics": ["tech_competition", "supply_chain"],
            "frame": "economic_pragmatism",
            "quote": "German firms called for balanced dialogue on semiconductor supply chains.",
        },
        {
            "id": "art-ru-pos-1",
            "src": "src_ru",
            "title": "Russia and China expand joint clean tech and industrial cooperation",
            "url": "https://example.ru/clean-tech-1",
            "pub": now - timedelta(hours=3),
            "stance": "Positive",
            "topics": ["tech_competition", "energy_climate"],
            "frame": "cooperation",
            "quote": "Both sides praised expanding industrial and clean-tech collaboration.",
        },
        {
            "id": "art-us-neg-2",
            "src": "src_us",
            "title": "Washington debates new tariffs on Chinese electric vehicles",
            "url": "https://example.us/ev-tariffs-2",
            "pub": now - timedelta(hours=4),
            "stance": "Negative",
            "topics": ["trade_tariffs"],
            "frame": "economic_rivalry",
            "quote": "Lawmakers argued Chinese EV subsidies undercut domestic manufacturers.",
        },
        # Previous week (2026-11-16) — 2 articles
        {
            "id": "art-us-prevw-1",
            "src": "src_us",
            "title": "US and China hold preliminary trade talks",
            "url": "https://example.us/prev-week-1",
            "pub": now - timedelta(days=10),
            "stance": "Neutral",
            "topics": ["trade_tariffs"],
            "frame": "diplomatic_engagement",
            "quote": "Negotiators met to discuss tariff frameworks.",
        },
        {
            "id": "art-de-prevw-2",
            "src": "src_de",
            "title": "EU reviews clean energy imports from China",
            "url": "https://example.de/prev-week-2",
            "pub": now - timedelta(days=9),
            "stance": "Neutral",
            "topics": ["energy_climate"],
            "frame": "economic_pragmatism",
            "quote": "European regulators assessed solar and battery supply chains.",
        },
        # Previous month (2026-10-15) — 1 article
        {
            "id": "art-de-prevm-1",
            "src": "src_de",
            "title": "Germany publishes October China trade review",
            "url": "https://example.de/prev-month-1",
            "pub": datetime(2026, 10, 15, 8, 0, tzinfo=timezone.utc),
            "stance": "Neutral",
            "topics": ["trade_tariffs"],
            "frame": "economic_pragmatism",
            "quote": "Trade ministry released bilateral trade figures with China.",
        },
    ]

    for item in articles_info:
        session.add(
            Article(
                id=item["id"],
                source_id=item["src"],
                title=item["title"],
                url=item["url"],
                canonical_url=item["url"],
                content_clean=item["quote"] + " Extended China-related reporting body.",
                published_at=item["pub"],
                first_seen_at=item["pub"] + timedelta(minutes=15),
                processing_status="done",
                analysis_status="completed",
                china_relevance_level="core",
                china_relevance_weight=1.0,
                exclude_from_metrics=False,
            )
        )
        session.add(
            ArticleAnalysis(
                id=str(uuid4()),
                article_id=item["id"],
                provider="deepseek",
                model_name="deepseek-chat",
                prompt_version="deepseek_analyze_v1.0",
                schema_version="article_analysis_v1.0",
                taxonomy_version="taxonomy_v1.0",
                analysis_status="completed",
                structured_result={
                    "schema_version": "article_analysis_v1.0",
                    "taxonomy_version": "taxonomy_v1.0",
                    "topics_v1": item["topics"],
                    "topics": {"primary": item["topics"][0]},
                    "framing": {"primary": item["frame"]},
                    "sentiment": {"label": item["stance"].lower(), "score": 0.0},
                    "china_stance": {
                        "stance_label": item["stance"],
                        "stance_confidence": 0.85,
                        "stance_evidence": [{"quote": item["quote"]}],
                        "analysis_status": "classified",
                    },
                },
            )
        )

    ev_id = "ev-semi-controls-001"
    session.add(
        Event(
            id=ev_id,
            title="US Semiconductor Export Controls on China AI Chips",
            summary="US tightened AI chip export controls while Germany and Russia responded differently.",
            event_type="tech_competition",
            status="active",
            importance_score=0.88,
            actor_key="us_gov",
            action_key="export_control",
            object_key="china_ai_chips",
            event_time=now - timedelta(hours=5),
            created_at=now - timedelta(hours=2),
            window_start=now - timedelta(hours=5),
            window_end=now,
        )
    )
    for aid in ("art-us-neg-1", "art-de-neu-1", "art-ru-pos-1"):
        session.add(EventArticle(id=str(uuid4()), event_id=ev_id, article_id=aid, relation="covers"))

    session.commit()
    return {"event_id": ev_id, "day": "2026-11-26", "month": "2026-11"}


class FakeJsonLLMClient:
    """Deterministic stub implementing JsonLLMClient with call tracking & failure injection."""

    def __init__(self, *, event_id: str, fail_tasks: set[str] | None = None) -> None:
        self.event_id = event_id
        self.fail_tasks = set(fail_tasks or set())
        self.calls: list[dict[str, Any]] = []

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
    ) -> LLMCallResult:
        # Extract task_type from user_prompt header
        task_type = "executive_analysis"
        report_type = "daily"
        for tok in user_prompt.splitlines()[0].split():
            if tok.startswith("task_type="):
                task_type = tok.split("=", 1)[1]
            elif tok.startswith("report_type="):
                report_type = tok.split("=", 1)[1]

        self.calls.append(
            {
                "report_type": report_type,
                "task_type": task_type,
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
            }
        )
        if task_type in self.fail_tasks:
            raise RuntimeError(f"Simulated LLM timeout on {task_type}")

        payload = self._build_output(report_type, task_type)
        return LLMCallResult(
            parsed=payload,
            raw_text="{}",
            provider="fake-deepseek",
            model_version=model or "deepseek-chat",
            prompt_tokens=300,
            completion_tokens=200,
            total_tokens=500,
            latency_ms=120,
            estimated_cost_usd=0.0001,
        )

    def _build_output(self, report_type: str, task_type: str) -> dict[str, Any]:
        if task_type == "executive_analysis":
            return {
                "summary": f"{report_type} 监测样本中，科技竞争与贸易议题成为核心驱动。",
                "findings": [
                    {
                        "title": "芯片管制议题驱动多国媒体关注",
                        "conclusion": "美德俄三国监测媒体围绕芯片出口管制与产业合作同步报道。",
                        "classification": "Fact",
                        "evidence_refs": [
                            {"type": "event", "ref_id": self.event_id, "label": "芯片出口管制事件"},
                            {"type": "article", "ref_id": "art-us-neg-1", "label": "US 报道"},
                            {"type": "metric", "ref_id": "metric:GLOBAL:ALL", "label": "全球总量"},
                        ],
                        "reasoning": "基于事件关联文章及 V1.0 确定性统计。",
                        "confidence": "medium",
                        "limitations": ["当前样本仅覆盖已接入媒体"],
                    },
                    {
                        "title": "后续或引发供应链再平衡讨论",
                        "conclusion": "若出口管制细则落地，可能带动欧洲产业链媒体持续跟进。",
                        "classification": "Hypothesis",
                        "evidence_refs": [{"type": "article", "ref_id": "art-de-neu-1", "label": "DE 报道"}],
                        "reasoning": "德国媒体已开始评估供应链调整影响。",
                        "confidence": "low",
                        "limitations": ["尚待后续官方细则验证"],
                    },
                ],
                "important_changes": ["科技竞争与关税议题成为关注焦点"],
                "main_drivers": ["US Semiconductor Export Controls on China AI Chips"],
                "uncertainties": ["当前历史窗口仍较短，需持续观察"],
                "follow_up_questions": ["欧洲政策层是否发布配套回应？"],
            }
        if task_type == "event_analysis":
            return {
                "summary": "芯片出口管制事件引发美德俄三国差异化报道。",
                "event_interpretations": [
                    {
                        "event_id": self.event_id,
                        "title": "US Semiconductor Export Controls on China AI Chips",
                        "background": "围绕高端芯片出口管制与全球产业链分工。",
                        "what_happened": "美方收紧对华 AI 芯片出口限制，德国关注供应链，俄媒突出合作。",
                        "event_actual_changes": "美方推动新一轮 AI 芯片限制措施。",
                        "coverage_attention_changes": "美德俄监测源在同一窗口内同步跟进。",
                        "country_followup_timing": "俄美德媒体先后发布相关报道。",
                        "country_differences": "美媒偏安全框架，德媒偏经济务实，俄媒偏合作框架。",
                        "media_viewpoints": ["关注国家安全风险", "呼吁产业链平衡对话"],
                        "current_status": "active",
                        "why_it_matters": "直接影响半导体供应链与科技竞争叙事走向。",
                        "what_to_monitor": ["管制清单细则", "欧洲企业表态"],
                        "evidence_refs": [
                            {"type": "event", "ref_id": self.event_id},
                            {"type": "article", "ref_id": "art-us-neg-1"},
                            {"type": "article", "ref_id": "art-de-neu-1"},
                        ],
                        "confidence": "medium",
                        "limitations": ["仅代表已接入样本"],
                    }
                ],
                "findings": [],
                "uncertainties": [],
            }
        if task_type == "topic_trend_analysis":
            return {
                "summary": "科技竞争议题关注度上升，但与立场变化分列评估。",
                "topic_trends": [
                    {
                        "topic_id": "tech_competition",
                        "topic_label": "科技竞争",
                        "attention_change": "本周期报道量较上周期上升。",
                        "stance_change": "立场分布呈现美负、德中、俄正分化，并未出现单一方向恶化。",
                        "topic_structure_change": "从传统贸易向半导体与清洁技术交叉延展。",
                        "drivers": ["US Semiconductor Export Controls on China AI Chips"],
                        "persistence": "ongoing",
                        "evidence_refs": [
                            {"type": "metric", "ref_id": "metric:TOPIC:tech_competition"},
                            {"type": "article", "ref_id": "art-us-neg-1"},
                        ],
                        "confidence": "medium",
                        "limitations": ["部分历史周期样本偏少"],
                    }
                ],
                "findings": [],
                "uncertainties": [],
            }
        if task_type == "cross_country_analysis":
            return {
                "summary": "美德俄监测媒体在芯片议题上呈现明显叙事分化。",
                "cross_country": [
                    {
                        "subject_type": "event",
                        "subject_id": self.event_id,
                        "subject_label": "AI 芯片出口管制",
                        "common_focus": "均聚焦对华芯片政策与供应链影响。",
                        "country_frames": [
                            {
                                "country_id": "US",
                                "main_frame": "国家安全与技术竞争框架",
                                "unique_angle": "强调 AI 芯片安全风险",
                                "sample_note": "基于 US 监测媒体代表文章",
                                "evidence_refs": [{"type": "article", "ref_id": "art-us-neg-1"}],
                            },
                            {
                                "country_id": "DE",
                                "main_frame": "供应链务实平衡框架",
                                "unique_angle": "关注德国工业界承受力",
                                "sample_note": "样本偏少，不外推",
                                "evidence_refs": [{"type": "article", "ref_id": "art-de-neu-1"}],
                            },
                        ],
                        "major_differences": "美媒强调安全限制，德媒强调供应链稳定，俄媒强调技术合作。",
                        "emerging_or_shifting": "产业链务实声音在欧洲媒体中显现。",
                        "insufficient_sample_countries": ["DE", "RU"],
                        "evidence_refs": [
                            {"type": "article", "ref_id": "art-us-neg-1"},
                            {"type": "article", "ref_id": "art-de-neu-1"},
                            {"type": "article", "ref_id": "art-ru-pos-1"},
                        ],
                        "confidence": "medium",
                    }
                ],
                "findings": [],
                "uncertainties": [],
            }
        if task_type == "stance_analysis":
            return {
                "summary": "全球样本中负面与中性并存，需结合样本量与覆盖率解读。",
                "stance_analyses": [
                    {
                        "scope_type": "GLOBAL",
                        "scope_id": "ALL",
                        "scope_label": "全球涉华总量",
                        "rate_vs_count_note": "比例变化受总篇数基数影响，须与绝对篇数同步对照。",
                        "drivers": ["芯片出口管制报道增加负面样本"],
                        "coverage_limitation": "分国样本量较小，不构成国家官方立场推断。",
                        "evidence_refs": [
                            {"type": "metric", "ref_id": "metric:GLOBAL:ALL"},
                            {"type": "article", "ref_id": "art-us-neg-1"},
                        ],
                        "confidence": "medium",
                    }
                ],
                "findings": [],
                "uncertainties": [],
            }
        # emerging_signals
        return {
            "summary": "建议持续跟踪芯片出口管制细则与欧洲供应链回应。",
            "outlook_signals": [
                {
                    "signal": "若美方公布芯片管制执行细则，可能引发欧洲及亚太媒体新一轮跟进。",
                    "evidence_refs": [
                        {"type": "event", "ref_id": self.event_id},
                        {"type": "article", "ref_id": "art-us-neg-1"},
                    ],
                    "reasoning": "美德媒体已从不同角度切入芯片供应链议题。",
                    "confidence": "medium",
                    "what_to_monitor": ["出口管制清单更新", "德企公开表态"],
                    "potential_trigger": "商务部或欧盟发布正式政策文件",
                    "uncertainty": "政策落地节奏存在不确定性，需视后续公开声明验证。",
                }
            ],
            "findings": [],
            "uncertainties": ["尚不能确认是否演变为长期趋势"],
            "follow_up_questions": ["是否出现跨国联合声明？"],
        }


def test_prompts_differentiated_across_daily_weekly_monthly() -> None:
    """Acceptance #2: Daily, Weekly, Monthly use distinct task lists and versioned prompts."""
    d_specs = list_report_tasks("daily")
    w_specs = list_report_tasks("weekly")
    m_specs = list_report_tasks("monthly")

    assert [s.task_type for s in d_specs] == ["executive_analysis", "event_analysis", "emerging_signals"]
    assert len(w_specs) == 6
    assert len(m_specs) == 6

    all_versions = [s.prompt_version for s in d_specs + w_specs + m_specs]
    assert len(all_versions) == len(set(all_versions)), "Prompt versions must be unique per report+task"

    # Executive prompts must differ meaningfully across Daily / Weekly / Monthly
    d_exec = get_task_prompt_spec("daily", "executive_analysis")
    w_exec = get_task_prompt_spec("weekly", "executive_analysis")
    m_exec = get_task_prompt_spec("monthly", "executive_analysis")
    assert d_exec.task_instructions != w_exec.task_instructions
    assert w_exec.task_instructions != m_exec.task_instructions
    assert d_exec.system_prompt != m_exec.system_prompt


def test_three_layer_validator_numeric_evidence_reasoning(db_session: Session) -> None:
    """Acceptance #4, #8, #9: Numeric, Evidence, and Reasoning validation enforce strict guardrails."""
    meta = _seed_corpus(db_session)
    report = build_daily_report(db_session, day=meta["day"], analyze=False)
    bundle = prepare_evidence_bundle(db_session, report_type="daily", payload=report)

    bad_output = NarrativeTaskOutput(
        task_type="executive_analysis",
        report_type="daily",
        summary="今日样本中报道量增长说明对华立场恶化，且出现 93.7% 暴涨。",
        findings=[
            # 1. Fact with NO valid evidence (forged article_id + forged URL) -> must downgrade to Hypothesis
            Finding(
                title="无证据事实",
                conclusion="某国全面转向。",
                classification="Fact",
                evidence_refs=[
                    EvidenceRef(type="article", ref_id="fake-article-999", url="https://evil.fake/1"),
                ],
                confidence="high",
            ),
            # 2. Composite score violation -> must be dropped
            Finding(
                title="违规综合评分",
                conclusion="本月对华总分为 72 分，综合舆情指数下降。",
                classification="Inference",
                evidence_refs=[EvidenceRef(type="metric", ref_id="metric:GLOBAL:ALL")],
            ),
            # 3. Media written as official stance + invented number -> flagged & downgraded
            Finding(
                title="媒体当官方立场",
                conclusion="美媒报道表明国家官方立场是全面对抗，涨幅 88.4%。",
                classification="Fact",
                evidence_refs=[EvidenceRef(type="article", ref_id="art-us-neg-1")],
            ),
        ],
        topic_trends=[
            TopicTrendItem(
                topic_id="tech_competition",
                topic_label="科技竞争",
                attention_change="报道量上升",
                stance_change="保持分化",
                persistence="ongoing",
                evidence_refs=[EvidenceRef(type="metric", ref_id="metric:TOPIC:tech_competition")],
            )
        ],
        outlook_signals=[
            OutlookSignal(
                signal="冲突必然发生并已成定局。",
                evidence_refs=[EvidenceRef(type="event", ref_id=meta["event_id"])],
                reasoning="报道增加。",
                confidence="high",
            )
        ],
    )

    validated, vreport = validate_task_output(bad_output, bundle)
    assert vreport["ok"] is False
    assert vreport["needs_review"] is True
    assert vreport["dropped_count"] >= 1  # composite_score_claim dropped
    assert vreport["downgraded_count"] >= 2
    assert any("93.7%" in x or "88.4%" in x for x in vreport["numeric_issues"])
    assert any("fake-article-999" in x for x in vreport["evidence_issues"])
    assert any("media_as_official_stance" in x for x in vreport["reasoning_issues"])
    assert any("volume_as_attitude" in x for x in vreport["reasoning_issues"])
    assert any("outlook_non_conditional" in x for x in vreport["reasoning_issues"])

    # No remaining Fact may lack evidence_refs
    for f in validated.findings:
        if f.classification == "Fact":
            assert len(f.evidence_refs) > 0
    # Valid article ref should have DB-backed URL injected, never forged URL
    f_valid_art = next(f for f in validated.findings if f.title == "媒体当官方立场")
    assert f_valid_art.evidence_refs[0].url == "https://example.us/semi-controls-1"
    assert f_valid_art.classification == "Inference"  # downgraded from Fact
    # Outlook signal gets conditional uncertainty appended
    assert "条件性" in validated.outlook_signals[0].uncertainty


def test_evidence_ref_string_shorthand_coercion(db_session: Session) -> None:
    """Verify LLM string-shorthand evidence_refs coerce cleanly and validate against DB allowlists."""
    meta = _seed_corpus(db_session)
    report = build_daily_report(db_session, day=meta["day"], analyze=False)
    bundle = prepare_evidence_bundle(db_session, report_type="daily", payload=report)

    coerced = NarrativeTaskOutput.model_validate(
        {
            "task_type": "executive_analysis",
            "report_type": "daily",
            "summary": "简写证据引用测试。",
            "findings": [
                {
                    "title": "简写引用自动规范化",
                    "conclusion": "芯片管制议题驱动多国监测媒体报道。",
                    "classification": "Fact",
                    "evidence_refs": [
                        "metric:GLOBAL:ALL",
                        "article:art-us-neg-1",
                        meta["event_id"],  # bare event id without prefix
                    ],
                }
            ],
        }
    )
    validated, vreport = validate_task_output(coerced, bundle)
    assert vreport["evidence_issues"] == []
    refs = validated.findings[0].evidence_refs
    assert [(r.type, r.ref_id) for r in refs] == [
        ("metric", "metric:GLOBAL:ALL"),
        ("article", "art-us-neg-1"),
        ("event", meta["event_id"]),
    ]
    assert refs[1].url == "https://example.us/semi-controls-1"


def test_daily_weekly_monthly_e2e_caching_retry_and_fallback(db_session: Session) -> None:
    """Acceptance #1, #3, #5, #6, #7, #10: E2E Daily/Weekly/Monthly, cache reuse, partial retry, fallback."""
    meta = _seed_corpus(db_session)
    ev_id = meta["event_id"]

    # 1. Graceful fallback when LLM key is missing (no crash, deterministic report valid)
    no_key_settings = Settings(llm_api_key="", database_url="sqlite:///:memory:")
    daily_fallback = build_daily_report(db_session, day=meta["day"], analyze=False)
    assert daily_fallback["intelligence"]["status"] == "rule_only"
    assert daily_fallback["validation"]["ok"] is True

    # Run with missing key via runner directly -> fallback_reason recorded, report still valid
    from gni.reports.narrative.runner import run_report_intelligence

    fb = run_report_intelligence(
        db_session,
        report_type="daily",
        period=daily_fallback["period"],
        payload=daily_fallback,
        settings=no_key_settings,
    )
    assert fb["status"] == "failed"
    assert "fallback" in (fb.get("fallback_reason") or "").lower()

    # 2. Partial failure + selective retry + cache reuse on Daily
    partial_client = FakeJsonLLMClient(event_id=ev_id, fail_tasks={"event_analysis"})
    daily_partial = build_daily_report(
        db_session,
        day=meta["day"],
        analyze=True,
        force_analyze=True,
        llm_client=partial_client,
    )
    assert daily_partial["intelligence"]["status"] == "partial"
    assert daily_partial["intelligence"]["meta"]["completed_tasks"] == 2
    assert daily_partial["intelligence"]["meta"]["failed_tasks"] == 1
    assert len(partial_client.calls) == 3

    # Retry ONLY the failed task -> completed_tasks becomes 3/3, only 1 LLM call made!
    retry_client = FakeJsonLLMClient(event_id=ev_id)
    daily_complete = build_daily_report(
        db_session,
        day=meta["day"],
        analyze=True,
        analyze_tasks=["event_analysis"],
        llm_client=retry_client,
    )
    assert len(retry_client.calls) == 1
    assert retry_client.calls[0]["task_type"] == "event_analysis"
    assert daily_complete["intelligence"]["status"] == "completed"
    assert daily_complete["intelligence"]["meta"]["completed_tasks"] == 3
    assert daily_complete["generator"] == "rule_brief_v4+llm_intelligence"
    assert daily_complete["validation"]["ok"] is True

    # Cache hit on subsequent analyze=True (force=False): 0 LLM calls!
    cache_probe = FakeJsonLLMClient(event_id=ev_id)
    daily_cached = build_daily_report(
        db_session, day=meta["day"], analyze=True, force_analyze=False, llm_client=cache_probe
    )
    assert len(cache_probe.calls) == 0
    assert daily_cached["intelligence"]["status"] == "completed"

    # Markdown renders structured intelligence & evidence refs
    md = render_daily_markdown(daily_cached)
    assert "Intelligence Narrative Analysis" in md
    assert ev_id in md

    # 3. Weekly report E2E (6 tasks,本周 vs 上周 + 跨国叙事比较)
    weekly_client = FakeJsonLLMClient(event_id=ev_id)
    weekly = build_weekly_report(
        db_session,
        end_day=meta["day"],
        analyze=True,
        llm_client=weekly_client,
    )
    assert len(weekly_client.calls) == 6
    assert weekly["intelligence"]["meta"]["completed_tasks"] == 6
    assert weekly["validation"]["ok"] is True
    assert "cross_country_analysis" in weekly["intelligence"]["tasks"]
    assert "topic_trend_analysis" in weekly["intelligence"]["tasks"]
    assert weekly["sections"]["summary"]["kpis"]["china_articles"] == 4
    assert weekly["sections"]["summary"]["kpis"]["prev_week_articles"] == 2

    # 4. Monthly report E2E (6 tasks, 6-month article-level history, honest missing_months)
    monthly_client = FakeJsonLLMClient(event_id=ev_id)
    monthly = build_monthly_report(
        db_session,
        month=meta["month"],
        analyze=True,
        llm_client=monthly_client,
    )
    assert len(monthly_client.calls) == 6
    assert monthly["validation"]["ok"] is True
    hist = monthly["sections"]["historical_v1_stats"]
    assert len(hist) == 6
    # 2026-10 has 1 article, 2026-11 has 6 articles, earlier 4 months have 0
    by_m = {h["month"]: h["article_count"] for h in hist}
    assert by_m["2026-11"] == 6
    assert by_m["2026-10"] == 1
    assert len(monthly["sections"]["quality"]["missing_months"]) == 4
    assert len(monthly["sections"]["country_profiles"]) == 3

    # Verify DB persistence in report_narrative_tasks
    stored_count = db_session.query(ReportNarrativeTask).count()
    assert stored_count == 3 + 6 + 6


def test_api_reports_get_and_analyze_route(tmp_path, monkeypatch) -> None:
    """Acceptance #10 & API cache-first + explicit analyze endpoint verification."""
    from fastapi.testclient import TestClient

    from gni.api.app import app
    from gni.core.config import get_settings
    from gni.infrastructure.db import ensure_schema, reset_engine, session_scope

    db_file = tmp_path / "api_narrative_test.db"
    monkeypatch.setenv("GNI_DATABASE_URL", f"sqlite:///{db_file}")
    monkeypatch.setenv("GNI_LLM_API_KEY", "")
    get_settings.cache_clear()
    reset_engine()
    ensure_schema()

    try:
        with session_scope() as s:
            meta = _seed_corpus(s)

        client = TestClient(app)
        # Cache-first GET returns fast rule report with intelligence.status == rule_only
        r_daily = client.get(f"/api/reports/daily?date={meta['day']}")
        assert r_daily.status_code == 200
        d_json = r_daily.json()
        assert d_json["schema_version"] == "daily_report_schema_v4"
        assert d_json["intelligence"]["status"] == "rule_only"
        assert d_json["validation"]["ok"] is True

        r_weekly = client.get(f"/api/reports/weekly?end={meta['day']}")
        assert r_weekly.status_code == 200
        assert r_weekly.json()["intelligence"]["status"] == "rule_only"
        assert r_weekly.json()["validation"]["ok"] is True

        r_monthly = client.get(f"/api/reports/monthly?month={meta['month']}")
        assert r_monthly.status_code == 200
        assert r_monthly.json()["intelligence"]["status"] == "rule_only"
        assert r_monthly.json()["validation"]["ok"] is True

        # Explicit POST /analyze without API key degrades gracefully without 500
        r_post = client.post("/api/reports/daily/analyze", json={"period": meta["day"]})
        assert r_post.status_code == 200
        post_json = r_post.json()
        assert post_json["intelligence"]["status"] == "failed"
        assert post_json["validation"]["ok"] is True
    finally:
        reset_engine()
        get_settings.cache_clear()


def test_evidence_enrichment_safe_trim_and_extended_validator(db_session: Session) -> None:
    """Verify Issue 2/3/5/8 fixes: non-risk event inclusion, counter_examples, safe JSON trim, extended validator, budget, markdown."""
    import json

    from gni.analysis.budget import llm_allowed, snapshot_budget
    from gni.reports.monthly import render_monthly_markdown
    from gni.reports.narrative.runner import _build_user_prompt
    from gni.reports.narrative.schemas import CrossCountryItem
    from gni.reports.weekly import render_weekly_markdown

    meta = _seed_corpus(db_session)
    report = build_daily_report(db_session, day=meta["day"], analyze=False)
    bundle = prepare_evidence_bundle(db_session, report_type="daily", payload=report)

    # 1. Event evidence has timeline, no rule signal score in summary, and article cards have media_type/feed_scope
    assert len(bundle.events) >= 1
    ev0 = bundle.events[0]
    assert "对华信号" not in (ev0.get("summary") or "")
    assert isinstance(ev0.get("timeline"), list)
    assert len(bundle.articles) >= 1
    assert "media_type" in bundle.articles[0]
    assert "feed_scope" in bundle.articles[0]
    # Counter-examples extracted (contradicting dominant stance)
    assert len(bundle.counter_examples) >= 1
    exec_slice = bundle.for_task("executive_analysis")
    assert "counter_examples" in exec_slice

    # 2. _build_user_prompt NEVER produces invalid truncated JSON even under tight max_chars
    spec = get_task_prompt_spec("daily", "executive_analysis")
    tight_prompt = _build_user_prompt(spec, bundle, max_chars=1800)
    ev_json_part = tight_prompt.split("EVIDENCE JSON:\n", 1)[1]
    parsed_ev = json.loads(ev_json_part)
    assert isinstance(parsed_ev, dict)
    assert "statistical" in parsed_ev

    # 3. Extended validator catches ungrounded numbers in important_changes & cross_country + empty evidence_refs
    bad_ext = NarrativeTaskOutput(
        task_type="cross_country_analysis",
        report_type="weekly",
        summary="跨国比较测试。",
        important_changes=["本周暴涨 91.3% 创历史新高"],
        cross_country=[
            CrossCountryItem(
                subject_type="topic",
                subject_id="tech_competition",
                subject_label="科技竞争",
                common_focus="各国关注度上升 77.7%。",
                evidence_refs=[],
            )
        ],
    )
    validated_ext, vrep = validate_task_output(bad_ext, bundle)
    assert vrep["ok"] is False
    assert any("91.3%" in x for x in vrep["numeric_issues"])
    assert any("77.7%" in x for x in vrep["numeric_issues"])
    assert validated_ext.cross_country[0].needs_review is True

    # 4. Budget: report LLM tasks ignore daily_article_limit & track ReportNarrativeTask cost
    cfg = Settings(daily_article_limit=0, daily_llm_budget_usd=5.0)
    snap = snapshot_budget(db_session, cfg)
    assert llm_allowed(snap, estimated_cost_usd=0.01, ignore_article_limit=False) is False
    assert llm_allowed(snap, estimated_cost_usd=0.01, ignore_article_limit=True) is True

    # 5. Weekly & Monthly Markdown renderers work cleanly
    weekly = build_weekly_report(db_session, end_day=meta["day"], analyze=False)
    monthly = build_monthly_report(db_session, month=meta["month"], analyze=False)
    assert "GNI Weekly Intelligence Report" in render_weekly_markdown(weekly)
    assert "GNI Monthly Strategic Review" in render_monthly_markdown(monthly)



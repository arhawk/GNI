"""Phase 5 tests: Unified Evidence Package, 9-Task Assessment Engine, Validator & Boundary Cases."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from gni.analysis.deepseek import LLMCallResult
from gni.analysis.service import analyze_article
from gni.core.contracts import AssessmentResultContract, EvidencePackageContract
from gni.events.narratives import ArticleNarrativeInput, cluster_narratives, persist_event_narratives
from gni.infrastructure.models import (
    Article,
    ArticleVersion,
    Base,
    Country,
    Event,
    EventArticle,
    Organization,
    ReportNarrativeTask,
    Source,
)
from gni.reports.daily import build_daily_report
from gni.reports.narrative.assessment import (
    CANONICAL_ASSESSMENT_TASKS,
    list_assessment_tasks,
    run_assessment_suite,
    run_assessment_task,
)
from gni.reports.narrative.evidence import build_task_evidence_package
from gni.reports.narrative.assessment_validator import NarrativeTaskOutput, validate_task_output


@pytest.fixture
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with SessionLocal() as session:
        yield session


def _seed_monitoring_corpus(session: Session) -> dict[str, Any]:
    """Seed a multi-country, multi-topic, mixed-stance + quoted-actor + NULL event_time corpus."""
    for cid, name in [("US", "United States"), ("GB", "United Kingdom"), ("SG", "Singapore")]:
        session.add(Country(id=cid, code=cid, name=name))
        session.add(Organization(id=f"org_{cid.lower()}", country_id=cid, name=f"{cid} Media Org"))
        session.add(
            Source(
                id=f"src_{cid.lower()}",
                organization_id=f"org_{cid.lower()}",
                country_id=cid,
                name=f"{cid} Wire",
                source_type="mainstream_independent",
                active_status="active",
                language="en",
            )
        )
    session.flush()

    day_str = "2026-11-26"
    pub_base = datetime(2026, 11, 26, 6, 0, tzinfo=timezone.utc)
    specs = [
        (
            "src_us",
            "Washington imposes stricter semiconductor export controls on China",
            (
                "Washington announced stricter semiconductor export controls targeting China chipmakers in Beijing.\n\n"
                "U.S. officials warned of national security threat and imposed tough sanctions on advanced chips."
            ),
        ),
        (
            "src_gb",
            "London reviews China electric vehicle tariffs and semiconductor supply chains",
            (
                "British analysts noted that China's semiconductor supply chains and electric vehicle exports draw mixed reactions.\n\n"
                "However, trade groups refuted claims of immediate disruption and praised breakthrough green cooperation."
            ),
        ),
        (
            "src_sg",
            "Regional official comments on China semiconductor partnership",
            (
                "A regional minister said in a statement that \"China brings strong cooperation and breakthrough growth.\"\n\n"
                "According to officials who told reporters, \"Beijing remains a constructive trade partner.\""
            ),
        ),
    ]
    aids: list[str] = []
    for idx, (sid, title, body) in enumerate(specs):
        art = Article(
            id=str(uuid4()),
            source_id=sid,
            title=title,
            url=f"https://example.test/{idx}/{uuid4()}",
            content_original=body,
            content_clean=body,
            language="en",
            published_at=pub_base.replace(hour=6 + idx),
            first_seen_at=pub_base.replace(hour=6 + idx),
            quality_status="ok",
            processing_status="done",
            analysis_status="pending",
        )
        session.add(art)
        ver = ArticleVersion(
            id=str(uuid4()),
            article_id=art.id,
            version_no=1,
            content_clean=body,
            char_count=len(body),
            quality_status="ok",
        )
        session.add(ver)
        session.flush()
        analyze_article(session, art, provider="heuristic", allow_llm=False)
        session.flush()
        aids.append(art.id)

    # Seed Event with event_time=None (must never be substituted with published_at)
    ev = Event(
        id=str(uuid4()),
        title="US tightens semiconductor export controls on China",
        summary="Cross-country coverage of semiconductor export controls.",
        event_time=None,
        status="proto",
        importance_score=0.82,
    )
    session.add(ev)
    session.flush()
    for aid in aids:
        session.add(EventArticle(id=str(uuid4()), event_id=ev.id, article_id=aid, relation="covers"))

    # Persist NarrativeCluster with supporting & counter evidence
    clusters = cluster_narratives(
        [
            ArticleNarrativeInput(
                article_id=aids[0],
                country_id="US",
                published_at=pub_base,
                frame="security_threat",
                claim="Semiconductor export controls curb strategic chip risks from China",
                attribution="support",
                tone="negative",
                quote="U.S. officials warned of national security threat and imposed tough sanctions.",
            ),
            ArticleNarrativeInput(
                article_id=aids[1],
                country_id="GB",
                published_at=pub_base.replace(hour=7),
                frame="security_threat",
                claim="Trade groups refute that semiconductor export controls stop cooperation with China",
                attribution="refute",
                tone="positive",
                quote="Trade groups refuted claims of immediate disruption.",
            ),
        ]
    )
    persist_event_narratives(session, event_id=ev.id, clusters=clusters)
    session.flush()
    return {"day": day_str, "article_ids": aids, "event_id": ev.id}


class _GroundedMockLLM:
    def __init__(self, *, article_id: str, event_id: str, fail: bool = False) -> None:
        self.article_id = article_id
        self.event_id = event_id
        self.fail = fail
        self.calls = 0

    def generate_json(self, **kwargs: Any) -> LLMCallResult:
        self.calls += 1
        if self.fail:
            raise TimeoutError("Simulated LLM timeout")
        payload = {
            "summary": "当期监测样本聚焦涉华半导体管制议题，美国与英国媒体叙事存在明显分化。",
            "findings": [
                {
                    "title": "当期涉华报道集中于半导体与经贸",
                    "conclusion": "被监测媒体样本共覆盖涉华文章 3 篇，涉及芯片管制与绿色合作议题。",
                    "classification": "Fact",
                    "evidence_refs": [
                        {"type": "metric", "ref_id": "metric:GLOBAL:ALL", "label": "全球总量"},
                        {"type": "article", "ref_id": self.article_id, "label": "代表报道"},
                    ],
                    "supporting_metrics": ["metric:GLOBAL:ALL"],
                    "reasoning": "基于 V1.0 统计快照与代表文章正文证据。",
                    "confidence": "medium",
                    "limitations": ["样本量较小（n=3）"],
                },
                {
                    "title": "英美媒体叙事焦点存在差异",
                    "conclusion": "美国样本侧重安全与制裁框架，英国样本同时呈现供应链与反驳声音。",
                    "classification": "Inference",
                    "evidence_refs": [{"type": "article", "ref_id": self.article_id, "label": "原文片段"}],
                    "reasoning": "结合叙事簇正反证据归纳。",
                    "confidence": "medium",
                    "limitations": ["样本覆盖媒体有限"],
                },
                {
                    "title": "后续盟友政策协同仍待验证",
                    "conclusion": "若欧洲进一步跟进芯片限制，跨国负面报道可能上升。",
                    "classification": "Hypothesis",
                    "evidence_refs": [{"type": "event", "ref_id": self.event_id, "label": "关联事件"}],
                    "reasoning": "待观察条件性假设。",
                    "confidence": "low",
                    "limitations": ["尚无明确时间表"],
                },
            ],
            "event_interpretations": [
                {
                    "event_id": self.event_id,
                    "title": "US tightens semiconductor export controls on China",
                    "background": "中美芯片管制持续演变。",
                    "what_happened": "美方宣布更严格半导体出口管制，多国媒体跟进报道。",
                    "event_actual_changes": "管制范围涉及先进芯片设备。",
                    "coverage_attention_changes": "美英新三国信源当日均出现报道。",
                    "country_differences": "美国偏重安全框架，英国呈现多方声音，新加坡多为引述表态。",
                    "media_viewpoints": ["安全风险担忧", "供应链反驳声音"],
                    "why_it_matters": "可能影响跨国科技产业链预期。",
                    "what_to_monitor": ["欧盟及亚洲盟友后续表态"],
                    "evidence_refs": [
                        {"type": "event", "ref_id": self.event_id, "label": "事件"},
                        {"type": "article", "ref_id": self.article_id, "label": "报道"},
                    ],
                    "confidence": "medium",
                    "limitations": ["event_time 为空，仅记录报道发布时间"],
                }
            ],
            "outlook_signals": [
                {
                    "signal": "若欧盟跟进出口限制，半导体议题跨国报道可能持续升温。",
                    "observation_object": "semiconductors_export_controls",
                    "evidence_refs": [{"type": "event", "ref_id": self.event_id, "label": "芯片事件"}],
                    "trigger_metrics": ["metric:GLOBAL:ALL"],
                    "reasoning": "当前已出现多国媒体关注。",
                    "confidence": "low",
                    "what_to_monitor": ["欧盟委员会贸易声明"],
                    "potential_trigger": "欧盟发布正式限制清单",
                    "alternative_explanation": "仅为例行政策吹风",
                    "alternative_scenario": "若各方缓和磋商，关注度将回落。",
                    "uncertainty": "样本量有限",
                }
            ],
            "uncertainties": ["当前窗口样本规模较小（n=3），需结合多日趋势复核。"],
            "follow_up_questions": ["后续是否出现官方正式细则文本？"],
        }
        raw = json.dumps(payload, ensure_ascii=False)
        return LLMCallResult(
            parsed=payload,
            raw_text=raw,
            provider="mock",
            model_version="deepseek-chat-test",
            prompt_tokens=300,
            completion_tokens=400,
            total_tokens=700,
            latency_ms=120,
            estimated_cost_usd=0.0005,
        )


def test_evidence_package_traceability_and_no_raw_fulltext_dump(db_session: Session) -> None:
    meta = _seed_monitoring_corpus(db_session)
    report = build_daily_report(db_session, day=meta["day"], analyze=False)

    pkg, bundle = build_task_evidence_package(
        db_session,
        task_type="sentiment_stance_analysis",
        report_type="daily",
        payload=report,
    )
    assert isinstance(pkg, EvidencePackageContract)
    assert pkg.task_type == "sentiment_stance_analysis"
    assert pkg.coverage["global_article_count"] == 3
    assert pkg.coverage["quoted_actor_articles"] >= 1
    assert len(pkg.representative_evidence) >= 1
    assert len(pkg.narratives) >= 1

    # Verify traceable fields on evidence items
    ev0 = pkg.representative_evidence[0]
    assert ev0["article_id"] in meta["article_ids"]
    assert ev0["evidence_id"]
    assert ev0["article_version_id"]
    assert ev0["published_at"]
    assert ev0["source_name"]
    assert ev0["analysis_task"] == "sentiment_stance_analysis"
    # No raw fulltext key dumped in current_articles
    for art in pkg.current_articles:
        assert "content_original" not in art
        assert "content_clean" not in art


def test_all_9_canonical_assessment_tasks_run_through_unified_framework(db_session: Session) -> None:
    assert len(list_assessment_tasks()) == 9
    meta = _seed_monitoring_corpus(db_session)
    report = build_daily_report(db_session, day=meta["day"], analyze=False)
    mock_llm = _GroundedMockLLM(article_id=meta["article_ids"][0], event_id=meta["event_id"])

    results = run_assessment_suite(
        db_session,
        task_types=CANONICAL_ASSESSMENT_TASKS,
        report_type="daily",
        payload=report,
        client=mock_llm,
        force=True,
    )
    assert set(results.keys()) == set(CANONICAL_ASSESSMENT_TASKS)
    assert mock_llm.calls == 9

    for tt, res in results.items():
        assert isinstance(res, AssessmentResultContract)
        assert res.task_type == tt
        assert res.status in {"completed", "needs_review"}
        assert len(res.observations) >= 1  # Fact
        assert len(res.interpretations) >= 1  # Inference
        assert len(res.hypotheses) >= 1  # Hypothesis
        assert len(res.evidence_refs) >= 1
        assert "not be interpreted as empirical accuracy" in res.confidence_note

    # Second call with force=False hits DB cache in ReportNarrativeTask (0 extra LLM calls)
    cached_res = run_assessment_task(
        db_session,
        task_type="overall_situation_assessment",
        report_type="daily",
        payload=report,
        client=mock_llm,
        force=False,
    )
    assert mock_llm.calls == 9
    assert cached_res.task_type == "overall_situation_assessment"
    db_rows = db_session.scalars(select(ReportNarrativeTask)).all()
    assert len(db_rows) == 9


def test_assessment_validator_catches_coordinated_propagation_and_volume_as_risk(
    db_session: Session,
) -> None:
    meta = _seed_monitoring_corpus(db_session)
    report = build_daily_report(db_session, day=meta["day"], analyze=False)
    _, bundle = build_task_evidence_package(
        db_session,
        task_type="risk_signal_assessment",
        report_type="daily",
        payload=report,
    )

    bad_out = NarrativeTaskOutput.model_validate(
        {
            "task_type": "risk_signal_assessment",
            "summary": "多国媒体同时报道证实了协调传播，且负面报道数量增加直接说明现实风险上升。",
            "findings": [
                {
                    "title": "未经证实的协调传播断言",
                    "conclusion": "多国同时报道证实存在协调传播，且负面报道增加意味着战略风险上升 99.9%。",
                    "classification": "Fact",
                    "evidence_refs": [],  # Missing required evidence for Fact
                    "confidence": "high",
                }
            ],
        }
    )
    validated, val_rep = validate_task_output(bad_out, bundle)
    assert val_rep["needs_review"] is True
    all_issues = " | ".join(
        list(val_rep.get("reasoning_issues") or [])
        + list(val_rep.get("evidence_issues") or [])
        + list(val_rep.get("numeric_issues") or [])
    )
    assert "coordinated_propagation_overclaim" in all_issues
    assert "volume_as_real_risk" in all_issues
    assert "99.9%" in all_issues or "missing_evidence" in all_issues or "Fact" in all_issues
    # Fact without evidence must be downgraded from Fact
    assert validated.findings[0].classification != "Fact"


def test_assessment_handles_zero_data_and_llm_timeout_gracefully(db_session: Session) -> None:
    # 1. Zero-data window -> deterministic insufficient_data (never calls LLM)
    empty_report = build_daily_report(db_session, day="2026-11-26", analyze=False)
    mock_should_not_run = _GroundedMockLLM(article_id="none", event_id="none")
    res_empty = run_assessment_task(
        db_session,
        task_type="overall_situation_assessment",
        report_type="daily",
        payload=empty_report,
        client=mock_should_not_run,
    )
    assert res_empty.status == "insufficient_data"
    assert mock_should_not_run.calls == 0

    # 2. LLM timeout on non-empty corpus -> graceful failed status with grounded fallback
    meta = _seed_monitoring_corpus(db_session)
    report = build_daily_report(db_session, day=meta["day"], analyze=False)
    failing_llm = _GroundedMockLLM(article_id=meta["article_ids"][0], event_id=meta["event_id"], fail=True)
    res_fail = run_assessment_task(
        db_session,
        task_type="change_detection_assessment",
        report_type="daily",
        payload=report,
        client=failing_llm,
        force=True,
        allow_fallback=True,
    )
    assert res_fail.status == "failed"
    assert len(res_fail.evidence_refs) >= 1
    assert any("Simulated LLM timeout" in lim for lim in res_fail.limitations)

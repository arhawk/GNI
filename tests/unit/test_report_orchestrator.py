"""Unit tests for Canonical ReportOrchestrator: single task registry, single execution path, caching & partial retry."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from gni.analysis.deepseek import LLMCallResult
from gni.core.contracts import AssessmentResultContract
from gni.infrastructure.models import Article, ArticleAnalysis, Base, Country, Organization, Source
from gni.reports.daily import build_daily_report
from gni.reports.monthly import build_monthly_report
from gni.reports.orchestrator import (
    REPORT_TASK_PROFILES,
    build_assessments_meta,
    resolve_profile_tasks,
)
from gni.reports.weekly import build_weekly_report


class _StubLLM:
    def __init__(self, fail_on: set[str] | None = None) -> None:
        self.calls: list[str] = []
        self.fail_on = fail_on or set()

    def generate_json(self, *, system_prompt: str, user_prompt: str, **kwargs: Any) -> LLMCallResult:
        self.calls.append(system_prompt[:60])
        for tag in self.fail_on:
            if tag in system_prompt:
                raise RuntimeError(f"simulated failure on {tag}")
        out = {
            "summary": "基于监测样本的确定性摘要。",
            "findings": [
                {
                    "title": "关键观察",
                    "conclusion": "监测样本显示涉华报道集中于科技竞争议题。",
                    "classification": "Fact",
                    "confidence": "medium",
                    "evidence_refs": [{"type": "article", "ref_id": "a1", "label": "Sample"}],
                }
            ],
            "uncertainties": ["样本覆盖有限"],
            "follow_up_questions": ["持续跟踪后续报道"],
        }
        return LLMCallResult(
            provider="deepseek",
            raw_text=json.dumps(out, ensure_ascii=False),
            parsed=out,
            model_version="deepseek-test-v2",
            prompt_tokens=100,
            completion_tokens=80,
            total_tokens=180,
            latency_ms=42,
            estimated_cost_usd=0.0002,
        )


def _seed(session: Session) -> None:
    session.add(Country(id="US", code="US", name="United States"))
    session.add(Organization(id="org_us", country_id="US", name="Org US"))
    session.add(
        Source(
            id="src_us",
            organization_id="org_us",
            country_id="US",
            name="US Wire",
            source_type="news_agency",
            active_status="active",
        )
    )
    now = datetime(2026, 11, 26, 6, 0, tzinfo=timezone.utc)
    session.add(
        Article(
            id="a1",
            source_id="src_us",
            url="https://example.us/1",
            canonical_url="https://example.us/1",
            title="US China tech competition update",
            processing_status="done",
            analysis_status="completed",
            china_relevance_level="core",
            published_at=now - timedelta(hours=2),
            first_seen_at=now - timedelta(hours=2),
        )
    )
    session.add(
        ArticleAnalysis(
            id="ana1",
            article_id="a1",
            provider="deepseek",
            model_name="deepseek-chat",
            prompt_version="deepseek_analyze_v1.0",
            schema_version="article_analysis_v1.0",
            taxonomy_version="taxonomy_v1.0",
            analysis_status="completed",
            structured_result={
                "schema_version": "article_analysis_v1.0",
                "taxonomy_version": "taxonomy_v1.0",
                "china_stance": {"stance_label": "Neutral", "expression_owner": "media"},
                "topics_v1": ["tech_competition"],
                "boards_v1": ["economy_tech"],
            },
        )
    )
    session.commit()


def test_task_profiles_and_execution_order() -> None:
    assert set(REPORT_TASK_PROFILES.keys()) == {"daily", "weekly", "monthly"}
    daily_core = resolve_profile_tasks("daily", profile="core")
    assert daily_core.index("event_analysis") < daily_core.index("overall_situation_assessment")
    assert daily_core.index("overall_situation_assessment") < daily_core.index("outlook_assessment")
    assert len(daily_core) == 5

    weekly_core = resolve_profile_tasks("weekly", profile="core")
    assert len(weekly_core) == 8
    monthly_full = resolve_profile_tasks("monthly", profile="full")
    assert len(monthly_full) == 9


def test_orchestrator_cache_hit_and_partial_retry_across_daily_weekly_monthly() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        _seed(session)
        stub = _StubLLM()

        # Daily via single canonical orchestrator
        d1 = build_daily_report(
            session,
            day="2026-11-26",
            analyze=True,
            analyze_tasks=["event_analysis", "overall_situation_assessment"],
            llm_client=stub,
        )
        assert d1["assessments_meta"]["engine"] == "canonical_orchestrator"
        assert "overall_situation_assessment" in d1["assessments"]
        assert "event_analysis" in d1["assessments"]
        assert "intelligence" not in d1
        assert len(stub.calls) == 2

        # Weekly via single canonical orchestrator (2-task subset)
        w1 = build_weekly_report(
            session,
            end_day="2026-11-26",
            persist_snapshot=False,
            analyze=True,
            analyze_tasks=["event_analysis", "overall_situation_assessment"],
            llm_client=stub,
        )
        assert w1["assessments_meta"]["engine"] == "canonical_orchestrator"
        assert "overall_situation_assessment" in w1["assessments"]
        assert "event_analysis" in w1["assessments"]
        assert "intelligence" not in w1
        assert len(stub.calls) == 4

        # Second call without force hits cache (0 new LLM calls)
        w2 = build_weekly_report(
            session,
            end_day="2026-11-26",
            persist_snapshot=False,
            analyze=True,
            analyze_tasks=["event_analysis", "overall_situation_assessment"],
            llm_client=stub,
        )
        assert len(stub.calls) == 4
        assert w2["assessments_meta"]["meta"]["completed_tasks"] >= 2

        # Monthly partial retry: fail on event_analysis, then retry only event_analysis
        failing_stub = _StubLLM(fail_on={"重点事件"})
        m1 = build_monthly_report(
            session,
            month="2026-11",
            persist_snapshot=False,
            analyze=True,
            analyze_tasks=["event_analysis", "overall_situation_assessment"],
            llm_client=failing_stub,
        )
        assert m1["assessments_meta"]["task_statuses"]["event_analysis"]["status"] == "failed"
        assert m1["assessments_meta"]["task_statuses"]["overall_situation_assessment"]["status"] in {
            "completed",
            "needs_review",
        }

        m2 = build_monthly_report(
            session,
            month="2026-11",
            persist_snapshot=False,
            analyze=True,
            analyze_tasks=["event_analysis"],
            force_analyze=True,
            llm_client=stub,
        )
        assert m2["assessments_meta"]["task_statuses"]["event_analysis"]["status"] in {"completed", "needs_review"}
        assert "overall_situation_assessment" in m2["assessments"]


def test_assessments_meta_counts_optional_tasks_consistently() -> None:
    """Optional tasks included in assessments must also be counted in total_tasks so completed <= total."""
    profile = REPORT_TASK_PROFILES["daily"]

    def _mk(task_type: str, status: str = "completed") -> AssessmentResultContract:
        return AssessmentResultContract(
            task_type=task_type,
            task_version="v2.0",
            report_type="daily",
            period="2026-11-26",
            evidence_hash="h1",
            generated_at="2026-11-26T00:00:00+00:00",
            model_version="deepseek-test",
            prompt_version="v2.0",
            executive_summary="ok",
            status=status,  # type: ignore[arg-type]
        )

    # All 5 core tasks + 4 optional tasks -> 9/9 completed
    all_tasks = list(profile.core_tasks) + list(profile.optional_tasks)
    meta_full = build_assessments_meta(
        report_type="daily",
        period="2026-11-26",
        evidence_hash="h1",
        assessments={tt: _mk(tt) for tt in all_tasks},
        profile=profile,
    )
    assert meta_full["meta"]["completed_tasks"] == len(all_tasks)
    assert meta_full["meta"]["total_tasks"] == len(all_tasks)
    assert meta_full["status"] == "completed"

    # 4 core tasks + 1 optional task -> 5/6 and still partial because 1 core task is pending
    partial_tasks = list(profile.core_tasks[:4]) + [profile.optional_tasks[0]]
    meta_partial = build_assessments_meta(
        report_type="daily",
        period="2026-11-26",
        evidence_hash="h1",
        assessments={tt: _mk(tt) for tt in partial_tasks},
        profile=profile,
    )
    assert meta_partial["meta"]["completed_tasks"] == 5
    assert meta_partial["meta"]["total_tasks"] == 6
    assert meta_partial["status"] == "partial"


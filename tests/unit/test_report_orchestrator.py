"""Unit tests for Task 2: Unified ReportOrchestrator, Task Profiles, and Canonical->Legacy Projection."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from gni.analysis.deepseek import LLMCallResult
from gni.infrastructure.models import Article, ArticleAnalysis, Base, Country, Organization, Source
from gni.reports.monthly import build_monthly_report
from gni.reports.orchestrator import (
    REPORT_TASK_PROFILES,
    ReportOrchestrator,
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
                "china_stance": "Neutral",
                "topics_v1": ["tech_competition"],
                "boards_v1": ["tech_industry"],
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


def test_orchestrator_cache_hit_and_partial_retry_across_weekly_and_monthly() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        _seed(session)
        stub = _StubLLM()

        # Weekly via orchestrator (2-task subset)
        w1 = build_weekly_report(
            session,
            end_day="2026-11-26",
            persist_snapshot=False,
            analyze=True,
            analyze_tasks=["event_analysis", "overall_situation_assessment"],
            llm_client=stub,
            use_orchestrator=True,
        )
        assert w1["intelligence"]["engine"] == "canonical_orchestrator"
        assert "executive_analysis" in w1["intelligence"]["tasks"]
        assert "event_analysis" in w1["intelligence"]["tasks"]
        assert len(stub.calls) == 2

        # Second call without force hits cache (0 new LLM calls)
        w2 = build_weekly_report(
            session,
            end_day="2026-11-26",
            persist_snapshot=False,
            analyze=True,
            analyze_tasks=["event_analysis", "overall_situation_assessment"],
            llm_client=stub,
            use_orchestrator=True,
        )
        assert len(stub.calls) == 2
        assert w2["intelligence"]["meta"]["completed_tasks"] == 2

        # Partial retry of 1 new task preserves previously cached tasks
        orch = ReportOrchestrator()
        r3 = orch.run(
            session,
            report_type="weekly",
            payload=w2,
            tasks=["outlook_assessment"],
            llm_client=stub,
        )
        assert len(stub.calls) == 3
        assert set(r3.assessments.keys()) == {
            "event_analysis",
            "overall_situation_assessment",
            "outlook_assessment",
        }

        # Monthly via orchestrator uses report-scoped prompt_version & populates governance fields
        m1 = build_monthly_report(
            session,
            end_day="2026-11-26",
            persist_snapshot=False,
            analyze=True,
            analyze_tasks=["overall_situation_assessment"],
            llm_client=stub,
            use_orchestrator=True,
        )
        assert m1["intelligence"]["engine"] == "canonical_orchestrator"
        canon = m1["intelligence"]["canonical_tasks"]["overall_situation_assessment"]
        assert canon["report_type"] == "monthly"
        assert canon["prompt_version"] == "monthly:assess_overall_v2.0"
        assert canon["model_version"] == "deepseek-test-v2"
        assert canon["schema_version"]

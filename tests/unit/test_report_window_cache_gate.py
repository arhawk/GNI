"""Unit tests for Task 3: Time Windows (incl. mid-month MTD & leap year), Cache Identity, and Quality Gate."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from gni.analysis.deepseek import LLMCallResult
from gni.core.config import Settings
from gni.infrastructure.models import Article, Base, Country, Organization, Source
from gni.reports.monthly import build_monthly_report
from gni.reports.narrative.assessment import run_assessment_task
from gni.reports.quality_gate import evaluate_report_quality_gate
from gni.reports.window import (
    in_half_open_window,
    resolve_daily_window,
    resolve_monthly_window,
    resolve_weekly_window,
)


def test_window_boundaries_leap_year_and_year_end() -> None:
    tz = ZoneInfo("Asia/Shanghai")

    # Leap year Feb 2024 has 29 days
    feb = resolve_monthly_window("2024-02", now=datetime(2024, 3, 5, 12, 0, tzinfo=tz))
    assert feb.total_days == 29
    assert feb.is_partial_period is False
    assert feb.period == "2024-02"

    # Year-end crossing weekly window (rolling 7d ending 2026-01-03)
    wk = resolve_weekly_window("2026-01-03")
    assert wk.window_mode == "rolling_7d"
    assert wk.period == "2025-12-28_2026-01-03"
    assert (wk.end - wk.start).days == 7
    assert (wk.prev_end - wk.prev_start).days == 7

    # Exact half-open boundary [start, end)
    d = resolve_daily_window("2026-11-26")
    assert in_half_open_window(d.start, d.start, d.end) is True
    assert in_half_open_window(d.end, d.start, d.end) is False


def test_mid_month_mtd_fair_comparison() -> None:
    tz = ZoneInfo("Asia/Shanghai")
    # Mid-month: Nov 15, 2026 (15 elapsed days of 30)
    mid_now = datetime(2026, 11, 15, 10, 0, tzinfo=tz)
    win = resolve_monthly_window("2026-11", now=mid_now)
    assert win.is_partial_period is True
    assert win.elapsed_days == 15
    assert (win.effective_prev_end - win.effective_prev_start).days == 15
    assert "MTD" in win.comparison_note

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(Country(id="US", code="US", name="United States"))
        session.add(Organization(id="org_us", country_id="US", name="Org US"))
        session.add(Source(id="src_us", organization_id="org_us", country_id="US", name="Wire", source_type="media"))
        # 1 article in Nov 1..15, 1 article in Oct 1..15, 1 article in Oct 25 (excluded from fair MTD prev!)
        session.add_all(
            [
                Article(
                    id="nov-10",
                    source_id="src_us",
                    url="https://e.com/nov10",
                    canonical_url="https://e.com/nov10",
                    title="China Nov 10",
                    china_relevance_level="core",
                    published_at=datetime(2026, 11, 10, 4, 0, tzinfo=timezone.utc),
                ),
                Article(
                    id="oct-10",
                    source_id="src_us",
                    url="https://e.com/oct10",
                    canonical_url="https://e.com/oct10",
                    title="China Oct 10",
                    china_relevance_level="core",
                    published_at=datetime(2026, 10, 10, 4, 0, tzinfo=timezone.utc),
                ),
                Article(
                    id="oct-25",
                    source_id="src_us",
                    url="https://e.com/oct25",
                    canonical_url="https://e.com/oct25",
                    title="China Oct 25 late month",
                    china_relevance_level="core",
                    published_at=datetime(2026, 10, 25, 4, 0, tzinfo=timezone.utc),
                ),
            ]
        )
        session.commit()

        rep = build_monthly_report(session, month="2026-11", persist_snapshot=False, now=mid_now)
        assert rep["window_spec"]["is_partial_period"] is True
        # Fair MTD prev only counts oct-10 (1), NOT oct-25 -> delta == 0 instead of -1!
        assert rep["sections"]["summary"]["kpis"]["china_articles"] == 1
        assert rep["sections"]["summary"]["kpis"]["prev_month_articles"] == 1
        assert rep["sections"]["summary"]["kpis"]["delta"] == 0
        assert rep["quality_gate"]["status"] == "passed_with_warnings"


def test_cache_invalidation_on_model_version_change() -> None:
    class _ModelStub:
        def __init__(self) -> None:
            self.calls = 0

        def generate_json(self, *, model: str | None = None, **kwargs: Any) -> LLMCallResult:
            self.calls += 1
            out = {"summary": f"ok-{self.calls}", "findings": [], "uncertainties": [], "follow_up_questions": []}
            return LLMCallResult(
                provider="deepseek",
                raw_text=json.dumps(out),
                parsed=out,
                model_version=model or "m1",
                prompt_tokens=10,
                completion_tokens=10,
                total_tokens=20,
                latency_ms=5,
                estimated_cost_usd=0.0,
            )

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(Country(id="US", code="US", name="United States"))
        session.add(Organization(id="org_us", country_id="US", name="Org US"))
        session.add(Source(id="src_us", organization_id="org_us", country_id="US", name="Wire", source_type="media"))
        session.add(
            Article(
                id="a1",
                source_id="src_us",
                url="https://e.com/1",
                canonical_url="https://e.com/1",
                title="China trade",
                china_relevance_level="core",
                published_at=datetime(2026, 11, 26, 4, 0, tzinfo=timezone.utc),
            )
        )
        session.commit()

        payload = {
            "report_type": "daily",
            "period": "2026-11-26",
            "sections": {
                "v1_stats": {"global": {"article_count": 1, "positive_count": 0, "neutral_count": 1, "negative_count": 0, "unclassified_count": 0}},
                "summary": {"kpis": {"china_articles": 1}},
            },
        }
        stub = _ModelStub()
        cfg1 = Settings(llm_model="deepseek-chat")
        cfg2 = Settings(llm_model="deepseek-reasoner")

        run_assessment_task(session, task_type="overall_situation_assessment", report_type="daily", payload=payload, client=stub, settings=cfg1)
        assert stub.calls == 1
        # Same model hits cache
        run_assessment_task(session, task_type="overall_situation_assessment", report_type="daily", payload=payload, client=stub, settings=cfg1)
        assert stub.calls == 1
        # Different model invalidates cache and calls LLM again
        run_assessment_task(session, task_type="overall_situation_assessment", report_type="daily", payload=payload, client=stub, settings=cfg2)
        assert stub.calls == 2


def test_quality_gate_three_states() -> None:
    # Passed
    ok_payload = {
        "report_type": "daily",
        "period": "2026-11-26",
        "period_start": "2026-11-26T00:00:00+08:00",
        "period_end": "2026-11-27T00:00:00+08:00",
        "schema_version": "daily_report_schema_v4",
        "sections": {
            "v1_stats": {
                "global": {
                    "article_count": 10,
                    "positive_count": 2,
                    "neutral_count": 4,
                    "negative_count": 2,
                    "unclassified_count": 2,
                    "positive_rate": 0.25,
                    "neutral_rate": 0.5,
                    "negative_rate": 0.25,
                    "stance_coverage_rate": 0.8,
                }
            }
        },
    }
    assert evaluate_report_quality_gate(ok_payload)["status"] == "passed"

    # Blocked when Unclassified leaks into denominator (e.g. positive_rate=0.2 instead of 0.25)
    bad_payload = json.loads(json.dumps(ok_payload))
    bad_payload["sections"]["v1_stats"]["global"]["positive_rate"] = 0.2
    res = evaluate_report_quality_gate(bad_payload)
    assert res["status"] == "blocked"
    assert any(i["code"] == "unclassified_leaked_into_denominator" for i in res["blocking_issues"])

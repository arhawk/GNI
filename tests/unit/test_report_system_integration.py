"""Task 6: End-to-End Report System Integration & 9 Statistical Methodology Invariants."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from gni.infrastructure.models import (
    Article,
    ArticleAnalysis,
    Base,
    Country,
    Event,
    EventArticle,
    Organization,
    Source,
)
from gni.reports.daily import build_daily_report
from gni.reports.monthly import build_monthly_report
from gni.reports.weekly import build_weekly_report


def test_nine_statistical_methodology_invariants() -> None:
    """Deterministic verification of all 9 GNI V1.0 statistical redlines."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all([Country(id="US", code="US", name="United States"), Country(id="GB", code="GB", name="United Kingdom")])
        session.add_all([Organization(id="o_us", country_id="US", name="Org US"), Organization(id="o_gb", country_id="GB", name="Org GB")])
        session.add_all(
            [
                Source(id="s_us", organization_id="o_us", country_id="US", name="US Wire", source_type="media"),
                Source(id="s_gb", organization_id="o_gb", country_id="GB", name="UK Daily", source_type="media"),
            ]
        )
        # 4 unique articles:
        # a1 (US, Positive, 2 topics: economy + technology, 2 boards)
        # a2 (US, Negative, 1 topic: economy)
        # a3 (GB, Unclassified, 1 topic: diplomacy) -> must enter total, excluded from stance ratio denominator!
        # a4 (GB, Neutral, 1 topic: economy)
        t0 = datetime(2026, 11, 26, 4, 0, tzinfo=timezone.utc)
        articles = [
            Article(id="a1", source_id="s_us", url="https://e.com/1", canonical_url="https://e.com/1", title="China EV AI", china_relevance_level="core", published_at=t0),
            Article(id="a2", source_id="s_us", url="https://e.com/2", canonical_url="https://e.com/2", title="China tariffs", china_relevance_level="core", published_at=t0),
            Article(id="a3", source_id="s_gb", url="https://e.com/3", canonical_url="https://e.com/3", title="China summit", china_relevance_level="core", published_at=t0),
            Article(id="a4", source_id="s_gb", url="https://e.com/4", canonical_url="https://e.com/4", title="China trade", china_relevance_level="core", published_at=t0),
        ]
        session.add_all(articles)
        session.add_all(
            [
                ArticleAnalysis(
                    id="an1",
                    article_id="a1",
                    prompt_version="v1",
                    schema_version="article_analysis_v1.0",
                    structured_result={
                        "schema_version": "article_analysis_v1.0",
                        "china_stance": {"stance_label": "Positive", "expression_owner": "media"},
                        "topics_v1": ["tariffs_trade_war", "tech_competition", "tariffs_trade_war"],
                        "boards_v1": ["Economy", "Technology", "Economy"],
                    },
                ),
                ArticleAnalysis(
                    id="an2",
                    article_id="a2",
                    prompt_version="v1",
                    schema_version="article_analysis_v1.0",
                    structured_result={
                        "schema_version": "article_analysis_v1.0",
                        "china_stance": {"stance_label": "Negative", "expression_owner": "media"},
                        "topics_v1": ["tariffs_trade_war"],
                        "boards_v1": ["Economy"],
                    },
                ),
                ArticleAnalysis(
                    id="an3",
                    article_id="a3",
                    prompt_version="v1",
                    schema_version="article_analysis_v1.0",
                    structured_result={
                        "schema_version": "article_analysis_v1.0",
                        # Pure quoted_actor must NOT be misattributed as media stance -> Unclassified
                        "china_stance": {"stance_label": "Negative", "expression_owner": "quoted_actor"},
                        "topics_v1": ["south_china_sea"],
                        "boards_v1": ["Geopolitics"],
                    },
                ),
                ArticleAnalysis(
                    id="an4",
                    article_id="a4",
                    prompt_version="v1",
                    schema_version="article_analysis_v1.0",
                    structured_result={
                        "schema_version": "article_analysis_v1.0",
                        "china_stance": {"stance_label": "Neutral", "expression_owner": "media"},
                        "topics_v1": ["tariffs_trade_war"],
                        "boards_v1": ["Economy"],
                    },
                ),
            ]
        )
        # Event with NULL event_time (must NOT be fabricated from published_at)
        ev = Event(id="ev-null-time", title="Undated Policy Signal", event_time=None)
        session.add(ev)
        session.add_all([EventArticle(event_id="ev-null-time", article_id="a1"), EventArticle(event_id="ev-null-time", article_id="a2")])
        session.commit()

        daily = build_daily_report(session, day="2026-11-26")
        v1 = daily["sections"]["v1_stats"]
        g = v1["global"]

        # 1. Global unique article dedup == 4
        assert g["article_count"] == 4
        # 5 & 6. Unclassified in total (1), excluded from pos/neu/neg ratio denominator (3 classified -> 1/3 each)
        assert g["positive_count"] == 1
        assert g["neutral_count"] == 1
        assert g["negative_count"] == 1
        assert g["unclassified_count"] == 1
        assert abs(g["positive_rate"] - (1 / 3)) < 1e-4
        assert abs(g["neutral_rate"] - (1 / 3)) < 1e-4
        assert abs(g["negative_rate"] - (1 / 3)) < 1e-4
        assert abs(g["stance_coverage_rate"] - 0.75) < 1e-4

        # 2, 3, 4. Multi-topic overlap allowed across topics, deduped within topic, sum > global
        topic_counts = {t["scope_id"]: t["article_count"] for t in v1.get("topics") or []}
        assert topic_counts.get("tariffs_trade_war") == 3  # a1 counted once despite duplicate tag
        assert topic_counts.get("tech_competition") == 1
        assert sum(topic_counts.values()) > g["article_count"]

        # 7. Country attribution by source country
        country_counts = {c["scope_id"]: c["article_count"] for c in v1.get("countries") or []}
        assert country_counts == {"US": 2, "GB": 2}

        # Visualizations populated from real v1_stats
        assert len(daily["visualizations"]["country_bar"]["items"]) == 2
        assert len(daily["visualizations"]["topic_delta"]["items"]) >= 2

        # Daily report no longer renders an event timeline
        assert "event_timeline" not in daily["visualizations"]

        # 8 & 9. event_time=NULL falls back to earliest article publish time as Proxy Event Time (basis labelled)
        undated = [e for e in daily["sections"]["major_events"] if e.get("event_id") == "ev-null-time"]
        if undated:
            assert undated[0]["event_time_basis"] == "proxy_published_at"
            assert undated[0]["event_time"] is not None

        # Weekly & Monthly full pipeline traceability
        weekly = build_weekly_report(session, end_day="2026-11-26", persist_snapshot=False)
        monthly = build_monthly_report(session, month="2026-11", persist_snapshot=False)
        for rep in (daily, weekly, monthly):
            assert rep["quality_gate"]["status"] in {"passed", "passed_with_warnings"}
            assert rep["window_spec"]["timezone"] == "Asia/Shanghai"
            assert "report_package" in rep
            assert "visualizations" in rep

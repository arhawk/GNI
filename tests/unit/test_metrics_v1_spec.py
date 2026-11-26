"""GNI Statistical Methodology V1.0 — Section 11 Acceptance Criteria (1..10) tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from gni.analysis.heuristic import SCHEMA_VERSION, build_structured_analysis
from gni.analysis.l2_fulltext import screen_fulltext
from gni.analysis.l3_spans import extract_china_spans
from gni.analysis.relevance import assess_relevance
from gni.analysis.stance_util import extract_v1_china_stance, extract_v1_topics
from gni.core.config import get_settings
from gni.events.fingerprint import FingerprintCard
from gni.events.match import FingerprintCluster
from gni.events.service import _persist_fingerprint_cluster
from gni.infrastructure.db import ensure_schema, reset_engine, session_scope
from gni.infrastructure.models import (
    Article,
    ArticleAnalysis,
    Country,
    Event,
    Organization,
    Source,
    StatSnapshot,
)
from gni.metrics.definitions import METHODOLOGY_VERSION, TAXONOMY_V1_VERSION, V1_ANALYSIS_VERSION
from gni.metrics.service import run_v1_stat_snapshots
from gni.metrics.taxonomy_v1 import boards_for_topics, load_taxonomy_v1
from gni.metrics.v1_stats import V1ArticleInput, compute_v1_stat_snapshots, group_snapshots_by_scope
from gni.reports.daily import build_daily_report, render_daily_markdown
from gni.reports.monthly import build_monthly_report
from gni.reports.validate import validate_daily_report
from gni.reports.weekly import build_weekly_report

WIN_START = datetime(2026, 11, 1, 0, 0, tzinfo=timezone.utc)
WIN_END = datetime(2026, 12, 1, 0, 0, tzinfo=timezone.utc)
PUB_IN = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)


def _by_key(rows):
    return {(r.scope_type, r.scope_id): r for r in rows}


def test_v1_taxonomy_fixed_4_boards_15_topics():
    tax = load_taxonomy_v1()
    assert tax.version == TAXONOMY_V1_VERSION
    assert len(tax.boards) == 4
    assert len(tax.topics) == 15
    assert boards_for_topics(["tech_competition", "semiconductors_export_controls"]) == ["economy_tech"]
    assert boards_for_topics(["south_china_sea", "tariffs_trade_war"]) == [
        "security_military",
        "economy_tech",
    ]


# Acceptance 1: One article hits 2 topics -> both topics count 1, global counts 1.
# Acceptance 2: One article hits 2 topics in the SAME board -> that board counts 1.
def test_acceptance_1_and_2_multi_topic_same_board_dedup():
    art = V1ArticleInput(
        article_id="a1",
        source_id="src_us",
        source_country="US",
        published_at=PUB_IN,
        china_relevance_level="core",
        topics_v1=["tech_competition", "semiconductors_export_controls"],
        stance_label="Negative",
        analysis_schema_version=V1_ANALYSIS_VERSION,
    )
    snaps = _by_key(compute_v1_stat_snapshots([art], period_start=WIN_START, period_end=WIN_END))
    assert snaps[("GLOBAL", "ALL")].article_count == 1
    assert snaps[("TOPIC", "tech_competition")].article_count == 1
    assert snaps[("TOPIC", "semiconductors_export_controls")].article_count == 1
    assert snaps[("BOARD", "economy_tech")].article_count == 1


# Acceptance 3: One article hits 2 different boards -> both boards count 1, global counts 1.
def test_acceptance_3_cross_board_overlap_global_dedup():
    art = V1ArticleInput(
        article_id="a2",
        source_id="src_au",
        source_country="AU",
        published_at=PUB_IN,
        china_relevance_level="substantial",
        topics_v1=["south_china_sea", "us_china_relations"],
        stance_label="Neutral",
        analysis_schema_version=V1_ANALYSIS_VERSION,
    )
    snaps = _by_key(compute_v1_stat_snapshots([art], period_start=WIN_START, period_end=WIN_END))
    assert snaps[("GLOBAL", "ALL")].article_count == 1
    assert snaps[("BOARD", "security_military")].article_count == 1
    assert snaps[("BOARD", "politics_diplomacy")].article_count == 1


# Acceptance 4, 6, 7: Unclassified stays in article_count, excluded from P/N/N denominator;
# P+N+N rates sum to 100%; stance_coverage_rate reflects classified/total (including legacy=Unclassified).
def test_acceptance_4_6_7_unclassified_denominator_rates_and_coverage():
    # Example from V1.0 Section 5.2: 200 Pos, 500 Neu, 200 Neg, 100 Unclassified (incl. legacy)
    rows: list[V1ArticleInput] = []
    idx = 0
    for label, n, schema in (
        ("Positive", 2, V1_ANALYSIS_VERSION),
        ("Neutral", 5, V1_ANALYSIS_VERSION),
        ("Negative", 2, V1_ANALYSIS_VERSION),
        ("Unclassified", 1, V1_ANALYSIS_VERSION),
    ):
        for _ in range(n):
            idx += 1
            rows.append(
                V1ArticleInput(
                    article_id=f"art_{idx}",
                    source_id="src_us",
                    source_country="US",
                    published_at=PUB_IN,
                    china_relevance_level="core",
                    topics_v1=["china_economy"],
                    stance_label=label,
                    analysis_schema_version=schema,
                )
            )
    snaps = _by_key(compute_v1_stat_snapshots(rows, period_start=WIN_START, period_end=WIN_END))
    g = snaps[("GLOBAL", "ALL")]
    assert g.article_count == 10
    assert g.positive_count == 2
    assert g.neutral_count == 5
    assert g.negative_count == 2
    assert g.unclassified_count == 1
    assert g.stance_coverage_rate == pytest.approx(0.9, abs=1e-6)
    assert g.positive_rate == pytest.approx(2 / 9, abs=1e-5)
    assert g.neutral_rate == pytest.approx(5 / 9, abs=1e-5)
    assert g.negative_rate == pytest.approx(2 / 9, abs=1e-5)
    assert (g.positive_rate + g.neutral_rate + g.negative_rate) == pytest.approx(1.0, abs=1e-5)


def test_strict_legacy_analysis_treated_as_unclassified():
    legacy_structured = {
        "schema_version": "article_analysis_v0.2",
        "stances": [{"target_id": "china", "stance": "critical", "status": "known"}],
        "topics": {"primary": "economy_trade"},
    }
    assert extract_v1_china_stance(legacy_structured, schema_version="article_analysis_v0.2") == "Unclassified"
    assert extract_v1_topics(legacy_structured, schema_version="article_analysis_v0.2") == []


# Acceptance 5: Same article-level stance is used consistently across GLOBAL, COUNTRY, BOARD, TOPIC.
def test_acceptance_5_single_article_consistency_across_all_4_scopes():
    art = V1ArticleInput(
        article_id="a_single",
        source_id="src_in",
        source_country="IN",
        published_at=PUB_IN,
        china_relevance_level="core",
        topics_v1=["tariffs_trade_war", "belt_and_road"],
        stance_label="Positive",
        analysis_schema_version=V1_ANALYSIS_VERSION,
    )
    snaps = _by_key(compute_v1_stat_snapshots([art], period_start=WIN_START, period_end=WIN_END))
    for key in (
        ("GLOBAL", "ALL"),
        ("COUNTRY", "IN"),
        ("BOARD", "economy_tech"),
        ("BOARD", "politics_diplomacy"),
        ("TOPIC", "tariffs_trade_war"),
        ("TOPIC", "belt_and_road"),
    ):
        row = snaps[key]
        assert row.article_count == 1
        assert row.positive_count == 1
        assert row.positive_rate == pytest.approx(1.0)
        assert row.stance_coverage_rate == pytest.approx(1.0)
        assert row.article_ids == ["a_single"]


# Acceptance 8: Duplicate ingestion / URL tracking params / same content_hash must NOT double count.
def test_acceptance_8_deduplication_url_params_and_content_hash():
    a1 = V1ArticleInput(
        article_id="a_orig",
        source_id="src_us",
        source_country="US",
        published_at=PUB_IN,
        canonical_url="https://example.com/china-chips?utm_source=rss&fbclid=123",
        content_hash="hash_abc",
        china_relevance_level="core",
        topics_v1=["semiconductors_export_controls"],
        stance_label="Negative",
        analysis_schema_version=V1_ANALYSIS_VERSION,
    )
    a2_url_dup = V1ArticleInput(
        article_id="a_dup_url",
        source_id="src_us",
        source_country="US",
        published_at=PUB_IN,
        canonical_url="https://example.com/china-chips?utm_medium=social",
        content_hash="hash_different",
        china_relevance_level="core",
        topics_v1=["semiconductors_export_controls"],
        stance_label="Negative",
        analysis_schema_version=V1_ANALYSIS_VERSION,
    )
    a3_hash_dup = V1ArticleInput(
        article_id="a_dup_hash",
        source_id="src_us",
        source_country="US",
        published_at=PUB_IN,
        canonical_url="https://mirror.example.com/repost",
        content_hash="hash_abc",
        china_relevance_level="core",
        topics_v1=["semiconductors_export_controls"],
        stance_label="Negative",
        analysis_schema_version=V1_ANALYSIS_VERSION,
    )
    snaps = _by_key(
        compute_v1_stat_snapshots([a1, a2_url_dup, a3_hash_dup], period_start=WIN_START, period_end=WIN_END)
    )
    assert snaps[("GLOBAL", "ALL")].article_count == 1
    assert snaps[("TOPIC", "semiconductors_export_controls")].article_count == 1


# Acceptance 9 (pure + DB): Article stats strictly use published_at (not first_seen_at),
# and event_time is never filled from published_at.
# Acceptance 10: Every snapshot row is traceable to article_ids and stance_evidence.
@pytest.fixture()
def db(tmp_path, monkeypatch):
    db_path = tmp_path / "v1_spec.sqlite"
    monkeypatch.setenv("GNI_DATABASE_URL", f"sqlite:///{db_path}")
    get_settings.cache_clear()
    reset_engine()
    ensure_schema()
    yield
    reset_engine()
    get_settings.cache_clear()


def test_acceptance_9_and_10_db_snapshot_published_at_traceability_and_reports(db):
    with session_scope() as session:
        session.merge(Country(id="US", code="US", name="United States"))
        session.merge(Organization(id="org_us", country_id="US", name="US Media", organization_type="media"))
        session.merge(
            Source(
                id="src_us_test",
                organization_id="org_us",
                country_id="US",
                name="US Test Outlet",
                source_type="mainstream_independent",
                access_method="rss",
                adapter_type="rss_adapter",
                active_status="active",
                language="en",
                feed_scope="INTERNATIONAL_NEWS",
            )
        )

        # Article 1: published_at inside window -> MUST be counted
        body = (
            "China faces new semiconductor export controls from Washington, "
            "raising trade war tariffs and tech competition risks. "
            "Chinese officials warned the restrictions threaten supply chain stability."
        )
        l2 = screen_fulltext(
            body,
            title="US chip export controls on China",
            title_screening_label="explicit_relevant",
        )
        spans = extract_china_spans(body, l2, language="en")
        rel = assess_relevance(
            l2,
            title="US chip export controls on China",
            span_count=len(spans),
            valid_span_count=sum(1 for s in spans if s.validation_status == "valid"),
        )
        structured = build_structured_analysis(
            language="en",
            title="US chip export controls on China",
            content_clean=body,
            l2_matched_entities=l2.matched_entities,
            spans=spans,
            relevance=rel,
        )
        assert structured["schema_version"] == SCHEMA_VERSION
        assert structured["china_stance"]["stance_evidence"]

        aid_in = str(uuid4())
        session.add(
            Article(
                id=aid_in,
                source_id="src_us_test",
                title="US chip export controls on China",
                url="https://example.test/in-window",
                canonical_url="https://example.test/in-window",
                content_clean=body,
                language="en",
                published_at=PUB_IN,
                first_seen_at=PUB_IN,
                china_relevance_level="core",
                china_relevance_weight=0.9,
                processing_status="done",
                analysis_status="completed",
                exclude_from_metrics=False,
                content_hash="h_in_1",
            )
        )
        session.add(
            ArticleAnalysis(
                id=str(uuid4()),
                article_id=aid_in,
                provider="heuristic",
                model_name="heuristic-rules",
                schema_version=SCHEMA_VERSION,
                taxonomy_version=TAXONOMY_V1_VERSION,
                structured_result=structured,
            )
        )

        # Article 2: published_at is None, only first_seen_at is inside window -> MUST NOT be counted
        aid_no_pub = str(uuid4())
        session.add(
            Article(
                id=aid_no_pub,
                source_id="src_us_test",
                title="China missing published_at article",
                url="https://example.test/no-pub",
                canonical_url="https://example.test/no-pub",
                language="en",
                published_at=None,
                first_seen_at=PUB_IN,
                china_relevance_level="core",
                china_relevance_weight=0.9,
                processing_status="done",
                analysis_status="completed",
                exclude_from_metrics=False,
                content_hash="h_no_pub",
            )
        )
        session.flush()

        # Event check: event_time remains None even though article has published_at (V1.0 §8.2)
        card = FingerprintCard(
            article_id=aid_in,
            actor="United States",
            action="announces",
            object="semiconductor export controls",
            event_time=None,
            published_at=PUB_IN,
            confidence=0.8,
            summary="US chip export controls on China",
        )
        eid, _ = _persist_fingerprint_cluster(session, FingerprintCluster(cards=[card]))
        session.flush()
        ev = session.get(Event, eid)
        assert ev is not None and ev.event_time is None

        # Run and persist V1.0 stat snapshots
        res = run_v1_stat_snapshots(
            session,
            period_start=WIN_START,
            period_end=WIN_END,
            persist=True,
        )
        assert res["methodology_version"] == METHODOLOGY_VERSION
        assert res["persisted"] is True
        g = res["by_scope"]["global"]
        assert g["article_count"] == 1
        assert g["article_ids"] == [aid_in]
        assert aid_no_pub not in g["article_ids"]
        # Traceability to article-level stance_evidence
        assert aid_in in res["evidence_by_article"]
        assert res["evidence_by_article"][aid_in][0]["quote"]

        # Verify persisted rows in stat_snapshots table
        persisted_rows = list(session.scalars(select(StatSnapshot)).all())
        assert len(persisted_rows) == res["snapshot_count"]
        global_db = next(r for r in persisted_rows if r.scope_type == "GLOBAL")
        assert global_db.article_count == 1
        assert global_db.article_ids == [aid_in]
        assert global_db.methodology_version == METHODOLOGY_VERSION

        # Verify Daily / Weekly / Monthly reports integrate V1.0 stats cleanly
        daily = build_daily_report(session, day="2026-11-20")
        assert daily["methodology_version"] == METHODOLOGY_VERSION
        assert daily["sections"]["v1_stats"]["global"]["article_count"] == 1
        val = validate_daily_report(daily)
        assert val["ok"], val["errors"]
        md = render_daily_markdown(daily)
        assert "GNI DAILY Intelligence Report" in md
        assert METHODOLOGY_VERSION in md

        weekly = build_weekly_report(session, end_day="2026-11-20", persist_snapshot=False)
        assert weekly["methodology_version"] == METHODOLOGY_VERSION
        assert weekly["sections"]["v1_stats"]["global"]["article_count"] == 1

        monthly = build_monthly_report(session, month="2026-11", persist_snapshot=False)
        assert monthly["methodology_version"] == METHODOLOGY_VERSION
        assert monthly["sections"]["v1_stats"]["global"]["article_count"] == 1


def test_body_only_topic_classification_rejects_title_only_keyword():
    """V1.0 §2.3: topic classification must not rely solely on title keywords."""
    body = "Beijing released a routine administrative notice today with no sector details."
    l2 = screen_fulltext(body, title="South China Sea and Taiwan Strait semiconductor tariff")
    spans = extract_china_spans(body, l2, language="en")
    rel = assess_relevance(
        l2,
        title="South China Sea and Taiwan Strait semiconductor tariff",
        span_count=len(spans),
        valid_span_count=sum(1 for s in spans if s.validation_status == "valid"),
    )
    result = build_structured_analysis(
        language="en",
        title="South China Sea and Taiwan Strait semiconductor tariff",
        content_clean=body,
        l2_matched_entities=l2.matched_entities,
        spans=spans,
        relevance=rel,
    )
    assert result["topics_v1"] == []
    assert result["boards_v1"] == []

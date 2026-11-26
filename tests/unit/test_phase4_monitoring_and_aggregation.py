"""Phase 4 deterministic tests: Metrics, Change Detection, Event & Narrative Aggregation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from gni.events.extract import extract_from_structured_candidates
from gni.events.fingerprint import FingerprintCard
from gni.events.match import cluster_fingerprints
from gni.events.narratives import (
    ArticleNarrativeInput,
    cluster_narratives,
    persist_event_narratives,
)
from gni.events.service import merge_events, split_event
from gni.infrastructure.models import (
    Article,
    Base,
    Country,
    Event,
    EventArticle,
    EventNarrativeEvidence,
    EventRevision,
    NarrativeCluster,
    Organization,
    Source,
    StatSnapshot,
)
from gni.metrics.changes import (
    compute_consecutive_increase,
    detect_cross_country_divergence,
    detect_stance_shift,
    detect_volume_change,
)
from gni.metrics.service import get_historical_trend
from gni.metrics.v1_stats import V1ArticleInput, compute_v1_stat_snapshots


@pytest.fixture
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with SessionLocal() as session:
        session.add(Country(id="US", code="US", name="United States"))
        session.add(Organization(id="org_us", country_id="US", name="Wire"))
        session.add(
            Source(
                id="src_us",
                organization_id="org_us",
                country_id="US",
                name="US Wire",
                source_type="public_service",
                active_status="active",
            )
        )
        session.flush()
        yield session


def _t(day: int, hour: int = 12) -> datetime:
    return datetime(2026, 11, day, hour, 0, tzinfo=timezone.utc)


def test_p4_case1_to_5_metrics_dedup_topics_unclassified_country_source_time_window() -> None:
    """Covers duplicate URL/hash, multi-topic dedup, Unclassified, Source.country_id, SOURCE scope, and [start, end)."""
    p_start = _t(20, 0)
    p_end = _t(21, 0)

    rows = [
        # Duplicate URL tracking params -> must count once
        V1ArticleInput(
            article_id="a1",
            url="https://news.example.com/p1?utm_source=x",
            content_hash="h1",
            published_at=_t(20, 10),
            source_country="US",
            source_id="src_us_1",
            china_relevance_level="core",
            topics_v1=["semiconductors_export_controls", "tech_competition", "taiwan_strait"],
            stance_label="Negative",
            sentiment_label="negative",
            analysis_schema_version="article_analysis_v1.0",
        ),
        V1ArticleInput(
            article_id="a1_dup",
            url="https://news.example.com/p1?utm_medium=y",
            content_hash="h1_other",
            published_at=_t(20, 11),
            source_country="US",
            source_id="src_us_1",
            china_relevance_level="core",
            topics_v1=["semiconductors_export_controls"],
            stance_label="Negative",
            sentiment_label="negative",
            analysis_schema_version="article_analysis_v1.0",
        ),
        # Unclassified stance from UK outlet -> stays in total, excluded from P/N/N denominator
        V1ArticleInput(
            article_id="a2",
            url="https://uk.example.com/p2",
            content_hash="h2",
            published_at=_t(20, 15),
            source_country="GB",
            source_id="src_gb_1",
            china_relevance_level="substantial",
            topics_v1=["tariffs_trade_war"],
            stance_label="Unclassified",
            sentiment_label="mixed",
            analysis_schema_version="article_analysis_v1.0",
        ),
        # Exactly at period_end -> MUST BE EXCLUDED ([start, end))
        V1ArticleInput(
            article_id="a_out_of_window",
            url="https://uk.example.com/p3",
            content_hash="h3",
            published_at=p_end,
            source_country="GB",
            source_id="src_gb_1",
            china_relevance_level="core",
            topics_v1=["tariffs_trade_war"],
            stance_label="Positive",
            analysis_schema_version="article_analysis_v1.0",
        ),
    ]

    snaps = compute_v1_stat_snapshots(
        rows,
        period_start=p_start,
        period_end=p_end,
        include_zero_taxonomy=False,
        include_source_scope=True,
    )
    by_key = {(s.scope_type, s.scope_id): s for s in snaps}

    # Global: 2 unique in-window articles; 1 Negative, 1 Unclassified -> negative_rate = 1.0, coverage = 0.5
    g = by_key[("GLOBAL", "ALL")]
    assert g.article_count == 2
    assert g.negative_count == 1
    assert g.unclassified_count == 1
    assert g.negative_rate == 1.0
    assert g.stance_coverage_rate == 0.5
    assert g.sentiment_counts == {"negative": 1, "mixed": 1}

    # Country attribution strictly by source_country
    assert by_key[("COUNTRY", "US")].article_count == 1
    assert by_key[("COUNTRY", "GB")].article_count == 1
    # Source scope present
    assert by_key[("SOURCE", "src_us_1")].article_count == 1
    assert by_key[("SOURCE", "src_gb_1")].article_count == 1
    # Multi-topic same-board dedup: a1 has 2 topics in economy_tech, board economy_tech has a1 + a2 = 2
    assert by_key[("BOARD", "economy_tech")].article_count == 2
    board_keys = [k[1] for k in by_key if k[0] == "BOARD"]
    assert len(board_keys) == 2
    other_board = [b for b in board_keys if b != "economy_tech"][0]
    assert by_key[("BOARD", other_board)].article_count == 1


def test_p4_historical_trend_helper(db_session: Session) -> None:
    for d, cnt in [(18, 4), (19, 6), (20, 9)]:
        db_session.add(
            StatSnapshot(
                id=str(uuid4()),
                period_start=_t(d, 0),
                period_end=_t(d + 1, 0),
                scope_type="GLOBAL",
                scope_id="ALL",
                article_count=cnt,
                positive_count=1,
                neutral_count=1,
                negative_count=cnt - 2,
                unclassified_count=0,
                positive_rate=round(1 / cnt, 4),
                neutral_rate=round(1 / cnt, 4),
                negative_rate=round((cnt - 2) / cnt, 4),
                stance_coverage_rate=1.0,
                methodology_version="methodology_v1.0",
                taxonomy_version="taxonomy_v1.0",
                analysis_version="article_analysis_v1.0",
                article_ids=[],
                generated_at=_t(d + 1, 1),
            )
        )
    db_session.flush()
    trend = get_historical_trend(db_session, scope_type="GLOBAL", scope_id="ALL", limit=10)
    assert [t["article_count"] for t in trend] == [4, 6, 9]
    assert compute_consecutive_increase([t["article_count"] for t in trend]) == 2


def test_p4_case6_missing_event_time_never_filled_with_published_at() -> None:
    pub = _t(20, 8)
    cards = extract_from_structured_candidates(
        article_id="a_evt_1",
        structured={
            "event_candidates": [
                {
                    "event_relation": "new_event_candidate",
                    "actor": "US",
                    "action": "impose",
                    "object": "chip export controls",
                    "event_time": None,
                    "location": "Washington",
                    "summary": "US imposes chip export controls on China.",
                    "event_evidence_refs": ["ev_span_0"],
                    "confidence": 0.8,
                }
            ]
        },
        published_at=pub,
    )
    assert len(cards) == 1
    assert cards[0].event_time is None
    assert cards[0].published_at == pub


def test_p4_case7_change_detection_suppresses_small_sample_and_detects_real_shifts() -> None:
    # Small sample: 1 -> 2 (+100%) MUST be suppressed
    suppressed = detect_volume_change(
        subject="US",
        recent_count=2,
        baseline_mean=1.0,
        min_sample_size=5,
        min_abs_delta=3,
        min_rel_change=0.5,
        source_count=1,
    )
    assert suppressed is None

    # Real multi-source spike: baseline 3.0 -> 12 across 2 countries, 4 sources, 2 consecutive periods
    sig = detect_volume_change(
        subject="semiconductors_export_controls",
        signal_type="topic_shift",
        recent_count=12,
        baseline_mean=3.0,
        min_sample_size=5,
        min_abs_delta=3,
        min_rel_change=0.5,
        country_count=2,
        source_count=4,
        min_sources=2,
        consecutive_periods=2,
        supporting_articles=["a1", "a2"],
    )
    assert sig is not None
    assert sig.signal_type == "topic_shift"
    assert sig.confidence == "high"
    assert sig.trigger_metrics["abs_delta"] == 9.0

    # Stance shift & cross-country divergence
    base_snaps = compute_v1_stat_snapshots(
        [
            V1ArticleInput(
                article_id=f"b{i}",
                source_id="src_us",
                published_at=_t(19, i),
                source_country="US",
                china_relevance_level="core",
                topics_v1=["tariffs_trade_war"],
                stance_label="Neutral" if i < 4 else "Negative",
                analysis_schema_version="article_analysis_v1.0",
            )
            for i in range(6)
        ],
        period_start=_t(19, 0),
        period_end=_t(20, 0),
        include_zero_taxonomy=False,
    )
    rec_snaps = compute_v1_stat_snapshots(
        [
            V1ArticleInput(
                article_id=f"r{i}",
                source_id="src_us",
                published_at=_t(20, i),
                source_country="US",
                china_relevance_level="core",
                topics_v1=["tariffs_trade_war"],
                stance_label="Negative" if i < 5 else "Neutral",
                analysis_schema_version="article_analysis_v1.0",
            )
            for i in range(6)
        ],
        period_start=_t(20, 0),
        period_end=_t(21, 0),
        include_zero_taxonomy=False,
    )
    st_sig = detect_stance_shift(
        subject="US",
        recent_row=[s for s in rec_snaps if s.scope_type == "COUNTRY"][0],
        baseline_row=[s for s in base_snaps if s.scope_type == "COUNTRY"][0],
        min_classified=5,
        source_count=2,
    )
    assert st_sig is not None
    assert st_sig.signal_type == "stance_shift"

    div_rows = [
        V1ArticleInput(
            article_id=f"us_{i}",
            source_id="src_us",
            published_at=_t(20, i),
            source_country="US",
            china_relevance_level="core",
            topics_v1=["tariffs_trade_war"],
            stance_label="Negative",
            analysis_schema_version="article_analysis_v1.0",
        )
        for i in range(3)
    ] + [
        V1ArticleInput(
            article_id=f"sg_{i}",
            source_id="src_sg",
            published_at=_t(20, i),
            source_country="SG",
            china_relevance_level="core",
            topics_v1=["tariffs_trade_war"],
            stance_label="Positive",
            analysis_schema_version="article_analysis_v1.0",
        )
        for i in range(3)
    ]
    div_sig = detect_cross_country_divergence(div_rows, topic_id="tariffs_trade_war", min_per_country=3)
    assert div_sig is not None
    assert div_sig.signal_type == "cross_country_divergence"
    assert div_sig.trigger_metrics["rate_gap"] == 1.0


def test_p4_case8_event_false_merge_prevention_and_merge_split_audit(db_session: Session) -> None:
    # Different actors/actions sharing only "China" keyword MUST NOT merge
    c1 = FingerprintCard(
        article_id="art_1",
        actor="US",
        action="sanctions",
        object="semiconductor export controls on China",
        published_at=_t(20, 10),
        confidence=0.8,
    )
    c2 = FingerprintCard(
        article_id="art_2",
        actor="EU",
        action="signs",
        object="green aviation agreement with China",
        published_at=_t(20, 11),
        confidence=0.8,
    )
    clusters = cluster_fingerprints([c1, c2], use_llm=False)
    assert len(clusters) == 2

    # Traceable merge & split with EventRevision audit rows
    e1 = Event(id=str(uuid4()), title="Event A", status="proto")
    e2 = Event(id=str(uuid4()), title="Event B", status="proto")
    a1 = Article(id=str(uuid4()), source_id="src_us", title="A1", url=f"https://e.com/{uuid4()}")
    a2 = Article(id=str(uuid4()), source_id="src_us", title="A2", url=f"https://e.com/{uuid4()}")
    db_session.add_all([e1, e2, a1, a2])
    db_session.flush()
    db_session.add_all(
        [
            EventArticle(id=str(uuid4()), event_id=e1.id, article_id=a1.id),
            EventArticle(id=str(uuid4()), event_id=e2.id, article_id=a2.id),
        ]
    )
    db_session.flush()

    mres = merge_events(db_session, keep_id=e1.id, merge_id=e2.id, actor="analyst_1")
    assert mres["articles_moved"] == 1
    sres = split_event(
        db_session,
        source_event_id=e1.id,
        article_ids_to_split=[a2.id],
        new_title="Event B restored",
        actor="analyst_1",
    )
    assert sres["articles_moved"] == 1
    revs = db_session.scalars(select(EventRevision).where(EventRevision.event_id == e1.id)).all()
    assert {r.action for r in revs} == {"merge", "split"}


def test_p4_case9_narrative_aggregation_distinguishes_topic_and_keeps_counter_evidence(
    db_session: Session,
) -> None:
    items = [
        # Same frame + overlapping claim -> cluster together
        ArticleNarrativeInput(
            article_id="a1",
            country_id="US",
            published_at=_t(20, 9),
            frame="security_threat",
            claim="Advanced semiconductor exports strengthen military AI capabilities",
            attribution="support",
            tone="negative",
            quote="Advanced semiconductor exports strengthen military AI capabilities.",
            topic_ids=("semiconductors_export_controls",),
        ),
        ArticleNarrativeInput(
            article_id="a2",
            country_id="GB",
            published_at=_t(20, 12),
            frame="security_threat",
            claim="Analysts refute that semiconductor exports directly strengthen military AI",
            attribution="refute",
            tone="positive",
            quote="Analysts refute that semiconductor exports directly strengthen military AI.",
            topic_ids=("semiconductors_export_controls",),
        ),
        # SAME topic_id, DIFFERENT frame & claim -> MUST NOT cluster with above
        ArticleNarrativeInput(
            article_id="a3",
            country_id="DE",
            published_at=_t(20, 14),
            frame="economic_impact",
            claim="Automotive chip supply chains face higher procurement costs in Europe",
            attribution="mention",
            tone="neutral",
            quote="Automotive chip supply chains face higher procurement costs in Europe.",
            topic_ids=("semiconductors_export_controls",),
        ),
    ]
    clusters = cluster_narratives(items, min_claim_jaccard=0.25)
    assert len(clusters) == 2

    sec = [c for c in clusters if c.canonical_frame == "security_threat"][0]
    assert sec.related_articles == ["a1", "a2"]
    assert sec.related_countries == ["GB", "US"]
    assert len(sec.supporting_evidence) == 1
    assert len(sec.counter_evidence) == 1

    # Persist into existing NarrativeCluster + EventNarrativeEvidence ORM tables
    ev = Event(id=str(uuid4()), title="Chip controls debate", status="proto")
    db_session.add(ev)
    for aid in ("a1", "a2", "a3"):
        db_session.add(Article(id=aid, source_id="src_us", title=aid, url=f"https://e.com/{aid}"))
    db_session.flush()

    stats = persist_event_narratives(db_session, event_id=ev.id, clusters=clusters)
    assert stats["clusters_written"] == 2
    assert stats["evidence_written"] == 3
    assert len(db_session.scalars(select(NarrativeCluster)).all()) == 2
    assert len(db_session.scalars(select(EventNarrativeEvidence)).all()) == 3

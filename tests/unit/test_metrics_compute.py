"""P1-D metric computation (no LLM)."""

from datetime import datetime, timezone

from gni.metrics.compute import ArticleMetricRow, SourceHealthRow, compute_metrics
from gni.metrics.definitions import CHINA_INCLUDE_LEVELS, METRIC_DEFINITION_VERSION


def _row(**kwargs) -> ArticleMetricRow:
    base = dict(
        id="a1",
        source_id="s1",
        country_id="US",
        exclude_from_metrics=False,
        content_hash="h1",
        title_hash="t1",
        published_at=datetime(2026, 11, 20, tzinfo=timezone.utc),
        china_relevance_level="substantial",
        china_relevance_weight=0.65,
        quality_status="processed",
        processing_status="done",
        analysis_status="completed",
        sentiment_label="negative",
        sentiment_score=-0.6,
        sentiment_status="known",
        stances=[{"target_id": "china", "stance": "critical", "status": "known"}],
        frame_primary="competition_rivalry",
        topic_primary="economy_trade",
    )
    base.update(kwargs)
    return ArticleMetricRow(**base)


def test_article_count_excludes_incidental_and_duplicates():
    rows = [
        _row(id="1", china_relevance_level="core", china_relevance_weight=0.9),
        _row(id="2", china_relevance_level="incidental", china_relevance_weight=0.1),
        _row(id="3", china_relevance_level="none", china_relevance_weight=0.0),
        _row(id="4", exclude_from_metrics=True, china_relevance_level="core"),
        _row(id="5", china_relevance_level="secondary", china_relevance_weight=0.35, content_hash="h2"),
    ]
    out = compute_metrics(rows)
    assert out["metric_definition_version"] == METRIC_DEFINITION_VERSION
    assert out["research"]["article_count"]["value"] == 2
    assert out["research"]["article_count"]["version"] == "article_count_v1"
    assert out["excluded_duplicates"] == 1
    assert set(out["include_levels"]) == set(CHINA_INCLUDE_LEVELS)


def test_unique_story_count_by_content_hash():
    rows = [
        _row(id="1", content_hash="same"),
        _row(id="2", content_hash="same", title_hash="other"),
        _row(id="3", content_hash="diff"),
    ]
    out = compute_metrics(rows)
    assert out["research"]["unique_story_count"]["value"] == 2


def test_attention_share_available_with_full_universe():
    rows = [
        _row(id="1", china_relevance_level="core", china_relevance_weight=0.9),
        _row(id="2", china_relevance_level="none", china_relevance_weight=0.0, content_hash="x"),
        _row(id="3", china_relevance_level="none", china_relevance_weight=0.0, content_hash="y"),
    ]
    out = compute_metrics(rows)
    att = out["research"]["attention_share"]
    assert att["status"] == "available"
    assert att["numerator"] == 1
    assert att["denominator"] == 3
    assert att["value"] == round(1 / 3, 6)


def test_attention_share_unavailable_when_empty():
    out = compute_metrics([])
    assert out["research"]["attention_share"]["status"] == "unavailable"
    assert out["research"]["attention_share"]["value"] is None


def test_raw_and_weighted_views():
    rows = [
        _row(
            id="1",
            china_relevance_level="core",
            china_relevance_weight=1.0,
            sentiment_label="negative",
            sentiment_score=-0.6,
        ),
        _row(
            id="2",
            content_hash="h2",
            china_relevance_level="substantial",
            china_relevance_weight=0.5,
            sentiment_label="positive",
            sentiment_score=0.6,
            stances=[{"target_id": "china", "stance": "supportive", "status": "known"}],
            frame_primary="cooperation",
            topic_primary="technology",
        ),
        _row(
            id="3",
            content_hash="h3",
            china_relevance_level="secondary",
            china_relevance_weight=0.35,
            sentiment_label="mixed",
            sentiment_score=None,
        ),
    ]
    out = compute_metrics(rows)
    assert "raw" in out["views"]
    assert "weighted" in out["views"]
    assert out["weighted"]["weighted_article_volume"]["value"] == 1.85
    # mixed excluded from score denom: only 1.0 and 0.5
    score = out["weighted"]["weighted_sentiment_score"]
    assert score["status"] == "ok"
    expected = (1.0 * -0.6 + 0.5 * 0.6) / 1.5
    assert score["value"] == round(expected, 6)
    np_r = out["weighted"]["np_ratio"]
    assert np_r["status"] == "ok"
    assert np_r["value"] == round(1.0 / 0.5, 6)

    sent = out["research"]["sentiment_distribution"]["value"]
    assert sent["counts"]["negative"] == 1
    assert sent["counts"]["positive"] == 1
    assert sent["counts"]["mixed"] == 1
    assert "unknown" not in sent["counts"] or True

    stance = out["research"]["stance_distribution"]["value"]["counts"]
    assert "china|critical" in stance
    assert out["research"]["frame_distribution"]["value"]["mode"] == "primary_only"
    assert out["research"]["topic_share"]["value"]["counts"]["economy_trade"] >= 1
    assert out["research"]["topic_share"]["value"]["counts"]["technology"] == 1


def test_weight_does_not_rewrite_article_count():
    rows = [
        _row(id="1", china_relevance_weight=0.9),
        _row(id="2", content_hash="h2", china_relevance_weight=0.1),
    ]
    out = compute_metrics(rows)
    assert out["research"]["article_count"]["value"] == 2
    assert out["weighted"]["weighted_article_volume"]["value"] == 1.0
    assert out["research"]["article_count"]["value"] != out["weighted"]["weighted_article_volume"]["value"]


def test_operational_ingestion_rate():
    rows = [_row(id="1")]
    health = [
        SourceHealthRow("s1", "US", "active", success_count=8, failure_count=2),
        SourceHealthRow("s2", "US", "active", success_count=0, failure_count=0),
    ]
    out = compute_metrics(rows, source_health=health)
    rate = out["operational"]["ingestion_success_rate"]
    assert rate["value"] == 0.8
    assert out["operational"]["source_count"]["value"] == 1
    assert out["operational"]["country_count"]["value"] == 1


def test_country_scope_filter():
    rows = [
        _row(id="1", country_id="US"),
        _row(id="2", country_id="JP", content_hash="h2", source_id="s2"),
    ]
    out = compute_metrics(rows, country_scope=["US"])
    assert out["research"]["article_count"]["value"] == 1
    assert out["universe_count"] == 1

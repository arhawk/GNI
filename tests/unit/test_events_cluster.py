from datetime import datetime, timedelta, timezone

from gni.events.cluster import ArticleSeed, cluster_articles, jaccard
from gni.events.geo import centroid


def test_jaccard_basic():
    assert jaccard({"china", "trade"}, {"china", "tariff"}) == 1 / 3


def test_cluster_merges_similar_titles():
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    seeds = [
        ArticleSeed(
            id="a1",
            title="China trade talks resume in Brussels",
            source_id="s1",
            country_id="DE",
            published_at=t0,
            china_relevance_level="core",
            frame_primary="economic_cooperation",
            topic_primary="trade",
            sentiment_label="neutral",
        ),
        ArticleSeed(
            id="a2",
            title="China trade talks resume amid tariffs",
            source_id="s2",
            country_id="US",
            published_at=t0 + timedelta(hours=5),
            china_relevance_level="core",
            frame_primary="economic_competition",
            topic_primary="trade",
            sentiment_label="negative",
        ),
        ArticleSeed(
            id="a3",
            title="Unrelated cricket scores overnight",
            source_id="s3",
            country_id="IN",
            published_at=t0,
            china_relevance_level="incidental",
            frame_primary=None,
            topic_primary="other",
            sentiment_label=None,
        ),
    ]
    clusters = cluster_articles(seeds, similarity=0.3)
    multi = [c for c in clusters if len(c.article_ids) >= 2]
    assert len(multi) == 1
    assert set(multi[0].article_ids) == {"a1", "a2"}
    assert multi[0].country_ids == {"DE", "US"}


def test_centroid_known():
    assert centroid("US") is not None
    assert centroid("zz") is None

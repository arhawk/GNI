"""Batch2/3 smoke: geo maritime, attention gate, alerts dedupe helpers, weekly builder import."""

from datetime import datetime, timezone

from gni.events.fingerprint import normalize_action, normalize_actor
from gni.events.geo import location_pin_spec
from gni.metrics.compute import ArticleMetricRow, compute_metrics
from gni.sources.seed import infer_feed_scope


def test_maritime_no_fake_coords():
    pin = location_pin_spec(text="Tensions rise in the South China Sea")
    assert pin["geographic_precision"] == "maritime"
    assert pin["lat"] is None and pin["lon"] is None
    assert pin["country_id"] is None


def test_city_pin_may_have_coords():
    pin = location_pin_spec(text="Talks in Beijing")
    assert pin["geographic_precision"] == "city"
    assert pin["country_id"] == "CN"
    assert pin["lat"] is not None


def test_attention_unavailable_for_china_focused_denom():
    now = datetime.now(timezone.utc)
    rows = [
        ArticleMetricRow(
            id=f"a{i}",
            source_id="us_voa_english",
            country_id="US",
            published_at=now,
            first_seen_at=now,
            china_relevance_level="substantial",
            feed_scope="CHINA_FOCUSED",
        )
        for i in range(4)
    ] + [
        ArticleMetricRow(
            id="b1",
            source_id="us_voa_english",
            country_id="US",
            published_at=now,
            first_seen_at=now,
            china_relevance_level="none",
            feed_scope="CHINA_FOCUSED",
        )
    ]
    out = compute_metrics(rows)
    att = out["research"]["attention_share"]
    assert att["status"] == "unavailable"
    assert att["value"] is None


def test_infer_feed_scope_voa_china():
    assert (
        infer_feed_scope(
            {
                "source_id": "us_voa_english",
                "name": "Voice of America — China News (RSS)",
                "feed_scope": "CHINA_FOCUSED",
            }
        )
        == "CHINA_FOCUSED"
    )
    assert (
        infer_feed_scope(
            {
                "source_id": "us_state_press",
                "name": "U.S. Department of State — Press Releases",
                "source_type": "gov_comms",
            }
        )
        == "GOVERNMENT_RELEASES"
    )


def test_fingerprint_no_fake_and_imports():
    assert normalize_actor("zzz_unknown_actor") is None
    assert normalize_action("zzz_unknown_verb") is None
    from gni.reports.monthly import build_monthly_report, SCHEMA_VERSION as M
    from gni.reports.weekly import build_weekly_report, SCHEMA_VERSION as W

    assert W.startswith("weekly")
    assert M.startswith("monthly")
    assert callable(build_weekly_report) and callable(build_monthly_report)


def test_daily_sentiment_bar_skips_government():
    from types import SimpleNamespace

    from gni.reports.daily import _sentiment_bar_from_evidence

    sources = {
        "a": SimpleNamespace(feed_scope="INTERNATIONAL_NEWS"),
        "g": SimpleNamespace(feed_scope="GOVERNMENT_RELEASES"),
    }
    out = _sentiment_bar_from_evidence(
        [
            {"source_id": "a", "sentiment": "positive"},
            {"source_id": "a", "sentiment": "negative"},
            {"source_id": "g", "sentiment": "negative"},
        ],
        sources,
    )
    assert out["sentiment_n"] == 2
    assert out["sentiment_skipped_government"] == 1
    assert out["sentiment_counts"]["positive"] == 1
    assert out["sentiment_counts"]["negative"] == 1

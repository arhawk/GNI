"""Unit tests for GdeltAdapter, cross-source URL deduplication, and seed config."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from gni.infrastructure.models import Article, Base, Country, Organization, Source
from gni.ingestion.gdelt_adapter import GdeltAdapter, _parse_gdelt_seendate
from gni.ingestion.service import get_adapter, upsert_article
from gni.reports.risk_tagging import MEDIA_TYPE_ZH, media_type_bucket
from gni.sources.seed import load_seed_file


def _mem_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_gdelt_adapter_registered_and_parses_item():
    adapter = get_adapter("gdelt_adapter")
    assert isinstance(adapter, GdeltAdapter)

    raw = {
        "url": "https://www.reuters.com/world/china/example-2026-11-26/",
        "title": "US and China hold trade talks in Geneva",
        "seendate": "20261126T081500Z",
        "domain": "reuters.com",
        "language": "English",
        "sourcecountry": "United States",
    }
    parsed = adapter.parse(raw)
    assert parsed["url"] == raw["url"]
    assert parsed["canonical_url"] == raw["url"]
    assert parsed["title"] == raw["title"]
    assert parsed["published_at"] == datetime(2026, 11, 26, 8, 15, 0, tzinfo=timezone.utc)
    assert parsed["language"] == "en"
    assert parsed["quality_status"] == "gdelt_stub"
    assert parsed["discovery_provider"] == "gdelt"
    assert parsed["origin_domain"] == "reuters.com"
    assert _parse_gdelt_seendate("invalid") is None


def test_gdelt_adapter_fetch_retries_429_then_succeeds():
    adapter = GdeltAdapter(max_attempts=3, min_interval_sec=0.0)
    req = httpx.Request("GET", "https://api.gdeltproject.org/api/v2/doc/doc")
    resp_429 = httpx.Response(429, text="Please limit requests to one every 5 seconds", request=req)
    resp_200 = httpx.Response(
        200,
        json={"articles": [{"url": "https://example.com/a", "title": "China news"}]},
        request=req,
    )

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.get.side_effect = [resp_429, resp_200]

    with (
        patch("gni.ingestion.gdelt_adapter.httpx.Client", return_value=mock_client),
        patch("tenacity.nap.time.sleep", return_value=None),
    ):
        items = adapter.fetch({"query": "China sourcecountry:US"})

    assert len(items) == 1
    assert items[0]["url"] == "https://example.com/a"
    assert mock_client.get.call_count == 2


def test_gdelt_adapter_fetch_does_not_retry_400():
    adapter = GdeltAdapter(max_attempts=3, min_interval_sec=0.0)
    req = httpx.Request("GET", "https://api.gdeltproject.org/api/v2/doc/doc")
    resp_400 = httpx.Response(400, text="Bad query", request=req)

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.get.return_value = resp_400

    with patch("gni.ingestion.gdelt_adapter.httpx.Client", return_value=mock_client):
        with pytest.raises(httpx.HTTPStatusError):
            adapter.fetch({"query": "invalid"})

    assert mock_client.get.call_count == 1


def test_upsert_article_cross_source_dedupe_preserves_native_rss():
    session = _mem_session()
    session.add(Country(id="US", code="US", name="United States"))
    session.add(Organization(id="org_rss", country_id="US", name="Native RSS Org"))
    session.add(Organization(id="org_gdelt", country_id="US", name="GDELT"))
    rss_src = Source(
        id="us_native_rss",
        organization_id="org_rss",
        country_id="US",
        name="Native RSS",
        source_type="mainstream_independent",
        adapter_type="rss_adapter",
        language="en",
    )
    gdelt_src = Source(
        id="us_gdelt_china",
        organization_id="org_gdelt",
        country_id="US",
        name="GDELT US",
        source_type="aggregator_discovery",
        adapter_type="gdelt_adapter",
        language="multi",
        config={"discovery_provider": "gdelt"},
    )
    session.add_all([rss_src, gdelt_src])
    session.flush()

    shared_url = "https://example.com/china-tariffs-2026"
    rss_art, created1 = upsert_article(
        session,
        rss_src,
        {"url": shared_url, "title": "Original RSS Title", "content_original": "RSS body"},
    )
    session.flush()
    assert created1 is True

    # GDELT discovers the same URL: must return the native RSS article without creating a duplicate.
    gdelt_dup, created2 = upsert_article(
        session,
        gdelt_src,
        {"url": shared_url, "title": "GDELT Title", "language": "en"},
    )
    assert created2 is False
    assert gdelt_dup.id == rss_art.id
    assert gdelt_dup.source_id == "us_native_rss"
    assert gdelt_dup.title == "Original RSS Title"

    # GDELT discovers a new URL: creates a new article with resolved language.
    gdelt_new, created3 = upsert_article(
        session,
        gdelt_src,
        {
            "url": "https://example.com/unique-gdelt-story",
            "title": "Unique GDELT Story",
            "language": "de",
            "quality_status": "gdelt_stub",
        },
    )
    session.flush()
    assert created3 is True
    assert gdelt_new.source_id == "us_gdelt_china"
    assert gdelt_new.language == "de"
    assert len(session.scalars(select(Article)).all()) == 2


def test_seed_contains_new_worldmonitor_and_gdelt_sources():
    data = load_seed_file()
    by_id = {s["source_id"]: s for s in data["sources"]}
    for expected in (
        "de_tagesschau",
        "de_spiegel",
        "de_dw_german",
        "in_toi_world",
        "in_ht_world",
        "in_et_news",
        "in_livemint_news",
        "us_rfa_mandarin",
        "us_the_diplomat",
        "us_gdelt_china",
        "in_gdelt_china",
        "de_gdelt_china",
        "ru_gdelt_china",
        "au_gdelt_china",
        "ru_moscow_times",
        "ru_meduza",
        "ru_rt_russia",
        "au_smh_world",
        "au_sbs_world",
        "au_abc_justin",
    ):
        assert expected in by_id
        assert by_id[expected]["active_status"] == "active"

    assert media_type_bucket(MagicMock(source_type="aggregator_discovery", feed_scope="CHINA_FOCUSED")) == "aggregator_discovery"
    assert MEDIA_TYPE_ZH["aggregator_discovery"] == "聚合发现"

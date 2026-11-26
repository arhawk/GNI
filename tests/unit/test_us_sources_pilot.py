"""Unit tests for US Sources Pilot: RSS/Atom parse, 403/429 handling, and seed hygiene."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest
import yaml

from gni.ingestion.rss_adapter import RssAdapter, parse_feed_xml

RSS2_SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <title>Sample US Feed</title>
  <item>
    <title>Item With Date</title>
    <link>https://example.com/a1</link>
    <pubDate>Thu, 26 Nov 2026 02:30:00 GMT</pubDate>
    <description>Summary A</description>
  </item>
  <item>
    <title>Item Missing Date</title>
    <link>https://example.com/a2</link>
  </item>
</channel></rss>
"""

ATOM_SAMPLE = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Sample Atom</title>
  <entry>
    <title>Atom Story</title>
    <link href="https://example.com/atom1"/>
    <updated>2026-11-26T03:00:00Z</updated>
    <summary>Atom summary</summary>
  </entry>
</feed>
"""


def test_rss2_and_missing_published_stays_none():
    items = parse_feed_xml(RSS2_SAMPLE)
    assert len(items) == 2
    assert items[0]["title"] == "Item With Date"
    assert items[0]["published_at"] is not None
    assert items[0]["time_precision"] == "second"
    assert items[1]["title"] == "Item Missing Date"
    assert items[1]["published_at"] is None
    assert items[1]["time_precision"] == "unknown"


def test_atom_parse():
    items = parse_feed_xml(ATOM_SAMPLE)
    assert len(items) == 1
    assert items[0]["title"] == "Atom Story"
    assert items[0]["url"] == "https://example.com/atom1"
    assert items[0]["published_at"] is not None


def test_rss_403_does_not_retry():
    calls = {"n": 0}

    def fake_get(self, url):  # noqa: ANN001
        calls["n"] += 1
        req = httpx.Request("GET", url)
        return httpx.Response(403, request=req)

    adapter = RssAdapter(max_attempts=3)
    with patch.object(httpx.Client, "get", fake_get):
        with pytest.raises(httpx.HTTPStatusError):
            adapter.fetch({"feed_url": "https://example.com/403.xml"})
    assert calls["n"] == 1


def test_rss_429_surfaces_retry_after():
    def fake_get(self, url):  # noqa: ANN001
        req = httpx.Request("GET", url)
        return httpx.Response(429, headers={"Retry-After": "120"}, request=req)

    adapter = RssAdapter(max_attempts=1)
    with patch.object(httpx.Client, "get", fake_get):
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            adapter.fetch({"feed_url": "https://example.com/429.xml"})
    assert "Retry-After: 120" in str(exc_info.value)


def test_us_sources_seed_pilot_hygiene():
    seed_path = Path(__file__).resolve().parents[2] / "configs" / "sources_seed.yaml"
    data = yaml.safe_load(seed_path.read_text(encoding="utf-8"))
    orgs = {o["id"] for o in data.get("organizations") or []}
    us_sources = [s for s in (data.get("sources") or []) if s.get("country_id") == "US"]
    active_us = [s for s in us_sources if s.get("active_status") == "active"]

    # Pilot active US feeds, each bound to a registered organization
    assert 5 <= len(active_us) <= 20
    for s in us_sources:
        assert s.get("organization_id") in orgs
        assert s.get("source_type") in {
            "state_controlled",
            "public_service",
            "mainstream_independent",
            "gov_comms",
        }
        assert s.get("feed_scope") in {
            "CHINA_FOCUSED",
            "INTERNATIONAL_NEWS",
            "GENERAL_NEWS",
            "GOVERNMENT_RELEASES",
            "TOPIC_FEED",
        }

    # Diversity: at least 3 distinct organizations, 3 source_types, 3 feed_scopes among active US
    assert len({s["organization_id"] for s in active_us}) >= 3
    assert len({s["source_type"] for s in active_us}) >= 3
    assert len({s["feed_scope"] for s in active_us}) >= 3

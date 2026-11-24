from pathlib import Path

import httpx
import pytest

from gni.ingestion.rss_adapter import RssAdapter, parse_feed_xml

FIXTURE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Synthetic Fixture Feed</title>
    <item>
      <title>China technology export rules</title>
      <link>https://example.test/articles/1</link>
      <description>Synthetic summary about technology.</description>
      <pubDate>Mon, 23 Nov 2026 10:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Another item</title>
      <link>https://example.test/articles/2</link>
      <description>More synthetic text.</description>
    </item>
  </channel>
</rss>
"""


def test_parse_feed_xml_fixture():
    items = parse_feed_xml(FIXTURE)
    assert len(items) == 2
    assert items[0]["url"] == "https://example.test/articles/1"
    assert items[0]["title"] == "China technology export rules"
    assert items[0]["quality_status"] == "rss_stub"
    assert items[0]["published_at"] is not None


def test_rss_adapter_retries_then_succeeds(monkeypatch):
    adapter = RssAdapter(max_attempts=3, timeout=5.0)
    calls = {"n": 0}

    class FakeResponse:
        def __init__(self, text: str, status_code: int = 200):
            self.text = text
            self.status_code = status_code

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                raise httpx.HTTPStatusError(
                    "error",
                    request=httpx.Request("GET", "https://example.test/feed"),
                    response=httpx.Response(self.status_code),
                )

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url: str):
            calls["n"] += 1
            if calls["n"] < 2:
                raise httpx.ConnectError("temporary")
            return FakeResponse(FIXTURE)

    monkeypatch.setattr("gni.ingestion.rss_adapter.httpx.Client", FakeClient)
    entries = adapter.fetch({"feed_url": "https://example.test/feed.xml"})
    assert len(entries) == 2
    assert calls["n"] == 2


def test_rss_adapter_rejects_tbd():
    adapter = RssAdapter()
    with pytest.raises(ValueError, match="TBD"):
        adapter.fetch({"feed_url": "TBD"})


def test_rss_adapter_uses_per_source_user_agent(monkeypatch):
    adapter = RssAdapter(user_agent="default-bot")
    seen: dict[str, str] = {}

    class FakeResponse:
        text = FIXTURE
        status_code = 200

        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        def __init__(self, *args, **kwargs):
            seen["ua"] = kwargs.get("headers", {}).get("User-Agent", "")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url: str):
            return FakeResponse()

    monkeypatch.setattr("gni.ingestion.rss_adapter.httpx.Client", FakeClient)
    adapter.fetch(
        {
            "feed_url": "https://example.test/feed.xml",
            "user_agent": "custom-ua-for-source",
        }
    )
    assert seen["ua"] == "custom-ua-for-source"


def test_fixture_file_marked_synthetic():
    path = Path(__file__).resolve().parents[2] / "data" / "samples" / "synthetic_rss.xml"
    text = path.read_text(encoding="utf-8")
    assert "Synthetic" in text
    assert len(parse_feed_xml(text)) == 2

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

from gni.ingestion.service import _hash_text, get_adapter, upsert_article
from gni.ingestion.rss_adapter import RssAdapter


def test_get_adapter_rss():
    assert isinstance(get_adapter("rss_adapter"), RssAdapter)


def test_hash_text_stable():
    assert _hash_text("abc") == _hash_text("abc")
    assert _hash_text(None) is None


def test_upsert_article_insert_then_update():
    session = MagicMock()
    session.scalar.return_value = None
    source = SimpleNamespace(id="us_rfa_english", language="en", timezone="UTC")
    item = {
        "title": "Hello",
        "url": "https://example.test/a",
        "content_original": "body",
        "published_at": datetime(2026, 11, 23, tzinfo=timezone.utc),
        "quality_status": "rss_stub",
    }
    article, created = upsert_article(session, source, item)
    assert created is True
    session.add.assert_called()
    assert article.url == "https://example.test/a"

    existing = SimpleNamespace(
        title="Old",
        content_original="old",
        published_at=None,
        content_hash=None,
        title_hash=None,
        updated_at=None,
    )
    session.scalar.return_value = existing
    article2, created2 = upsert_article(session, source, {**item, "title": "New"})
    assert created2 is False
    assert existing.title == "New"

"""RSS adapter using httpx + feedparser with retries."""

from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from time import struct_time
from typing import Any

import feedparser
import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from gni.ingestion.base import BaseAdapter

DEFAULT_UA = "GNI-ResearchBot/0.1 (+internal-research; mailto:research@localhost)"


def _struct_time_to_dt(value: struct_time | None) -> datetime | None:
    if value is None:
        return None
    return datetime(*value[:6], tzinfo=timezone.utc)


def _parse_published(entry: dict[str, Any]) -> datetime | None:
    dt = _struct_time_to_dt(entry.get("published_parsed")) or _struct_time_to_dt(
        entry.get("updated_parsed")
    )
    if dt is not None:
        return dt
    raw = entry.get("published") or entry.get("updated")
    if not raw:
        return None
    try:
        parsed = parsedate_to_datetime(raw)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError, IndexError):
        return None


class RssAdapter(BaseAdapter):
    def __init__(
        self,
        *,
        timeout: float = 30.0,
        user_agent: str = DEFAULT_UA,
        max_attempts: int = 3,
    ) -> None:
        self.timeout = timeout
        self.user_agent = user_agent
        self.max_attempts = max_attempts

    def fetch(self, source_config: dict[str, Any]) -> list[Any]:
        feed_url = source_config.get("feed_url") or source_config.get("feed_or_api_url")
        if not feed_url or feed_url == "TBD":
            raise ValueError("RSS feed_url missing or TBD")

        @retry(
            reraise=True,
            stop=stop_after_attempt(self.max_attempts),
            wait=wait_exponential(multiplier=0.5, min=0.5, max=8),
            retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
        )
        def _get() -> str:
            with httpx.Client(
                timeout=self.timeout,
                follow_redirects=True,
                headers={"User-Agent": self.user_agent},
            ) as client:
                response = client.get(feed_url)
                response.raise_for_status()
                return response.text

        body = _get()
        parsed = feedparser.parse(body)
        if getattr(parsed, "bozo", False) and not parsed.entries:
            raise ValueError(f"Failed to parse RSS feed: {getattr(parsed, 'bozo_exception', '')}")
        return list(parsed.entries)

    def parse(self, raw_item: Any) -> dict[str, Any]:
        entry = raw_item if isinstance(raw_item, dict) else dict(raw_item)
        link = (entry.get("link") or "").strip()
        title = (entry.get("title") or "").strip() or None
        summary = entry.get("summary") or entry.get("description") or ""
        if isinstance(summary, str):
            summary = summary.strip()
        else:
            summary = str(summary)
        published_at = _parse_published(entry)
        return {
            "title": title,
            "url": link,
            "canonical_url": link or None,
            "content_original": summary or None,
            "published_at": published_at,
            "time_precision": "second" if published_at else "unknown",
            "quality_status": "rss_stub",
        }

    def health_check(self, source_config: dict[str, Any]) -> dict[str, str]:
        try:
            entries = self.fetch(source_config)
            return {"status": "ok", "entries": str(len(entries))}
        except Exception as exc:  # noqa: BLE001 — surface adapter health
            return {"status": "error", "error": str(exc)}


def parse_feed_xml(xml_text: str) -> list[dict[str, Any]]:
    """Parse feed XML without network — for unit tests."""
    adapter = RssAdapter()
    parsed = feedparser.parse(xml_text)
    return [adapter.parse(e) for e in parsed.entries]

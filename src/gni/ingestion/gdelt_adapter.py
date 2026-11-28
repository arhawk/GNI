"""GDELT DOC 2.0 API adapter with polite rate limiting and 429 backoff."""

from __future__ import annotations

import fcntl
import logging
import random
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_random_exponential

from gni.ingestion.base import BaseAdapter
from gni.ingestion.rss_adapter import DEFAULT_UA

logger = logging.getLogger(__name__)

GDELT_DOC_ENDPOINT = "https://api.gdeltproject.org/api/v2/doc/doc"
_NON_RETRYABLE_STATUS = {400, 401, 403, 404, 407, 410}
_RATE_LOCK = threading.Lock()
_LAST_REQUEST_TS: float = 0.0
DEFAULT_LOCK_PATH = Path(__file__).resolve().parents[3] / "data" / "gdelt_rate_limit.lock"

_LANG_MAP = {
    "english": "en",
    "chinese": "zh",
    "german": "de",
    "russian": "ru",
    "hindi": "hi",
    "french": "fr",
    "spanish": "es",
    "japanese": "ja",
    "korean": "ko",
}


def _is_retryable_gdelt_exc(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code if exc.response is not None else 0
        if code in _NON_RETRYABLE_STATUS:
            return False
        return code == 429 or code >= 500
    return isinstance(exc, (httpx.HTTPError, httpx.TimeoutException))


def _parse_gdelt_seendate(value: str | None) -> datetime | None:
    if not value:
        return None
    raw = value.strip()
    for fmt in ("%Y%m%dT%H%M%SZ", "%Y%m%d%H%M%S", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _normalize_language(value: str | None) -> str | None:
    if not value:
        return None
    low = value.strip().lower()
    if low in _LANG_MAP:
        return _LANG_MAP[low]
    if len(low) == 2:
        return low
    return low[:16]


class GdeltAdapter(BaseAdapter):
    """Fetch China-focused discovery articles from GDELT DOC 2.0 ArtList JSON API."""

    def __init__(
        self,
        *,
        timeout: float = 45.0,
        user_agent: str = DEFAULT_UA,
        max_attempts: int = 5,
        min_interval_sec: float = 10.0,
        jitter_sec: float = 2.5,
        lock_path: Path | None = DEFAULT_LOCK_PATH,
    ) -> None:
        self.timeout = timeout
        self.user_agent = user_agent
        self.max_attempts = max_attempts
        self.min_interval_sec = min_interval_sec
        self.jitter_sec = jitter_sec
        self.lock_path = lock_path

    def _wait_rate_limit(self) -> None:
        """Enforce minimum spacing across threads AND processes via file lock."""
        global _LAST_REQUEST_TS
        if self.min_interval_sec <= 0:
            return
        target_gap = self.min_interval_sec + (
            random.uniform(0.0, self.jitter_sec) if self.jitter_sec > 0 else 0.0
        )
        with _RATE_LOCK:
            if self.lock_path is not None:
                self.lock_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.lock_path, "a+", encoding="utf-8") as fh:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
                    try:
                        fh.seek(0)
                        raw = fh.read().strip()
                        last_ts = float(raw) if raw else 0.0
                        now = time.time()
                        elapsed = now - last_ts
                        if last_ts > 0 and elapsed < target_gap:
                            time.sleep(target_gap - elapsed)
                        now = time.time()
                        fh.seek(0)
                        fh.truncate()
                        fh.write(f"{now:.6f}")
                        fh.flush()
                        _LAST_REQUEST_TS = time.monotonic()
                    finally:
                        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
                return

            now = time.monotonic()
            elapsed = now - _LAST_REQUEST_TS
            if _LAST_REQUEST_TS > 0 and elapsed < target_gap:
                time.sleep(target_gap - elapsed)
            _LAST_REQUEST_TS = time.monotonic()

    def fetch(self, source_config: dict[str, Any]) -> list[Any]:
        query = (source_config.get("query") or "").strip()
        if not query:
            raise ValueError("GDELT source_config requires 'query'")
        endpoint = (
            source_config.get("api_url")
            or source_config.get("feed_or_api_url")
            or GDELT_DOC_ENDPOINT
        )
        maxrecords = int(source_config.get("maxrecords") or 50)
        timespan = str(source_config.get("timespan") or "24h")
        sort = str(source_config.get("sort") or "DateDesc")
        params = {
            "query": query,
            "mode": "ArtList",
            "format": "json",
            "maxrecords": str(max(1, min(maxrecords, 250))),
            "timespan": timespan,
            "sort": sort,
        }
        headers = {
            "User-Agent": source_config.get("user_agent") or self.user_agent,
            "Accept": "application/json, */*",
            "X-GNI-Client": "GNI-ResearchBot/0.1",
        }

        @retry(
            reraise=True,
            stop=stop_after_attempt(self.max_attempts),
            wait=wait_random_exponential(multiplier=8.0, min=8.0, max=40.0),
            retry=retry_if_exception(_is_retryable_gdelt_exc),
        )
        def _get() -> dict[str, Any]:
            self._wait_rate_limit()
            with httpx.Client(
                timeout=self.timeout,
                follow_redirects=True,
                headers=headers,
            ) as client:
                response = client.get(endpoint, params=params)
                if response.status_code == 429:
                    msg = f"HTTP 429 Too Many Requests from GDELT: {response.text[:160]}"
                    raise httpx.HTTPStatusError(
                        msg, request=response.request, response=response
                    )
                response.raise_for_status()
                text = (response.text or "").strip()
                if not text:
                    return {"articles": []}
                return response.json()

        payload = _get()
        articles = payload.get("articles") if isinstance(payload, dict) else None
        if not isinstance(articles, list):
            return []
        return articles

    def parse(self, raw_item: Any) -> dict[str, Any]:
        item = raw_item if isinstance(raw_item, dict) else {}
        url = (item.get("url") or "").strip()
        title = (item.get("title") or "").strip() or None
        domain = (item.get("domain") or "").strip() or None
        sourcecountry = (item.get("sourcecountry") or "").strip() or None
        published_at = _parse_gdelt_seendate(item.get("seendate"))
        language = _normalize_language(item.get("language"))
        summary_parts = [p for p in (title, f"Source domain: {domain}" if domain else None) if p]
        return {
            "title": title,
            "url": url,
            "canonical_url": url,
            "content_original": " — ".join(summary_parts) if summary_parts else None,
            "published_at": published_at,
            "language": language,
            "quality_status": "gdelt_stub",
            "time_precision": "minute" if published_at else None,
            "discovery_provider": "gdelt",
            "origin_domain": domain,
            "origin_country": sourcecountry,
        }

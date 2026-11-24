"""Fetch article HTML and extract main text."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx
from bs4 import BeautifulSoup
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from gni.ingestion.rss_adapter import DEFAULT_UA
from gni.processing.normalize import clean_extracted_text

logger = logging.getLogger(__name__)

MIN_CHARS = 80


@dataclass
class ExtractionResult:
    content_clean: str | None
    raw_html_excerpt: str | None
    method: str
    quality_status: str
    error_message: str | None = None


def _bs4_extract(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript", "nav", "footer", "header", "aside"]):
        tag.decompose()
    article = soup.find("article")
    root = article or soup.find("main") or soup.body or soup
    paragraphs = [p.get_text(" ", strip=True) for p in root.find_all(["p", "h1", "h2", "h3"])]
    if paragraphs:
        return clean_extracted_text("\n\n".join(p for p in paragraphs if p))
    return clean_extracted_text(root.get_text("\n", strip=True))


def extract_from_html(html: str) -> ExtractionResult:
    if not html or not html.strip():
        return ExtractionResult(None, None, "empty", "insufficient_text", "empty html")

    excerpt = html[:8000]
    text: str | None = None
    method = "bs4"
    try:
        import trafilatura

        extracted = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=False,
            favor_precision=True,
        )
        if extracted and len(extracted.strip()) >= MIN_CHARS:
            text = clean_extracted_text(extracted)
            method = "trafilatura"
    except Exception as exc:  # noqa: BLE001
        logger.debug("trafilatura failed: %s", exc)

    if text is None:
        try:
            text = _bs4_extract(html)
            method = "bs4"
        except Exception as exc:  # noqa: BLE001
            return ExtractionResult(None, excerpt, "failed", "insufficient_text", str(exc)[:500])

    if not text or len(text) < MIN_CHARS:
        return ExtractionResult(
            text,
            excerpt,
            method,
            "insufficient_text",
            f"extracted text too short ({len(text or '')} chars)",
        )
    return ExtractionResult(text, excerpt, method, "extracted", None)


def fetch_html(
    url: str,
    *,
    user_agent: str | None = None,
    timeout: float = 30.0,
) -> str:
    headers = {
        "User-Agent": user_agent or DEFAULT_UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "X-GNI-Client": "GNI-ResearchBot/0.1",
    }

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=8),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    )
    def _get() -> str:
        with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.text

    return _get()


def fetch_and_extract(url: str, source_config: dict[str, Any] | None = None) -> ExtractionResult:
    cfg = source_config or {}
    try:
        html = fetch_html(url, user_agent=cfg.get("user_agent"))
    except Exception as exc:  # noqa: BLE001
        return ExtractionResult(None, None, "fetch_failed", "insufficient_text", str(exc)[:500])
    return extract_from_html(html)

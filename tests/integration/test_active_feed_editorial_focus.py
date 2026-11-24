"""Live feed quality: active sources must carry international/China title mix.

Marked integration — needs network. Skip cleanly when offline.
"""

from __future__ import annotations

import httpx
import feedparser
import pytest

from gni.sources.editorial_focus import DEFAULT_MIN_INTL_OR_CHINA_RATIO, passes_editorial_focus
from gni.sources.seed import DEFAULT_SEED, load_seed_file

BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
TITLE_SAMPLE_N = 25


def _fetch_titles(url: str, *, user_agent: str | None = None) -> list[str]:
    headers = {
        "User-Agent": user_agent or BROWSER_UA,
        "Accept": "application/rss+xml, application/xml, text/xml, */*",
        "X-GNI-Client": "GNI-ResearchBot/0.1",
    }
    with httpx.Client(timeout=30.0, follow_redirects=True, headers=headers) as client:
        response = client.get(url)
        response.raise_for_status()
        parsed = feedparser.parse(response.content)
    return [e.get("title") or "" for e in parsed.entries[:TITLE_SAMPLE_N]]


@pytest.mark.integration
def test_active_feeds_meet_intl_or_china_ratio():
    try:
        httpx.get("https://example.com", timeout=5.0).raise_for_status()
    except Exception as exc:  # noqa: BLE001 — offline skip
        pytest.skip(f"network unavailable: {exc}")

    data = load_seed_file(DEFAULT_SEED)
    active = [s for s in data["sources"] if s.get("active_status") == "active"]
    failures: list[str] = []

    for row in active:
        sid = row["source_id"]
        url = row.get("feed_or_api_url") or ""
        ua = (row.get("config") or {}).get("user_agent")
        try:
            titles = _fetch_titles(url, user_agent=ua)
        except Exception as exc:  # noqa: BLE001 — collect per-source
            # Transient rate limits (e.g. RFA 429) — soft-skip that source
            if "429" in str(exc):
                continue
            failures.append(f"{sid}: fetch error {exc}")
            continue

        ok, detail = passes_editorial_focus(
            titles,
            source_id=sid,
            name=row.get("name") or "",
            feed_url=url,
            min_ratio=DEFAULT_MIN_INTL_OR_CHINA_RATIO,
        )
        if not ok:
            sample = "; ".join(titles[:5]) or "(no titles)"
            failures.append(
                f"{sid}: rate={detail['rate']:.2f} < threshold={detail['threshold']} "
                f"n={detail['n']} sample=[{sample}]"
            )

    assert not failures, "active feed editorial focus failures:\n" + "\n".join(failures)

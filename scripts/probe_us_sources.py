#!/usr/bin/env python3
"""Read-only probe for US existing + P1/P2 candidate RSS feeds.

Checks HTTP status, RSS/Atom parse, latest 2 items (title, url, published_at in UTC & Asia/Shanghai),
whether today's news (Asia/Shanghai) is present, and lightweight HTTP reachability of the 2 article URLs.
Writes a markdown log to docs/source-research/US_SOURCE_PROBE_LOG.md.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import feedparser
import httpx

from gni.ingestion.rss_adapter import DEFAULT_UA, _parse_published

SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
BROWSER_COMPAT_UA = "Mozilla/5.0 (compatible; GNI-ResearchBot/0.1; +internal-research)"

CANDIDATES: list[dict[str, Any]] = [
    # Existing active US sources
    {
        "group": "existing_active",
        "source_id": "us_voa_english",
        "name": "Voice of America — China News (RSS)",
        "source_type": "state_controlled",
        "feed_scope": "CHINA_FOCUSED",
        "url": "https://www.voanews.com/api/zmjuqtl-vomx-tpey_jqq",
        "ua": DEFAULT_UA,
    },
    {
        "group": "existing_active",
        "source_id": "us_voa_east_asia",
        "name": "Voice of America — East Asia News (RSS)",
        "source_type": "state_controlled",
        "feed_scope": "CHINA_FOCUSED",
        "url": "https://www.voanews.com/api/zobo_l-vomx-tpepvmv",
        "ua": DEFAULT_UA,
    },
    {
        "group": "existing_active",
        "source_id": "us_rfa_english",
        "name": "Radio Free Asia (English RSS)",
        "source_type": "state_controlled",
        "feed_scope": "CHINA_FOCUSED",
        "url": "https://www.rfa.org/english/rss",
        "ua": DEFAULT_UA,
    },
    {
        "group": "existing_active",
        "source_id": "us_state_press",
        "name": "U.S. Department of State — Press Releases (RSS)",
        "source_type": "gov_comms",
        "feed_scope": "GOVERNMENT_RELEASES",
        "url": "https://www.state.gov/rss-feed/press-releases/feed/",
        "ua": BROWSER_COMPAT_UA,
    },
    # Existing inactive US sources
    {
        "group": "existing_inactive",
        "source_id": "us_rfa_mandarin",
        "name": "Radio Free Asia (Mandarin RSS)",
        "source_type": "state_controlled",
        "feed_scope": "CHINA_FOCUSED",
        "url": "https://www.rfa.org/mandarin/rss",
        "ua": DEFAULT_UA,
    },
    {
        "group": "existing_inactive",
        "source_id": "us_defense_news",
        "name": "U.S. Department of Defense News",
        "source_type": "gov_comms",
        "feed_scope": "GOVERNMENT_RELEASES",
        "url": "https://www.defense.gov/DesktopModules/ArticleCS/RSS.ashx?max=10&ContentType=1&Site=945",
        "ua": DEFAULT_UA,
    },
    {
        "group": "existing_inactive",
        "source_id": "us_federal_register_state",
        "name": "Federal Register — State Department",
        "source_type": "gov_comms",
        "feed_scope": "GOVERNMENT_RELEASES",
        "url": "https://www.federalregister.gov/api/v1/documents.rss?conditions%5Bagencies%5D%5B%5D=state-department",
        "ua": DEFAULT_UA,
    },
    # P1 Candidates
    {
        "group": "P1",
        "source_id": "us_npr_news",
        "name": "NPR News",
        "source_type": "public_service",
        "feed_scope": "GENERAL_NEWS",
        "url": "https://feeds.npr.org/1001/rss.xml",
        "ua": DEFAULT_UA,
    },
    {
        "group": "P1",
        "source_id": "us_pbs_newshour",
        "name": "PBS NewsHour Headlines",
        "source_type": "public_service",
        "feed_scope": "GENERAL_NEWS",
        "url": "https://www.pbs.org/newshour/feeds/rss/headlines",
        "ua": DEFAULT_UA,
    },
    {
        "group": "P1",
        "source_id": "us_nbc_news",
        "name": "NBC News — Top News",
        "source_type": "mainstream_independent",
        "feed_scope": "GENERAL_NEWS",
        "url": "https://feeds.nbcnews.com/nbcnews/public/news",
        "ua": DEFAULT_UA,
    },
    {
        "group": "P1",
        "source_id": "us_cbs_news",
        "name": "CBS News — Latest",
        "source_type": "mainstream_independent",
        "feed_scope": "GENERAL_NEWS",
        "url": "https://www.cbsnews.com/latest/rss/main",
        "ua": DEFAULT_UA,
    },
    {
        "group": "P1",
        "source_id": "us_abc_news",
        "name": "ABC News — Top Stories",
        "source_type": "mainstream_independent",
        "feed_scope": "GENERAL_NEWS",
        "url": "https://abcnews.com/abcnews/topstories",
        "ua": DEFAULT_UA,
    },
    # P2 Candidates
    {
        "group": "P2",
        "source_id": "us_nyt_world",
        "name": "The New York Times — World",
        "source_type": "mainstream_independent",
        "feed_scope": "INTERNATIONAL_NEWS",
        "url": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
        "ua": DEFAULT_UA,
    },
    {
        "group": "P2",
        "source_id": "us_nyt_us",
        "name": "The New York Times — US",
        "source_type": "mainstream_independent",
        "feed_scope": "GENERAL_NEWS",
        "url": "https://rss.nytimes.com/services/xml/rss/nyt/US.xml",
        "ua": DEFAULT_UA,
    },
    {
        "group": "P2",
        "source_id": "us_fox_news",
        "name": "Fox News — Latest",
        "source_type": "mainstream_independent",
        "feed_scope": "GENERAL_NEWS",
        "url": "https://moxie.foxnews.com/google-publisher/latest.xml",
        "ua": DEFAULT_UA,
    },
    {
        "group": "P2",
        "source_id": "us_politico",
        "name": "Politico — Politics",
        "source_type": "mainstream_independent",
        "feed_scope": "TOPIC_FEED",
        "url": "https://rss.politico.com/politics-news.xml",
        "ua": DEFAULT_UA,
    },
    {
        "group": "P2",
        "source_id": "us_the_hill",
        "name": "The Hill — News",
        "source_type": "mainstream_independent",
        "feed_scope": "TOPIC_FEED",
        "url": "https://thehill.com/news/feed/",
        "ua": DEFAULT_UA,
    },
]


def _check_article_url(client: httpx.Client, url: str) -> str:
    if not url:
        return "no_url"
    try:
        r = client.get(url, timeout=15.0, follow_redirects=True)
        return f"HTTP {r.status_code}"
    except httpx.TimeoutException:
        return "timeout"
    except Exception as exc:  # noqa: BLE001
        return f"err:{type(exc).__name__}"


def probe_one(item: dict[str, Any], today_shanghai: str) -> dict[str, Any]:
    headers = {
        "User-Agent": item["ua"],
        "Accept": "application/rss+xml, application/xml, text/xml, */*",
        "X-GNI-Client": "GNI-ResearchBot/0.1",
    }
    res: dict[str, Any] = {
        **item,
        "http_status": None,
        "content_type": None,
        "entry_count": 0,
        "has_today": False,
        "today_count": 0,
        "latest_published_shanghai": None,
        "samples": [],
        "error": None,
    }
    try:
        with httpx.Client(timeout=20.0, follow_redirects=True, headers=headers) as client:
            r = client.get(item["url"])
            res["http_status"] = r.status_code
            res["content_type"] = (r.headers.get("content-type") or "").split(";")[0].strip()
            if r.status_code != 200:
                res["error"] = f"HTTP {r.status_code}"
                return res
            parsed = feedparser.parse(r.text)
            entries = list(parsed.entries or [])
            res["entry_count"] = len(entries)
            if getattr(parsed, "bozo", False) and not entries:
                res["error"] = f"parse_error: {getattr(parsed, 'bozo_exception', '')}"
                return res

            enriched: list[tuple[datetime, dict[str, Any], datetime | None]] = []
            for e in entries:
                dt = _parse_published(e)
                sort_key = dt or datetime(1970, 1, 1, tzinfo=timezone.utc)
                enriched.append((sort_key, e, dt))
            enriched.sort(key=lambda x: x[0], reverse=True)

            today_count = 0
            for _, _, dt in enriched:
                if dt and dt.astimezone(SHANGHAI_TZ).date().isoformat() == today_shanghai:
                    today_count += 1
            res["today_count"] = today_count
            res["has_today"] = today_count > 0
            if enriched and enriched[0][2] is not None:
                res["latest_published_shanghai"] = enriched[0][2].astimezone(SHANGHAI_TZ).isoformat()

            for _, e, dt in enriched[:2]:
                link = (e.get("link") or "").strip()
                title = (e.get("title") or "").strip()
                dt_utc = dt.isoformat() if dt else None
                dt_sh = dt.astimezone(SHANGHAI_TZ).isoformat() if dt else None
                is_today = bool(dt and dt.astimezone(SHANGHAI_TZ).date().isoformat() == today_shanghai)
                url_status = _check_article_url(client, link)
                res["samples"].append(
                    {
                        "title": title,
                        "url": link,
                        "published_utc": dt_utc,
                        "published_shanghai": dt_sh,
                        "is_today": is_today,
                        "article_http": url_status,
                    }
                )
    except httpx.TimeoutException:
        res["error"] = "timeout"
    except Exception as exc:  # noqa: BLE001
        res["error"] = f"{type(exc).__name__}: {str(exc)[:120]}"
    return res


def render_markdown(results: list[dict[str, Any]], now_sh: datetime) -> str:
    today_str = now_sh.date().isoformat()
    lines = [
        "# US Source Probe Log",
        "",
        f"- Probe time (Asia/Shanghai): `{now_sh.isoformat()}`",
        f"- Today window (Asia/Shanghai): `{today_str}`",
        f"- Total probed: `{len(results)}`",
        "",
        "## Summary Table",
        "",
        "| Group | source_id | Name | Type | Scope | HTTP | Entries | Today? | Today N | Latest (Shanghai) | Error |",
        "|---|---|---|---|---|---:|---:|---|---:|---|---|",
    ]
    for r in results:
        lines.append(
            f"| {r['group']} | `{r['source_id']}` | {r['name']} | `{r['source_type']}` | `{r['feed_scope']}` "
            f"| {r['http_status'] or '—'} | {r['entry_count']} | {'YES' if r['has_today'] else 'NO'} "
            f"| {r['today_count']} | `{r['latest_published_shanghai'] or '—'}` | {r['error'] or '—'} |"
        )

    lines += ["", "## Sample 2 Items per Source", ""]
    for r in results:
        lines.append(f"### `{r['source_id']}` — {r['name']} ({r['group']})")
        lines.append(f"- Feed: `{r['url']}`")
        lines.append(
            f"- HTTP: `{r['http_status']}` | Content-Type: `{r['content_type']}` | "
            f"Entries: `{r['entry_count']}` | Today ({today_str}): `{'YES' if r['has_today'] else 'NO'}` ({r['today_count']})"
        )
        if r["error"]:
            lines.append(f"- Error: `{r['error']}`")
        for idx, s in enumerate(r["samples"], 1):
            lines.append(
                f"  {idx}. **{s['title']}** | pub_sh=`{s['published_shanghai']}` | "
                f"today=`{s['is_today']}` | article_http=`{s['article_http']}` | {s['url']}"
            )
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    now_sh = datetime.now(SHANGHAI_TZ)
    today_str = now_sh.date().isoformat()
    results: list[dict[str, Any]] = []
    for item in CANDIDATES:
        r = probe_one(item, today_str)
        results.append(r)
        print(
            f"[{r['group']:17}] {r['source_id']:26} http={str(r['http_status']):4} "
            f"entries={r['entry_count']:3} today={'YES' if r['has_today'] else 'NO ':3}({r['today_count']:2}) "
            f"err={r['error'] or '-'}",
            flush=True,
        )

    out_dir = Path(__file__).resolve().parents[1] / "docs" / "source-research"
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / "US_SOURCE_PROBE_LOG.md"
    md_path.write_text(render_markdown(results, now_sh), encoding="utf-8")

    json_path = Path("/tmp/us_source_probe.json")
    json_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWrote {md_path} and {json_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

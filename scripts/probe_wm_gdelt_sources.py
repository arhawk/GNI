#!/usr/bin/env python3
"""Read-only live probe for WorldMonitor DE/IN/US native RSS candidates and GDELT DOC 2.0 API."""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from probe_us_sources import BROWSER_COMPAT_UA, SHANGHAI_TZ, probe_one, render_markdown
from gni.ingestion.rss_adapter import DEFAULT_UA

WM_RSS_CANDIDATES: list[dict[str, Any]] = [
    # DE (WorldMonitor feeds.ts)
    {
        "group": "DE_media",
        "source_id": "de_tagesschau",
        "name": "Tagesschau (ARD)",
        "source_type": "public_service",
        "feed_scope": "GENERAL_NEWS",
        "url": "https://www.tagesschau.de/xml/rss2/",
        "ua": DEFAULT_UA,
    },
    {
        "group": "DE_media",
        "source_id": "de_spiegel",
        "name": "Der Spiegel — Top News",
        "source_type": "mainstream_independent",
        "feed_scope": "GENERAL_NEWS",
        "url": "https://www.spiegel.de/schlagzeilen/tops/index.rss",
        "ua": DEFAULT_UA,
    },
    {
        "group": "DE_media",
        "source_id": "de_zeit",
        "name": "Die Zeit — News",
        "source_type": "mainstream_independent",
        "feed_scope": "GENERAL_NEWS",
        "url": "https://newsfeed.zeit.de/index",
        "ua": DEFAULT_UA,
    },
    {
        "group": "DE_media",
        "source_id": "de_dw_german",
        "name": "Deutsche Welle (German all)",
        "source_type": "public_service",
        "feed_scope": "GENERAL_NEWS",
        "url": "https://rss.dw.com/rdf/rss-de-all",
        "ua": DEFAULT_UA,
    },
    # IN (WorldMonitor + Indian mainstream RSS)
    {
        "group": "IN_media",
        "source_id": "in_toi_world",
        "name": "Times of India — World",
        "source_type": "mainstream_independent",
        "feed_scope": "INTERNATIONAL_NEWS",
        "url": "https://timesofindia.indiatimes.com/rssfeeds/296589292.cms",
        "ua": BROWSER_COMPAT_UA,
    },
    {
        "group": "IN_media",
        "source_id": "in_ht_world",
        "name": "Hindustan Times — World News",
        "source_type": "mainstream_independent",
        "feed_scope": "INTERNATIONAL_NEWS",
        "url": "https://www.hindustantimes.com/feeds/rss/world-news/rssfeed.xml",
        "ua": BROWSER_COMPAT_UA,
    },
    {
        "group": "IN_media",
        "source_id": "in_et_news",
        "name": "The Economic Times — News",
        "source_type": "mainstream_independent",
        "feed_scope": "GENERAL_NEWS",
        "url": "https://economictimes.indiatimes.com/news/rssfeeds/1715249553.cms",
        "ua": BROWSER_COMPAT_UA,
    },
    {
        "group": "IN_media",
        "source_id": "in_livemint_news",
        "name": "Livemint — News",
        "source_type": "mainstream_independent",
        "feed_scope": "GENERAL_NEWS",
        "url": "https://www.livemint.com/rss/news",
        "ua": BROWSER_COMPAT_UA,
    },
    {
        "group": "IN_media",
        "source_id": "in_ndtv",
        "name": "NDTV — Top Stories",
        "source_type": "mainstream_independent",
        "feed_scope": "GENERAL_NEWS",
        "url": "https://feeds.feedburner.com/ndtvnews-top-stories",
        "ua": DEFAULT_UA,
    },
    # US / Asia high-signal
    {
        "group": "US_china",
        "source_id": "us_rfa_mandarin",
        "name": "Radio Free Asia (Mandarin RSS)",
        "source_type": "state_controlled",
        "feed_scope": "CHINA_FOCUSED",
        "url": "https://www.rfa.org/mandarin/rss",
        "ua": DEFAULT_UA,
    },
    {
        "group": "US_china",
        "source_id": "us_the_diplomat",
        "name": "The Diplomat",
        "source_type": "mainstream_independent",
        "feed_scope": "INTERNATIONAL_NEWS",
        "url": "https://thediplomat.com/feed/",
        "ua": BROWSER_COMPAT_UA,
    },
]

GDELT_QUERIES: list[dict[str, str]] = [
    {
        "source_id": "us_gdelt_china",
        "country_id": "US",
        "query": "(China OR Chinese OR Beijing OR Taiwan) sourcecountry:US",
    },
    {
        "source_id": "in_gdelt_china",
        "country_id": "IN",
        "query": "(China OR Chinese OR Beijing OR Taiwan) sourcecountry:IN",
    },
    {
        "source_id": "de_gdelt_china",
        "country_id": "DE",
        "query": "(China OR Chinese OR Beijing OR Taiwan) sourcecountry:GM",
    },
]


def probe_gdelt_one(item: dict[str, str]) -> dict[str, Any]:
    url = "https://api.gdeltproject.org/api/v2/doc/doc"
    params = {
        "query": item["query"],
        "mode": "ArtList",
        "format": "json",
        "maxrecords": "20",
        "timespan": "24h",
        "sort": "DateDesc",
    }
    res: dict[str, Any] = {
        "source_id": item["source_id"],
        "country_id": item["country_id"],
        "query": item["query"],
        "http_status": None,
        "count": 0,
        "domains": [],
        "samples": [],
        "error": None,
    }
    try:
        with httpx.Client(timeout=25.0, follow_redirects=True, headers={"User-Agent": DEFAULT_UA}) as client:
            r = client.get(url, params=params)
            res["http_status"] = r.status_code
            if r.status_code != 200:
                res["error"] = f"HTTP {r.status_code}: {r.text[:160]}"
                return res
            data = r.json()
            arts = data.get("articles") or []
            res["count"] = len(arts)
            domains = sorted({str(a.get("domain") or "") for a in arts if a.get("domain")})
            res["domains"] = domains[:10]
            for a in arts[:3]:
                res["samples"].append(
                    {
                        "title": a.get("title"),
                        "url": a.get("url"),
                        "domain": a.get("domain"),
                        "seendate": a.get("seendate"),
                        "language": a.get("language"),
                    }
                )
    except Exception as exc:
        res["error"] = f"{type(exc).__name__}: {exc}"
    return res


def main() -> int:
    now_sh = datetime.now(SHANGHAI_TZ)
    today_str = now_sh.date().isoformat()
    rss_results: list[dict[str, Any]] = []
    for c in WM_RSS_CANDIDATES:
        r = probe_one(c, today_str)
        rss_results.append(r)
        art_codes = ",".join(s["article_http"] for s in r["samples"]) or "-"
        print(
            f"[RSS] [{r['group']:8}] {r['source_id']:18} HTTP={str(r['http_status']):4} "
            f"entries={r['entry_count']:3} today={r['today_count']:2} art=[{art_codes}] "
            f"err={r['error'] or '-'}",
            file=sys.stderr,
            flush=True,
        )

    gdelt_results: list[dict[str, Any]] = []
    for idx, q in enumerate(GDELT_QUERIES):
        if idx > 0:
            time.sleep(6.0)
        gr = probe_gdelt_one(q)
        gdelt_results.append(gr)
        print(
            f"[GDELT] {gr['source_id']}: HTTP={gr['http_status']} count={gr['count']} "
            f"domains={','.join(gr['domains'][:4])} err={gr['error'] or '-'}",
            file=sys.stderr,
        )

    md = render_markdown(rss_results, now_sh)
    md = md.replace(
        "# US Source Probe Log",
        "# WorldMonitor Native RSS & GDELT DOC 2.0 Probe Log",
        1,
    )
    gdelt_lines = [
        "",
        "## GDELT DOC 2.0 API Probe (`timespan=24h`, `maxrecords=20`)",
        "",
        "| source_id | Country | HTTP | Articles | Top Domains | Error |",
        "|---|---|---:|---:|---|---|",
    ]
    for gr in gdelt_results:
        gdelt_lines.append(
            f"| `{gr['source_id']}` | `{gr['country_id']}` | {gr['http_status'] or 'ERR'} | "
            f"{gr['count']} | {', '.join(gr['domains'][:5]) or '—'} | {gr['error'] or '—'} |"
        )
    for gr in gdelt_results:
        gdelt_lines.append(f"\n### `{gr['source_id']}` (`{gr['query']}`)")
        for i, s in enumerate(gr["samples"], 1):
            gdelt_lines.append(
                f"  {i}. **{s.get('title')}** | domain=`{s.get('domain')}` | lang=`{s.get('language')}` | seen=`{s.get('seendate')}` | {s.get('url')}"
            )

    out_path = Path("docs/source-research/WM_GDELT_PROBE_LOG_20261126.md")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md + "\n".join(gdelt_lines) + "\n", encoding="utf-8")
    print(f"Wrote {out_path}", file=sys.stderr)
    print(
        json.dumps(
            {"rss": rss_results, "gdelt": gdelt_results, "probe_utc": datetime.now(timezone.utc).isoformat()},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Read-only live probe for RU/AU WorldMonitor RSS, GDELT (RS/AS), and <=5 recovery attempts per stale source."""

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

RU_AU_CANDIDATES: list[dict[str, Any]] = [
    # RU (WorldMonitor feeds.ts)
    {
        "group": "RU_media",
        "source_id": "ru_moscow_times",
        "name": "The Moscow Times (RSS)",
        "source_type": "mainstream_independent",
        "feed_scope": "GENERAL_NEWS",
        "url": "https://www.themoscowtimes.com/rss/news",
        "ua": BROWSER_COMPAT_UA,
    },
    {
        "group": "RU_media",
        "source_id": "ru_meduza",
        "name": "Meduza (Russian RSS)",
        "source_type": "mainstream_independent",
        "feed_scope": "GENERAL_NEWS",
        "url": "https://meduza.io/rss/all",
        "ua": BROWSER_COMPAT_UA,
    },
    {
        "group": "RU_media",
        "source_id": "ru_rt_russia",
        "name": "RT — Russia News (RSS)",
        "source_type": "state_controlled",
        "feed_scope": "GENERAL_NEWS",
        "url": "https://www.rt.com/rss/russia/",
        "ua": DEFAULT_UA,
    },
    # AU (WorldMonitor + mainstream AU)
    {
        "group": "AU_media",
        "source_id": "au_smh_world",
        "name": "Sydney Morning Herald — World (RSS)",
        "source_type": "mainstream_independent",
        "feed_scope": "INTERNATIONAL_NEWS",
        "url": "https://www.smh.com.au/rss/world.xml",
        "ua": BROWSER_COMPAT_UA,
    },
    {
        "group": "AU_media",
        "source_id": "au_sbs_world",
        "name": "SBS News — World (RSS)",
        "source_type": "public_service",
        "feed_scope": "INTERNATIONAL_NEWS",
        "url": "https://www.sbs.com.au/news/topic/world/feed",
        "ua": BROWSER_COMPAT_UA,
    },
    {
        "group": "AU_media",
        "source_id": "au_abc_justin",
        "name": "ABC News Australia — Just In (RSS)",
        "source_type": "public_service",
        "feed_scope": "GENERAL_NEWS",
        "url": "https://www.abc.net.au/news/feed/2942460/rss.xml",
        "ua": DEFAULT_UA,
    },
]

# Strictly <=5 attempts per stale/failed source
STALE_RECOVERY: dict[str, list[dict[str, Any]]] = {
    "us_voa_english": [
        {
            "group": "STALE_VOA",
            "source_id": "voa_try1_top_en",
            "name": "VOA English Top Stories",
            "source_type": "state_controlled",
            "feed_scope": "INTERNATIONAL_NEWS",
            "url": "https://www.voanews.com/api/z-$otevtiq",
            "ua": BROWSER_COMPAT_UA,
        },
        {
            "group": "STALE_VOA",
            "source_id": "voa_try2_china_alt",
            "name": "VOA China Alt Feed",
            "source_type": "state_controlled",
            "feed_scope": "CHINA_FOCUSED",
            "url": "https://www.voanews.com/api/zmgqoe$moi",
            "ua": BROWSER_COMPAT_UA,
        },
        {
            "group": "STALE_VOA",
            "source_id": "voa_try3_mandarin_top",
            "name": "VOA Chinese (Mandarin) Top Stories",
            "source_type": "state_controlled",
            "feed_scope": "CHINA_FOCUSED",
            "url": "https://www.voachinese.com/api/z-$otevtiq",
            "ua": BROWSER_COMPAT_UA,
        },
        {
            "group": "STALE_VOA",
            "source_id": "voa_try4_mandarin_china",
            "name": "VOA Chinese — China Desk",
            "source_type": "state_controlled",
            "feed_scope": "CHINA_FOCUSED",
            "url": "https://www.voachinese.com/api/zmjuqtl-vomx-tpey_jqq",
            "ua": BROWSER_COMPAT_UA,
        },
        {
            "group": "STALE_VOA",
            "source_id": "voa_try5_world",
            "name": "VOA English World",
            "source_type": "state_controlled",
            "feed_scope": "INTERNATIONAL_NEWS",
            "url": "https://www.voanews.com/api/z_-mqyl-vomx-tpey_jqq",
            "ua": BROWSER_COMPAT_UA,
        },
    ],
    "us_state_press": [
        {
            "group": "STALE_STATE",
            "source_id": "state_try1_browser_ua",
            "name": "State Dept Press Releases (Browser UA)",
            "source_type": "gov_comms",
            "feed_scope": "GOVERNMENT_RELEASES",
            "url": "https://www.state.gov/rss-feed/press-releases/feed/",
            "ua": BROWSER_COMPAT_UA,
        },
        {
            "group": "STALE_STATE",
            "source_id": "state_try2_alt_path",
            "name": "State Dept Press Releases Alt Path",
            "source_type": "gov_comms",
            "feed_scope": "GOVERNMENT_RELEASES",
            "url": "https://www.state.gov/press-releases/feed/",
            "ua": BROWSER_COMPAT_UA,
        },
        {
            "group": "STALE_STATE",
            "source_id": "state_try3_main_feed",
            "name": "State Dept Main Feed",
            "source_type": "gov_comms",
            "feed_scope": "GOVERNMENT_RELEASES",
            "url": "https://www.state.gov/feed/",
            "ua": BROWSER_COMPAT_UA,
        },
        {
            "group": "STALE_STATE",
            "source_id": "state_try4_gh_mirror",
            "name": "State Dept Press Releases (GitHub RSS Mirror)",
            "source_type": "gov_comms",
            "feed_scope": "GOVERNMENT_RELEASES",
            "url": "https://raw.githubusercontent.com/markschaver/State-Department-PR/master/data.rss",
            "ua": DEFAULT_UA,
        },
    ],
    "in_indian_express": [
        {
            "group": "STALE_IE",
            "source_id": "ie_try1_world_browser",
            "name": "Indian Express — World (Browser UA)",
            "source_type": "mainstream_independent",
            "feed_scope": "INTERNATIONAL_NEWS",
            "url": "https://indianexpress.com/section/world/feed/",
            "ua": BROWSER_COMPAT_UA,
        },
        {
            "group": "STALE_IE",
            "source_id": "ie_try2_india_browser",
            "name": "Indian Express — India (Browser UA)",
            "source_type": "mainstream_independent",
            "feed_scope": "GENERAL_NEWS",
            "url": "https://indianexpress.com/section/india/feed/",
            "ua": BROWSER_COMPAT_UA,
        },
        {
            "group": "STALE_IE",
            "source_id": "ie_try3_main_browser",
            "name": "Indian Express — Main (Browser UA)",
            "source_type": "mainstream_independent",
            "feed_scope": "GENERAL_NEWS",
            "url": "https://indianexpress.com/feed/",
            "ua": BROWSER_COMPAT_UA,
        },
    ],
}

GDELT_QUERIES: list[dict[str, str]] = [
    {
        "source_id": "ru_gdelt_china",
        "country_id": "RU",
        "query": "(China OR Chinese OR Beijing OR Taiwan) sourcecountry:RS",
    },
    {
        "source_id": "au_gdelt_china",
        "country_id": "AU",
        "query": "(China OR Chinese OR Beijing OR Taiwan) sourcecountry:AS",
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
        "error": None,
    }
    try:
        with httpx.Client(timeout=25.0, follow_redirects=True, headers={"User-Agent": DEFAULT_UA}) as client:
            r = client.get(url, params=params)
            res["http_status"] = r.status_code
            if r.status_code != 200:
                res["error"] = f"HTTP {r.status_code}: {r.text[:140]}"
                return res
            data = r.json()
            arts = data.get("articles") or []
            res["count"] = len(arts)
            res["domains"] = sorted({str(a.get("domain") or "") for a in arts if a.get("domain")})[:8]
    except Exception as exc:
        res["error"] = f"{type(exc).__name__}: {exc}"
    return res


def main() -> int:
    now_sh = datetime.now(SHANGHAI_TZ)
    today_str = now_sh.date().isoformat()
    all_rss: list[dict[str, Any]] = []

    print("=== RU & AU Native RSS ===", file=sys.stderr, flush=True)
    for c in RU_AU_CANDIDATES:
        r = probe_one(c, today_str)
        all_rss.append(r)
        art_codes = ",".join(s["article_http"] for s in r["samples"]) or "-"
        print(
            f"[RSS] [{r['group']:8}] {r['source_id']:18} HTTP={str(r['http_status']):4} "
            f"entries={r['entry_count']:3} today={r['today_count']:2} art=[{art_codes}] "
            f"latest={r.get('latest_shanghai') or '-'} err={r['error'] or '-'}",
            file=sys.stderr,
            flush=True,
        )

    print("=== Stale / Failed Source Recovery (<=5 attempts each) ===", file=sys.stderr, flush=True)
    for target, attempts in STALE_RECOVERY.items():
        for c in attempts:
            r = probe_one(c, today_str)
            all_rss.append(r)
            art_codes = ",".join(s["article_http"] for s in r["samples"]) or "-"
            print(
                f"[REC] [{target:17}] {r['source_id']:22} HTTP={str(r['http_status']):4} "
                f"entries={r['entry_count']:3} today={r['today_count']:2} art=[{art_codes}] "
                f"latest={r.get('latest_shanghai') or '-'} err={r['error'] or '-'}",
                file=sys.stderr,
                flush=True,
            )

    print("=== GDELT DOC 2.0 (RU/AU) ===", file=sys.stderr, flush=True)
    gdelt_results: list[dict[str, Any]] = []
    for idx, q in enumerate(GDELT_QUERIES):
        if idx > 0:
            time.sleep(6.5)
        gr = probe_gdelt_one(q)
        gdelt_results.append(gr)
        print(
            f"[GDELT] {gr['source_id']:15} HTTP={gr['http_status']} count={gr['count']} "
            f"domains={','.join(gr['domains'][:4])} err={gr['error'] or '-'}",
            file=sys.stderr,
            flush=True,
        )

    md = render_markdown(all_rss, now_sh).replace(
        "# US Source Probe Log",
        "# RU/AU Expansion & Stale Source Recovery Probe Log",
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

    out_path = Path("docs/source-research/RU_AU_STALE_PROBE_LOG_20261126.md")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md + "\n".join(gdelt_lines) + "\n", encoding="utf-8")
    print(f"Wrote {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Read-only probe for 12 US/IN/AU native RSS sources from GNI_RSS_API_SOURCE_CATALOG."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from probe_us_sources import BROWSER_COMPAT_UA, SHANGHAI_TZ, probe_one, render_markdown
from gni.ingestion.rss_adapter import DEFAULT_UA

CATALOG_CANDIDATES: list[dict[str, Any]] = [
    # US (7)
    {
        "group": "US_gov",
        "source_id": "us_whitehouse_briefings",
        "name": "White House — Briefings & Statements",
        "source_type": "gov_comms",
        "feed_scope": "GOVERNMENT_RELEASES",
        "url": "https://www.whitehouse.gov/briefings-statements/feed/",
        "ua": BROWSER_COMPAT_UA,
    },
    {
        "group": "US_gov",
        "source_id": "us_whitehouse_actions",
        "name": "White House — Presidential Actions",
        "source_type": "gov_comms",
        "feed_scope": "GOVERNMENT_RELEASES",
        "url": "https://www.whitehouse.gov/presidential-actions/feed/",
        "ua": BROWSER_COMPAT_UA,
    },
    {
        "group": "US_media",
        "source_id": "us_axios",
        "name": "Axios",
        "source_type": "mainstream_independent",
        "feed_scope": "GENERAL_NEWS",
        "url": "https://api.axios.com/feed/",
        "ua": DEFAULT_UA,
    },
    {
        "group": "US_media",
        "source_id": "us_wsj",
        "name": "Wall Street Journal — US News",
        "source_type": "mainstream_independent",
        "feed_scope": "GENERAL_NEWS",
        "url": "https://feeds.content.dowjones.io/public/rss/RSSUSnews",
        "ua": DEFAULT_UA,
    },
    {
        "group": "US_tech",
        "source_id": "us_the_verge",
        "name": "The Verge",
        "source_type": "mainstream_independent",
        "feed_scope": "TOPIC_FEED",
        "url": "https://www.theverge.com/rss/index.xml",
        "ua": DEFAULT_UA,
    },
    {
        "group": "US_tech",
        "source_id": "us_mit_tech_review",
        "name": "MIT Technology Review",
        "source_type": "mainstream_independent",
        "feed_scope": "TOPIC_FEED",
        "url": "https://www.technologyreview.com/feed/",
        "ua": DEFAULT_UA,
    },
    {
        "group": "US_tech",
        "source_id": "us_wired",
        "name": "Wired",
        "source_type": "mainstream_independent",
        "feed_scope": "TOPIC_FEED",
        "url": "https://www.wired.com/feed/rss",
        "ua": DEFAULT_UA,
    },
    # IN (3)
    {
        "group": "IN_media",
        "source_id": "in_the_hindu",
        "name": "The Hindu — National",
        "source_type": "mainstream_independent",
        "feed_scope": "GENERAL_NEWS",
        "url": "https://www.thehindu.com/news/national/feeder/default.rss",
        "ua": DEFAULT_UA,
    },
    {
        "group": "IN_media",
        "source_id": "in_indian_express",
        "name": "The Indian Express — India",
        "source_type": "mainstream_independent",
        "feed_scope": "GENERAL_NEWS",
        "url": "https://indianexpress.com/section/india/feed/",
        "ua": DEFAULT_UA,
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
    # AU (2)
    {
        "group": "AU_media",
        "source_id": "au_guardian",
        "name": "The Guardian — Australia News",
        "source_type": "mainstream_independent",
        "feed_scope": "GENERAL_NEWS",
        "url": "https://www.theguardian.com/australia-news/rss",
        "ua": DEFAULT_UA,
    },
    {
        "group": "AU_media",
        "source_id": "au_guardian_pacific",
        "name": "The Guardian — Pacific Islands",
        "source_type": "mainstream_independent",
        "feed_scope": "INTERNATIONAL_NEWS",
        "url": "https://www.theguardian.com/world/pacific-islands/rss",
        "ua": DEFAULT_UA,
    },
]


def main() -> int:
    now_sh = datetime.now(SHANGHAI_TZ)
    today_str = now_sh.date().isoformat()
    results: list[dict[str, Any]] = []
    for item in CATALOG_CANDIDATES:
        r = probe_one(item, today_str)
        results.append(r)
        art_codes = ",".join(s["article_http"] for s in r["samples"]) or "-"
        print(
            f"[{r['group']:8}] {r['source_id']:24} http={str(r['http_status']):4} "
            f"entries={r['entry_count']:3} today={'YES' if r['has_today'] else 'NO ':3}({r['today_count']:2}) "
            f"art=[{art_codes}] err={r['error'] or '-'}",
            flush=True,
        )

    out_dir = Path(__file__).resolve().parents[1] / "docs" / "source-research"
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / "CATALOG_PROBE_LOG_20261126.md"
    md_path.write_text(
        render_markdown(results, now_sh).replace("# US Source Probe Log", "# Catalog US / IN / AU Source Probe Log"),
        encoding="utf-8",
    )
    Path("/tmp/catalog_source_probe.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nWrote {md_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

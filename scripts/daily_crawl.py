"""Daily serial crawl for all active RSS + GDELT sources (covers today + yesterday).

Runs in a single process so the cross-process GDELT rate-limit lock and polite spacing
keep all 5 GDELT sources under GDELT's rate limit without 429 bursts.

Usage:
    .venv/bin/python scripts/daily_crawl.py                # seed -> ingest (RSS+GDELT) -> process
    .venv/bin/python scripts/daily_crawl.py --analyze      # also run analysis on new articles
    .venv/bin/python scripts/daily_crawl.py --source de_gdelt_china
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone

from gni.infrastructure.db import session_scope
from gni.ingestion.service import run_ingestion
from gni.processing.service import run_processing
from gni.sources.seed import seed_sources


def main() -> int:
    parser = argparse.ArgumentParser(description="Daily serial RSS + GDELT crawl and processing.")
    parser.add_argument("--source", default=None, help="Optional single source_id to crawl.")
    parser.add_argument("--skip-seed", action="store_true", help="Skip syncing sources_seed.yaml first.")
    parser.add_argument("--skip-process", action="store_true", help="Only ingest, skip processing.")
    parser.add_argument("--analyze", action="store_true", help="Also run analysis after processing.")
    parser.add_argument("--analyze-limit", type=int, default=200, help="Max articles to analyze if --analyze.")
    args = parser.parse_args()

    summary: dict[str, object] = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "source_filter": args.source,
    }

    if not args.skip_seed:
        with session_scope() as session:
            summary["seeded"] = seed_sources(session)

    with session_scope() as session:
        jobs = run_ingestion(session, source_id=args.source)
        ok = sum(1 for j in jobs if j.status == "success")
        failed = [
            {"source_id": j.source_id, "error": (j.error_message or "")[:160]}
            for j in jobs
            if j.status != "success"
        ]
        summary["ingestion"] = {
            "total_sources": len(jobs),
            "success": ok,
            "failed_count": len(failed),
            "failed": failed,
        }

    if not args.skip_process:
        with session_scope() as session:
            pjob = run_processing(session, source_id=args.source)
            summary["processing"] = {
                "job_id": pjob.id,
                "status": pjob.status,
                "processed": pjob.processed_count,
                "failed": pjob.failed_count,
            }

    if args.analyze:
        from gni.analysis.service import run_analysis

        with session_scope() as session:
            arun = run_analysis(session, limit=args.analyze_limit, source_id=args.source)
            summary["analysis"] = {
                "run_id": arun.id,
                "status": arun.status,
                "processed": arun.processed_count,
                "failed": arun.failed_count,
            }

    summary["finished_at"] = datetime.now(timezone.utc).isoformat()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

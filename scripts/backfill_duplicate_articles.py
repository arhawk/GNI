"""Backfill cross-source duplicate markers for already-ingested articles (idempotent).

Problem this fixes: ingestion-time dedup used to compare content_hash only within the same
source, so syndicated copies across sources (e.g. DW English vs DW Asia) were both kept,
both analysed by the LLM, and counted twice in the daily header.

What it does:
- Groups articles by exact content_hash across ALL sources.
- Within each group, the primary records (duplicate_of_article_id IS NULL) are reduced to one
  canonical record using the same keep rule as the V1.0 statistics layer:
  primary > has a valid China stance conclusion > earlier first_seen_at > article_id.
- Every other primary record gets duplicate_of_article_id -> canonical,
  exclude_from_metrics=True, quality_status='duplicate', pipeline_state=DEDUPLICATED.

Default is a dry run (prints the plan, writes nothing). Pass --apply to write.
A second --apply run changes nothing. After applying, re-run the V1.0 snapshots / reports
for the affected dates (printed at the end).

Usage:
    python scripts/backfill_duplicate_articles.py            # dry run
    python scripts/backfill_duplicate_articles.py --apply    # write
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from gni.analysis.stance_util import extract_v1_china_stance
from gni.infrastructure.db import session_scope
from gni.infrastructure.models import Article, ArticleAnalysis
from gni.infrastructure.pipeline_state import DEDUPLICATED, set_pipeline_state
from gni.metrics.service import _latest_analyses
from gni.metrics.v1_stats import V1ArticleInput, dedup_keep_preference

SAMPLE_LIMIT = 30


def _to_v1(article: Article, analysis: ArticleAnalysis | None) -> V1ArticleInput:
    structured = (analysis.structured_result if analysis else None) or {}
    schema_ver = analysis.schema_version if analysis else None
    return V1ArticleInput(
        article_id=article.id,
        source_id=article.source_id,
        source_country=None,
        published_at=article.published_at,
        canonical_url=article.canonical_url,
        url=article.url,
        content_hash=article.content_hash,
        duplicate_of_article_id=article.duplicate_of_article_id,
        first_seen_at=article.first_seen_at,
        stance_label=extract_v1_china_stance(structured, schema_version=schema_ver),
        analysis_schema_version=schema_ver,
    )


def plan_backfill(session: Session) -> tuple[list[tuple[Article, Article]], dict[str, Any]]:
    """Return (marks, summary). marks = [(duplicate_article, canonical_article), ...]."""
    articles = list(
        session.scalars(select(Article).where(Article.content_hash.is_not(None))).all()
    )
    by_hash: dict[str, list[Article]] = defaultdict(list)
    for art in articles:
        by_hash[art.content_hash.strip()].append(art)

    multi_groups = {h: m for h, m in by_hash.items() if len(m) > 1}
    # Only groups with 2+ primary (unmarked) records need work; the rest are already resolved.
    work: dict[str, list[Article]] = {}
    for h, members in multi_groups.items():
        primary = [a for a in members if a.duplicate_of_article_id is None]
        if len(primary) > 1:
            work[h] = primary

    analyses = _latest_analyses(session, [a.id for g in work.values() for a in g])

    marks: list[tuple[Article, Article]] = []
    samples: list[dict[str, Any]] = []
    for h, primary in sorted(work.items()):
        inputs = {a.id: _to_v1(a, analyses.get(a.id)) for a in primary}
        canonical_id = min(inputs, key=lambda aid: dedup_keep_preference(inputs[aid]))
        canonical = next(a for a in primary if a.id == canonical_id)
        dups = [a for a in primary if a.id != canonical_id]
        for dup in dups:
            marks.append((dup, canonical))
        if len(samples) < SAMPLE_LIMIT:
            samples.append(
                {
                    "content_hash": h[:12],
                    "canonical": {
                        "article_id": canonical.id,
                        "source_id": canonical.source_id,
                        "url": canonical.url,
                        "stance": inputs[canonical.id].stance_label,
                    },
                    "duplicates": [
                        {
                            "article_id": d.id,
                            "source_id": d.source_id,
                            "url": d.url,
                            "stance": inputs[d.id].stance_label,
                        }
                        for d in dups
                    ],
                }
            )

    affected_dates = sorted({
        (d.published_at.date().isoformat() if d.published_at else "unknown")
        for d, _ in marks
    })
    summary: dict[str, Any] = {
        "hash_groups_total": len(by_hash),
        "hash_groups_with_multiple_rows": len(multi_groups),
        "hash_groups_needing_fix": len(work),
        "articles_to_mark_duplicate": len(marks),
        "affected_published_dates_utc": affected_dates,
        "samples": samples,
    }
    return marks, summary


def apply_backfill(marks: list[tuple[Article, Article]]) -> int:
    for dup, canonical in marks:
        dup.duplicate_of_article_id = canonical.id
        dup.exclude_from_metrics = True
        dup.quality_status = "duplicate"
        set_pipeline_state(dup, DEDUPLICATED)
    return len(marks)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="write changes (default: dry run)")
    args = parser.parse_args()

    with session_scope() as session:
        marks, summary = plan_backfill(session)
        print(json.dumps({"mode": "apply" if args.apply else "dry_run", **summary}, ensure_ascii=False, indent=2))
        if args.apply and marks:
            applied = apply_backfill(marks)
            print(f"applied: marked {applied} articles as duplicates")
        elif args.apply:
            print("applied: nothing to do (already idempotent)")


if __name__ == "__main__":
    main()

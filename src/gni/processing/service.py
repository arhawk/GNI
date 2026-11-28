"""P1-B processing orchestration: extract, clean, dedup, L1 title screen."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from gni.infrastructure.models import (
    Article,
    ArticleScreening,
    ArticleVersion,
    CollectionTask,
    ProcessingJob,
    Source,
)
from gni.infrastructure.pipeline_state import (
    DEDUPLICATED,
    EXTRACTION_COMPLETED,
    set_pipeline_state,
)
from gni.processing.extractor import fetch_and_extract
from gni.processing.hashutil import sha256_text
from gni.processing.language import detect_language
from gni.processing.normalize import normalize_title_for_dedup, normalize_url
from gni.processing.title_l1 import screen_title

logger = logging.getLogger(__name__)


def _next_version_no(session: Session, article_id: str) -> int:
    rows = session.scalars(
        select(ArticleVersion.version_no).where(ArticleVersion.article_id == article_id)
    ).all()
    return (max(rows) + 1) if rows else 1


_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def _seniority_key(article: Article) -> tuple[bool, datetime, str]:
    """Smaller key = seen earlier = canonical. Missing first_seen_at sorts last."""
    fs = article.first_seen_at
    if fs is not None and fs.tzinfo is None:
        fs = fs.replace(tzinfo=timezone.utc)
    return (fs is None, fs or _EPOCH, article.id or "")


def _find_duplicate(
    session: Session,
    article: Article,
    *,
    content_hash: str | None,
    title_norm: str,
) -> Article | None:
    """Return the canonical primary record this article duplicates, or None.

    1. Exact ``content_hash`` match across ALL sources (syndicated / wire copies). Only
       primary records (not already marked duplicate) qualify, and only if they were
       first seen before this article, so the earliest record stays canonical.
    2. Same-source normalized-title near-duplicate (unchanged; titles are not compared
       across sources because they collide too easily).
    """
    if content_hash:
        hash_q = select(Article).where(
            Article.content_hash == content_hash,
            Article.id != article.id,
            Article.duplicate_of_article_id.is_(None),
            Article.exclude_from_metrics.is_(False),
        )
        my_key = _seniority_key(article)
        earlier = [o for o in session.scalars(hash_q).all() if _seniority_key(o) < my_key]
        if earlier:
            return min(earlier, key=_seniority_key)

    if not title_norm:
        return None
    q = select(Article).where(
        Article.source_id == article.source_id,
        Article.id != article.id,
        Article.exclude_from_metrics.is_(False),
    )
    for other in session.scalars(q).all():
        if normalize_title_for_dedup(other.title) == title_norm:
            # Prefer the earlier first_seen as canonical
            if other.first_seen_at and article.first_seen_at:
                if other.first_seen_at <= article.first_seen_at:
                    return other
            elif other.id < article.id:
                return other
    return None


def process_article(
    session: Session,
    article: Article,
    *,
    skip_fetch: bool = False,
    offline_html: str | None = None,
) -> dict[str, Any]:
    """Process one article. Never raises out — returns status dict."""
    source = session.get(Source, article.source_id)
    source_cfg = dict(source.config or {}) if source else {}
    result: dict[str, Any] = {"article_id": article.id, "ok": True}

    try:
        if article.canonical_url:
            article.canonical_url = normalize_url(article.canonical_url) or article.canonical_url
        if article.url:
            article.url = article.url.strip()

        # L1 title screening (rules only)
        l1 = screen_title(article.title, summary=article.content_original)
        screening = ArticleScreening(
            id=str(uuid4()),
            article_id=article.id,
            stage="title",
            screening_label=l1.label,
            reason_codes=l1.reason_codes,
            matched_entities=l1.matched_entities,
            confidence=l1.confidence,
            requires_human_review=l1.requires_human_review,
            priority=l1.priority,
            rule_version=l1.rule_version,
            entity_dictionary_version=l1.entity_dictionary_version,
            schema_version="title_screening_v0.1",
            input_hash=l1.input_hash,
        )
        session.add(screening)
        article.title_screening_label = l1.label
        article.title_screening_priority = l1.priority
        result["title_screening"] = l1.label

        # Full-text extraction
        if offline_html is not None:
            from gni.processing.extractor import extract_from_html

            extraction = extract_from_html(offline_html)
        elif skip_fetch:
            # Use RSS stub summary as weak body when offline
            from gni.processing.normalize import clean_extracted_text

            stub = clean_extracted_text(article.content_original or "")
            from gni.processing.extractor import ExtractionResult, MIN_CHARS

            if stub and len(stub) >= MIN_CHARS:
                extraction = ExtractionResult(stub, None, "rss_summary", "extracted_stub", None)
            else:
                extraction = ExtractionResult(
                    stub or None,
                    None,
                    "rss_summary",
                    "insufficient_text",
                    "stub too short; fetch skipped",
                )
        else:
            extraction = fetch_and_extract(article.url, source_cfg)

        lang = detect_language(
            extraction.content_clean or article.content_original,
            fallback=(source.language if source else None) or article.language,
        )
        content_hash = sha256_text(extraction.content_clean)
        title_hash = sha256_text(article.title)
        version = ArticleVersion(
            id=str(uuid4()),
            article_id=article.id,
            version_no=_next_version_no(session, article.id),
            extraction_method=extraction.method,
            raw_html_excerpt=extraction.raw_html_excerpt,
            content_clean=extraction.content_clean,
            content_hash=content_hash,
            language=lang,
            char_count=len(extraction.content_clean) if extraction.content_clean else 0,
            quality_status=extraction.quality_status,
            error_message=extraction.error_message,
            extracted_at=datetime.now(timezone.utc),
        )
        session.add(version)
        session.flush()
        screening.article_version_id = version.id

        if extraction.content_clean:
            article.content_clean = extraction.content_clean
        article.content_hash = content_hash or article.content_hash
        article.title_hash = title_hash or article.title_hash
        if lang:
            article.language = lang

        title_norm = normalize_title_for_dedup(article.title)
        dup = _find_duplicate(session, article, content_hash=content_hash, title_norm=title_norm)
        article.latest_article_version_id = version.id
        if dup is None and article.duplicate_of_article_id is not None:
            # Previously marked duplicate but no longer matches an earlier primary record.
            article.duplicate_of_article_id = None
            article.exclude_from_metrics = False
        if dup is not None:
            article.duplicate_of_article_id = dup.id
            article.exclude_from_metrics = True
            article.quality_status = "duplicate"
            result["duplicate_of"] = dup.id
            set_pipeline_state(article, DEDUPLICATED)
        elif extraction.quality_status in {"insufficient_text", "fetch_failed"}:
            article.quality_status = "insufficient_text"
            # Title screened + extraction attempted; final MVP state.
            set_pipeline_state(article, EXTRACTION_COMPLETED)
        else:
            article.quality_status = (
                "processed_stub" if extraction.method == "rss_summary" else "processed"
            )
            # MVP merges NORMALIZED → TITLE_SCREENED → EXTRACTION_COMPLETED into final state.
            set_pipeline_state(article, EXTRACTION_COMPLETED)

        article.processing_status = "done"
        article.processed_at = datetime.now(timezone.utc)
        article.updated_at = datetime.now(timezone.utc)
        result["quality_status"] = article.quality_status
        result["version_id"] = version.id
        result["pipeline_state"] = article.pipeline_state
    except Exception as exc:  # noqa: BLE001
        logger.exception("process_article failed article_id=%s", article.id)
        article.processing_status = "failed"
        article.quality_status = "processing_failed"
        article.processed_at = datetime.now(timezone.utc)
        result["ok"] = False
        result["error"] = str(exc)[:500]
    return result


def run_processing(
    session: Session,
    *,
    limit: int | None = None,
    source_id: str | None = None,
    article_id: str | None = None,
    skip_fetch: bool = False,
    reprocess: bool = False,
) -> ProcessingJob:
    job = ProcessingJob(
        id=str(uuid4()),
        status="running",
        started_at=datetime.now(timezone.utc),
        stats={},
    )
    session.add(job)
    session.flush()

    task = CollectionTask(
        id=str(uuid4()),
        task_type="process",
        source_id=source_id,
        status="running",
        started_at=datetime.now(timezone.utc),
        legacy_job_id=job.id,
        code_version="process_v0.2_data_layers",
    )
    session.add(task)
    session.flush()

    q = select(Article)
    if article_id:
        q = q.where(Article.id == article_id)
    else:
        if source_id:
            q = q.where(Article.source_id == source_id)
        if not reprocess:
            q = q.where(Article.processing_status.in_(["pending", "failed"]))
        q = q.order_by(Article.first_seen_at.asc())
        if limit:
            q = q.limit(limit)

    articles = list(session.scalars(q).all())
    ok = 0
    failed = 0
    details: list[dict[str, Any]] = []
    for article in articles:
        # Commit-less per article within same session; isolate failures
        try:
            detail = process_article(session, article, skip_fetch=skip_fetch)
            details.append(detail)
            if detail.get("ok"):
                ok += 1
            else:
                failed += 1
            session.flush()
        except Exception as exc:  # noqa: BLE001
            failed += 1
            article.processing_status = "failed"
            details.append({"article_id": article.id, "ok": False, "error": str(exc)[:500]})
            session.flush()

    job.status = "success" if failed == 0 else ("partial" if ok else "failed")
    job.finished_at = datetime.now(timezone.utc)
    job.stats = {
        "attempted": len(articles),
        "ok": ok,
        "failed": failed,
        "skip_fetch": skip_fetch,
        "details_sample": details[:20],
    }
    task.status = job.status
    task.finished_at = job.finished_at
    task.stats = {
        "attempted": len(articles),
        "ok": ok,
        "failed": failed,
    }
    return job

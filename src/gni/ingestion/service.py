"""Ingestion orchestration: jobs, upsert articles, source health, L1 raw/discovered."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from gni.ingestion.base import BaseAdapter
from gni.ingestion.rss_adapter import RssAdapter
from gni.infrastructure.models import (
    Article,
    CollectionTask,
    DiscoveredArticle,
    IngestionJob,
    RawDocument,
    Source,
    SourceHealth,
)
from gni.infrastructure.pipeline_state import RAW_STORED, set_pipeline_state

logger = logging.getLogger(__name__)

# Cap raw payload stored in Postgres (R2 object_key reserved for larger bodies).
_RAW_PAYLOAD_MAX_CHARS = 256_000


def get_adapter(adapter_type: str) -> BaseAdapter:
    mapping: dict[str, type[BaseAdapter]] = {
        "rss_adapter": RssAdapter,
    }
    cls = mapping.get(adapter_type)
    if cls is None:
        raise ValueError(f"Unknown adapter_type: {adapter_type}")
    return cls()


def _hash_text(value: str | None) -> str | None:
    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _source_config(source: Source) -> dict[str, Any]:
    cfg = dict(source.config or {})
    cfg.setdefault("feed_url", source.feed_or_api_url)
    cfg.setdefault("feed_or_api_url", source.feed_or_api_url)
    return cfg


def _update_health(session: Session, source_id: str, *, ok: bool, error: str | None) -> None:
    health = session.get(SourceHealth, source_id)
    if health is None:
        health = SourceHealth(source_id=source_id, success_count=0, failure_count=0)
        session.add(health)
    now = datetime.now(timezone.utc)
    if ok:
        health.last_success_at = now
        health.success_count = (health.success_count or 0) + 1
        health.error_message = None
    else:
        health.last_failure_at = now
        health.failure_count = (health.failure_count or 0) + 1
        health.error_message = (error or "unknown error")[:2000]
    total = (health.success_count or 0) + (health.failure_count or 0)
    health.success_rate = (health.success_count or 0) / total if total else None
    health.updated_at = now


def _serialize_raw_payload(raw: Any) -> tuple[str, str]:
    """Return (payload_text truncated, content_type)."""
    if isinstance(raw, dict):
        text = json.dumps(raw, ensure_ascii=False, default=str)
        ctype = "api_json"
    elif hasattr(raw, "keys") and hasattr(raw, "get"):
        # feedparser entry-like
        try:
            text = json.dumps(dict(raw), ensure_ascii=False, default=str)
        except Exception:
            text = str(raw)
        ctype = "rss_item"
    else:
        text = str(raw)
        ctype = "rss_item"
    if len(text) > _RAW_PAYLOAD_MAX_CHARS:
        text = text[:_RAW_PAYLOAD_MAX_CHARS]
    return text, ctype


def upsert_article(session: Session, source: Source, item: dict[str, Any]) -> tuple[Article, bool]:
    url = (item.get("url") or "").strip()
    if not url:
        raise ValueError("article url required")
    existing = session.scalar(
        select(Article).where(Article.source_id == source.id, Article.url == url)
    )
    title = item.get("title")
    content_original = item.get("content_original")
    if existing is None:
        article = Article(
            id=str(uuid4()),
            source_id=source.id,
            title=title,
            url=url,
            canonical_url=item.get("canonical_url") or url,
            content_original=content_original,
            language=source.language,
            published_at=item.get("published_at"),
            content_hash=_hash_text(content_original),
            title_hash=_hash_text(title),
            quality_status=item.get("quality_status") or "rss_stub",
            source_timezone=source.timezone,
            time_precision=item.get("time_precision"),
            pipeline_state=RAW_STORED,
        )
        session.add(article)
        return article, True

    existing.title = title or existing.title
    existing.content_original = content_original or existing.content_original
    existing.published_at = item.get("published_at") or existing.published_at
    existing.content_hash = _hash_text(existing.content_original)
    existing.title_hash = _hash_text(existing.title)
    existing.updated_at = datetime.now(timezone.utc)
    # Do not rewind pipeline_state on re-ingest of known articles.
    if not existing.pipeline_state or existing.pipeline_state == "DISCOVERED":
        set_pipeline_state(existing, RAW_STORED)
    return existing, False


def _record_discovery(
    session: Session,
    *,
    source: Source,
    task: CollectionTask,
    raw: Any,
    parsed: dict[str, Any],
    article: Article,
) -> None:
    url = (parsed.get("url") or "").strip()
    payload_text, content_type = _serialize_raw_payload(raw)
    raw_doc = RawDocument(
        id=str(uuid4()),
        source_id=source.id,
        collection_task_id=task.id,
        url=url,
        content_type=content_type,
        payload_text=payload_text,
        payload_hash=_hash_text(payload_text),
        fetched_at=datetime.now(timezone.utc),
    )
    session.add(raw_doc)
    session.flush()

    discovered = session.scalar(
        select(DiscoveredArticle).where(
            DiscoveredArticle.source_id == source.id, DiscoveredArticle.url == url
        )
    )
    if discovered is None:
        discovered = DiscoveredArticle(
            id=str(uuid4()),
            source_id=source.id,
            url=url,
            canonical_url=parsed.get("canonical_url") or url,
            title=parsed.get("title"),
            published_at=parsed.get("published_at"),
            discovered_at=datetime.now(timezone.utc),
            raw_document_id=raw_doc.id,
            article_id=article.id,
            status="promoted",
            collection_task_id=task.id,
        )
        session.add(discovered)
        session.flush()
    else:
        discovered.raw_document_id = raw_doc.id
        discovered.article_id = article.id
        discovered.status = "promoted"
        discovered.title = parsed.get("title") or discovered.title
        discovered.published_at = parsed.get("published_at") or discovered.published_at
        discovered.collection_task_id = task.id
        session.flush()

    raw_doc.discovered_article_id = discovered.id
    article.latest_raw_document_id = raw_doc.id
    set_pipeline_state(article, RAW_STORED)


def ingest_source(session: Session, source: Source) -> IngestionJob:
    job = IngestionJob(
        id=str(uuid4()),
        source_id=source.id,
        status="running",
        started_at=datetime.now(timezone.utc),
        stats={},
    )
    session.add(job)
    session.flush()

    task = CollectionTask(
        id=str(uuid4()),
        task_type="ingest",
        source_id=source.id,
        status="running",
        started_at=datetime.now(timezone.utc),
        legacy_job_id=job.id,
        code_version="ingest_v0.2_data_layers",
    )
    session.add(task)
    session.flush()

    inserted = 0
    updated = 0
    skipped = 0
    try:
        adapter = get_adapter(source.adapter_type)
        raw_items = adapter.fetch(_source_config(source))
        for raw in raw_items:
            parsed = adapter.parse(raw)
            if not parsed.get("url"):
                skipped += 1
                continue
            article, created = upsert_article(session, source, parsed)
            session.flush()
            _record_discovery(
                session, source=source, task=task, raw=raw, parsed=parsed, article=article
            )
            if created:
                inserted += 1
            else:
                updated += 1
        job.status = "success"
        job.stats = {
            "fetched": len(raw_items),
            "inserted": inserted,
            "updated": updated,
            "skipped": skipped,
        }
        job.finished_at = datetime.now(timezone.utc)
        task.status = "success"
        task.stats = dict(job.stats)
        task.finished_at = job.finished_at
        _update_health(session, source.id, ok=True, error=None)
        logger.info(
            "ingest success source=%s fetched=%s inserted=%s updated=%s",
            source.id,
            len(raw_items),
            inserted,
            updated,
        )
    except Exception as exc:
        job.status = "failed"
        job.error = str(exc)[:4000]
        job.stats = {"inserted": inserted, "updated": updated, "skipped": skipped}
        job.finished_at = datetime.now(timezone.utc)
        task.status = "failed"
        task.error = job.error
        task.stats = dict(job.stats or {})
        task.finished_at = job.finished_at
        _update_health(session, source.id, ok=False, error=str(exc))
        logger.exception("ingest failed source=%s", source.id)
    session.flush()
    return job


def run_ingestion(
    session: Session,
    *,
    source_id: str | None = None,
) -> list[IngestionJob]:
    stmt = select(Source).where(Source.active_status == "active")
    if source_id:
        stmt = stmt.where(Source.id == source_id)
    sources = list(session.scalars(stmt))
    if not sources:
        raise ValueError("No active sources matched")
    return [ingest_source(session, s) for s in sources]

"""Ingestion orchestration: jobs, upsert articles, source health."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from gni.ingestion.api_adapter import ApiAdapter
from gni.ingestion.base import BaseAdapter
from gni.ingestion.rss_adapter import RssAdapter
from gni.ingestion.web_adapter import WebAdapter
from gni.infrastructure.models import Article, IngestionJob, Source, SourceHealth

logger = logging.getLogger(__name__)


def get_adapter(adapter_type: str) -> BaseAdapter:
    mapping: dict[str, type[BaseAdapter]] = {
        "rss_adapter": RssAdapter,
        "api_adapter": ApiAdapter,
        "web_adapter": WebAdapter,
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
        )
        session.add(article)
        return article, True

    existing.title = title or existing.title
    existing.content_original = content_original or existing.content_original
    existing.published_at = item.get("published_at") or existing.published_at
    existing.content_hash = _hash_text(existing.content_original)
    existing.title_hash = _hash_text(existing.title)
    existing.updated_at = datetime.now(timezone.utc)
    return existing, False


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
            _, created = upsert_article(session, source, parsed)
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

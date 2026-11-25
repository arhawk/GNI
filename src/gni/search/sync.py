"""Full reindex + incremental article sync into Meilisearch."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from gni.infrastructure.models import Article, Event
from gni.search.meili import (
    ARTICLES_INDEX,
    EVENTS_INDEX,
    delete_all_documents,
    ensure_indexes,
    meili_available,
    upsert_documents,
)


def article_doc(a: Article) -> dict[str, Any]:
    return {
        "id": a.id,
        "kind": "article",
        "title": a.title or "",
        "summary": (a.content_clean or "")[:2000],
        "content": (a.content_clean or "")[:8000],
    }


def event_doc(e: Event) -> dict[str, Any]:
    return {
        "id": e.id,
        "kind": "event",
        "title": e.title or "",
        "summary": e.summary or "",
        "content": e.summary or "",
    }


def reindex_all(session: Session) -> dict[str, Any]:
    if not meili_available():
        return {"ok": False, "reason": "meilisearch_unavailable"}
    ensure_indexes()
    delete_all_documents(ARTICLES_INDEX)
    delete_all_documents(EVENTS_INDEX)
    articles = list(session.scalars(select(Article).limit(50_000)).all())
    events = list(session.scalars(select(Event).limit(20_000)).all())
    # batch
    batch = 500
    for i in range(0, len(articles), batch):
        upsert_documents(ARTICLES_INDEX, [article_doc(a) for a in articles[i : i + batch]])
    for i in range(0, len(events), batch):
        upsert_documents(EVENTS_INDEX, [event_doc(e) for e in events[i : i + batch]])
    return {
        "ok": True,
        "articles": len(articles),
        "events": len(events),
    }


def sync_articles(session: Session, article_ids: list[str]) -> dict[str, Any]:
    if not article_ids:
        return {"ok": True, "synced": 0}
    if not meili_available():
        return {"ok": False, "reason": "meilisearch_unavailable", "synced": 0}
    ensure_indexes()
    rows = list(session.scalars(select(Article).where(Article.id.in_(article_ids))).all())
    if rows:
        upsert_documents(ARTICLES_INDEX, [article_doc(a) for a in rows])
    return {"ok": True, "synced": len(rows)}

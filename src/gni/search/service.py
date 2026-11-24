"""Title + body search over events/articles (DB-native, no external engine)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from gni.infrastructure.models import Article, Country, Event, Source


def search_all(session: Session, q: str, *, limit: int = 20) -> dict[str, Any]:
    term = (q or "").strip()
    if len(term) < 2:
        return {"query": term, "results": []}
    pattern = f"%{term}%"
    results: list[dict[str, Any]] = []

    # Countries by id/name
    countries = list(
        session.scalars(
            select(Country).where(
                or_(Country.id.ilike(pattern), Country.name.ilike(pattern), Country.code.ilike(pattern))
            ).limit(5)
        ).all()
    )
    for c in countries:
        results.append(
            {
                "kind": "country",
                "id": c.id,
                "title": c.name or c.id,
                "subtitle": c.id,
                "url": None,
                "href": f"/countries?c={c.id}",
            }
        )

    # Sources
    sources_hit = list(
        session.scalars(
            select(Source).where(
                or_(Source.id.ilike(pattern), Source.name.ilike(pattern))
            ).limit(5)
        ).all()
    )
    for s in sources_hit:
        results.append(
            {
                "kind": "source",
                "id": s.id,
                "title": s.name or s.id,
                "subtitle": s.country_id,
                "url": None,
                "href": f"/countries?c={s.country_id}",
            }
        )

    remain = max(0, limit - len(results))
    events = list(
        session.scalars(
            select(Event)
            .where(or_(Event.title.ilike(pattern), Event.summary.ilike(pattern)))
            .order_by(Event.updated_at.desc())
            .limit(max(remain, 8))
        ).all()
    )
    for e in events:
        if len(results) >= limit:
            break
        results.append(
            {
                "kind": "event",
                "id": e.id,
                "title": e.title,
                "subtitle": e.status,
                "url": None,
                "href": f"/events/{e.id}",
            }
        )

    remain = max(0, limit - len(results))
    if remain:
        articles = list(
            session.scalars(
                select(Article)
                .where(
                    or_(
                        Article.title.ilike(pattern),
                        Article.content_clean.ilike(pattern),
                    )
                )
                .order_by(Article.first_seen_at.desc())
                .limit(remain)
            ).all()
        )
        src_map = {
            s.id: s
            for s in session.scalars(
                select(Source).where(Source.id.in_({a.source_id for a in articles}))
            ).all()
        } if articles else {}
        for a in articles:
            src = src_map.get(a.source_id)
            results.append(
                {
                    "kind": "article",
                    "id": a.id,
                    "title": a.title or a.id,
                    "subtitle": (src.country_id if src else None) or a.source_id,
                    "url": a.url,
                    "href": None,
                    "match": "body" if a.title and term.lower() not in (a.title or "").lower() else "title",
                }
            )

    return {"query": term, "results": results[:limit]}

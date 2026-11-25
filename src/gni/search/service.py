"""Search: Meilisearch IDs → Postgres hydrate; ilike fallback when Meili down."""

from __future__ import annotations

from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from gni.infrastructure.models import Article, Country, Event, Source


def search_all(session: Session, q: str, *, limit: int = 20) -> dict[str, Any]:
    term = (q or "").strip()
    if len(term) < 2:
        return {"query": term, "results": [], "backend": "none"}

    results: list[dict[str, Any]] = []
    backend = "ilike"

    # Always resolve countries/sources from PG (small tables)
    pattern = f"%{term}%"
    countries = list(
        session.scalars(
            select(Country)
            .where(
                or_(
                    Country.id.ilike(pattern),
                    Country.name.ilike(pattern),
                    Country.code.ilike(pattern),
                )
            )
            .limit(5)
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

    sources_hit = list(
        session.scalars(
            select(Source)
            .where(or_(Source.id.ilike(pattern), Source.name.ilike(pattern)))
            .limit(5)
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

    meili_ok = False
    try:
        from gni.search.meili import (
            ARTICLES_INDEX,
            EVENTS_INDEX,
            meili_available,
            search_index,
        )

        if meili_available():
            meili_ok = True
            backend = "meilisearch"
            remain = max(0, limit - len(results))
            ev_hits = search_index(EVENTS_INDEX, term, limit=max(8, remain // 2 + 2))
            event_ids = [h["id"] for h in ev_hits if h.get("id")]
            if event_ids:
                events = {
                    e.id: e
                    for e in session.scalars(select(Event).where(Event.id.in_(event_ids))).all()
                }
                for eid in event_ids:
                    e = events.get(eid)
                    if not e or len(results) >= limit:
                        continue
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
                art_hits = search_index(ARTICLES_INDEX, term, limit=remain)
                art_ids = [h["id"] for h in art_hits if h.get("id")]
                if art_ids:
                    articles = {
                        a.id: a
                        for a in session.scalars(
                            select(Article).where(Article.id.in_(art_ids))
                        ).all()
                    }
                    src_ids = {a.source_id for a in articles.values()}
                    src_map = {
                        s.id: s
                        for s in session.scalars(select(Source).where(Source.id.in_(src_ids))).all()
                    }
                    for aid in art_ids:
                        a = articles.get(aid)
                        if not a or len(results) >= limit:
                            continue
                        src = src_map.get(a.source_id)
                        results.append(
                            {
                                "kind": "article",
                                "id": a.id,
                                "title": a.title or a.id,
                                "subtitle": (src.country_id if src else None) or a.source_id,
                                "url": a.url,
                                "href": None,
                                "match": "meili",
                            }
                        )
    except Exception:  # noqa: BLE001
        meili_ok = False
        backend = "ilike"

    if not meili_ok:
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
            src_map = (
                {
                    s.id: s
                    for s in session.scalars(
                        select(Source).where(Source.id.in_({a.source_id for a in articles}))
                    ).all()
                }
                if articles
                else {}
            )
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
                        "match": (
                            "body"
                            if a.title and term.lower() not in (a.title or "").lower()
                            else "title"
                        ),
                    }
                )

    return {"query": term, "results": results[:limit], "backend": backend}

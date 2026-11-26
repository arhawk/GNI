"""Narratives API endpoints: NarrativeCluster + deterministic clustering fallback + evidence."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from gni.api.routers.common import (
    as_utc,
    extract_article_narratives,
    load_cached_assessments,
    project_article_summary,
    resolve_window,
)
from gni.analysis.stance_util import extract_v1_china_stance, extract_v1_topics
from gni.events.narratives import ArticleNarrativeInput, cluster_narratives
from gni.infrastructure.db import session_scope
from gni.infrastructure.models import (
    Article,
    EventNarrativeEvidence,
    NarrativeCluster,
    Source,
)
from gni.metrics.definitions import CHINA_INCLUDE_LEVELS
from gni.metrics.service import _latest_analyses

router = APIRouter(tags=["narratives"])

_NON_COORDINATION_NOTE = (
    "多个国家或多家媒体同时出现相似叙事，不足以证明存在协调传播；"
    "此处仅展示观察到的跨国文本相似性与原文证据。"
)


def _collect_narratives(
    session: Any,
    *,
    days: int = 30,
    start: str | None = None,
    end: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    p_start, p_end = resolve_window(session, days=days, start=start, end=end)
    sources = {s.id: s for s in session.scalars(select(Source)).all()}
    clusters = list(session.scalars(select(NarrativeCluster)).all())
    ev_rows = list(session.scalars(select(EventNarrativeEvidence)).all())

    articles = list(session.scalars(select(Article)).all())
    in_win = [
        a
        for a in articles
        if not a.exclude_from_metrics
        and a.china_relevance_level in CHINA_INCLUDE_LEVELS
        and (dt := as_utc(a.published_at)) is not None
        and p_start <= dt < p_end
    ]
    analyses = _latest_analyses(session, [a.id for a in in_win])
    article_map = {a.id: a for a in articles}

    items: list[dict[str, Any]] = []

    if clusters:
        ev_by_cluster: dict[str, list[EventNarrativeEvidence]] = {}
        for row in ev_rows:
            ev_by_cluster.setdefault(row.narrative_cluster_id, []).append(row)
        for c in clusters:
            linked = ev_by_cluster.get(c.id, [])
            a_ids = list(dict.fromkeys([r.article_id for r in linked if r.article_id]))
            countries = sorted(
                {
                    sources[article_map[aid].source_id].country_id
                    for aid in a_ids
                    if aid in article_map
                    and article_map[aid].source_id in sources
                    and sources[article_map[aid].source_id].country_id
                }
            )
            topics: set[str] = set()
            seen_times = []
            supporting = []
            counter = []
            for r in linked:
                a = article_map.get(r.article_id)
                if a and a.published_at:
                    seen_times.append(as_utc(a.published_at))
                ana = analyses.get(r.article_id)
                if ana:
                    for t in extract_v1_topics(ana.structured_result or {}, schema_version=ana.schema_version):
                        topics.add(t)
                stance_of_art = (
                    extract_v1_china_stance(ana.structured_result or {}, schema_version=ana.schema_version)
                    if ana
                    else None
                )
                entry = {
                    "article_id": r.article_id,
                    "quote": r.quote,
                    "title": a.title if a else None,
                    "source_country": sources[a.source_id].country_id if (a and a.source_id in sources) else None,
                    "published_at": a.published_at.isoformat() if (a and a.published_at) else None,
                    "stance_label": stance_of_art,
                }
                if (r.quote and str(r.quote).lower().startswith("[counter]")) or stance_of_art == "Positive":
                    counter.append(entry)
                else:
                    supporting.append(entry)
            valid_times = [t for t in seen_times if t is not None]
            items.append(
                {
                    "narrative_id": c.id,
                    "name": c.label,
                    "core_claim": c.summary or c.label,
                    "main_frame": c.frame_id,
                    "trend_status": "dominant" if len(a_ids) >= 5 else ("emerging" if len(a_ids) >= 2 else "observed"),
                    "related_topics": sorted(topics),
                    "related_countries": countries,
                    "article_count": len(a_ids),
                    "article_ids": a_ids,
                    "first_seen": min(valid_times).isoformat() if valid_times else None,
                    "last_seen": max(valid_times).isoformat() if valid_times else None,
                    "supporting_evidence": supporting[:10],
                    "counter_evidence": counter[:5],
                    "source": "narrative_cluster",
                }
            )

    if not items:
        # Deterministic clustering from Phase 3 article narratives
        n_inputs: list[ArticleNarrativeInput] = []
        for a in in_win:
            ana = analyses.get(a.id)
            structured = (ana.structured_result if ana else None) or {}
            src = sources.get(a.source_id)
            stance = extract_v1_china_stance(structured, schema_version=ana.schema_version if ana else None)
            for n in extract_article_narratives(structured):
                n_inputs.append(
                    ArticleNarrativeInput(
                        article_id=a.id,
                        claim=n.get("claim") or n.get("label") or "",
                        frame=n.get("frame"),
                        stance_label=stance,
                        country_id=src.country_id if src else None,
                        published_at=as_utc(a.published_at),
                    )
                )
        clustered = cluster_narratives(n_inputs)
        for cl in clustered:
            a_ids = list(cl.article_ids)
            topics_set: set[str] = set()
            for aid in a_ids:
                ana = analyses.get(aid)
                if ana:
                    for t in extract_v1_topics(ana.structured_result or {}, schema_version=ana.schema_version):
                        topics_set.add(t)
            items.append(
                {
                    "narrative_id": cl.narrative_id,
                    "name": cl.label,
                    "core_claim": cl.core_claim,
                    "main_frame": cl.frame,
                    "trend_status": cl.status or ("dominant" if cl.article_count >= 5 else "emerging"),
                    "related_topics": sorted(topics_set),
                    "related_countries": list(cl.countries),
                    "article_count": cl.article_count,
                    "article_ids": a_ids,
                    "first_seen": cl.first_seen.isoformat() if cl.first_seen else None,
                    "last_seen": cl.last_seen.isoformat() if cl.last_seen else None,
                    "supporting_evidence": [
                        {
                            "article_id": aid,
                            "title": article_map[aid].title if aid in article_map else None,
                            "quote": cl.core_claim,
                            "source_country": sources[article_map[aid].source_id].country_id
                            if (aid in article_map and article_map[aid].source_id in sources)
                            else None,
                            "published_at": article_map[aid].published_at.isoformat()
                            if (aid in article_map and article_map[aid].published_at)
                            else None,
                        }
                        for aid in cl.supporting_article_ids[:8]
                    ],
                    "counter_evidence": [
                        {
                            "article_id": aid,
                            "title": article_map[aid].title if aid in article_map else None,
                            "quote": None,
                            "source_country": sources[article_map[aid].source_id].country_id
                            if (aid in article_map and article_map[aid].source_id in sources)
                            else None,
                            "published_at": article_map[aid].published_at.isoformat()
                            if (aid in article_map and article_map[aid].published_at)
                            else None,
                        }
                        for aid in cl.counter_article_ids[:5]
                    ],
                    "source": "deterministic_cluster",
                }
            )

    items.sort(key=lambda x: (-int(x.get("article_count") or 0), str(x.get("name") or "")))
    meta = {
        "period_start": p_start.isoformat(),
        "period_end": p_end.isoformat(),
        "days": days,
        "total": len(items),
        "non_coordination_note": _NON_COORDINATION_NOTE,
    }
    return items, meta


@router.get("/api/narratives")
def api_narratives(
    days: int = Query(30, ge=1, le=365),
    start: str | None = Query(None),
    end: str | None = Query(None),
) -> dict[str, Any]:
    with session_scope() as session:
        items, meta = _collect_narratives(session, days=days, start=start, end=end)
        cached = load_cached_assessments(session, report_type="daily")
        return {
            "meta": meta,
            "narratives": items,
            "narrative_assessment": cached.get("narrative_analysis"),
        }


@router.get("/api/narratives/{narrative_id}")
def api_narrative_detail(
    narrative_id: str,
    days: int = Query(30, ge=1, le=365),
) -> dict[str, Any]:
    with session_scope() as session:
        items, meta = _collect_narratives(session, days=days)
        target = next((n for n in items if n["narrative_id"] == narrative_id), None)
        if not target:
            raise HTTPException(status_code=404, detail="narrative not found")
        a_ids = target.get("article_ids") or []
        articles = (
            list(session.scalars(select(Article).where(Article.id.in_(a_ids))).all()) if a_ids else []
        )
        sources = {s.id: s for s in session.scalars(select(Source)).all()}
        analyses = _latest_analyses(session, [a.id for a in articles])
        return {
            "meta": meta,
            "narrative": target,
            "articles": [
                project_article_summary(a, sources.get(a.source_id), analyses.get(a.id))
                for a in articles[:30]
            ],
        }

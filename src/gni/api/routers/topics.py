"""Topics API endpoints: 4 Boards x 15 fixed Topics (deterministic V1.0 stats, trends, events, articles)."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import timedelta
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
from gni.analysis.stance_util import extract_v1_topics
from gni.infrastructure.db import session_scope
from gni.infrastructure.models import Article, Event, EventArticle, Source
from gni.metrics.changes import detect_volume_change
from gni.metrics.definitions import CHINA_INCLUDE_LEVELS, METHODOLOGY_VERSION, TAXONOMY_V1_VERSION
from gni.metrics.service import _latest_analyses, run_v1_stat_snapshots
from gni.metrics.taxonomy_v1 import load_taxonomy_v1

router = APIRouter(tags=["topics"])


@router.get("/api/topics")
def api_topics(
    days: int = Query(30, ge=1, le=365),
    start: str | None = Query(None),
    end: str | None = Query(None),
) -> dict[str, Any]:
    with session_scope() as session:
        p_start, p_end = resolve_window(session, days=days, start=start, end=end)
        span = p_end - p_start
        prev_start, prev_end = p_start - span, p_start

        cur = run_v1_stat_snapshots(session, period_start=p_start, period_end=p_end, persist=False)
        prev = run_v1_stat_snapshots(session, period_start=prev_start, period_end=prev_end, persist=False)
        tax = load_taxonomy_v1()

        prev_topic_counts = {
            r["scope_id"]: int(r.get("article_count") or 0)
            for r in (prev.get("by_scope", {}).get("topics") or [])
        }
        global_count = int((cur.get("by_scope", {}).get("global") or {}).get("article_count") or 0)

        topics_out = []
        for t in cur.get("by_scope", {}).get("topics") or []:
            tid = t["scope_id"]
            cnt = int(t.get("article_count") or 0)
            prev_cnt = prev_topic_counts.get(tid, 0)
            delta = cnt - prev_cnt
            sig = detect_volume_change(
                subject=f"TOPIC:{tid}",
                recent_count=cnt,
                baseline_mean=float(prev_cnt),
                supporting_articles=list(t.get("article_ids") or [])[:10],
            )
            topics_out.append(
                {
                    **t,
                    "topic_id": tid,
                    "share_of_global": round(cnt / global_count, 4) if global_count > 0 else 0.0,
                    "prev_article_count": prev_cnt,
                    "delta": delta,
                    "change_signal": sig.model_dump(mode="json") if sig else None,
                }
            )

        return {
            "meta": {
                "period_start": p_start.isoformat(),
                "period_end": p_end.isoformat(),
                "days": days,
                "methodology_version": METHODOLOGY_VERSION,
                "taxonomy_version": TAXONOMY_V1_VERSION,
                "global_unique_article_count": global_count,
                "overlap_note": (
                    "Multi-label taxonomy: a single article may belong to multiple topics "
                    "(counted at most once per topic). Topic article counts may overlap and "
                    "must NOT be summed to equal global unique article_count."
                ),
            },
            "boards": cur.get("by_scope", {}).get("boards") or [],
            "topics": topics_out,
            "taxonomy_boards": [
                {
                    "board_id": b.id,
                    "label_zh": b.name_zh,
                    "topic_ids": [t.id for t in tax.topics if t.board_id == b.id],
                }
                for b in tax.boards
            ],
        }


@router.get("/api/topics/{topic_id}")
def api_topic_detail(
    topic_id: str,
    days: int = Query(30, ge=1, le=365),
    start: str | None = Query(None),
    end: str | None = Query(None),
    limit: int = Query(30, ge=1, le=100),
) -> dict[str, Any]:
    tax = load_taxonomy_v1()
    topic_map = {t.id: t for t in tax.topics}
    if topic_id not in topic_map:
        raise HTTPException(status_code=404, detail=f"unknown topic_id: {topic_id}")
    spec = topic_map[topic_id]

    with session_scope() as session:
        p_start, p_end = resolve_window(session, days=days, start=start, end=end)
        cur = run_v1_stat_snapshots(session, period_start=p_start, period_end=p_end, persist=False)
        topic_row = next(
            (t for t in (cur.get("by_scope", {}).get("topics") or []) if t.get("scope_id") == topic_id),
            None,
        )
        article_ids = list((topic_row or {}).get("article_ids") or [])

        articles = (
            list(session.scalars(select(Article).where(Article.id.in_(article_ids))).all())
            if article_ids
            else []
        )
        sources = {s.id: s for s in session.scalars(select(Source)).all()}
        analyses = _latest_analyses(session, [a.id for a in articles])

        # Daily volume trend by published_at
        daily_counts: Counter[str] = Counter()
        country_counts: Counter[str] = Counter()
        source_counts: Counter[str] = Counter()
        narrative_counts: Counter[str] = Counter()
        for a in articles:
            dt = as_utc(a.published_at)
            if dt:
                daily_counts[dt.strftime("%Y-%m-%d")] += 1
            src = sources.get(a.source_id)
            if src and src.country_id:
                country_counts[src.country_id] += 1
            source_counts[src.name if src else a.source_id] += 1
            ana = analyses.get(a.id)
            for n in extract_article_narratives((ana.structured_result if ana else None) or {}):
                narrative_counts[n["label"]] += 1

        trend_series = [
            {"date": d, "article_count": daily_counts[d]} for d in sorted(daily_counts.keys())
        ]

        # Related events
        ev_links = (
            list(session.scalars(select(EventArticle).where(EventArticle.article_id.in_(article_ids))).all())
            if article_ids
            else []
        )
        ev_counts: Counter[str] = Counter(link.event_id for link in ev_links)
        ev_ids = [eid for eid, _ in ev_counts.most_common(10)]
        events_map = (
            {e.id: e for e in session.scalars(select(Event).where(Event.id.in_(ev_ids))).all()}
            if ev_ids
            else {}
        )
        related_events = [
            {
                "event_id": eid,
                "title": events_map[eid].title,
                "event_type": events_map[eid].event_type,
                "event_time": events_map[eid].event_time.isoformat() if events_map[eid].event_time else None,
                "topic_article_count": ev_counts[eid],
            }
            for eid in ev_ids
            if eid in events_map
        ]

        # Article summaries sorted newest first by published_at
        ev_by_article: dict[str, list[str]] = defaultdict(list)
        for link in ev_links:
            ev_by_article[link.article_id].append(link.event_id)

        articles_sorted = sorted(
            articles,
            key=lambda x: as_utc(x.published_at) or (p_start - timedelta(days=1)),
            reverse=True,
        )
        article_rows = [
            project_article_summary(a, sources.get(a.source_id), analyses.get(a.id), event_ids=ev_by_article.get(a.id))
            for a in articles_sorted[:limit]
        ]

        cached = load_cached_assessments(session, report_type="daily")
        return {
            "topic": {
                "topic_id": topic_id,
                "board_id": spec.board_id,
                "label_zh": spec.name_zh,
                **(topic_row or {}),
            },
            "meta": {
                "period_start": p_start.isoformat(),
                "period_end": p_end.isoformat(),
                "days": days,
                "methodology_version": METHODOLOGY_VERSION,
                "taxonomy_version": TAXONOMY_V1_VERSION,
                "overlap_note": "Topic counts allow multi-label overlap across topics and cannot be summed to equal global unique article_count.",
            },
            "trend": trend_series,
            "by_country": [
                {"country_id": cid, "article_count": n}
                for cid, n in country_counts.most_common()
            ],
            "top_sources": [
                {"source_name": name, "article_count": n}
                for name, n in source_counts.most_common(10)
            ],
            "top_narratives": [
                {"label": label, "article_count": n}
                for label, n in narrative_counts.most_common(8)
            ],
            "related_events": related_events,
            "articles": article_rows,
            "topic_assessment": cached.get("topic_analysis"),
        }

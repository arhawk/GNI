"""Countries API endpoints: list, multi-country comparison (V1.0 deterministic), detail, china-attitude."""

from __future__ import annotations

from collections import Counter
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from gni.api.routers.common import (
    extract_article_narratives,
    extract_sentiment_label,
    load_cached_assessments,
    project_article_summary,
    resolve_window,
)
from gni.analysis.stance_util import extract_v1_topics
from gni.dashboard.pages_api import countries_list_payload, country_detail_payload
from gni.events.service import get_country_china_attitude
from gni.infrastructure.db import session_scope
from gni.infrastructure.models import Article, Country, Event, EventArticle, Source
from gni.metrics.definitions import METHODOLOGY_VERSION, TAXONOMY_V1_VERSION
from gni.metrics.service import _latest_analyses, run_v1_stat_snapshots

router = APIRouter(tags=["countries"])


@router.get("/api/countries")
def api_countries() -> dict[str, Any]:
    with session_scope() as session:
        return countries_list_payload(session)


@router.get("/api/countries/compare")
def api_countries_compare(
    countries: str = Query(..., description="Comma-separated ISO country codes, e.g. US,RU,DE"),
    days: int = Query(30, ge=1, le=365),
    start: str | None = Query(None),
    end: str | None = Query(None),
) -> dict[str, Any]:
    selected = [c.strip().upper() for c in countries.split(",") if c.strip()]
    if not selected:
        raise HTTPException(status_code=400, detail="at least one country code is required")
    selected = list(dict.fromkeys(selected))[:10]

    with session_scope() as session:
        p_start, p_end = resolve_window(session, days=days, start=start, end=end)
        span = p_end - p_start
        prev_start, prev_end = p_start - span, p_start

        cur = run_v1_stat_snapshots(session, period_start=p_start, period_end=p_end, persist=False)
        prev = run_v1_stat_snapshots(session, period_start=prev_start, period_end=prev_end, persist=False)

        cur_by_c = {r["scope_id"]: r for r in (cur.get("by_scope", {}).get("countries") or [])}
        prev_by_c = {r["scope_id"]: r for r in (prev.get("by_scope", {}).get("countries") or [])}
        country_meta = {c.id: c for c in session.scalars(select(Country)).all()}
        sources = {s.id: s for s in session.scalars(select(Source)).all()}

        comparison = []
        for cid in selected:
            row = cur_by_c.get(cid)
            prev_row = prev_by_c.get(cid)
            article_ids = list((row or {}).get("article_ids") or [])
            articles = (
                list(session.scalars(select(Article).where(Article.id.in_(article_ids))).all())
                if article_ids
                else []
            )
            analyses = _latest_analyses(session, [a.id for a in articles])

            sentiment_counts: Counter[str] = Counter()
            topic_counts: Counter[str] = Counter()
            narrative_counts: Counter[str] = Counter()
            active_src_ids: set[str] = set()
            for a in articles:
                active_src_ids.add(a.source_id)
                ana = analyses.get(a.id)
                structured = (ana.structured_result if ana else None) or {}
                schema_ver = ana.schema_version if ana else None
                sentiment_counts[extract_sentiment_label(structured)] += 1
                for tid in extract_v1_topics(structured, schema_version=schema_ver):
                    topic_counts[tid] += 1
                for n in extract_article_narratives(structured):
                    narrative_counts[n["label"]] += 1

            ev_links = (
                list(session.scalars(select(EventArticle).where(EventArticle.article_id.in_(article_ids))).all())
                if article_ids
                else []
            )
            ev_counts: Counter[str] = Counter(l.event_id for l in ev_links)
            top_ev_ids = [eid for eid, _ in ev_counts.most_common(5)]
            events_map = (
                {e.id: e for e in session.scalars(select(Event).where(Event.id.in_(top_ev_ids))).all()}
                if top_ev_ids
                else {}
            )

            art_count = int((row or {}).get("article_count") or 0)
            prev_count = int((prev_row or {}).get("article_count") or 0)
            classified = (
                int((row or {}).get("positive_count") or 0)
                + int((row or {}).get("neutral_count") or 0)
                + int((row or {}).get("negative_count") or 0)
            )
            total_sources = sum(1 for s in sources.values() if s.country_id == cid)

            comparison.append(
                {
                    "country_id": cid,
                    "country_name": country_meta[cid].name if cid in country_meta else cid,
                    "article_count": art_count,
                    "prev_article_count": prev_count,
                    "delta": art_count - prev_count,
                    "reporting_sources": len(active_src_ids),
                    "total_registered_sources": total_sources,
                    "small_sample_warning": art_count < 10 or classified < 5,
                    "sample_note": (
                        f"样本量较小（{art_count} 篇，已标注立场 {classified} 篇），立场比例仅供参考，不可外推为该国媒体整体立场。"
                        if (art_count < 10 or classified < 5)
                        else None
                    ),
                    "sentiment_counts": dict(sentiment_counts),
                    "stance": {
                        "target": "china_mainland",
                        "positive_count": int((row or {}).get("positive_count") or 0),
                        "neutral_count": int((row or {}).get("neutral_count") or 0),
                        "negative_count": int((row or {}).get("negative_count") or 0),
                        "unclassified_count": int((row or {}).get("unclassified_count") or 0),
                        "classified_count": classified,
                        "positive_rate": (row or {}).get("positive_rate"),
                        "neutral_rate": (row or {}).get("neutral_rate"),
                        "negative_rate": (row or {}).get("negative_rate"),
                        "stance_coverage_rate": (row or {}).get("stance_coverage_rate"),
                    },
                    "topics_top": [
                        {"topic_id": tid, "article_count": n}
                        for tid, n in topic_counts.most_common(6)
                    ],
                    "narratives_top": [
                        {"label": lbl, "article_count": n}
                        for lbl, n in narrative_counts.most_common(5)
                    ],
                    "top_events": [
                        {
                            "event_id": eid,
                            "title": events_map[eid].title,
                            "article_count": ev_counts[eid],
                        }
                        for eid in top_ev_ids
                        if eid in events_map
                    ],
                    "representative_articles": [
                        project_article_summary(a, sources.get(a.source_id), analyses.get(a.id))
                        for a in articles[:5]
                    ],
                }
            )

        cached = load_cached_assessments(session, report_type="daily")
        return {
            "meta": {
                "period_start": p_start.isoformat(),
                "period_end": p_end.isoformat(),
                "days": days,
                "methodology_version": METHODOLOGY_VERSION,
                "taxonomy_version": TAXONOMY_V1_VERSION,
                "attribution_note": "国家归属严格按照信源所属国家 (source_country)，不按事件发生地归属。",
                "stance_note": "立场比例分母不包含 Unclassified；情感与对华立场分开展示。",
            },
            "countries": comparison,
            "country_comparison_assessment": cached.get("country_comparison"),
        }


@router.get("/api/countries/{country_id}")
def api_country_detail(country_id: str) -> dict[str, Any]:
    with session_scope() as session:
        detail = country_detail_payload(session, country_id)
        if not detail:
            raise HTTPException(status_code=404, detail="country not found")
        return detail


@router.get("/api/countries/{country_id}/china-attitude")
def api_country_china_attitude(
    country_id: str,
    window: str = Query("30d"),
) -> dict[str, Any]:
    with session_scope() as session:
        return get_country_china_attitude(session, country_id.upper(), window=window)

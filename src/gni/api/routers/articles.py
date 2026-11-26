"""Articles & Evidence Explorer endpoints: paginated filterable articles, full article intelligence, direct evidence lookup."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

from gni.api.routers.common import (
    as_utc,
    extract_article_narratives,
    extract_expression_owner,
    extract_sentiment_label,
    extract_verified_evidence,
    parse_iso,
    project_article_summary,
)
from gni.analysis.stance_util import (
    extract_v1_china_stance,
    extract_v1_stance_evidence,
    extract_v1_topics,
)
from gni.infrastructure.db import session_scope
from gni.infrastructure.models import (
    Article,
    ArticleVersion,
    Event,
    EventArticle,
    EventNarrativeEvidence,
    NarrativeCluster,
    Source,
)
from gni.metrics.definitions import CHINA_INCLUDE_LEVELS
from gni.metrics.service import _latest_analyses

router = APIRouter(tags=["articles", "evidence"])


class ArticleTraceRequest(BaseModel):
    article_ids: list[str] = Field(default_factory=list)
    limit: int = Field(default=30, ge=1, le=50)


@router.post("/api/articles/trace")
def api_articles_trace(body: ArticleTraceRequest) -> dict[str, Any]:
    """Return traceable article metadata + V1.0 China stance & stance_evidence for given article_ids."""
    ids = [str(x).strip() for x in body.article_ids if str(x).strip()][: body.limit]
    if not ids:
        return {"articles": []}
    with session_scope() as session:
        articles = list(session.scalars(select(Article).where(Article.id.in_(ids))).all())
        sources = {s.id: s for s in session.scalars(select(Source)).all()}
        analyses = _latest_analyses(session, [a.id for a in articles])
        rows = []
        for a in articles:
            src = sources.get(a.source_id)
            ana = analyses.get(a.id)
            structured = (ana.structured_result if ana else None) or {}
            schema_ver = ana.schema_version if ana else None
            stance = extract_v1_china_stance(structured, schema_version=schema_ver)
            ev = extract_v1_stance_evidence(structured, schema_version=schema_ver)
            verified_ev = extract_verified_evidence(a, src, ana)
            cs = structured.get("china_stance") if isinstance(structured.get("china_stance"), dict) else {}
            conf = cs.get("stance_confidence") if schema_ver in {"article_analysis_v1.0", "article_analysis_v1.1"} else None
            rows.append(
                {
                    "article_id": a.id,
                    "published_at": a.published_at.isoformat() if a.published_at else None,
                    "source_country": src.country_id if src else None,
                    "source_id": a.source_id,
                    "source_name": src.name if src else a.source_id,
                    "title": a.title,
                    "url": a.url,
                    "stance_label": stance,
                    "stance_confidence": conf if isinstance(conf, (int, float)) else None,
                    "stance_evidence": ev,
                    "verified_evidence": verified_ev,
                    "expression_owner": extract_expression_owner(structured),
                    "topics_v1": extract_v1_topics(structured, schema_version=schema_ver),
                }
            )
        rows.sort(key=lambda r: str(r.get("published_at") or ""), reverse=True)
        return {"articles": rows}


@router.get("/api/articles")
def api_articles_list(
    start: str | None = Query(None, description="ISO UTC published_at >= start"),
    end: str | None = Query(None, description="ISO UTC published_at < end"),
    country: str | None = Query(None, description="Source country_id, e.g. US"),
    source: str | None = Query(None, description="source_id or partial source name"),
    topic: str | None = Query(None, description="V1.0 topic_id"),
    event_id: str | None = Query(None, description="Linked event_id"),
    narrative: str | None = Query(None, description="Narrative cluster id or label substring"),
    sentiment: str | None = Query(None, description="positive|neutral|negative|unknown"),
    stance: str | None = Query(None, description="Positive|Neutral|Negative|Unclassified"),
    q: str | None = Query(None, description="Title/content keyword search"),
    china_only: bool = Query(True, description="Filter to China-relevant set by default"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
) -> dict[str, Any]:
    start_dt = parse_iso(start)
    end_dt = parse_iso(end)
    with session_scope() as session:
        sources = {s.id: s for s in session.scalars(select(Source)).all()}
        articles = list(session.scalars(select(Article)).all())

        # Optional event_id filter set
        event_article_ids: set[str] | None = None
        if event_id:
            event_article_ids = {
                r.article_id
                for r in session.scalars(
                    select(EventArticle).where(EventArticle.event_id == event_id)
                ).all()
            }

        # Optional narrative cluster id filter set
        narrative_article_ids: set[str] | None = None
        if narrative:
            cluster_links = {
                r.article_id
                for r in session.scalars(
                    select(EventNarrativeEvidence).where(
                        EventNarrativeEvidence.narrative_cluster_id == narrative
                    )
                ).all()
            }
            if cluster_links:
                narrative_article_ids = cluster_links

        # Event links map for all candidate articles
        all_ea = list(session.scalars(select(EventArticle)).all())
        ev_by_article: dict[str, list[str]] = defaultdict(list)
        for link in all_ea:
            ev_by_article[link.article_id].append(link.event_id)

        # Pre-filter cheap fields before loading analyses
        pre: list[Article] = []
        country_u = country.strip().upper() if country else None
        source_l = source.strip().lower() if source else None
        q_l = q.strip().lower() if q else None

        for a in articles:
            if china_only and (a.exclude_from_metrics or a.china_relevance_level not in CHINA_INCLUDE_LEVELS):
                continue
            if event_article_ids is not None and a.id not in event_article_ids:
                continue
            dt = as_utc(a.published_at)
            if start_dt and (dt is None or dt < start_dt):
                continue
            if end_dt and (dt is None or dt >= end_dt):
                continue
            src = sources.get(a.source_id)
            if country_u and (not src or (src.country_id or "").upper() != country_u):
                continue
            if source_l:
                sname = (src.name if src else "").lower()
                if source_l not in a.source_id.lower() and source_l not in sname:
                    continue
            if q_l:
                hay = f"{a.title or ''} {(a.content_clean or '')[:800]}".lower()
                if q_l not in hay:
                    continue
            pre.append(a)

        analyses = _latest_analyses(session, [a.id for a in pre])
        topic_f = topic.strip() if topic else None
        sent_f = sentiment.strip().lower() if sentiment else None
        stance_f = stance.strip().lower() if stance else None
        narr_l = narrative.strip().lower() if narrative else None

        matched: list[dict[str, Any]] = []
        for a in pre:
            ana = analyses.get(a.id)
            summary = project_article_summary(
                a, sources.get(a.source_id), ana, event_ids=ev_by_article.get(a.id, [])
            )
            if topic_f and topic_f not in summary["topics_v1"]:
                continue
            if sent_f and str(summary["sentiment_label"]).lower() != sent_f:
                continue
            if stance_f and str(summary["stance_label"]).lower() != stance_f:
                continue
            if narr_l:
                if narrative_article_ids is not None:
                    if a.id not in narrative_article_ids:
                        continue
                else:
                    if not any(narr_l in str(n.get("label") or "").lower() for n in summary["narratives"]):
                        continue
            matched.append(summary)

        # Strictly sort by published_at descending
        matched.sort(key=lambda r: str(r.get("published_at") or ""), reverse=True)
        total = len(matched)
        offset = (page - 1) * page_size
        page_items = matched[offset : offset + page_size]

        return {
            "items": page_items,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": max(1, (total + page_size - 1) // page_size),
            },
            "sort": "published_at_desc",
        }


@router.get("/api/articles/{article_id}")
def api_article_detail(article_id: str) -> dict[str, Any]:
    with session_scope() as session:
        article = session.get(Article, article_id)
        if not article:
            raise HTTPException(status_code=404, detail="article not found")
        source = session.get(Source, article.source_id)
        ana = _latest_analyses(session, [article.id]).get(article.id)
        structured = (ana.structured_result if ana else None) or {}
        intel = (
            structured.get("article_intelligence")
            if isinstance(structured.get("article_intelligence"), dict)
            else None
        )

        # Linked events
        ea_ids = [
            r.event_id
            for r in session.scalars(
                select(EventArticle).where(EventArticle.article_id == article.id)
            ).all()
        ]
        events = (
            list(session.scalars(select(Event).where(Event.id.in_(ea_ids))).all()) if ea_ids else []
        )

        # Linked narrative clusters
        ne_rows = list(
            session.scalars(
                select(EventNarrativeEvidence).where(EventNarrativeEvidence.article_id == article.id)
            ).all()
        )
        cluster_ids = list({r.narrative_cluster_id for r in ne_rows})
        clusters = (
            {c.id: c for c in session.scalars(select(NarrativeCluster).where(NarrativeCluster.id.in_(cluster_ids))).all()}
            if cluster_ids
            else {}
        )

        latest_ver = session.scalar(
            select(ArticleVersion)
            .where(ArticleVersion.article_id == article.id)
            .order_by(ArticleVersion.version_no.desc())
            .limit(1)
        )

        summary = project_article_summary(article, source, ana, event_ids=ea_ids)
        evidence_segments = extract_verified_evidence(article, source, ana)
        body_text = article.content_clean or article.content_original or ""
        limitations: list[str] = []
        if not body_text.strip():
            limitations.append("系统未保存该文章正文，仅展示标题、元数据与已有证据摘录。")
        if not article.url:
            limitations.append("原始链接缺失。")
        if summary["expression_owner"] == "quoted_actor":
            limitations.append("立场归属为引述对象 (quoted_actor)，不代表媒体自身立场。")

        return {
            **summary,
            "canonical_url": article.canonical_url,
            "content_excerpt": body_text[:4000],
            "content_length": len(body_text),
            "article_version_id": latest_ver.id if latest_ver else None,
            "evidence_segments": evidence_segments,
            "article_intelligence": intel,
            "related_events": [
                {
                    "event_id": e.id,
                    "title": e.title,
                    "event_type": e.event_type,
                    "event_time": e.event_time.isoformat() if e.event_time else None,
                }
                for e in events
            ],
            "related_narratives": [
                {
                    "narrative_id": cid,
                    "name": clusters[cid].label,
                    "frame": clusters[cid].frame_id,
                }
                for cid in cluster_ids
                if cid in clusters
            ]
            or summary["narratives"],
            "data_source": source.name if source else article.source_id,
            "limitations": limitations,
        }


@router.get("/api/evidence/{evidence_id:path}")
def api_evidence_lookup(evidence_id: str) -> dict[str, Any]:
    """Resolve an evidence_id or article_id to its exact verified span, context, and parent article."""
    target = evidence_id.strip()
    if not target:
        raise HTTPException(status_code=400, detail="evidence_id is required")

    with session_scope() as session:
        # 1. Direct article_id lookup
        direct_article = session.get(Article, target)
        if direct_article:
            detail = api_article_detail(direct_article.id)
            segs = detail.get("evidence_segments") or []
            return {
                "resolved_by": "article_id",
                "evidence_id": segs[0]["evidence_id"] if segs else f"article:{direct_article.id}",
                "article_id": direct_article.id,
                "evidence": segs[0] if segs else None,
                "all_evidence_segments": segs,
                "article": detail,
            }

        # 2. Structured ev:{article_id}:... pattern or scan latest analyses
        candidate_article_id: str | None = None
        if target.startswith("ev:"):
            parts = target.split(":")
            if len(parts) >= 2 and parts[1]:
                candidate_article_id = parts[1]

        if candidate_article_id:
            art = session.get(Article, candidate_article_id)
            if art:
                detail = api_article_detail(art.id)
                segs = detail.get("evidence_segments") or []
                match = next((s for s in segs if s.get("evidence_id") == target), segs[0] if segs else None)
                return {
                    "resolved_by": "evidence_id",
                    "evidence_id": target,
                    "article_id": art.id,
                    "evidence": match,
                    "all_evidence_segments": segs,
                    "article": detail,
                }

        # 3. Fallback scan for custom evidence_id inside article_intelligence
        articles = list(session.scalars(select(Article)).all())
        sources = {s.id: s for s in session.scalars(select(Source)).all()}
        analyses = _latest_analyses(session, [a.id for a in articles])
        for a in articles:
            segs = extract_verified_evidence(a, sources.get(a.source_id), analyses.get(a.id))
            for s in segs:
                if s.get("evidence_id") == target:
                    detail = api_article_detail(a.id)
                    return {
                        "resolved_by": "evidence_id_scan",
                        "evidence_id": target,
                        "article_id": a.id,
                        "evidence": s,
                        "all_evidence_segments": detail.get("evidence_segments") or [],
                        "article": detail,
                    }

        raise HTTPException(status_code=404, detail=f"evidence not found: {target}")

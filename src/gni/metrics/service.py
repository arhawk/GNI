"""Load articles and persist metric_runs."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from gni.infrastructure.models import Article, ArticleAnalysis, MetricRun, Source, SourceHealth
from gni.metrics.compute import ArticleMetricRow, SourceHealthRow, compute_metrics
from gni.metrics.definitions import (
    DEDUPLICATION_METHOD,
    METRIC_DEFINITION_VERSION,
    RELEVANCE_WEIGHT_VERSION,
)

logger = logging.getLogger(__name__)


def _latest_analyses(session: Session, article_ids: list[str]) -> dict[str, ArticleAnalysis]:
    if not article_ids:
        return {}
    rows = session.scalars(
        select(ArticleAnalysis)
        .where(ArticleAnalysis.article_id.in_(article_ids))
        .order_by(ArticleAnalysis.created_at.desc())
    ).all()
    latest: dict[str, ArticleAnalysis] = {}
    for row in rows:
        if row.article_id not in latest:
            latest[row.article_id] = row
    return latest


def _row_from_article(
    article: Article,
    country_id: str | None,
    analysis: ArticleAnalysis | None,
    *,
    feed_scope: str | None = None,
    ownership_type: str | None = None,
    government_control_level: str | None = None,
) -> ArticleMetricRow:
    structured = (analysis.structured_result if analysis else None) or {}
    sentiment = _as_mapping(structured.get("sentiment"))
    framing = _as_mapping(structured.get("framing"))
    topics = _as_mapping(structured.get("topics"))
    stances = structured.get("stances") or []
    return ArticleMetricRow(
        id=article.id,
        source_id=article.source_id,
        country_id=country_id,
        exclude_from_metrics=bool(article.exclude_from_metrics),
        content_hash=article.content_hash,
        title_hash=article.title_hash,
        published_at=article.published_at,
        first_seen_at=article.first_seen_at,
        china_relevance_level=article.china_relevance_level,
        china_relevance_weight=article.china_relevance_weight,
        quality_status=article.quality_status,
        processing_status=article.processing_status,
        analysis_status=article.analysis_status,
        feed_scope=feed_scope,
        ownership_type=ownership_type,
        government_control_level=government_control_level,
        sentiment_label=sentiment.get("label") if isinstance(sentiment.get("label"), str) else None,
        sentiment_score=sentiment.get("score") if isinstance(sentiment.get("score"), (int, float)) else None,
        sentiment_status=sentiment.get("status") if isinstance(sentiment.get("status"), str) else None,
        stances=list(stances) if isinstance(stances, list) else [],
        frame_primary=_primary_label(framing, structured.get("framing")),
        topic_primary=_primary_label(topics, structured.get("topics")),
    )


def _as_mapping(value: object) -> dict:
    return value if isinstance(value, dict) else {}


def _primary_label(mapped: dict, raw: object) -> str | None:
    primary = mapped.get("primary")
    if isinstance(primary, str):
        return primary
    # DeepSeek occasionally returns a bare list of topic/frame ids
    if isinstance(raw, list) and raw:
        first = raw[0]
        if isinstance(first, str):
            return first
        if isinstance(first, dict) and isinstance(first.get("id"), str):
            return first["id"]
    return None


def run_metrics(
    session: Session,
    *,
    days: int | None = 7,
    window_start: datetime | None = None,
    window_end: datetime | None = None,
    country: str | None = None,
    source_id: str | None = None,
    target: str = "china",
    timezone_name: str = "UTC",
) -> MetricRun:
    end = window_end or datetime.now(timezone.utc)
    if window_start is not None:
        start = window_start
    elif days is not None:
        start = end - timedelta(days=days)
    else:
        start = None

    country_scope = [country] if country else None
    source_scope = [source_id] if source_id else None

    session.flush()
    sources = {s.id: s for s in session.scalars(select(Source)).all()}
    articles = list(session.scalars(select(Article)).all())
    analyses = _latest_analyses(session, [a.id for a in articles])

    rows: list[ArticleMetricRow] = []
    for article in articles:
        src = sources.get(article.source_id)
        country_id = src.country_id if src else None
        rows.append(
            _row_from_article(
                article,
                country_id,
                analyses.get(article.id),
                feed_scope=getattr(src, "feed_scope", None) if src else None,
                ownership_type=getattr(src, "ownership_type", None) if src else None,
                government_control_level=getattr(src, "government_control_level", None)
                if src
                else None,
            )
        )

    health_rows: list[SourceHealthRow] = []
    health_map = {
        h.source_id: h
        for h in session.scalars(select(SourceHealth)).all()
    }
    for sid, src in sources.items():
        h = health_map.get(sid)
        health_rows.append(
            SourceHealthRow(
                source_id=sid,
                country_id=src.country_id,
                active_status=src.active_status,
                success_count=h.success_count if h else 0,
                failure_count=h.failure_count if h else 0,
            )
        )

    results = compute_metrics(
        rows,
        source_health=health_rows,
        window_start=start,
        window_end=end,
        country_scope=country_scope,
        source_scope=source_scope,
        target_scope=target,
        timezone=timezone_name,
    )

    research = results.get("research") or {}
    attention = research.get("attention_share") or {}
    article_count = research.get("article_count") or {}

    run = MetricRun(
        id=str(uuid4()),
        status="success",
        metric_definition_version=METRIC_DEFINITION_VERSION,
        relevance_weight_version=RELEVANCE_WEIGHT_VERSION,
        deduplication_method=DEDUPLICATION_METHOD,
        timezone=timezone_name,
        window_start=start,
        window_end=end,
        country_scope=country_scope,
        source_scope=source_scope,
        topic_scope=None,
        target_scope=target,
        numerator=article_count.get("numerator"),
        denominator=attention.get("denominator"),
        excluded_count=results.get("excluded_duplicates") or 0,
        missing_count=article_count.get("missing_count") or 0,
        results=results,
        computed_at=datetime.now(timezone.utc),
        stats={
            "universe_count": results.get("universe_count"),
            "attention_share_status": attention.get("status"),
        },
    )
    session.add(run)
    session.flush()
    return run


def metric_run_to_dict(run: MetricRun) -> dict[str, Any]:
    return {
        "run_id": run.id,
        "status": run.status,
        "metric_definition_version": run.metric_definition_version,
        "relevance_weight_version": run.relevance_weight_version,
        "deduplication_method": run.deduplication_method,
        "timezone": run.timezone,
        "window_start": run.window_start.isoformat() if run.window_start else None,
        "window_end": run.window_end.isoformat() if run.window_end else None,
        "country_scope": run.country_scope,
        "source_scope": run.source_scope,
        "target_scope": run.target_scope,
        "numerator": run.numerator,
        "denominator": run.denominator,
        "excluded_count": run.excluded_count,
        "missing_count": run.missing_count,
        "computed_at": run.computed_at.isoformat() if run.computed_at else None,
        "stats": run.stats,
        "results": run.results,
    }

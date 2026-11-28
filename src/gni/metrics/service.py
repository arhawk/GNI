"""Load articles and persist metric_runs."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from gni.analysis.stance_util import (
    extract_v1_china_stance,
    extract_v1_stance_evidence,
    extract_v1_topics,
)
from gni.infrastructure.models import (
    Article,
    ArticleAnalysis,
    MetricRun,
    Source,
    SourceHealth,
    StatSnapshot,
)
from gni.metrics.compute import ArticleMetricRow, SourceHealthRow, compute_metrics
from gni.metrics.definitions import (
    DEDUPLICATION_METHOD,
    METHODOLOGY_VERSION,
    METRIC_DEFINITION_VERSION,
    RELEVANCE_WEIGHT_VERSION,
    TAXONOMY_V1_VERSION,
    V1_ANALYSIS_VERSION,
)
from gni.metrics.v1_stats import (
    V1ArticleInput,
    compute_v1_stat_snapshots,
    group_snapshots_by_scope,
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


def run_v1_stat_snapshots(
    session: Session,
    *,
    period_start: datetime,
    period_end: datetime,
    persist: bool = True,
    include_zero_taxonomy: bool = True,
    include_source_scope: bool = False,
) -> dict[str, Any]:
    """Compute (and optionally persist) V1.0 traceable stat snapshots across 4 scopes."""
    sources = {s.id: s for s in session.scalars(select(Source)).all()}
    articles = list(session.scalars(select(Article)).all())
    analyses = _latest_analyses(session, [a.id for a in articles])

    inputs: list[V1ArticleInput] = []
    evidence_by_article: dict[str, list[dict[str, Any]]] = {}
    for a in articles:
        src = sources.get(a.source_id)
        ana = analyses.get(a.id)
        structured = (ana.structured_result if ana else None) or {}
        schema_ver = ana.schema_version if ana else None
        stance = extract_v1_china_stance(structured, schema_version=schema_ver)
        topics = extract_v1_topics(structured, schema_version=schema_ver)
        ev = extract_v1_stance_evidence(structured, schema_version=schema_ver)
        if ev:
            evidence_by_article[a.id] = ev
        inputs.append(
            V1ArticleInput(
                article_id=a.id,
                source_id=a.source_id,
                source_country=src.country_id if src else None,
                published_at=a.published_at,
                canonical_url=a.canonical_url,
                url=a.url,
                content_hash=a.content_hash,
                exclude_from_metrics=bool(a.exclude_from_metrics),
                duplicate_of_article_id=a.duplicate_of_article_id,
                first_seen_at=a.first_seen_at,
                china_relevance_level=a.china_relevance_level,
                topics_v1=topics,
                stance_label=stance,
                stance_evidence=ev,
                analysis_schema_version=schema_ver,
                sentiment_label=(
                    (structured.get("sentiment") or {}).get("label")
                    if isinstance(structured.get("sentiment"), dict)
                    else None
                ),
            )
        )

    generated_at = datetime.now(timezone.utc)
    rows = compute_v1_stat_snapshots(
        inputs,
        period_start=period_start,
        period_end=period_end,
        generated_at=generated_at,
        include_zero_taxonomy=include_zero_taxonomy,
        include_source_scope=include_source_scope,
    )

    if persist:
        for r in rows:
            session.add(
                StatSnapshot(
                    id=str(uuid4()),
                    period_start=r.period_start,
                    period_end=r.period_end,
                    scope_type=r.scope_type,
                    scope_id=r.scope_id,
                    article_count=r.article_count,
                    positive_count=r.positive_count,
                    neutral_count=r.neutral_count,
                    negative_count=r.negative_count,
                    unclassified_count=r.unclassified_count,
                    positive_rate=r.positive_rate,
                    neutral_rate=r.neutral_rate,
                    negative_rate=r.negative_rate,
                    stance_coverage_rate=r.stance_coverage_rate,
                    methodology_version=r.methodology_version,
                    taxonomy_version=r.taxonomy_version,
                    analysis_version=r.analysis_version,
                    article_ids=r.article_ids,
                    generated_at=r.generated_at,
                )
            )
        session.flush()

    return {
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "methodology_version": METHODOLOGY_VERSION,
        "taxonomy_version": TAXONOMY_V1_VERSION,
        "analysis_version": V1_ANALYSIS_VERSION,
        "generated_at": generated_at.isoformat(),
        "persisted": persist,
        "snapshot_count": len(rows),
        "by_scope": group_snapshots_by_scope(rows),
        "snapshots": [r.to_dict() for r in rows],
        "evidence_by_article": evidence_by_article,
    }


def get_historical_trend(
    session: Session,
    *,
    scope_type: str,
    scope_id: str,
    limit: int = 30,
) -> list[dict[str, Any]]:
    """Return chronological historical StatSnapshot series for a given scope."""
    rows = list(
        session.scalars(
            select(StatSnapshot)
            .where(
                StatSnapshot.scope_type == scope_type,
                StatSnapshot.scope_id == scope_id,
            )
            .order_by(StatSnapshot.period_start.desc(), StatSnapshot.generated_at.desc())
            .limit(max(1, limit * 3))
        ).all()
    )
    # Keep latest generated snapshot per (period_start, period_end)
    dedup: dict[tuple[datetime, datetime], StatSnapshot] = {}
    for r in rows:
        key = (r.period_start, r.period_end)
        if key not in dedup:
            dedup[key] = r
    ordered = sorted(dedup.values(), key=lambda x: x.period_start)[-limit:]
    return [
        {
            "period_start": r.period_start.isoformat(),
            "period_end": r.period_end.isoformat(),
            "scope_type": r.scope_type,
            "scope_id": r.scope_id,
            "article_count": r.article_count,
            "positive_count": r.positive_count,
            "neutral_count": r.neutral_count,
            "negative_count": r.negative_count,
            "unclassified_count": r.unclassified_count,
            "positive_rate": r.positive_rate,
            "neutral_rate": r.neutral_rate,
            "negative_rate": r.negative_rate,
            "stance_coverage_rate": r.stance_coverage_rate,
            "methodology_version": r.methodology_version,
        }
        for r in ordered
    ]

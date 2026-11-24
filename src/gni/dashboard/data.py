"""Dashboard data access — DB queries without Streamlit dependency."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

NAV_PAGES = [
    "Overview",
    "Countries",
    "News & Events",
    "Articles",
    "Reports",
    "Alerts",
    "Sources & Quality",
    "Research",
]

from sqlalchemy import select
from sqlalchemy.orm import Session

from gni.infrastructure.models import (
    Article,
    ArticleAnalysis,
    ArticleChinaSpan,
    Country,
    Source,
    SourceHealth,
)
from gni.metrics.compute import ArticleMetricRow, SourceHealthRow, compute_metrics, is_china_included
from gni.metrics.definitions import CHINA_INCLUDE_LEVELS, METRIC_DEFINITION_VERSION, RELEVANCE_WEIGHT_VERSION
from gni.metrics.service import _latest_analyses, _row_from_article


MAX_WINDOW_DAYS = 366
PRESET_DAYS = (1, 7, 30, 90, 365)


@dataclass
class DashboardFilters:
    days: int = 30
    """Rolling length used when window_start/window_end are not both set."""
    window_start: datetime | None = None
    window_end: datetime | None = None
    """Absolute UTC bounds. If either is set, resolves with days / now as needed."""
    countries: list[str] = field(default_factory=list)
    source_ids: list[str] = field(default_factory=list)
    target: str = "china"
    relevance_levels: list[str] = field(default_factory=lambda: sorted(CHINA_INCLUDE_LEVELS))
    sentiments: list[str] = field(default_factory=list)
    stances: list[str] = field(default_factory=list)
    frames: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    analysis_statuses: list[str] = field(default_factory=list)
    timezone_label: str = "UTC"


@dataclass
class ArticleCard:
    id: str
    title: str | None
    url: str
    source_id: str
    source_name: str | None
    country_id: str | None
    published_at: datetime | None
    china_relevance_level: str | None
    china_relevance_weight: float | None
    sentiment_label: str | None
    stance_labels: list[str]
    topic_primary: str | None
    frame_primary: str | None
    analysis_status: str | None
    language: str | None
    structured_result: dict[str, Any] | None = None


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def window_bounds(
    days: int = 30,
    *,
    window_start: datetime | None = None,
    window_end: datetime | None = None,
) -> tuple[datetime, datetime]:
    """Resolve [start, end] UTC. Explicit bounds override rolling-from-now."""
    end = _as_utc(window_end) if window_end is not None else datetime.now(timezone.utc)
    if window_start is not None:
        start = _as_utc(window_start)
    else:
        start = end - timedelta(days=max(1, min(int(days), MAX_WINDOW_DAYS)))
    if start >= end:
        raise ValueError("window_start must be before window_end")
    span = (end - start).total_seconds() / 86400.0
    if span > MAX_WINDOW_DAYS:
        raise ValueError(f"window span exceeds {MAX_WINDOW_DAYS} days")
    return start, end


def resolve_filter_window(filters: DashboardFilters) -> tuple[datetime, datetime]:
    return window_bounds(
        filters.days,
        window_start=filters.window_start,
        window_end=filters.window_end,
    )


def article_data_range(session: Session) -> tuple[datetime | None, datetime | None]:
    """Min/max event times for timeline slider extents."""
    rows = session.scalars(select(Article)).all()
    times: list[datetime] = []
    for a in rows:
        t = a.published_at or a.first_seen_at
        if t is not None:
            times.append(_as_utc(t))
    if not times:
        return None, None
    return min(times), max(times)


def monitoring_panel_counts(session: Session) -> dict[str, int]:
    """P1-A panel: active sources and distinct countries among them (not China-set)."""
    active = [
        s
        for s in session.scalars(select(Source)).all()
        if (s.active_status or "").lower() == "active"
    ]
    countries = {s.country_id for s in active if s.country_id}
    return {
        "monitoring_countries": len(countries),
        "active_sources_registry": len(active),
    }


def load_countries(session: Session) -> list[dict[str, str]]:
    rows = session.scalars(select(Country).order_by(Country.id)).all()
    return [{"id": c.id, "name": c.name} for c in rows]


def load_sources(session: Session) -> list[dict[str, Any]]:
    rows = session.scalars(select(Source).order_by(Source.id)).all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "country_id": s.country_id,
            "active_status": s.active_status,
            "language": s.language,
            "ownership_type": s.ownership_type,
            "government_control_level": s.government_control_level,
            "verification_status": s.verification_status,
        }
        for s in rows
    ]


def load_source_health(session: Session) -> list[dict[str, Any]]:
    sources = {s.id: s for s in session.scalars(select(Source)).all()}
    health = {h.source_id: h for h in session.scalars(select(SourceHealth)).all()}
    out: list[dict[str, Any]] = []
    for sid, src in sources.items():
        h = health.get(sid)
        succ = h.success_count if h else 0
        fail = h.failure_count if h else 0
        total = succ + fail
        out.append(
            {
                "source_id": sid,
                "name": src.name,
                "country_id": src.country_id,
                "active_status": src.active_status,
                "success_count": succ,
                "failure_count": fail,
                "success_rate": (succ / total) if total else None,
                "last_success_at": h.last_success_at.isoformat() if h and h.last_success_at else None,
                "last_failure_at": h.last_failure_at.isoformat() if h and h.last_failure_at else None,
                "error_message": h.error_message if h else None,
            }
        )
    return out


def _build_rows(session: Session) -> tuple[list[ArticleMetricRow], dict[str, Article], dict[str, Source], dict[str, ArticleAnalysis]]:
    sources = {s.id: s for s in session.scalars(select(Source)).all()}
    articles = list(session.scalars(select(Article)).all())
    analyses = _latest_analyses(session, [a.id for a in articles])
    rows: list[ArticleMetricRow] = []
    for article in articles:
        src = sources.get(article.source_id)
        rows.append(
            _row_from_article(article, src.country_id if src else None, analyses.get(article.id))
        )
    return rows, {a.id: a for a in articles}, sources, analyses


def compute_dashboard_metrics(
    session: Session,
    filters: DashboardFilters,
) -> dict[str, Any]:
    start, end = resolve_filter_window(filters)
    rows, _, sources, _ = _build_rows(session)
    health_orm = {h.source_id: h for h in session.scalars(select(SourceHealth)).all()}
    health_rows = [
        SourceHealthRow(
            source_id=sid,
            country_id=src.country_id,
            active_status=src.active_status,
            success_count=health_orm[sid].success_count if sid in health_orm else 0,
            failure_count=health_orm[sid].failure_count if sid in health_orm else 0,
        )
        for sid, src in sources.items()
    ]
    country_scope = filters.countries or None
    source_scope = filters.source_ids or None
    include = frozenset(filters.relevance_levels) if filters.relevance_levels else CHINA_INCLUDE_LEVELS
    return compute_metrics(
        rows,
        source_health=health_rows,
        window_start=start,
        window_end=end,
        country_scope=country_scope,
        source_scope=source_scope,
        target_scope=filters.target,
        timezone=filters.timezone_label,
        include_levels=include,
    )


def _passes_article_filters(card: ArticleCard, filters: DashboardFilters) -> bool:
    if filters.countries and (card.country_id not in filters.countries):
        return False
    if filters.source_ids and (card.source_id not in filters.source_ids):
        return False
    if filters.relevance_levels:
        if (card.china_relevance_level or "") not in filters.relevance_levels:
            return False
    if filters.sentiments and (card.sentiment_label or "") not in filters.sentiments:
        return False
    if filters.frames and (card.frame_primary or "") not in filters.frames:
        return False
    if filters.topics and (card.topic_primary or "") not in filters.topics:
        return False
    if filters.languages and (card.language or "") not in filters.languages:
        return False
    if filters.analysis_statuses and (card.analysis_status or "") not in filters.analysis_statuses:
        return False
    if filters.stances:
        if not any(s in filters.stances for s in card.stance_labels):
            return False
    return True


def _in_window(dt: datetime | None, start: datetime, end: datetime) -> bool:
    if dt is None:
        return False
    dt = _as_utc(dt)
    return start <= dt <= end


def list_article_cards(
    session: Session,
    filters: DashboardFilters,
    *,
    china_only: bool = True,
    limit: int = 200,
) -> list[ArticleCard]:
    rows, articles, sources, analyses = _build_rows(session)
    start, end = resolve_filter_window(filters)
    include = frozenset(filters.relevance_levels) if filters.relevance_levels else CHINA_INCLUDE_LEVELS
    cards: list[ArticleCard] = []
    for row in rows:
        if row.exclude_from_metrics:
            continue
        if not _in_window(row.published_at or row.first_seen_at, start, end):
            continue
        if china_only and not is_china_included(row, include):
            continue
        article = articles[row.id]
        src = sources.get(row.source_id)
        analysis = analyses.get(row.id)
        structured = analysis.structured_result if analysis else None
        stance_labels = []
        for st in row.stances:
            if st.get("stance"):
                stance_labels.append(str(st["stance"]))
        card = ArticleCard(
            id=row.id,
            title=article.title,
            url=article.url,
            source_id=row.source_id,
            source_name=src.name if src else None,
            country_id=row.country_id,
            published_at=row.published_at or row.first_seen_at,
            china_relevance_level=row.china_relevance_level,
            china_relevance_weight=row.china_relevance_weight,
            sentiment_label=row.sentiment_label,
            stance_labels=stance_labels,
            topic_primary=row.topic_primary,
            frame_primary=row.frame_primary,
            analysis_status=row.analysis_status,
            language=article.language,
            structured_result=structured,
        )
        if not _passes_article_filters(card, filters):
            continue
        cards.append(card)

    cards.sort(key=lambda c: c.published_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return cards[:limit]


def get_article_detail(session: Session, article_id: str) -> dict[str, Any] | None:
    article = session.get(Article, article_id)
    if not article:
        return None
    source = session.get(Source, article.source_id)
    analyses = _latest_analyses(session, [article_id])
    analysis = analyses.get(article_id)
    spans = session.scalars(
        select(ArticleChinaSpan)
        .where(ArticleChinaSpan.article_id == article_id)
        .order_by(ArticleChinaSpan.paragraph_index.asc())
    ).all()
    return {
        "article": {
            "id": article.id,
            "title": article.title,
            "url": article.url,
            "language": article.language,
            "published_at": article.published_at.isoformat() if article.published_at else None,
            "china_relevance_level": article.china_relevance_level,
            "china_relevance_weight": article.china_relevance_weight,
            "analysis_status": article.analysis_status,
            "fulltext_screening_label": article.fulltext_screening_label,
            "content_clean": (article.content_clean or "")[:4000],
        },
        "source": {
            "id": source.id if source else None,
            "name": source.name if source else None,
            "country_id": source.country_id if source else None,
        },
        "analysis": {
            "provider": analysis.provider if analysis else None,
            "model_name": analysis.model_name if analysis else None,
            "schema_version": analysis.schema_version if analysis else None,
            "taxonomy_version": analysis.taxonomy_version if analysis else None,
            "relevance_weight_version": analysis.relevance_weight_version if analysis else None,
            "structured_result": analysis.structured_result if analysis else None,
        },
        "spans": [
            {
                "paragraph_index": s.paragraph_index,
                "text_original": s.text_original,
                "validation_status": s.validation_status,
                "char_start": s.char_start,
                "char_end": s.char_end,
            }
            for s in spans
        ],
        "meta": {
            "metric_definition_version": METRIC_DEFINITION_VERSION,
            "relevance_weight_version": RELEVANCE_WEIGHT_VERSION,
        },
    }


def country_breakdown(
    session: Session,
    filters: DashboardFilters,
) -> list[dict[str, Any]]:
    """Per-country article count + weighted volume for ranking charts."""
    metrics_by_country: list[dict[str, Any]] = []
    countries = filters.countries or [c["id"] for c in load_countries(session)]
    for cid in countries:
        f = DashboardFilters(
            days=filters.days,
            window_start=filters.window_start,
            window_end=filters.window_end,
            countries=[cid],
            source_ids=filters.source_ids,
            target=filters.target,
            relevance_levels=filters.relevance_levels,
            timezone_label=filters.timezone_label,
        )
        m = compute_dashboard_metrics(session, f)
        metrics_by_country.append(
            {
                "country_id": cid,
                "article_count": m["research"]["article_count"]["value"],
                "weighted_volume": m["weighted"]["weighted_article_volume"]["value"],
                "weighted_sentiment_score": m["weighted"]["weighted_sentiment_score"]["value"],
                "attention_share": m["research"]["attention_share"],
            }
        )
    metrics_by_country.sort(key=lambda x: x["article_count"] or 0, reverse=True)
    return metrics_by_country

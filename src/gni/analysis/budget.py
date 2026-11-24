"""LLM / analysis budget guards — stop analysis when capped; never block ingest."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from gni.core.config import Settings, get_settings
from gni.infrastructure.models import AnalysisRun, ArticleAnalysis


@dataclass
class BudgetSnapshot:
    articles_analyzed_today: int
    estimated_cost_usd_today: float
    daily_article_limit: int
    daily_llm_budget_usd: float
    articles_remaining: int
    llm_budget_remaining_usd: float
    exhausted: bool
    reason: str | None = None


def _utc_day_start() -> datetime:
    now = datetime.now(timezone.utc)
    return datetime(now.year, now.month, now.day, tzinfo=timezone.utc)


def snapshot_budget(session: Session, settings: Settings | None = None) -> BudgetSnapshot:
    settings = settings or get_settings()
    day_start = _utc_day_start()

    article_count = session.scalar(
        select(func.count()).select_from(ArticleAnalysis).where(ArticleAnalysis.created_at >= day_start)
    ) or 0

    cost = session.scalar(
        select(func.coalesce(func.sum(AnalysisRun.estimated_cost_usd), 0.0)).where(
            AnalysisRun.started_at >= day_start
        )
    ) or 0.0
    cost_f = float(cost)

    art_rem = max(0, settings.daily_article_limit - int(article_count))
    usd_rem = max(0.0, settings.daily_llm_budget_usd - cost_f)
    exhausted = art_rem <= 0
    reason = None
    if art_rem <= 0:
        reason = "daily_article_limit_reached"
    return BudgetSnapshot(
        articles_analyzed_today=int(article_count),
        estimated_cost_usd_today=cost_f,
        daily_article_limit=settings.daily_article_limit,
        daily_llm_budget_usd=settings.daily_llm_budget_usd,
        articles_remaining=art_rem,
        llm_budget_remaining_usd=usd_rem,
        exhausted=exhausted,
        reason=reason,
    )


def llm_allowed(snapshot: BudgetSnapshot, *, estimated_cost_usd: float = 0.0) -> bool:
    """Whether a paid LLM call is allowed. Heuristic path ignores this."""
    if snapshot.articles_remaining <= 0:
        return False
    if estimated_cost_usd > 0 and snapshot.llm_budget_remaining_usd < estimated_cost_usd:
        return False
    return True

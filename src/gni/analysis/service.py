"""P1-C analysis orchestration: L2 → L3 → Relevance → six-dim analyze."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from gni.analysis.budget import llm_allowed, snapshot_budget
from gni.analysis.deepseek import PROMPT_VERSION as DEEPSEEK_PROMPT, analyze_with_fallback
from gni.analysis.heuristic import PROMPT_VERSION as HEURISTIC_PROMPT, SCHEMA_VERSION, TAXONOMY_VERSION
from gni.analysis.l2_fulltext import SCHEMA_VERSION as L2_SCHEMA, screen_fulltext
from gni.analysis.l3_spans import extract_china_spans
from gni.analysis.relevance import RELEVANCE_WEIGHT_VERSION, assess_relevance
from gni.core.config import get_settings
from gni.infrastructure.models import (
    AnalysisRun,
    Article,
    ArticleAnalysis,
    ArticleChinaSpan,
    ArticleRelevanceAssessment,
    ArticleScreening,
    ArticleVersion,
)

logger = logging.getLogger(__name__)


def _latest_version(session: Session, article_id: str) -> ArticleVersion | None:
    return session.scalar(
        select(ArticleVersion)
        .where(ArticleVersion.article_id == article_id)
        .order_by(ArticleVersion.version_no.desc())
        .limit(1)
    )


def analyze_article(
    session: Session,
    article: Article,
    *,
    analysis_run_id: str | None = None,
    provider: str = "heuristic",
    allow_llm: bool = True,
) -> dict[str, Any]:
    """Run L2/L3/relevance/structured analysis for one article. Never raises out."""
    result: dict[str, Any] = {"article_id": article.id, "ok": True}
    settings = get_settings()
    try:
        version = _latest_version(session, article.id)
        content = (version.content_clean if version else None) or article.content_clean
        version_id = version.id if version else None

        l2 = screen_fulltext(
            content,
            title=article.title,
            title_screening_label=article.title_screening_label,
            quality_status=article.quality_status,
        )
        screening = ArticleScreening(
            id=str(uuid4()),
            article_id=article.id,
            article_version_id=version_id,
            stage="fulltext",
            screening_label=l2.label,
            reason_codes=l2.reason_codes,
            matched_entities=l2.matched_entities,
            supporting_paragraph_ids=l2.supporting_paragraph_ids,
            confidence=l2.confidence,
            requires_human_review=l2.requires_human_review,
            priority=None,
            rule_version=l2.rule_version,
            entity_dictionary_version=l2.entity_dictionary_version,
            schema_version=L2_SCHEMA,
            input_hash=l2.input_hash,
        )
        session.add(screening)
        article.fulltext_screening_label = l2.label
        result["fulltext_screening"] = l2.label

        spans = extract_china_spans(content, l2, language=article.language)
        valid_n = sum(1 for s in spans if s.validation_status == "valid")
        for span in spans:
            session.add(
                ArticleChinaSpan(
                    id=str(uuid4()),
                    article_id=article.id,
                    article_version_id=version_id,
                    paragraph_index=span.paragraph_index,
                    char_start=span.char_start if span.char_start >= 0 else None,
                    char_end=span.char_end if span.char_end >= 0 else None,
                    text_original=span.text_original,
                    language=span.language,
                    span_type=span.span_type,
                    related_entities=span.related_entities,
                    candidate_targets=span.candidate_targets,
                    relevance_reason=span.relevance_reason,
                    extraction_confidence=span.extraction_confidence,
                    validation_status=span.validation_status,
                )
            )
        result["span_count"] = len(spans)
        result["valid_span_count"] = valid_n

        relevance = assess_relevance(
            l2,
            title=article.title,
            span_count=len(spans),
            valid_span_count=valid_n,
        )
        session.add(
            ArticleRelevanceAssessment(
                id=str(uuid4()),
                article_id=article.id,
                article_version_id=version_id,
                relevance_level=relevance.relevance_level,
                relevance_weight=relevance.relevance_weight,
                content_share_estimate=relevance.content_share_estimate,
                headline_prominence=relevance.headline_prominence,
                thesis_contribution=relevance.thesis_contribution,
                china_actor_role=relevance.china_actor_role,
                analysis_depth=relevance.analysis_depth,
                reasoning_summary=relevance.reasoning_summary,
                assessment_version=relevance.assessment_version,
                review_status="auto",
                features=relevance.features,
            )
        )
        article.china_relevance_level = relevance.relevance_level
        article.china_relevance_weight = relevance.relevance_weight
        result["relevance_level"] = relevance.relevance_level
        result["relevance_weight"] = relevance.relevance_weight

        use_provider = provider
        if provider == "deepseek" and not allow_llm:
            use_provider = "heuristic"

        structured, used_provider, model_name, tokens, cost = analyze_with_fallback(
            provider_name=use_provider,
            language=article.language,
            title=article.title,
            content_clean=content,
            l2_matched_entities=l2.matched_entities,
            spans=spans,
            relevance=relevance,
            settings=settings,
        )
        prompt_version = DEEPSEEK_PROMPT if used_provider == "deepseek" else HEURISTIC_PROMPT

        analysis = ArticleAnalysis(
            id=str(uuid4()),
            article_id=article.id,
            analysis_run_id=analysis_run_id,
            article_version_id=version_id,
            provider=used_provider,
            model_name=model_name,
            prompt_version=prompt_version,
            schema_version=SCHEMA_VERSION,
            taxonomy_version=TAXONOMY_VERSION,
            relevance_weight_version=RELEVANCE_WEIGHT_VERSION,
            analysis_status=structured.get("analysis_status") or "completed",
            confidence=(structured.get("confidence") or {}).get("overall"),
            token_usage=tokens,
            estimated_cost_usd=cost,
            structured_result=structured,
        )
        session.add(analysis)

        article.analysis_status = analysis.analysis_status
        article.analyzed_at = datetime.now(timezone.utc)
        article.updated_at = datetime.now(timezone.utc)
        result["provider"] = used_provider
        result["analysis_status"] = analysis.analysis_status
        result["token_usage"] = tokens
        result["estimated_cost_usd"] = cost
    except Exception as exc:  # noqa: BLE001
        logger.exception("analyze_article failed article_id=%s", article.id)
        article.analysis_status = "failed"
        article.analyzed_at = datetime.now(timezone.utc)
        result["ok"] = False
        result["error"] = str(exc)[:500]
    return result


def run_analysis(
    session: Session,
    *,
    limit: int | None = None,
    source_id: str | None = None,
    article_id: str | None = None,
    provider: str | None = None,
    reanalyze: bool = False,
) -> AnalysisRun:
    settings = get_settings()
    requested = (provider or settings.llm_provider or "heuristic").lower()
    if requested == "deepseek" and not settings.llm_api_key:
        requested = "heuristic"

    run = AnalysisRun(
        id=str(uuid4()),
        status="running",
        provider=requested,
        model_name=settings.llm_model if requested == "deepseek" else "heuristic-rules",
        prompt_version=DEEPSEEK_PROMPT if requested == "deepseek" else HEURISTIC_PROMPT,
        schema_version=SCHEMA_VERSION,
        taxonomy_version=TAXONOMY_VERSION,
        relevance_weight_version=RELEVANCE_WEIGHT_VERSION,
        started_at=datetime.now(timezone.utc),
        stats={},
    )
    session.add(run)
    session.flush()

    budget = snapshot_budget(session, settings)
    if budget.exhausted and not article_id:
        run.status = "budget_exhausted"
        run.finished_at = datetime.now(timezone.utc)
        run.stats = {
            "attempted": 0,
            "ok": 0,
            "failed": 0,
            "skipped_budget": True,
            "budget": budget.__dict__,
        }
        return run

    q = select(Article)
    if article_id:
        q = q.where(Article.id == article_id)
    else:
        q = q.where(Article.processing_status == "done")
        q = q.where(Article.exclude_from_metrics.is_(False))
        if source_id:
            q = q.where(Article.source_id == source_id)
        if not reanalyze:
            q = q.where(Article.analysis_status.in_(["pending", "failed"]))
        q = q.order_by(Article.first_seen_at.asc())
        cap = limit if limit is not None else settings.daily_article_limit
        cap = min(cap, budget.articles_remaining)
        if cap <= 0:
            run.status = "budget_exhausted"
            run.finished_at = datetime.now(timezone.utc)
            run.stats = {"attempted": 0, "ok": 0, "failed": 0, "skipped_budget": True}
            return run
        q = q.limit(cap)

    articles = list(session.scalars(q).all())
    ok = 0
    failed = 0
    stopped_budget = False
    total_tokens = 0
    total_cost = 0.0
    details: list[dict[str, Any]] = []

    for article in articles:
        live_budget = snapshot_budget(session, settings)
        if live_budget.exhausted:
            stopped_budget = True
            break

        allow_llm = requested == "deepseek" and llm_allowed(live_budget, estimated_cost_usd=0.002)
        detail = analyze_article(
            session,
            article,
            analysis_run_id=run.id,
            provider=requested,
            allow_llm=allow_llm,
        )
        details.append(detail)
        if detail.get("ok"):
            ok += 1
            total_tokens += int(detail.get("token_usage") or 0)
            total_cost += float(detail.get("estimated_cost_usd") or 0.0)
        else:
            failed += 1
        session.flush()

    if stopped_budget and ok == 0 and failed == 0:
        run.status = "budget_exhausted"
    elif failed == 0:
        run.status = "success"
    elif ok:
        run.status = "partial"
    else:
        run.status = "failed"

    run.finished_at = datetime.now(timezone.utc)
    run.token_usage = total_tokens
    run.estimated_cost_usd = total_cost
    run.stats = {
        "attempted": len(details),
        "ok": ok,
        "failed": failed,
        "provider_requested": requested,
        "stopped_budget": stopped_budget,
        "budget": snapshot_budget(session, settings).__dict__,
        "details_sample": details[:20],
    }
    return run

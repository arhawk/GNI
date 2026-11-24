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
    CollectionTask,
)
from gni.infrastructure.pipeline_state import (
    ANALYTICS_RELEVANCE_LEVELS,
    ANALYSIS_COMPLETED,
    AVAILABLE_FOR_ANALYTICS,
    FULLTEXT_SCREENED,
    set_pipeline_state,
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
        set_pipeline_state(article, FULLTEXT_SCREENED)

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
            confidence=_overall_confidence(structured.get("confidence")),
            token_usage=tokens,
            estimated_cost_usd=cost,
            structured_result=structured,
        )
        session.add(analysis)

        article.analysis_status = analysis.analysis_status
        article.analyzed_at = datetime.now(timezone.utc)
        article.updated_at = datetime.now(timezone.utc)
        if l2.label == "not_china_related":
            set_pipeline_state(article, FULLTEXT_SCREENED)
        elif (article.china_relevance_level or "") in ANALYTICS_RELEVANCE_LEVELS and (
            analysis.analysis_status == "completed"
        ):
            set_pipeline_state(article, AVAILABLE_FOR_ANALYTICS)
        else:
            set_pipeline_state(article, ANALYSIS_COMPLETED)
        result["provider"] = used_provider
        result["analysis_status"] = analysis.analysis_status
        result["pipeline_state"] = article.pipeline_state
        result["token_usage"] = tokens
        result["estimated_cost_usd"] = cost
    except Exception as exc:  # noqa: BLE001
        logger.exception("analyze_article failed article_id=%s", article.id)
        article.analysis_status = "failed"
        article.analyzed_at = datetime.now(timezone.utc)
        result["ok"] = False
        result["error"] = str(exc)[:500]
    return result


def _overall_confidence(confidence: Any) -> float | None:
    """DeepSeek sometimes returns confidence as a bare float instead of {overall: ...}."""
    if confidence is None:
        return None
    if isinstance(confidence, (int, float)):
        return float(confidence)
    if isinstance(confidence, dict):
        overall = confidence.get("overall")
        if isinstance(overall, (int, float)):
            return float(overall)
    return None


def _select_articles_for_analysis(
    session: Session,
    *,
    limit: int | None,
    source_id: str | None,
    article_id: str | None,
    reanalyze: bool,
    per_country: int | None,
    articles_remaining: int,
) -> tuple[list[Article], dict[str, int]]:
    """Pick articles; optional per-country cap then optional total limit (stricter wins)."""
    from collections import defaultdict

    from gni.infrastructure.models import Source

    if article_id:
        art = session.get(Article, article_id)
        return ([art] if art else []), {}

    q = select(Article).where(
        Article.processing_status == "done",
        Article.exclude_from_metrics.is_(False),
    )
    if source_id:
        q = q.where(Article.source_id == source_id)
    if not reanalyze:
        q = q.where(Article.analysis_status.in_(["pending", "failed"]))
    q = q.order_by(Article.first_seen_at.asc())

    # Fetch a wide pool when capping per country; otherwise apply limit in SQL.
    if per_country is not None and per_country > 0:
        pool_cap = max(per_country * 40, (limit or 0), 200)
        pool_cap = min(pool_cap, max(articles_remaining, 0) or pool_cap)
        candidates = list(session.scalars(q.limit(pool_cap)).all())
        sources = {
            s.id: s
            for s in session.scalars(
                select(Source).where(Source.id.in_({a.source_id for a in candidates}))
            ).all()
        } if candidates else {}
        by_country: dict[str, list[Article]] = defaultdict(list)
        for a in candidates:
            src = sources.get(a.source_id)
            cid = (src.country_id if src else None) or "UNK"
            if len(by_country[cid]) < per_country:
                by_country[cid].append(a)
        picked: list[Article] = []
        counts: dict[str, int] = {}
        for cid in sorted(by_country.keys()):
            rows = by_country[cid]
            counts[cid] = len(rows)
            picked.extend(rows)
        # Stable-ish: already first_seen order within country; keep country groups
        if limit is not None:
            picked = picked[: min(limit, articles_remaining)]
        else:
            picked = picked[:articles_remaining] if articles_remaining >= 0 else picked
        # Recount after total trim
        trimmed: dict[str, int] = defaultdict(int)
        sources2 = sources
        for a in picked:
            src = sources2.get(a.source_id)
            cid = (src.country_id if src else None) or "UNK"
            trimmed[cid] += 1
        return picked, dict(trimmed)

    cap = limit if limit is not None else 20
    cap = min(cap, articles_remaining) if articles_remaining >= 0 else cap
    if cap <= 0:
        return [], {}
    return list(session.scalars(q.limit(cap)).all()), {}


def run_analysis(
    session: Session,
    *,
    limit: int | None = None,
    source_id: str | None = None,
    article_id: str | None = None,
    provider: str | None = None,
    reanalyze: bool = False,
    per_country: int | None = None,
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

    task = CollectionTask(
        id=str(uuid4()),
        task_type="analyze",
        source_id=source_id,
        status="running",
        started_at=datetime.now(timezone.utc),
        legacy_job_id=run.id,
        code_version="analyze_v0.2_data_layers",
        config_snapshot=f"provider={requested}",
    )
    session.add(task)
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
        task.status = "budget_exhausted"
        task.finished_at = run.finished_at
        task.stats = {"skipped_budget": True}
        return run

    remaining = budget.articles_remaining
    if remaining <= 0 and not article_id:
        run.status = "budget_exhausted"
        run.finished_at = datetime.now(timezone.utc)
        run.stats = {"attempted": 0, "ok": 0, "failed": 0, "skipped_budget": True}
        task.status = "budget_exhausted"
        task.finished_at = run.finished_at
        task.stats = {"skipped_budget": True}
        return run

    effective_limit = limit
    if effective_limit is None and per_country is None and not article_id:
        effective_limit = settings.daily_article_limit

    articles, per_country_counts = _select_articles_for_analysis(
        session,
        limit=effective_limit,
        source_id=source_id,
        article_id=article_id,
        reanalyze=reanalyze,
        per_country=per_country,
        articles_remaining=remaining if not article_id else 10**9,
    )
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
        "per_country": per_country,
        "per_country_counts": per_country_counts,
        "budget": snapshot_budget(session, settings).__dict__,
        "details_sample": details[:20],
    }
    task.status = run.status
    task.finished_at = run.finished_at
    task.stats = {
        "attempted": len(details),
        "ok": ok,
        "failed": failed,
        "stopped_budget": stopped_budget,
        "per_country_counts": per_country_counts,
    }
    return run

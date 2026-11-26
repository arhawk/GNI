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
from gni.analysis.l3_spans import ChinaSpan, extract_china_spans, validate_span_quote
from gni.analysis.relevance import RELEVANCE_WEIGHT_VERSION, RelevanceAssessment, assess_relevance
from gni.core.config import get_settings
from gni.core.contracts import (
    ARTICLE_INTELLIGENCE_VERSION,
    ArticleAnalysisMetadataContract,
    ArticleEntityContract,
    ArticleEventCandidateContract,
    ArticleIntelligenceContract,
    ArticleNarrativeContract,
    ArticleQualityContract,
    ArticleRelevanceContract,
    ArticleSentimentContract,
    ArticleStanceContract,
    ArticleTopicContract,
    EvidenceSpanRef,
)
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
        body_chars = len(content or "")
        span_chars = sum(len(s.text_original or "") for s in spans if s.validation_status == "valid")

        relevance = assess_relevance(
            l2,
            title=article.title,
            span_count=len(spans),
            valid_span_count=valid_n,
            span_char_total=span_chars,
            body_char_total=body_chars,
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

        # Gate: clear not_china_related skips deep analysis (no LLM / heuristic six-dim).
        if l2.label == "not_china_related":
            gate_structured = validate_and_enrich_article_intelligence(
                {
                    "schema_version": SCHEMA_VERSION,
                    "taxonomy_version": TAXONOMY_VERSION,
                    "relevance_weight_version": RELEVANCE_WEIGHT_VERSION,
                    "analysis_status": "skipped_not_china",
                    "l2_label": l2.label,
                    "reason_codes": l2.reason_codes,
                    "topics_v1": [],
                    "boards_v1": [],
                    "china_stance": {
                        "target": "china_mainland",
                        "stance_label": "Unclassified",
                        "expression_owner": "unclear",
                        "stance_confidence": 0.0,
                        "stance_evidence": [],
                        "reasoning": "Not China-related (L2 gate).",
                        "analysis_status": "not_applicable",
                    },
                },
                article=article,
                article_version_id=version_id,
                content_clean=content,
                spans=[],
                relevance=relevance,
                provider="gate",
                model_name="skip",
                prompt_version="l2_gate_v1",
                token_usage=0,
            )
            analysis = ArticleAnalysis(
                id=str(uuid4()),
                article_id=article.id,
                analysis_run_id=analysis_run_id,
                article_version_id=version_id,
                provider="gate",
                model_name="skip",
                prompt_version="l2_gate_v1",
                schema_version=SCHEMA_VERSION,
                taxonomy_version=TAXONOMY_VERSION,
                relevance_weight_version=RELEVANCE_WEIGHT_VERSION,
                analysis_status="skipped_not_china",
                confidence=l2.confidence,
                token_usage=0,
                estimated_cost_usd=0.0,
                structured_result=gate_structured,
            )
            session.add(analysis)
            article.analysis_status = "skipped_not_china"
            article.analyzed_at = datetime.now(timezone.utc)
            article.updated_at = datetime.now(timezone.utc)
            set_pipeline_state(article, FULLTEXT_SCREENED)
            result["provider"] = "gate"
            result["analysis_status"] = "skipped_not_china"
            result["pipeline_state"] = article.pipeline_state
            result["token_usage"] = 0
            result["estimated_cost_usd"] = 0.0
            return result

        use_provider = provider
        if provider == "deepseek" and not allow_llm:
            use_provider = "heuristic"
        # possible_china / uncertain: prefer heuristic unless explicitly allowing LLM review
        if l2.label in {"possible_china", "uncertain"} and not allow_llm:
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
        structured = validate_and_enrich_article_intelligence(
            structured,
            article=article,
            article_version_id=version_id,
            content_clean=content,
            spans=spans,
            relevance=relevance,
            provider=used_provider,
            model_name=model_name,
            prompt_version=prompt_version,
            token_usage=tokens,
        )

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
        if (article.china_relevance_level or "") in ANALYTICS_RELEVANCE_LEVELS and (
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


def _locate_quote_in_text(content: str, quote: str) -> tuple[int | None, int | None, bool]:
    """Verify quote against content_clean and return (start, end, validated)."""
    if not content or not quote:
        return None, None, False
    q = quote.strip()
    if not q:
        return None, None, False
    idx = content.find(q)
    if idx >= 0:
        return idx, idx + len(q), True
    # Case-insensitive fallback for minor casing differences
    idx_ci = content.casefold().find(q.casefold())
    if idx_ci >= 0:
        return idx_ci, idx_ci + len(q), True
    return None, None, False


def validate_and_enrich_article_intelligence(
    structured: dict[str, Any],
    *,
    article: Article,
    article_version_id: str | None,
    content_clean: str | None,
    spans: list[ChinaSpan],
    relevance: RelevanceAssessment,
    provider: str,
    model_name: str,
    prompt_version: str,
    token_usage: int,
) -> dict[str, Any]:
    """Deterministic Evidence alignment, cross-field validation, Quality scoring & V2.0 contract projection."""
    text = content_clean or ""
    flags: list[str] = []
    needs_review = False
    validated_evidence: list[dict[str, Any]] = []
    seen_ev_ids: set[str] = set()

    # 1. Align and verify existing evidence entries against content_clean
    raw_ev = structured.get("evidence") if isinstance(structured.get("evidence"), list) else []
    for i, item in enumerate(raw_ev):
        if not isinstance(item, dict):
            continue
        quote = str(item.get("quote") or item.get("text_span") or "").strip()
        if not quote:
            continue
        ev_id = str(item.get("evidence_id") or f"ev_{i}")
        s_off = item.get("start_offset")
        e_off = item.get("end_offset")
        is_valid = validate_span_quote(text, quote, s_off, e_off) if text else False
        if not is_valid and text:
            s_off, e_off, is_valid = _locate_quote_in_text(text, quote)
        rec = EvidenceSpanRef(
            evidence_id=ev_id,
            article_id=article.id,
            article_version_id=article_version_id,
            text_span=quote[:500],
            start_offset=s_off,
            end_offset=e_off,
            paragraph_index=item.get("paragraph_index"),
            evidence_type=str(item.get("evidence_type") or "general"),
            supports_claim=str(item.get("supports_claim") or item.get("field_path") or ""),
            analysis_task="article_intelligence",
            validated=is_valid,
        ).model_dump()
        # Preserve backward-compatible quote / field_path keys
        rec["quote"] = rec["text_span"]
        if item.get("field_path"):
            rec["field_path"] = item["field_path"]
        validated_evidence.append(rec)
        seen_ev_ids.add(ev_id)

    # 2. Verify china_stance.stance_evidence quotes against original text
    cs = structured.get("china_stance") if isinstance(structured.get("china_stance"), dict) else {}
    stance_ev_raw = cs.get("stance_evidence") if isinstance(cs.get("stance_evidence"), list) else []
    aligned_stance_ev: list[dict[str, Any]] = []
    stance_ev_refs: list[str] = []
    unverified_stance_quotes = 0
    for idx, sev in enumerate(stance_ev_raw):
        if isinstance(sev, str):
            sev = {"quote": sev}
        if not isinstance(sev, dict):
            continue
        quote = str(sev.get("quote") or sev.get("text_span") or "").strip()
        if not quote:
            continue
        s_off = sev.get("start_offset")
        e_off = sev.get("end_offset")
        is_valid = validate_span_quote(text, quote, s_off, e_off) if text else False
        if not is_valid and text:
            s_off, e_off, is_valid = _locate_quote_in_text(text, quote)
        if not is_valid:
            unverified_stance_quotes += 1
        ev_id = str(sev.get("evidence_id") or f"ev_stance_quote_{idx}")
        aligned = {
            **sev,
            "evidence_id": ev_id,
            "article_id": article.id,
            "article_version_id": article_version_id,
            "quote": quote[:500],
            "start_offset": s_off,
            "end_offset": e_off,
            "validated": is_valid,
        }
        aligned_stance_ev.append(aligned)
        stance_ev_refs.append(ev_id)
        if ev_id not in seen_ev_ids:
            validated_evidence.append(
                EvidenceSpanRef(
                    evidence_id=ev_id,
                    article_id=article.id,
                    article_version_id=article_version_id,
                    text_span=quote[:500],
                    start_offset=s_off,
                    end_offset=e_off,
                    paragraph_index=sev.get("paragraph_index"),
                    evidence_type="stance",
                    supports_claim=f"china_stance={cs.get('stance_label')}",
                    validated=is_valid,
                ).model_dump()
                | {"quote": quote[:500]}
            )
            seen_ev_ids.add(ev_id)

    if aligned_stance_ev:
        cs["stance_evidence"] = aligned_stance_ev
    if unverified_stance_quotes > 0:
        flags.append("unverified_stance_quote")
        needs_review = True

    # 3. Cross-field validation: quoted_actor stance must not masquerade as media stance
    owner = str(cs.get("expression_owner") or "unclear").strip().lower()
    if owner not in {"media", "quoted_actor", "unclear"}:
        owner = "unclear"
    cs["expression_owner"] = owner
    cs.setdefault("target", "china_mainland")
    stance_label = str(cs.get("stance_label") or "Unclassified")
    if owner == "quoted_actor" and stance_label in {"Positive", "Neutral", "Negative"}:
        flags.append("quoted_actor_stance_excluded_from_media")
        needs_review = True
    if stance_label in {"Positive", "Negative"} and not any(x.get("validated") for x in aligned_stance_ev):
        flags.append("directional_stance_missing_verified_evidence")
        needs_review = True
    structured["china_stance"] = cs

    # 4. Compute ArticleQualityContract
    valid_spans = [s for s in spans if s.validation_status == "valid"]
    if not text or len(text) < 120:
        ext_q = "insufficient"
        flags.append("short_or_missing_body")
        needs_review = True
    elif article.quality_status == "rss_stub":
        ext_q = "stub"
        flags.append("rss_stub_only")
    elif article.quality_status in {"fetch_failed", "processing_failed"}:
        ext_q = "failed"
        flags.append("extraction_failed")
        needs_review = True
    else:
        ext_q = "ok"

    lang_q = "ok" if (article.language and article.language != "und") else "unknown"
    if lang_q == "unknown":
        flags.append("language_unknown")

    if stance_label == "Unclassified":
        cls_q = "unclassified"
    elif (cs.get("stance_confidence") or 0.0) >= 0.7 and not unverified_stance_quotes:
        cls_q = "high"
    elif (cs.get("stance_confidence") or 0.0) >= 0.45:
        cls_q = "medium"
    else:
        cls_q = "low"
        needs_review = True

    dims_present = sum(
        [
            1 if relevance.relevance_level not in {"uncertain"} else 0,
            1 if (structured.get("topics_v1") or []) else 0,
            1 if isinstance(structured.get("sentiment"), dict) and structured["sentiment"].get("label") else 0,
            1 if stance_label in {"Positive", "Neutral", "Negative"} else 0,
            1 if (structured.get("narratives") or structured.get("entities")) else 0,
            1 if any(e.get("validated") for e in validated_evidence) else 0,
        ]
    )
    completeness = round(dims_present / 6.0, 4)

    quality = ArticleQualityContract(
        completeness=completeness,
        language_quality=lang_q,
        extraction_quality=ext_q,
        classification_quality=cls_q,
        needs_review=needs_review,
        quality_flags=sorted(set(flags)),
    )

    # 5. Build canonical V2.0 ArticleIntelligenceContract projection
    raw_sent = structured.get("sentiment") if isinstance(structured.get("sentiment"), dict) else {}
    sent_label_raw = str(raw_sent.get("label") or "").strip().lower()
    sent_label = sent_label_raw if sent_label_raw in {"positive", "neutral", "negative", "mixed", "unknown"} else None

    topics_models: list[ArticleTopicContract] = []
    for t in structured.get("topics_structured") or []:
        if isinstance(t, dict) and t.get("topic_id"):
            topics_models.append(ArticleTopicContract.model_validate(t))
    if not topics_models and structured.get("topics_v1"):
        for idx, tid in enumerate(structured.get("topics_v1") or []):
            topics_models.append(
                ArticleTopicContract(
                    topic_id=str(tid),
                    relevance="primary" if idx == 0 else "secondary",
                    evidence_refs=stance_ev_refs[:1],
                )
            )

    nar_models = []
    for n in structured.get("narratives") or []:
        if isinstance(n, dict):
            try:
                nar_models.append(ArticleNarrativeContract.model_validate(n))
            except Exception:
                continue

    ent_models = []
    for idx, e in enumerate(structured.get("entities") or []):
        if isinstance(e, dict):
            ec = dict(e)
            ec.setdefault("entity_id", str(ec.get("normalized_id") or f"ent_{idx}"))
            ec.setdefault("canonical_name", str(ec.get("text") or ec["entity_id"]))
            ec.setdefault("entity_type", str(ec.get("type") or "other"))
            try:
                ent_models.append(ArticleEntityContract.model_validate(ec))
            except Exception:
                continue

    ev_cand_models = []
    for c in structured.get("event_candidates") or []:
        if isinstance(c, dict):
            try:
                ev_cand_models.append(ArticleEventCandidateContract.model_validate(c))
            except Exception:
                continue

    ev_span_models = [EvidenceSpanRef.model_validate(e) for e in validated_evidence]

    contract = ArticleIntelligenceContract(
        article_id=article.id,
        analysis_version=ARTICLE_INTELLIGENCE_VERSION,
        relevance=ArticleRelevanceContract(
            is_china_related=relevance.relevance_level in {"core", "substantial", "secondary", "incidental"}
            if relevance.relevance_level != "uncertain"
            else None,
            china_relevance_level=relevance.relevance_level,
            china_relevance_score=relevance.relevance_weight,
            relevant_passages=[s.text_original[:400] for s in valid_spans[:5]],
            relevance_reason=relevance.reasoning_summary or "",
        ),
        topics=topics_models,
        sentiment=ArticleSentimentContract(
            sentiment_label=sent_label,
            sentiment_target=str(raw_sent.get("sentiment_target") or "china_mainland"),
            evidence_refs=list(raw_sent.get("evidence_refs") or []),
            confidence=raw_sent.get("confidence", 0.0),
            reasoning=str(raw_sent.get("reasoning") or ""),
        ),
        stance=[
            ArticleStanceContract(
                target=str(cs.get("target") or "china_mainland"),
                stance_label=stance_label if stance_label in {"Positive", "Neutral", "Negative", "Unclassified"} else "Unclassified",
                expression_owner=owner,
                evidence_refs=stance_ev_refs,
                confidence=cs.get("stance_confidence", 0.0),
                reasoning=str(cs.get("reasoning") or ""),
            )
        ],
        narratives=nar_models,
        entities=ent_models,
        events=ev_cand_models,
        evidence=ev_span_models,
        quality=quality,
        analysis_metadata=ArticleAnalysisMetadataContract(
            record_source="model",
            model_name=model_name,
            model_version=model_name,
            prompt_version=prompt_version,
            analysis_version=ARTICLE_INTELLIGENCE_VERSION,
            schema_version=str(structured.get("schema_version") or SCHEMA_VERSION),
            taxonomy_version=str(structured.get("taxonomy_version") or TAXONOMY_VERSION),
            article_version_id=article_version_id,
            processed_at=datetime.now(timezone.utc).isoformat(),
            token_usage=int(token_usage or 0),
            processing_status=str(structured.get("analysis_status") or "completed"),
        ),
    )

    structured["article_intelligence_version"] = ARTICLE_INTELLIGENCE_VERSION
    structured["evidence"] = validated_evidence
    structured["quality"] = quality.model_dump()
    structured["article_intelligence"] = contract.model_dump()
    return structured


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
    reanalyze_legacy: bool = False,
    per_country: int | None,
    articles_remaining: int,
) -> tuple[list[Article], dict[str, int]]:
    """Pick articles; optional per-country cap then optional total limit (stricter wins)."""
    from collections import defaultdict

    from gni.infrastructure.models import Source

    if article_id:
        art = session.get(Article, article_id)
        return ([art] if art else []), {}

    legacy_article_ids: set[str] | None = None
    if reanalyze_legacy and not reanalyze:
        # Select articles whose latest ArticleAnalysis is NOT article_analysis_v1.0/v1.1
        all_ana = session.scalars(
            select(ArticleAnalysis).order_by(ArticleAnalysis.created_at.desc())
        ).all()
        latest_sv: dict[str, str | None] = {}
        for row in all_ana:
            if row.article_id not in latest_sv:
                latest_sv[row.article_id] = row.schema_version
        legacy_article_ids = {
            aid
            for aid, sv in latest_sv.items()
            if sv not in {"article_analysis_v1.0", "article_analysis_v1.1"}
        }
        if not legacy_article_ids:
            return [], {}

    from sqlalchemy import case, func

    priority_expr = case(
        (Article.title_screening_label == "explicit_relevant", 0),
        (Article.title_screening_label == "likely_relevant", 1),
        (Article.title_screening_label == "uncertain", 2),
        else_=3,
    )
    order_cols = (
        priority_expr.asc(),
        func.coalesce(Article.published_at, Article.first_seen_at).desc(),
    )

    q = select(Article).where(
        Article.processing_status == "done",
        Article.exclude_from_metrics.is_(False),
    )
    if source_id:
        q = q.where(Article.source_id == source_id)
    if legacy_article_ids is not None:
        q = q.where(Article.id.in_(list(legacy_article_ids)))
    elif not reanalyze:
        q = q.where(Article.analysis_status.in_(["pending", "failed"]))
    q = q.order_by(*order_cols)

    # Per-country: query each country separately so one backlog (e.g. RU) cannot starve others.
    if per_country is not None and per_country > 0:
        country_ids = list(
            session.scalars(
                select(Source.country_id).where(Source.country_id.is_not(None)).distinct()
            ).all()
        )
        picked: list[Article] = []
        counts: dict[str, int] = {}
        remaining = articles_remaining if articles_remaining >= 0 else 10**9
        for cid in sorted(str(c) for c in country_ids if c):
            if remaining <= 0:
                break
            take = min(per_country, remaining)
            cq = (
                select(Article)
                .join(Source, Source.id == Article.source_id)
                .where(
                    Article.processing_status == "done",
                    Article.exclude_from_metrics.is_(False),
                    Source.country_id == cid,
                )
            )
            if source_id:
                cq = cq.where(Article.source_id == source_id)
            if legacy_article_ids is not None:
                cq = cq.where(Article.id.in_(list(legacy_article_ids)))
            elif not reanalyze:
                cq = cq.where(Article.analysis_status.in_(["pending", "failed"]))
            cq = cq.order_by(*order_cols).limit(take)
            rows = list(session.scalars(cq).all())
            if not rows:
                continue
            counts[cid] = len(rows)
            picked.extend(rows)
            remaining -= len(rows)
        if limit is not None:
            picked = picked[:limit]
            trimmed: dict[str, int] = defaultdict(int)
            src_map = {
                s.id: s
                for s in session.scalars(
                    select(Source).where(Source.id.in_({a.source_id for a in picked}))
                ).all()
            } if picked else {}
            for a in picked:
                src = src_map.get(a.source_id)
                trimmed[(src.country_id if src else None) or "UNK"] += 1
            return picked, dict(trimmed)
        return picked, counts

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
    reanalyze_legacy: bool = False,
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
        reanalyze_legacy=reanalyze_legacy,
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

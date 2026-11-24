"""Pure metric computation — no LLM, no DB I/O."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from gni.metrics.definitions import (
    ARTICLE_COUNT_V,
    ATTENTION_SHARE_V,
    CHINA_INCLUDE_LEVELS,
    COUNTRY_COUNT_V,
    DEDUPLICATION_METHOD,
    EXTRACTION_SUCCESS_V,
    FRAME_DIST_V,
    INGESTION_SUCCESS_V,
    METRIC_DEFINITION_VERSION,
    NP_RATIO_V,
    RELEVANCE_WEIGHT_VERSION,
    SENTIMENT_COVERAGE_V,
    SENTIMENT_DIST_V,
    SENTIMENT_SCORE_MAP,
    SOURCE_COUNT_V,
    STANCE_DIST_V,
    TOPIC_SHARE_V,
    UNIQUE_STORY_COUNT_V,
    WEIGHTED_SENT_DIST_V,
    WEIGHTED_SENT_SCORE_V,
    WEIGHTED_VOLUME_V,
)


@dataclass
class ArticleMetricRow:
    """Minimal article + analysis fields needed for metrics."""

    id: str
    source_id: str
    country_id: str | None
    exclude_from_metrics: bool = False
    content_hash: str | None = None
    title_hash: str | None = None
    published_at: datetime | None = None
    first_seen_at: datetime | None = None
    china_relevance_level: str | None = None
    china_relevance_weight: float | None = None
    quality_status: str | None = None
    processing_status: str | None = None
    analysis_status: str | None = None
    # From latest structured_result
    sentiment_label: str | None = None
    sentiment_score: float | None = None
    sentiment_status: str | None = None
    stances: list[dict[str, Any]] = field(default_factory=list)
    frame_primary: str | None = None
    topic_primary: str | None = None


@dataclass
class SourceHealthRow:
    source_id: str
    country_id: str | None
    active_status: str | None
    success_count: int = 0
    failure_count: int = 0


def _metric(
    *,
    metric_id: str,
    version: str,
    value: Any,
    numerator: Any = None,
    denominator: Any = None,
    excluded_count: int = 0,
    missing_count: int = 0,
    unknown_count: int = 0,
    status: str = "ok",
    notes: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "metric_id": metric_id,
        "version": version,
        "value": value,
        "numerator": numerator,
        "denominator": denominator,
        "excluded_count": excluded_count,
        "missing_count": missing_count,
        "unknown_count": unknown_count,
        "status": status,
    }
    if notes:
        out["notes"] = notes
    if extra:
        out.update(extra)
    return out


def _as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _event_time(row: ArticleMetricRow) -> datetime | None:
    return _as_utc(row.published_at) or _as_utc(row.first_seen_at)


def _in_window(
    row: ArticleMetricRow,
    start: datetime | None,
    end: datetime | None,
) -> bool:
    t = _event_time(row)
    if t is None:
        return start is None and end is None
    start_u = _as_utc(start)
    end_u = _as_utc(end)
    if start_u and t < start_u:
        return False
    if end_u and t > end_u:
        return False
    return True


def is_china_included(row: ArticleMetricRow, levels: frozenset[str] = CHINA_INCLUDE_LEVELS) -> bool:
    return (row.china_relevance_level or "") in levels


def story_key(row: ArticleMetricRow) -> str:
    if row.content_hash:
        return f"c:{row.content_hash}"
    if row.title_hash:
        return f"t:{row.title_hash}"
    return f"id:{row.id}"


def compute_metrics(
    articles: list[ArticleMetricRow],
    *,
    source_health: list[SourceHealthRow] | None = None,
    window_start: datetime | None = None,
    window_end: datetime | None = None,
    country_scope: list[str] | None = None,
    source_scope: list[str] | None = None,
    target_scope: str = "china",
    timezone: str = "UTC",
    include_levels: frozenset[str] = CHINA_INCLUDE_LEVELS,
) -> dict[str, Any]:
    """Compute research + weighted + ops metrics for a scoped window."""
    excluded_dup = 0
    scoped: list[ArticleMetricRow] = []
    for a in articles:
        if country_scope and (a.country_id not in country_scope):
            continue
        if source_scope and (a.source_id not in source_scope):
            continue
        if not _in_window(a, window_start, window_end):
            continue
        if a.exclude_from_metrics:
            excluded_dup += 1
            continue
        scoped.append(a)

    universe = scoped  # all valid reports in scope (Attention denominator)
    china = [a for a in universe if is_china_included(a, include_levels)]
    missing_relevance = sum(
        1 for a in universe if not a.china_relevance_level or a.china_relevance_level == "uncertain"
    )

    # --- Article Count ---
    article_count = _metric(
        metric_id="article_count",
        version=ARTICLE_COUNT_V,
        value=len(china),
        numerator=len(china),
        denominator=None,
        excluded_count=excluded_dup,
        missing_count=missing_relevance,
        notes="Integer article count; never rewritten by weight.",
        extra={"sample_size": len(china)},
    )

    # --- Unique Story Count ---
    keys = {story_key(a) for a in china}
    unique_story = _metric(
        metric_id="unique_story_count",
        version=UNIQUE_STORY_COUNT_V,
        value=len(keys),
        numerator=len(keys),
        denominator=len(china) if china else 0,
        notes=f"dedup={DEDUPLICATION_METHOD}; MVP single-language hash clusters.",
    )

    # --- Attention Share ---
    denom = len(universe)
    numer = len(china)
    # Gate: unreliable if empty universe, or if every article already filtered to china-only
    # ingest with zero non-china ever observed AND all have china labels missing → still available
    # when denom>0. Unavailable when denom==0.
    # Extra gate: if source_scope is empty after filters → unavailable.
    if denom <= 0:
        attention = _metric(
            metric_id="attention_share",
            version=ATTENTION_SHARE_V,
            value=None,
            numerator=numer,
            denominator=denom,
            status="unavailable",
            notes="Denominator empty; formal Attention Share forbidden.",
        )
    else:
        attention = _metric(
            metric_id="attention_share",
            version=ATTENTION_SHARE_V,
            value=round(numer / denom, 6),
            numerator=numer,
            denominator=denom,
            status="available",
            notes="Denominator = all non-excluded articles in same source/time scope (full ingest).",
            extra={"article_count": numer},
        )

    # --- Sentiment / Stance / Frame / Topic (raw) ---
    sent_counts: Counter[str] = Counter()
    sent_unknown = 0
    stance_counts: Counter[str] = Counter()
    stance_missing = 0
    frame_counts: Counter[str] = Counter()
    topic_counts: Counter[str] = Counter()
    topic_missing = 0

    for a in china:
        label = a.sentiment_label
        status = a.sentiment_status or ""
        if label in {"positive", "negative", "neutral", "mixed"}:
            sent_counts[label] += 1
        else:
            sent_unknown += 1
            if status in {"unknown", "ambiguous", "insufficient_evidence"} or not label:
                pass

        if a.stances:
            for st in a.stances:
                tid = st.get("target_id") or target_scope
                stance = st.get("stance")
                st_status = st.get("status") or ""
                if stance is None or st_status in {
                    "unknown",
                    "ambiguous",
                    "insufficient_evidence",
                    "not_applicable",
                }:
                    stance_missing += 1
                    continue
                stance_counts[f"{tid}|{stance}"] += 1
        else:
            stance_missing += 1

        if a.frame_primary:
            frame_counts[a.frame_primary] += 1
        if a.topic_primary:
            topic_counts[a.topic_primary] += 1
        else:
            topic_missing += 1

    n_china = len(china) or 1
    sentiment_dist = _metric(
        metric_id="sentiment_distribution",
        version=SENTIMENT_DIST_V,
        value={
            "counts": dict(sent_counts),
            "shares": {k: round(v / n_china, 6) for k, v in sent_counts.items()},
            "unknown_or_missing": sent_unknown,
        },
        numerator=sum(sent_counts.values()),
        denominator=len(china),
        unknown_count=sent_unknown,
        notes="Raw counts; unknown/mixed not merged into neutral.",
    )

    stance_value = {
        "counts": dict(stance_counts),
        "shares": {k: round(v / max(sum(stance_counts.values()), 1), 6) for k, v in stance_counts.items()},
        "target_scope_default": target_scope,
    }
    stance_dist = _metric(
        metric_id="stance_distribution",
        version=STANCE_DIST_V,
        value=stance_value,
        numerator=sum(stance_counts.values()),
        denominator=len(china),
        missing_count=stance_missing,
        notes="Target-bound; key format target_id|stance.",
    )

    frame_total = sum(frame_counts.values()) or 1
    frame_dist = _metric(
        metric_id="frame_distribution",
        version=FRAME_DIST_V,
        value={
            "counts": dict(frame_counts),
            "shares": {k: round(v / frame_total, 6) for k, v in frame_counts.items()},
            "mode": "primary_only",
            "taxonomy_version": "taxonomy_v0.4",
        },
        numerator=sum(frame_counts.values()),
        denominator=len(china),
        notes="Primary frame only; shares may be <100% if missing primary.",
    )

    topic_total = sum(topic_counts.values()) or 1
    topic_share = _metric(
        metric_id="topic_share",
        version=TOPIC_SHARE_V,
        value={
            "counts": dict(topic_counts),
            "shares": {k: round(v / topic_total, 6) for k, v in topic_counts.items()},
            "mode": "primary_only",
        },
        numerator=sum(topic_counts.values()),
        denominator=len(china),
        missing_count=topic_missing,
        notes="Topic separated from Target; primary topic share.",
    )

    # --- Weighted views ---
    weights: list[float] = []
    for a in china:
        w = a.china_relevance_weight
        if w is None:
            continue
        weights.append(float(w))
    weighted_volume = _metric(
        metric_id="weighted_article_volume",
        version=WEIGHTED_VOLUME_V,
        value=round(sum(weights), 6),
        numerator=round(sum(weights), 6),
        denominator=None,
        missing_count=len(china) - len(weights),
        notes="Σ w_i; does not replace Article Count.",
        extra={"relevance_weight_version": RELEVANCE_WEIGHT_VERSION},
    )

    # Weighted sentiment by label
    w_by_label: dict[str, float] = defaultdict(float)
    score_num = 0.0
    score_den = 0.0
    coverage_num = 0.0
    coverage_den = 0.0
    excluded_from_score = 0

    for a in china:
        w = float(a.china_relevance_weight) if a.china_relevance_weight is not None else None
        if w is None:
            continue
        coverage_den += w
        label = a.sentiment_label
        if label in {"positive", "negative", "neutral", "mixed"}:
            w_by_label[label] += w
        if label in SENTIMENT_SCORE_MAP:
            s_i = a.sentiment_score if a.sentiment_score is not None else SENTIMENT_SCORE_MAP[label]
            score_num += w * float(s_i)
            score_den += w
            coverage_num += w
        else:
            # mixed / unknown / insufficient → not in score denom
            excluded_from_score += 1

    w_label_total = sum(w_by_label.values()) or 1.0
    weighted_sent_dist = _metric(
        metric_id="weighted_sentiment_distribution",
        version=WEIGHTED_SENT_DIST_V,
        value={
            "weighted_volumes": {k: round(v, 6) for k, v in w_by_label.items()},
            "shares": {k: round(v / w_label_total, 6) for k, v in w_by_label.items()},
        },
        numerator=round(sum(w_by_label.values()), 6),
        denominator=round(sum(weights), 6) if weights else 0,
        notes="Weighted by relevance_weight; mixed kept separate.",
    )

    if score_den > 0:
        w_score_val: float | None = round(score_num / score_den, 6)
        w_score_status = "ok"
    else:
        w_score_val = None
        w_score_status = "unavailable"

    weighted_sent_score = _metric(
        metric_id="weighted_sentiment_score",
        version=WEIGHTED_SENT_SCORE_V,
        value=w_score_val,
        numerator=round(score_num, 6),
        denominator=round(score_den, 6),
        excluded_count=excluded_from_score,
        status=w_score_status,
        notes=(
            "Σ(w_i×s_i)/Σ(w_i); mixed/unknown excluded from denominator. "
            "Not a national attitude score — monitored-outlet sample score only."
        ),
    )

    pos_w = w_by_label.get("positive", 0.0)
    neg_w = w_by_label.get("negative", 0.0)
    if pos_w > 0:
        np_val: float | None = round(neg_w / pos_w, 6)
        np_status = "ok"
    else:
        np_val = None
        np_status = "unavailable"
    np_ratio = _metric(
        metric_id="np_ratio",
        version=NP_RATIO_V,
        value=np_val,
        numerator=round(neg_w, 6),
        denominator=round(pos_w, 6),
        status=np_status,
        notes="Weighted negative volume / weighted positive volume.",
    )

    if coverage_den > 0:
        cov_val: float | None = round(coverage_num / coverage_den, 6)
        cov_status = "ok"
    else:
        cov_val = None
        cov_status = "unavailable"
    sentiment_coverage = _metric(
        metric_id="sentiment_coverage",
        version=SENTIMENT_COVERAGE_V,
        value=cov_val,
        numerator=round(coverage_num, 6),
        denominator=round(coverage_den, 6),
        status=cov_status,
        notes="Effective sentiment weight / included article weight.",
    )

    # --- Operational ---
    sources_in_china = {a.source_id for a in china}
    countries_in_china = {a.country_id for a in china if a.country_id}
    source_count = _metric(
        metric_id="source_count",
        version=SOURCE_COUNT_V,
        value=len(sources_in_china),
        numerator=len(sources_in_china),
        notes="Distinct sources among included China articles.",
    )
    country_count = _metric(
        metric_id="country_count",
        version=COUNTRY_COUNT_V,
        value=len(countries_in_china),
        numerator=len(countries_in_china),
        notes="Distinct countries among included China articles.",
    )

    health = source_health or []
    if country_scope:
        health = [h for h in health if h.country_id in country_scope]
    if source_scope:
        health = [h for h in health if h.source_id in source_scope]
    succ = sum(h.success_count for h in health)
    fail = sum(h.failure_count for h in health)
    ingest_den = succ + fail
    ingestion_success = _metric(
        metric_id="ingestion_success_rate",
        version=INGESTION_SUCCESS_V,
        value=round(succ / ingest_den, 6) if ingest_den else None,
        numerator=succ,
        denominator=ingest_den,
        status="ok" if ingest_den else "unavailable",
        notes="Operational; not a narrative conclusion.",
    )

    extracted_ok = sum(
        1
        for a in universe
        if a.quality_status in {"processed", "processed_stub", "ok", "rss_stub"}
        or (a.processing_status == "done" and a.quality_status not in {"insufficient_text", "fetch_failed", "processing_failed"})
    )
    extract_den = len(universe)
    extraction_success = _metric(
        metric_id="article_extraction_success_rate",
        version=EXTRACTION_SUCCESS_V,
        value=round(extracted_ok / extract_den, 6) if extract_den else None,
        numerator=extracted_ok,
        denominator=extract_den,
        status="ok" if extract_den else "unavailable",
        notes="Share of in-scope articles with usable extraction quality.",
    )

    return {
        "metric_definition_version": METRIC_DEFINITION_VERSION,
        "relevance_weight_version": RELEVANCE_WEIGHT_VERSION,
        "deduplication_method": DEDUPLICATION_METHOD,
        "timezone": timezone,
        "time_window": {
            "start": window_start.isoformat() if window_start else None,
            "end": window_end.isoformat() if window_end else None,
        },
        "country_scope": country_scope,
        "source_scope": source_scope,
        "topic_scope": None,
        "target_scope": target_scope,
        "include_levels": sorted(include_levels),
        "universe_count": len(universe),
        "excluded_duplicates": excluded_dup,
        "research": {
            "article_count": article_count,
            "unique_story_count": unique_story,
            "attention_share": attention,
            "sentiment_distribution": sentiment_dist,
            "stance_distribution": stance_dist,
            "frame_distribution": frame_dist,
            "topic_share": topic_share,
        },
        "weighted": {
            "weighted_article_volume": weighted_volume,
            "weighted_sentiment_distribution": weighted_sent_dist,
            "weighted_sentiment_score": weighted_sent_score,
            "np_ratio": np_ratio,
            "sentiment_coverage": sentiment_coverage,
            "weighted_positive_volume": round(pos_w, 6),
            "weighted_negative_volume": round(neg_w, 6),
            "weighted_neutral_volume": round(w_by_label.get("neutral", 0.0), 6),
        },
        "operational": {
            "source_count": source_count,
            "country_count": country_count,
            "ingestion_success_rate": ingestion_success,
            "article_extraction_success_rate": extraction_success,
        },
        "views": {
            "raw": {
                "article_count": article_count["value"],
                "sentiment_distribution": sentiment_dist["value"],
                "stance_distribution": stance_dist["value"],
                "frame_distribution": frame_dist["value"],
                "topic_share": topic_share["value"],
            },
            "weighted": {
                "weighted_article_volume": weighted_volume["value"],
                "weighted_sentiment_score": weighted_sent_score["value"],
                "weighted_sentiment_distribution": weighted_sent_dist["value"],
                "np_ratio": np_ratio["value"],
            },
        },
    }

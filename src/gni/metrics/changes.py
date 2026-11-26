"""Deterministic multi-factor Change Detection for GNI V2.0 Phase 4.

Every detector evaluates:
1. absolute count delta
2. relative change rate
3. rolling historical baseline
4. minimum sample size guard (prevents small-sample percentage false positives)
5. consecutive-period persistence (when multi-period series provided)
6. country and source breadth (prevents single-outlet noise)

Produces validated SignalRecordContract objects.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Iterable

from gni.core.contracts import SignalRecordContract
from gni.metrics.v1_stats import StatSnapshotRow, V1ArticleInput, deduplicate_v1_articles


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _breadth(rows: Iterable[V1ArticleInput]) -> tuple[int, int]:
    countries = {(r.source_country or "").strip().upper() for r in rows if (r.source_country or "").strip()}
    sources = {(r.source_id or "").strip() for r in rows if (r.source_id or "").strip()}
    return len(countries), len(sources)


def detect_volume_change(
    *,
    subject: str,
    signal_type: str = "attention_change",
    recent_count: int,
    baseline_mean: float,
    min_sample_size: int = 5,
    min_abs_delta: int = 3,
    min_rel_change: float = 0.5,
    country_count: int = 1,
    source_count: int = 1,
    min_sources: int = 1,
    consecutive_periods: int = 1,
    supporting_articles: list[str] | None = None,
) -> SignalRecordContract | None:
    """Multi-factor volume/topic change detector with strict small-sample protection."""
    if recent_count < min_sample_size:
        return None
    if source_count < min_sources:
        return None
    base = max(0.0, float(baseline_mean))
    abs_delta = recent_count - base
    if abs_delta < min_abs_delta:
        return None
    rel_change = (abs_delta / base) if base > 0 else float(recent_count)
    if rel_change < min_rel_change:
        return None

    conf = "high" if (recent_count >= min_sample_size * 2 and source_count >= 2 and consecutive_periods >= 2) else (
        "medium" if source_count >= 2 or consecutive_periods >= 2 else "low"
    )
    stype = signal_type if signal_type in {"attention_change", "topic_shift"} else "attention_change"
    now = _now_utc()
    return SignalRecordContract(
        signal_id=f"{stype}:{subject}:{now.strftime('%Y%m%d')}",
        signal_type=stype,  # type: ignore[arg-type]
        subject=subject,
        observation=(
            f"{subject} reached {recent_count} articles vs baseline {base:.1f} "
            f"(+{abs_delta:.1f}, +{rel_change:.0%}, countries={country_count}, sources={source_count})."
        ),
        trigger_metrics={
            "recent_count": recent_count,
            "baseline_mean": round(base, 3),
            "abs_delta": round(abs_delta, 3),
            "rel_change": round(rel_change, 4),
            "min_sample_size": min_sample_size,
            "consecutive_periods": consecutive_periods,
            "country_count": country_count,
            "source_count": source_count,
        },
        supporting_articles=list(supporting_articles or [])[:20],
        first_detected_at=now,
        last_updated_at=now,
        confidence=conf,  # type: ignore[arg-type]
        alternative_explanation=(
            "Single-source concentration or scheduled recurring event may explain part of the spike."
            if source_count <= 1
            else "Scheduled policy calendar or earnings cycle could coincide with the increase."
        ),
    )


def detect_stance_shift(
    *,
    subject: str,
    recent_row: StatSnapshotRow,
    baseline_row: StatSnapshotRow,
    min_classified: int = 5,
    min_coverage_rate: float = 0.4,
    min_rate_delta: float = 0.20,
    source_count: int = 1,
    min_sources: int = 1,
) -> SignalRecordContract | None:
    """Detect media-only V1.0 China stance shift while enforcing coverage & sample guards."""
    recent_classified = recent_row.positive_count + recent_row.neutral_count + recent_row.negative_count
    base_classified = baseline_row.positive_count + baseline_row.neutral_count + baseline_row.negative_count
    if recent_classified < min_classified or source_count < min_sources:
        return None
    if (recent_row.stance_coverage_rate or 0.0) < min_coverage_rate:
        return None
    if recent_row.negative_rate is None or baseline_row.negative_rate is None:
        return None

    neg_delta = recent_row.negative_rate - baseline_row.negative_rate
    pos_delta = (recent_row.positive_rate or 0.0) - (baseline_row.positive_rate or 0.0)
    if abs(neg_delta) < min_rate_delta and abs(pos_delta) < min_rate_delta:
        return None

    direction = "negative_rise" if neg_delta >= min_rate_delta else (
        "positive_rise" if pos_delta >= min_rate_delta else "directional_shift"
    )
    now = _now_utc()
    conf = "high" if (recent_classified >= min_classified * 2 and base_classified >= min_classified and source_count >= 2) else "medium"
    return SignalRecordContract(
        signal_id=f"stance_shift:{subject}:{now.strftime('%Y%m%d')}",
        signal_type="stance_shift",
        subject=subject,
        observation=(
            f"{subject} media-only stance shifted ({direction}): "
            f"negative_rate {baseline_row.negative_rate:.0%} -> {recent_row.negative_rate:.0%} "
            f"(classified n={recent_classified}, coverage={recent_row.stance_coverage_rate:.0%})."
        ),
        trigger_metrics={
            "direction": direction,
            "recent_negative_rate": recent_row.negative_rate,
            "baseline_negative_rate": baseline_row.negative_rate,
            "negative_rate_delta": round(neg_delta, 4),
            "recent_classified": recent_classified,
            "baseline_classified": base_classified,
            "stance_coverage_rate": recent_row.stance_coverage_rate,
            "source_count": source_count,
        },
        supporting_articles=list(recent_row.article_ids)[:20],
        first_detected_at=now,
        last_updated_at=now,
        confidence=conf,  # type: ignore[arg-type]
        alternative_explanation="Outlet mix change or topic composition shift may alter aggregate stance share.",
    )


def detect_cross_country_divergence(
    rows: Iterable[V1ArticleInput],
    *,
    topic_id: str,
    min_per_country: int = 3,
    min_rate_gap: float = 0.40,
) -> SignalRecordContract | None:
    """Detect when >=2 countries cover the same topic with sharply divergent media stance rates."""
    unique = deduplicate_v1_articles(rows)
    by_country: dict[str, list[V1ArticleInput]] = defaultdict(list)
    for r in unique:
        if topic_id not in (r.topics_v1 or []):
            continue
        cid = (r.source_country or "").strip().upper()
        if cid and r.stance_label in {"Positive", "Neutral", "Negative"}:
            by_country[cid].append(r)

    qualified: list[tuple[str, float, int, list[str]]] = []
    for cid, items in sorted(by_country.items()):
        if len(items) < min_per_country:
            continue
        neg_rate = sum(1 for x in items if x.stance_label == "Negative") / len(items)
        qualified.append((cid, neg_rate, len(items), [x.article_id for x in items]))

    if len(qualified) < 2:
        return None
    qualified.sort(key=lambda x: x[1])
    low_c, low_r, low_n, low_ids = qualified[0]
    high_c, high_r, high_n, high_ids = qualified[-1]
    gap = high_r - low_r
    if gap < min_rate_gap:
        return None

    now = _now_utc()
    return SignalRecordContract(
        signal_id=f"cross_country_divergence:{topic_id}:{low_c}_vs_{high_c}:{now.strftime('%Y%m%d')}",
        signal_type="cross_country_divergence",
        subject=f"{topic_id} ({high_c} vs {low_c})",
        observation=(
            f"Topic {topic_id} shows {gap:.0%} negative-stance gap between {high_c} ({high_r:.0%}, n={high_n}) "
            f"and {low_c} ({low_r:.0%}, n={low_n})."
        ),
        trigger_metrics={
            "topic_id": topic_id,
            "high_country": high_c,
            "high_negative_rate": round(high_r, 4),
            "high_classified": high_n,
            "low_country": low_c,
            "low_negative_rate": round(low_r, 4),
            "low_classified": low_n,
            "rate_gap": round(gap, 4),
        },
        supporting_articles=(high_ids + low_ids)[:20],
        first_detected_at=now,
        last_updated_at=now,
        confidence="high" if min(high_n, low_n) >= min_per_country * 2 else "medium",
        alternative_explanation="Different sub-events or source composition within each country may explain the divergence.",
    )


def compute_consecutive_increase(series_counts: list[int]) -> int:
    """Count trailing consecutive strictly-increasing periods (e.g. [2, 4, 7] -> 2)."""
    if len(series_counts) < 2:
        return 0
    streak = 0
    for idx in range(len(series_counts) - 1, 0, -1):
        if series_counts[idx] > series_counts[idx - 1]:
            streak += 1
        else:
            break
    return streak

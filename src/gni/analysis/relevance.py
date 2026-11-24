"""China Relevance Level / Weight mapping (provisional_v0.2)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from gni.analysis.l2_fulltext import FulltextScreenResult
from gni.processing.title_l1 import _fold

RELEVANCE_WEIGHT_VERSION = "provisional_v0.2"

# Midpoints from PROVISIONAL_CALIBRATION.md
LEVEL_WEIGHT_MIDPOINT: dict[str, float | None] = {
    "core": 0.90,
    "substantial": 0.65,
    "secondary": 0.35,
    "incidental": 0.10,
    "none": 0.00,
    "uncertain": None,
}


@dataclass
class RelevanceAssessment:
    relevance_level: str
    relevance_weight: float | None
    content_share_estimate: float | None = None
    headline_prominence: str | None = None
    thesis_contribution: str | None = None
    china_actor_role: str | None = None
    analysis_depth: str | None = None
    reasoning_summary: str | None = None
    assessment_version: str = RELEVANCE_WEIGHT_VERSION
    features: dict[str, Any] = field(default_factory=dict)


def _headline_prominence(title: str | None, matched: list[dict[str, Any]]) -> str:
    if not title:
        return "absent"
    folded = _fold(title)
    core_names = [
        str(m.get("canonical_name") or "").casefold()
        for m in matched
        if m.get("inclusion_scope") == "core"
    ]
    if any(n and n in folded for n in core_names):
        return "title"
    # any china-ish token already matched at L1 often; check common aliases lightly
    for token in ("china", "chinese", "中国", "китай", "chine", "cina"):
        if token in folded:
            return "title"
    return "body_only"


def assess_relevance(
    l2: FulltextScreenResult,
    *,
    title: str | None = None,
    span_count: int = 0,
    valid_span_count: int = 0,
) -> RelevanceAssessment:
    share = l2.content_share_estimate
    headline = _headline_prominence(title, l2.matched_entities)
    scopes = {m.get("inclusion_scope") for m in l2.matched_entities}

    if l2.label == "insufficient_text":
        return RelevanceAssessment(
            relevance_level="uncertain",
            relevance_weight=None,
            content_share_estimate=share,
            headline_prominence=headline,
            thesis_contribution="unknown",
            china_actor_role="unknown",
            analysis_depth="insufficient",
            reasoning_summary="Body text insufficient for relevance judgment.",
            features={"l2_label": l2.label, "reason_codes": l2.reason_codes},
        )

    if l2.label == "uncertain":
        return RelevanceAssessment(
            relevance_level="uncertain",
            relevance_weight=None,
            content_share_estimate=share,
            headline_prominence=headline,
            thesis_contribution="unclear",
            china_actor_role="unclear",
            analysis_depth="shallow",
            reasoning_summary=l2.summary_of_relevance or "Uncertain China relevance.",
            features={"l2_label": l2.label, "reason_codes": l2.reason_codes},
        )

    if l2.label == "not_china_related":
        if "incidental_mention_only" in (l2.reason_codes or []):
            return RelevanceAssessment(
                relevance_level="incidental",
                relevance_weight=LEVEL_WEIGHT_MIDPOINT["incidental"],
                content_share_estimate=share,
                headline_prominence=headline,
                thesis_contribution="removable",
                china_actor_role="mentioned",
                analysis_depth="shallow",
                reasoning_summary="Incidental mention; limited research value.",
                features={"l2_label": l2.label, "reason_codes": l2.reason_codes, "span_count": span_count},
            )
        return RelevanceAssessment(
            relevance_level="none",
            relevance_weight=LEVEL_WEIGHT_MIDPOINT["none"],
            content_share_estimate=share or 0.0,
            headline_prominence=headline,
            thesis_contribution="none",
            china_actor_role="absent",
            analysis_depth="none",
            reasoning_summary="No substantive China-related content.",
            features={"l2_label": l2.label, "reason_codes": l2.reason_codes},
        )

    # china_related → map level by share / headline / core scope
    share_v = share if share is not None else 0.0
    has_core = "core" in scopes
    deep = valid_span_count >= 3 or share_v >= 0.35

    if headline == "title" and has_core and share_v >= 0.35:
        level = "core"
        thesis = "central"
        role = "primary_subject"
        depth = "analytical" if deep else "descriptive"
    elif has_core and (share_v >= 0.15 or headline == "title" or valid_span_count >= 2):
        level = "substantial"
        thesis = "important"
        role = "major_actor"
        depth = "descriptive" if not deep else "analytical"
    elif share_v >= 0.08 or valid_span_count >= 1:
        level = "secondary"
        thesis = "supporting"
        role = "participant"
        depth = "shallow" if share_v < 0.12 else "descriptive"
    else:
        level = "incidental"
        thesis = "removable"
        role = "mentioned"
        depth = "shallow"

    return RelevanceAssessment(
        relevance_level=level,
        relevance_weight=LEVEL_WEIGHT_MIDPOINT[level],
        content_share_estimate=share,
        headline_prominence=headline,
        thesis_contribution=thesis,
        china_actor_role=role,
        analysis_depth=depth,
        reasoning_summary=(
            f"Mapped to {level} (share≈{share_v:.2f}, headline={headline}, "
            f"valid_spans={valid_span_count})."
        ),
        features={
            "l2_label": l2.label,
            "reason_codes": l2.reason_codes,
            "span_count": span_count,
            "valid_span_count": valid_span_count,
            "scopes": sorted(str(s) for s in scopes if s),
        },
    )

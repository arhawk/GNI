"""Target-bound stance helpers — never collapse all targets to stances[0]."""

from __future__ import annotations

from collections import Counter
from typing import Any

from gni.metrics.taxonomy_v1 import boards_for_topics, normalize_topic_ids

V1_ANALYSIS_SCHEMA_VERSION = "article_analysis_v1.0"
V1_COMPATIBLE_SCHEMA_VERSIONS = frozenset({"article_analysis_v1.0", "article_analysis_v1.1"})
VALID_V1_STANCES = frozenset({"Positive", "Neutral", "Negative"})
UNCLASSIFIED_STANCE = "Unclassified"


def extract_v1_expression_owner(
    structured: dict[str, Any] | None,
    schema_version: str | None = None,
) -> str:
    """Return 'media' | 'quoted_actor' | 'unclear' for V1.0+ china_stance."""
    if not isinstance(structured, dict):
        return "unclear"
    sv = schema_version or structured.get("schema_version")
    if sv not in V1_COMPATIBLE_SCHEMA_VERSIONS:
        return "unclear"
    cs = structured.get("china_stance")
    if not isinstance(cs, dict):
        return "unclear"
    owner = str(cs.get("expression_owner") or "unclear").strip().lower()
    if owner in {"media", "quoted_actor", "unclear"}:
        return owner
    return "unclear"


def extract_v1_china_stance(
    structured: dict[str, Any] | None,
    schema_version: str | None = None,
) -> str:
    """Strict V1.0+ China-related media stance reader.

    - Legacy (non-v1.0/v1.1) analyses are NEVER coerced into Positive/Neutral/Negative.
    - Purely quoted_actor expressions are NEVER counted as the media outlet's own stance.
    """
    if not isinstance(structured, dict):
        return UNCLASSIFIED_STANCE
    sv = schema_version or structured.get("schema_version")
    if sv not in V1_COMPATIBLE_SCHEMA_VERSIONS:
        return UNCLASSIFIED_STANCE
    cs = structured.get("china_stance")
    if not isinstance(cs, dict):
        return UNCLASSIFIED_STANCE
    owner = str(cs.get("expression_owner") or "").strip().lower()
    if owner == "quoted_actor":
        return UNCLASSIFIED_STANCE
    label = str(cs.get("stance_label") or "").strip()
    if label in VALID_V1_STANCES:
        return label
    return UNCLASSIFIED_STANCE


def extract_v1_stance_evidence(
    structured: dict[str, Any] | None,
    schema_version: str | None = None,
) -> list[dict[str, Any]]:
    if not isinstance(structured, dict):
        return []
    sv = schema_version or structured.get("schema_version")
    if sv not in V1_COMPATIBLE_SCHEMA_VERSIONS:
        return []
    cs = structured.get("china_stance")
    if not isinstance(cs, dict):
        return []
    ev = cs.get("stance_evidence")
    return [x for x in ev if isinstance(x, dict)] if isinstance(ev, list) else []


def extract_v1_topics(
    structured: dict[str, Any] | None,
    schema_version: str | None = None,
) -> list[str]:
    """Strict V1.0+ multi-label topics reader (only valid 15-topic IDs)."""
    if not isinstance(structured, dict):
        return []
    sv = schema_version or structured.get("schema_version")
    if sv not in V1_COMPATIBLE_SCHEMA_VERSIONS:
        return []
    raw = structured.get("topics_v1")
    if not isinstance(raw, list):
        return []
    return normalize_topic_ids(raw)


def extract_v1_boards(
    structured: dict[str, Any] | None,
    schema_version: str | None = None,
) -> list[str]:
    """Derive V1.0 board IDs strictly from valid V1.0 topic IDs."""
    return boards_for_topics(extract_v1_topics(structured, schema_version=schema_version))


def iter_stance_rows(structured: dict[str, Any] | None) -> list[dict[str, Any]]:
    raw = (structured or {}).get("stances") or []
    if not isinstance(raw, list):
        return []
    return [s for s in raw if isinstance(s, dict)]


def media_stances(structured: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Stances attributed to the outlet itself (exclude quoted speakers when marked)."""
    out: list[dict[str, Any]] = []
    for s in iter_stance_rows(structured):
        speaker = (s.get("speaker_type") or s.get("source") or "unknown").strip().lower()
        if speaker in {"quoted", "quote", "interview", "third_party", "cited"}:
            continue
        out.append(s)
    return out


def stance_counts_by_target(
    structured: dict[str, Any] | None, *, media_only: bool = True
) -> dict[str, Counter[str]]:
    rows = media_stances(structured) if media_only else iter_stance_rows(structured)
    by_t: dict[str, Counter[str]] = {}
    for s in rows:
        target = str(s.get("target") or s.get("target_id") or "unspecified").strip() or "unspecified"
        label = (s.get("stance") or "unknown").strip().lower() or "unknown"
        by_t.setdefault(target, Counter())[label] += 1
    return by_t


def all_stance_labels(
    structured: dict[str, Any] | None, *, media_only: bool = True
) -> Counter[str]:
    """Aggregate stance labels across targets (for article-level counts)."""
    total: Counter[str] = Counter()
    for counter in stance_counts_by_target(structured, media_only=media_only).values():
        total.update(counter)
    return total


def primary_stance_label(
    structured: dict[str, Any] | None,
    *,
    preferred_targets: tuple[str, ...] = ("china", "prc", "中国", "unspecified"),
) -> str:
    """Pick a display stance: prefer China-target media stance, else most common media stance."""
    by_t = stance_counts_by_target(structured, media_only=True)
    if not by_t:
        return "unknown"
    for pref in preferred_targets:
        for key, counter in by_t.items():
            if pref.casefold() in key.casefold() and counter:
                return counter.most_common(1)[0][0]
    flat = all_stance_labels(structured, media_only=True)
    if not flat:
        return "unknown"
    return flat.most_common(1)[0][0]


def sentiment_label(structured: dict[str, Any] | None) -> str:
    sent_val = (structured or {}).get("sentiment")
    raw = sent_val.get("label") if isinstance(sent_val, dict) else sent_val
    if not raw:
        return "unknown"
    s = str(raw).strip().lower()
    if s in {"positive", "pos", "favorable"}:
        return "positive"
    if s in {"negative", "neg", "unfavorable"}:
        return "negative"
    if s in {"neutral", "neu"}:
        return "neutral"
    if s in {"mixed"}:
        return "mixed"
    return "unknown"

"""Rule-based L2 full-text China screening (no LLM required)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from gni.processing.hashutil import sha256_text
from gni.processing.normalize import normalize_whitespace
from gni.processing.title_l1 import _fold, load_dictionary

MIN_FULLTEXT_CHARS = 120
RULE_VERSION = "fulltext_l2_rules_v0.1"
SCHEMA_VERSION = "fulltext_screening_v0.1"


# Pronoun / demonym soft signals — alone never force china_related; raise to possible/uncertain.
_SOFT_CHINA_TOKENS = (
    "beijing",
    "peking",
    "prc",
    "中方",
    "北京",
    "中国政府",
    "the country",
    "its authorities",
)


@dataclass
class FulltextScreenResult:
    label: str
    reason_codes: list[str] = field(default_factory=list)
    matched_entities: list[dict[str, Any]] = field(default_factory=list)
    supporting_paragraph_ids: list[int] = field(default_factory=list)
    candidate_targets: list[str] = field(default_factory=list)
    summary_of_relevance: str | None = None
    content_share_estimate: float | None = None
    paragraph_hit_share: float | None = None
    confidence: float | None = None
    requires_human_review: bool = False
    rule_version: str = RULE_VERSION
    entity_dictionary_version: str = "china_entity_dictionary_v0.2"
    input_hash: str | None = None
    paragraph_hits: list[dict[str, Any]] = field(default_factory=list)


def split_paragraphs(text: str) -> list[str]:
    raw = (text or "").replace("\r\n", "\n")
    parts = [normalize_whitespace(p) for p in raw.split("\n")]
    return [p for p in parts if p]


def _scan_paragraphs(
    paragraphs: list[str],
    dict_data: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], set[str], list[int]]:
    matches: list[dict[str, Any]] = []
    paragraph_hits: list[dict[str, Any]] = []
    scopes: set[str] = set()
    supporting: list[int] = []
    seen_ids: set[str] = set()

    for idx, para in enumerate(paragraphs):
        folded = _fold(para)
        para_entities: list[dict[str, Any]] = []
        for ent in dict_data.get("_compiled") or []:
            hit_aliases: list[str] = []
            for pattern, alias in ent.get("_patterns") or []:
                if pattern.search(para) or pattern.search(folded):
                    hit_aliases.append(alias)
            if not hit_aliases:
                continue
            scope = ent.get("inclusion_scope") or "secondary"
            scopes.add(scope)
            ent_payload = {
                "entity_id": ent.get("entity_id"),
                "canonical_name": ent.get("canonical_name"),
                "entity_type": ent.get("entity_type"),
                "inclusion_scope": scope,
                "aliases_hit": hit_aliases,
                "ambiguity_notes": ent.get("ambiguity_notes"),
            }
            para_entities.append(ent_payload)
            eid = str(ent.get("entity_id") or "")
            if eid and eid not in seen_ids:
                seen_ids.add(eid)
                matches.append(ent_payload)
        if para_entities:
            supporting.append(idx)
            paragraph_hits.append(
                {
                    "paragraph_index": idx,
                    "char_count": len(para),
                    "entities": para_entities,
                }
            )
    return matches, paragraph_hits, scopes, supporting


def screen_fulltext(
    content_clean: str | None,
    *,
    title: str | None = None,
    title_screening_label: str | None = None,
    quality_status: str | None = None,
    dict_path: str | None = None,
) -> FulltextScreenResult:
    dict_data = load_dictionary(dict_path)
    dict_version = dict_data.get("version") or "china_entity_dictionary_v0.2"
    text = normalize_whitespace(content_clean or "")
    input_hash = sha256_text(_fold(f"{title or ''}\n{text}"))

    if quality_status in {"insufficient_text", "fetch_failed", "processing_failed"}:
        return FulltextScreenResult(
            label="insufficient_text",
            reason_codes=["extraction_quality_insufficient"],
            confidence=0.9,
            entity_dictionary_version=dict_version,
            input_hash=input_hash,
        )

    if len(text) < MIN_FULLTEXT_CHARS:
        return FulltextScreenResult(
            label="insufficient_text",
            reason_codes=["body_too_short"],
            confidence=0.85,
            entity_dictionary_version=dict_version,
            input_hash=input_hash,
        )

    paragraphs = split_paragraphs(content_clean or "")
    if not paragraphs:
        paragraphs = [text]

    matches, paragraph_hits, scopes, supporting = _scan_paragraphs(paragraphs, dict_data)
    # Rough share: full length of hit paragraphs / body — NOT strict China-token chars.
    hit_chars = sum(h["char_count"] for h in paragraph_hits)
    total_chars = max(sum(len(p) for p in paragraphs), 1)
    paragraph_hit_share = round(hit_chars / total_chars, 4)
    share = paragraph_hit_share  # backward-compatible alias

    targets: list[str] = []
    for m in matches:
        name = m.get("canonical_name")
        if name and name not in targets:
            targets.append(str(name))

    title_conflict = title_screening_label in {
        "explicit_relevant",
        "likely_relevant",
    } and not matches

    folded_body = _fold(text)
    soft_hits = [t for t in _SOFT_CHINA_TOKENS if t in folded_body or t in (title or "").casefold()]

    if not matches:
        if title_conflict:
            return FulltextScreenResult(
                label="uncertain",
                reason_codes=["title_china_signal_body_no_entity"],
                confidence=0.4,
                requires_human_review=True,
                content_share_estimate=0.0,
                paragraph_hit_share=0.0,
                entity_dictionary_version=dict_version,
                input_hash=input_hash,
                summary_of_relevance="Title suggested China relevance but body had no entity hits.",
            )
        if soft_hits:
            return FulltextScreenResult(
                label="possible_china",
                reason_codes=["soft_china_signal_no_entity_dict_hit"],
                confidence=0.35,
                requires_human_review=True,
                content_share_estimate=0.0,
                paragraph_hit_share=0.0,
                entity_dictionary_version=dict_version,
                input_hash=input_hash,
                summary_of_relevance=f"Soft signals only ({', '.join(soft_hits[:4])}); needs review.",
            )
        return FulltextScreenResult(
            label="not_china_related",
            reason_codes=["no_china_entity_in_body"],
            confidence=0.75,
            content_share_estimate=0.0,
            paragraph_hit_share=0.0,
            entity_dictionary_version=dict_version,
            input_hash=input_hash,
        )

    if scopes <= {"ambiguous"}:
        return FulltextScreenResult(
            label="uncertain",
            reason_codes=["ambiguous_entity_only"],
            matched_entities=matches,
            supporting_paragraph_ids=supporting,
            candidate_targets=targets,
            content_share_estimate=share,
            paragraph_hit_share=paragraph_hit_share,
            confidence=0.45,
            requires_human_review=True,
            entity_dictionary_version=dict_version,
            input_hash=input_hash,
            paragraph_hits=paragraph_hits,
            summary_of_relevance="Only ambiguous geography/entity hits in body.",
        )

    # Incidental: single short hit paragraph, tiny share, no core entity → possible, not hard drop
    if (
        "core" not in scopes
        and len(supporting) == 1
        and share < 0.08
        and paragraph_hits[0]["char_count"] < 200
    ):
        return FulltextScreenResult(
            label="possible_china",
            reason_codes=["incidental_mention_only"],
            matched_entities=matches,
            supporting_paragraph_ids=supporting,
            candidate_targets=targets,
            content_share_estimate=share,
            paragraph_hit_share=paragraph_hit_share,
            confidence=0.55,
            requires_human_review=True,
            entity_dictionary_version=dict_version,
            input_hash=input_hash,
            paragraph_hits=paragraph_hits,
            summary_of_relevance="Brief incidental mention; classify as possible_china for recall.",
        )

    reasons = ["substantive_china_discussion"]
    if "core" in scopes:
        reasons.append("core_entity_in_body")
    if share >= 0.25:
        reasons.append("high_paragraph_hit_share")
    if title_screening_label == "explicit_relevant":
        reasons.append("title_and_body_aligned")

    return FulltextScreenResult(
        label="china_related",
        reason_codes=reasons,
        matched_entities=matches,
        supporting_paragraph_ids=supporting,
        candidate_targets=targets,
        content_share_estimate=share,
        paragraph_hit_share=paragraph_hit_share,
        confidence=0.8 if "core" in scopes else 0.7,
        entity_dictionary_version=dict_version,
        input_hash=input_hash,
        paragraph_hits=paragraph_hits,
        summary_of_relevance=(
            f"China-related content in {len(supporting)} paragraph(s); "
            f"paragraph_hit_share≈{share:.2f} (not strict China-token share)."
        ),
    )

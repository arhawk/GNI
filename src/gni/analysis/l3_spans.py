"""L3 China-related span extraction with original-text validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from gni.analysis.l2_fulltext import FulltextScreenResult, split_paragraphs
from gni.processing.normalize import normalize_whitespace


@dataclass
class ChinaSpan:
    paragraph_index: int
    char_start: int
    char_end: int
    text_original: str
    language: str | None = None
    span_type: str = "direct_mention"
    related_entities: list[dict[str, Any]] = field(default_factory=list)
    candidate_targets: list[str] = field(default_factory=list)
    relevance_reason: str | None = None
    extraction_confidence: float | None = None
    validation_status: str = "valid"


def _locate_paragraph(content: str, paragraph: str, paragraph_index: int) -> tuple[int, int] | None:
    """Find paragraph offsets in content_clean; prefer nth occurrence for index."""
    needle = paragraph
    if not needle:
        return None
    start = 0
    found_at: list[int] = []
    while True:
        idx = content.find(needle, start)
        if idx < 0:
            break
        found_at.append(idx)
        start = idx + 1
    if not found_at:
        # fallback: normalized search may fail if paragraph split differs — try first line
        compact = normalize_whitespace(needle)
        idx = normalize_whitespace(content).find(compact)
        if idx < 0:
            return None
        # cannot map reliably to original offsets
        return None
    if paragraph_index < len(found_at):
        pos = found_at[min(paragraph_index, len(found_at) - 1)]
    else:
        pos = found_at[0]
    return pos, pos + len(needle)


def extract_china_spans(
    content_clean: str | None,
    l2: FulltextScreenResult,
    *,
    language: str | None = None,
) -> list[ChinaSpan]:
    """Extract spans from L2 paragraph hits; validate against content_clean."""
    if l2.label != "china_related" or not content_clean:
        return []

    content = content_clean
    paragraphs = split_paragraphs(content)
    spans: list[ChinaSpan] = []
    hit_by_idx = {h["paragraph_index"]: h for h in l2.paragraph_hits}

    for idx in l2.supporting_paragraph_ids:
        para = paragraphs[idx] if 0 <= idx < len(paragraphs) else None
        if not para:
            continue
        hit = hit_by_idx.get(idx) or {}
        entities = list(hit.get("entities") or [])
        targets = [
            str(e.get("canonical_name"))
            for e in entities
            if e.get("canonical_name")
        ]
        loc = _locate_paragraph(content, para, idx)
        if loc is None:
            spans.append(
                ChinaSpan(
                    paragraph_index=idx,
                    char_start=-1,
                    char_end=-1,
                    text_original=para,
                    language=language,
                    span_type="direct_mention",
                    related_entities=entities,
                    candidate_targets=targets,
                    relevance_reason="entity_hit_paragraph",
                    extraction_confidence=0.5,
                    validation_status="span_validation_failed",
                )
            )
            continue
        start, end = loc
        # Verify slice equals paragraph
        slice_text = content[start:end]
        status = "valid" if slice_text == para else "span_validation_failed"
        spans.append(
            ChinaSpan(
                paragraph_index=idx,
                char_start=start if status == "valid" else -1,
                char_end=end if status == "valid" else -1,
                text_original=para if status == "valid" else slice_text or para,
                language=language,
                span_type="direct_mention",
                related_entities=entities,
                candidate_targets=targets,
                relevance_reason="entity_hit_paragraph",
                extraction_confidence=0.85 if status == "valid" else 0.4,
                validation_status=status,
            )
        )
    return spans


def validate_span_quote(content_clean: str, quote: str, start: int | None, end: int | None) -> bool:
    if not content_clean or not quote:
        return False
    if start is not None and end is not None and start >= 0 and end > start:
        return content_clean[start:end] == quote
    return quote in content_clean

"""Offline heuristic six-dimension article analysis (no API)."""

from __future__ import annotations

import re
from typing import Any

from gni.analysis.l3_spans import ChinaSpan
from gni.analysis.relevance import RELEVANCE_WEIGHT_VERSION, RelevanceAssessment
from gni.core.contracts import ARTICLE_INTELLIGENCE_VERSION
from gni.metrics.taxonomy_v1 import (
    TAXONOMY_V1_VERSION,
    boards_for_topics,
    load_taxonomy_v1,
    normalize_topic_ids,
)
from gni.processing.title_l1 import _fold

TAXONOMY_VERSION = TAXONOMY_V1_VERSION
SCHEMA_VERSION = "article_analysis_v1.0"
PROMPT_VERSION = "heuristic_v1.1"
MODEL_NAME = "heuristic-rules"

_QUOTE_MARKERS = (
    "said ",
    "according to",
    "told reporters",
    "stated that",
    "spokesperson",
    "in a statement",
    "\" ",
    "“",
    "表示",
    "称",
    "指出",
    "回应称",
)

TOPIC_KEYWORDS: list[tuple[str, list[str]]] = [
    # Prefer multi-token / specific terms; avoid bare "ai"/"tech" false positives.
    ("economy_trade", ["trade", "tariff", "export", "import", "investment", "wto", "贸易", "出口", "关税"]),
    (
        "technology",
        [
            "artificial intelligence",
            "generative ai",
            "semiconductor",
            "chip export",
            "export control",
            "huawei",
            "5g",
            "芯片",
            "半导体",
            "人工智能",
            "出口管制",
        ],
    ),
    (
        "security_military",
        [
            "military",
            "navy",
            "missile",
            "defense",
            "defence",
            "security pact",
            "security agreement",
            "pla",
            "军事",
            "国防",
            "安全协议",
        ],
    ),
    ("international_relations", ["diplomacy", "summit", "bilateral", "alliance", "外交", "峰会"]),
    ("environment_energy", ["climate", "carbon", "energy", "oil", "气候", "能源"]),
    ("politics_governance", ["election", "governance", "legislature", "选举", "治理"]),
    ("society_culture", ["culture", "education", "society", "人口", "社会", "文化", "教育"]),
]

FRAME_KEYWORDS: list[tuple[str, list[str]]] = [
    ("competition_rivalry", ["rival", "competition", "compete", "race", "竞争"]),
    ("security_threat", ["threat", "risk", "danger", "espionage", "威胁", "风险"]),
    ("economic_impact", ["market", "growth", "gdp", "recession", "经济影响", "增长"]),
    ("cooperation", ["cooperation", " jointly", "partnership", "deal", "合作", "伙伴"]),
    ("governance_ideology", ["authoritarian", "democracy", "ideology", "制度", "意识形态"]),
    ("development_innovation", ["innovation", "develop", "breakthrough", "创新", "发展"]),
    ("human_rights", ["human rights", "uyghur", "xinjiang", "人权", "新疆"]),
    ("international_order", ["rules-based", "order", "un", "international law", "国际秩序"]),
]

NEG_WORDS = {
    "threat", "threatens", "aggression", "coercion", "crackdown", "sanction",
    "sanctions", "espionage", "violation", "concern", "warning", "risk",
    "威胁", "制裁", "打压", "担忧", "风险", "侵犯",
}
POS_WORDS = {
    "cooperation", "partnership", "growth", "opportunity", "progress", "deal",
    "agreement", "boost", "成功", "合作", "机遇", "增长", "协议",
}


def _count_hits(text: str, words: set[str] | list[str]) -> int:
    folded = _fold(text)
    n = 0
    for w in words:
        if not w:
            continue
        wf = w.casefold()
        # CJK: allow substring; Latin: word-boundary only (avoid "pla"∈"players").
        if re.search(r"[\u4e00-\u9fff]", w):
            if w in folded or wf in folded:
                n += 1
        elif re.search(rf"(?<![a-z0-9]){re.escape(wf)}(?![a-z0-9])", folded):
            n += 1
    return n


def _pick_topics_v1(body_text: str) -> tuple[list[str], list[str]]:
    """Multi-label V1.0 classification over body/spans (never title-only)."""
    if not (body_text or "").strip():
        return [], []
    tax = load_taxonomy_v1()
    scored: list[tuple[int, int, str]] = []
    for idx, topic in enumerate(tax.topics):
        hits = _count_hits(body_text, list(topic.keywords))
        if hits > 0:
            scored.append((-hits, idx, topic.id))
    scored.sort()
    topic_ids = normalize_topic_ids([tid for _, _, tid in scored])
    return topic_ids, boards_for_topics(topic_ids)


def _detect_expression_owner(text: str) -> str:
    """Heuristic check whether stance-bearing text is predominantly quoted third-party speech."""
    if not (text or "").strip():
        return "unclear"
    low = text.casefold()
    quote_hits = sum(1 for m in _QUOTE_MARKERS if m in low or m in text)
    # Only flag quoted_actor when multiple explicit attribution cues appear and quotes wrap text
    if quote_hits >= 2 and ('"' in text or "“" in text):
        return "quoted_actor"
    return "media"


def _china_stance_v1(
    body_text: str,
    valid_spans: list[ChinaSpan],
    level: str,
    *,
    model_version: str = MODEL_NAME,
    prompt_version: str = PROMPT_VERSION,
) -> dict[str, Any]:
    """Article-level China-related stance (Positive/Neutral/Negative or Unclassified)."""
    if level in {"none", "uncertain"} or not valid_spans or not (body_text or "").strip():
        return {
            "target": "china_mainland",
            "stance_label": "Unclassified",
            "expression_owner": "unclear",
            "stance_confidence": 0.0,
            "stance_evidence": [],
            "reasoning": "Insufficient China-related body spans to classify stance.",
            "analysis_status": "unclassified",
            "model_version": model_version,
            "prompt_version": prompt_version,
        }

    neg = _count_hits(body_text, NEG_WORDS)
    pos = _count_hits(body_text, POS_WORDS)
    owner = _detect_expression_owner(body_text)
    evidence = [
        {
            "evidence_id": f"ev_span_{i}",
            "quote": s.text_original[:500],
            "start_offset": s.char_start if s.char_start >= 0 else None,
            "end_offset": s.char_end if s.char_end >= 0 else None,
            "paragraph_index": s.paragraph_index,
        }
        for i, s in enumerate(valid_spans[:3])
    ]

    # Mixed stance without clear dominant direction -> Unclassified (V1.0 §4.3)
    if neg > 0 and pos > 0 and abs(neg - pos) <= 1:
        return {
            "target": "china_mainland",
            "stance_label": "Unclassified",
            "expression_owner": owner,
            "stance_confidence": 0.35,
            "stance_evidence": evidence,
            "reasoning": f"Mixed positive ({pos}) and negative ({neg}) cues without clear dominance.",
            "analysis_status": "unclassified",
            "model_version": model_version,
            "prompt_version": prompt_version,
        }
    if neg > pos:
        label = "Negative"
        conf = min(0.85, 0.50 + 0.08 * (neg - pos))
        reason = f"Negative China-related lexical cues ({neg}) outweigh positive ({pos})."
    elif pos > neg:
        label = "Positive"
        conf = min(0.85, 0.50 + 0.08 * (pos - neg))
        reason = f"Positive China-related lexical cues ({pos}) outweigh negative ({neg})."
    else:
        label = "Neutral"
        conf = 0.55
        reason = "Descriptive China-related spans without clear directional polarity."

    return {
        "target": "china_mainland",
        "stance_label": label,
        "expression_owner": owner,
        "stance_confidence": round(conf, 3),
        "stance_evidence": evidence,
        "reasoning": reason,
        "analysis_status": "classified",
        "model_version": model_version,
        "prompt_version": prompt_version,
    }


def _pick_topic(blob: str) -> tuple[str | None, list[str]]:
    scores: list[tuple[int, str]] = []
    for topic_id, kws in TOPIC_KEYWORDS:
        scores.append((_count_hits(blob, kws), topic_id))
    scores.sort(reverse=True)
    # Require at least one solid hit; weak single-letter style matches removed upstream.
    if not scores or scores[0][0] < 1:
        return "other_unknown", []
    primary = scores[0][1]
    secondary = [t for c, t in scores[1:3] if c > 0]
    return primary, secondary


def _pick_frame(blob: str) -> tuple[str | None, list[str], str]:
    scores: list[tuple[int, str]] = []
    for frame_id, kws in FRAME_KEYWORDS:
        scores.append((_count_hits(blob, kws), frame_id))
    scores.sort(reverse=True)
    if not scores or scores[0][0] == 0:
        return "other_unknown", [], "insufficient_evidence"
    primary = scores[0][1]
    secondary = [f for c, f in scores[1:3] if c > 0]
    return primary, secondary, "known"


def _sentiment(blob: str) -> dict[str, Any]:
    neg = _count_hits(blob, NEG_WORDS)
    pos = _count_hits(blob, POS_WORDS)
    if neg == 0 and pos == 0:
        return {
            "label": "neutral",
            "score": 0.0,
            "emotions": [],
            "intensity": 0.2,
            "status": "known",
        }
    if neg > 0 and pos > 0 and abs(neg - pos) <= 1:
        return {
            "label": "mixed",
            "score": None,
            "emotions": ["concern", "uncertainty"],
            "intensity": 0.5,
            "status": "known",
        }
    if neg > pos:
        return {
            "label": "negative",
            "score": -0.60,
            "emotions": ["concern", "criticism"],
            "intensity": min(1.0, 0.4 + 0.1 * neg),
            "status": "known",
        }
    return {
        "label": "positive",
        "score": 0.60,
        "emotions": ["optimism"],
        "intensity": min(1.0, 0.4 + 0.1 * pos),
        "status": "known",
    }


def _stance_from_sentiment(sent_label: str | None) -> str:
    mapping = {
        "positive": "supportive",
        "negative": "critical",
        "neutral": "neutral",
        "mixed": "mixed",
    }
    return mapping.get(sent_label or "", "no_explicit_stance")


def _entities_from_matches(matched: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    type_map = {
        "country": "country",
        "government": "government_agency",
        "party": "organization",
        "person": "political_figure",
        "company": "company",
        "geography": "location",
        "policy": "policy",
        "metonym": "country",
        "indirect": "country",
    }
    for m in matched:
        eid = str(m.get("entity_id") or m.get("canonical_name") or "")
        if not eid or eid in seen:
            continue
        seen.add(eid)
        et = str(m.get("entity_type") or "other")
        mapped_type = type_map.get(et, "other")
        cname = str(m.get("canonical_name") or eid)
        aliases = [str(a) for a in (m.get("aliases_hit") or []) if a]
        out.append(
            {
                "entity_id": eid,
                "canonical_name": cname,
                "entity_type": mapped_type,
                "mentions": aliases or [cname],
                "roles": [str(m.get("inclusion_scope") or "mentioned")],
                "evidence_refs": [],
                # Backward-compatible keys
                "text": cname,
                "type": mapped_type,
                "normalized_id": m.get("entity_id"),
                "confidence": 0.75,
            }
        )
    return out


def _topics_structured_from_v1(topics_v1: list[str], evidence_ids: list[str]) -> list[dict[str, Any]]:
    tax = load_taxonomy_v1()
    tmap = {t.id: t for t in tax.topics}
    out: list[dict[str, Any]] = []
    for idx, tid in enumerate(topics_v1):
        t = tmap.get(tid)
        out.append(
            {
                "topic_id": tid,
                "topic_name": t.name_zh if t else tid,
                "sector_id": t.board_id if t else "",
                "relevance": "primary" if idx == 0 else "secondary",
                "evidence_refs": evidence_ids[:2],
            }
        )
    return out


def _narratives_heuristic(
    frame_primary: str | None,
    valid_spans: list[ChinaSpan],
    sent_label: str | None,
    owner: str,
) -> list[dict[str, Any]]:
    if not frame_primary or frame_primary == "other_unknown" or not valid_spans:
        return []
    span0 = valid_spans[0]
    return [
        {
            "narrative_id": f"nar_heur_{frame_primary}",
            "frame": frame_primary,
            "claim": span0.text_original[:240],
            "actor": "quoted_source" if owner == "quoted_actor" else "media_outlet",
            "target": "china_mainland",
            "attribution": "quote" if owner == "quoted_actor" else "mention",
            "tone": sent_label if sent_label in {"positive", "neutral", "negative", "mixed"} else "unclear",
            "evidence_refs": ["ev_span_0"],
            "confidence": 0.45,
        }
    ]


def _event_candidates_heuristic(
    title: str | None,
    valid_spans: list[ChinaSpan],
) -> list[dict[str, Any]]:
    t = (title or "").strip()
    if not t or not valid_spans:
        return []
    m = re.search(
        r"(?P<actor>[A-Z][\w\.\-]+(?:\s+[A-Z][\w\.\-]+){0,2})\s+"
        r"(?P<action>announces?|unveils?|signs?|launches?|approves?|sanctions?|warns?|meets?|visits?|imposes?)\s+"
        r"(?P<object>.{3,80})",
        t,
        re.I,
    )
    if not m:
        return []
    return [
        {
            "event_id": None,
            "event_relation": "new_event_candidate",
            "actor": m.group("actor").strip(" .,;:"),
            "action": m.group("action").strip().lower(),
            "object": m.group("object").strip(" .,;:"),
            "event_time": None,  # Never substitute published_at
            "location": None,
            "summary": t[:240],
            "event_evidence_refs": ["ev_span_0"],
            "confidence": 0.5,
        }
    ]


def build_structured_analysis(
    *,
    language: str | None,
    title: str | None,
    content_clean: str | None,
    l2_matched_entities: list[dict[str, Any]],
    spans: list[ChinaSpan],
    relevance: RelevanceAssessment,
) -> dict[str, Any]:
    valid_spans = [s for s in spans if s.validation_status == "valid"]
    span_blob = "\n".join(s.text_original for s in valid_spans) or (content_clean or "")
    body_blob = (content_clean or "").strip() or span_blob
    blob = f"{title or ''}\n{span_blob}"

    level = relevance.relevance_level
    weight = relevance.relevance_weight
    is_relevant = level in {"core", "substantial", "secondary", "incidental"}

    if level in {"none", "uncertain"} or not valid_spans:
        topics_v1: list[str] = []
        boards_v1: list[str] = []
        china_stance = _china_stance_v1(span_blob, valid_spans, level)
        primary_topic, secondary_topics = ("other_unknown", [])
        sent = {
            "label": None,
            "score": None,
            "emotions": [],
            "intensity": None,
            "status": "not_applicable" if level == "none" else "insufficient_evidence",
        }
        stances: list[dict[str, Any]] = [
            {
                "target_id": "china",
                "target_surface_form": "China",
                "stance": None,
                "strength": None,
                "status": "not_applicable" if level == "none" else "insufficient_evidence",
            }
        ]
        frame_primary, frame_secondary, frame_status = (
            None,
            [],
            "not_applicable" if level == "none" else "insufficient_evidence",
        )
        analysis_status = "insufficient_evidence" if level != "none" else "completed"
        field_status = {
            "topics": "insufficient_evidence",
            "sentiment": sent["status"],
            "stances": stances[0]["status"],
            "framing": frame_status,
        }
        confidence = {"overall": 0.35 if level != "none" else 0.7}
        evidence: list[dict[str, Any]] = []
    else:
        # V1.0 §2.3: topic classification must be based on article body/spans, never title-only.
        topics_v1, boards_v1 = _pick_topics_v1(body_blob)
        china_stance = _china_stance_v1(span_blob, valid_spans, level)
        if topics_v1:
            primary_topic, secondary_topics = topics_v1[0], topics_v1[1:]
        else:
            primary_topic, secondary_topics = _pick_topic(body_blob)
        sent = _sentiment(span_blob)
        sent["basis_segment_ids"] = [f"span_{i}" for i in range(len(valid_spans[:5]))]
        stance_label = _stance_from_sentiment(sent.get("label"))
        stances = [
            {
                "target_id": "china",
                "target_surface_form": "China",
                "stance": stance_label,
                "strength": sent.get("intensity"),
                "status": "known",
            }
        ]
        # Extra targets from entities when government/military appear
        for m in l2_matched_entities:
            eid = m.get("entity_id")
            if eid == "chinese_gov":
                stances.append(
                    {
                        "target_id": "chinese_government",
                        "target_surface_form": "Chinese Government",
                        "stance": stance_label,
                        "strength": sent.get("intensity"),
                        "status": "known",
                    }
                )
                break
        frame_primary, frame_secondary, frame_status = _pick_frame(blob)
        analysis_status = "completed"
        field_status = {
            "topics": "known" if primary_topic != "other_unknown" else "insufficient_evidence",
            "sentiment": sent["status"],
            "stances": "known",
            "framing": frame_status,
        }
        confidence = {
            "overall": 0.55,
            "sentiment": 0.5,
            "stance": 0.45,
            "topic": 0.5,
            "frame": 0.45,
        }
        evidence = []
        for i, s in enumerate(valid_spans[:5]):
            ev_id = f"ev_span_{i}"
            evidence.append(
                {
                    "evidence_id": ev_id,
                    "field_path": "china_relevance",
                    "quote": s.text_original[:500],
                    "text_span": s.text_original[:500],
                    "start_offset": s.char_start if s.char_start >= 0 else None,
                    "end_offset": s.char_end if s.char_end >= 0 else None,
                    "paragraph_index": s.paragraph_index,
                    "evidence_type": "relevance",
                    "supports_claim": "china_relevance",
                    "analysis_task": "article_intelligence",
                    "validated": True,
                    "confidence": s.extraction_confidence,
                }
            )
            if i == 0 and sent.get("label"):
                evidence.append(
                    {
                        "evidence_id": "ev_sentiment_0",
                        "field_path": "sentiment.label",
                        "quote": s.text_original[:500],
                        "text_span": s.text_original[:500],
                        "start_offset": s.char_start if s.char_start >= 0 else None,
                        "end_offset": s.char_end if s.char_end >= 0 else None,
                        "paragraph_index": s.paragraph_index,
                        "evidence_type": "sentiment",
                        "supports_claim": f"sentiment={sent.get('label')}",
                        "analysis_task": "article_intelligence",
                        "validated": True,
                        "confidence": 0.45,
                    }
                )
                evidence.append(
                    {
                        "evidence_id": "ev_stance_0",
                        "field_path": "china_stance.stance_label",
                        "quote": s.text_original[:500],
                        "text_span": s.text_original[:500],
                        "start_offset": s.char_start if s.char_start >= 0 else None,
                        "end_offset": s.char_end if s.char_end >= 0 else None,
                        "paragraph_index": s.paragraph_index,
                        "evidence_type": "stance",
                        "supports_claim": f"stance={china_stance.get('stance_label')}",
                        "analysis_task": "article_intelligence",
                        "validated": True,
                        "confidence": china_stance.get("stance_confidence") or 0.4,
                    }
                )

    entities = _entities_from_matches(l2_matched_entities)
    ev_ids = [f"ev_span_{i}" for i in range(len(valid_spans[:5]))]
    topics_structured = _topics_structured_from_v1(topics_v1, ev_ids)
    narratives = _narratives_heuristic(
        frame_primary,
        valid_spans,
        sent.get("label") if isinstance(sent, dict) else None,
        str(china_stance.get("expression_owner") or "unclear"),
    )
    event_candidates = _event_candidates_heuristic(title, valid_spans)
    sent.setdefault("sentiment_target", "china_mainland")
    sent.setdefault("confidence", 0.5 if sent.get("label") else 0.0)
    sent.setdefault("reasoning", "Lexical polarity over valid China spans.")
    sent.setdefault("evidence_refs", ["ev_sentiment_0"] if valid_spans and sent.get("label") else [])

    return {
        "schema_version": SCHEMA_VERSION,
        "article_intelligence_version": ARTICLE_INTELLIGENCE_VERSION,
        "taxonomy_version": TAXONOMY_VERSION,
        "relevance_weight_version": RELEVANCE_WEIGHT_VERSION,
        "language": language or "und",
        "china_relevance": {
            "is_relevant": is_relevant if level != "uncertain" else None,
            "level": level,
            "weight": weight,
            "estimated_share": relevance.content_share_estimate,
            "title_mentions_china": relevance.headline_prominence == "title",
            "lead_mentions_china": None,
            "china_is_primary_subject": level == "core",
            "features": relevance.features,
            "rationale": relevance.reasoning_summary or "",
            "confidence": 0.6,
            "status": "known" if level not in {"uncertain"} else "insufficient_evidence",
        },
        "topics": {
            "primary": primary_topic,
            "secondary": secondary_topics,
            "prominence": "core" if level == "core" else ("secondary_mention" if is_relevant else "unknown"),
        },
        "topics_v1": topics_v1,
        "boards_v1": boards_v1,
        "topics_structured": topics_structured,
        "china_stance": china_stance,
        "sentiment": sent,
        "stances": stances,
        "framing": {
            "primary": frame_primary,
            "secondary": frame_secondary,
            "status": frame_status,
        },
        "narratives": narratives,
        "entities": entities,
        "event_candidates": event_candidates,
        "claims": [n["claim"] for n in narratives],
        "evidence": evidence,
        "summary": relevance.reasoning_summary,
        "analysis_status": analysis_status,
        "field_status": field_status,
        "confidence": confidence,
        "notes": "Produced by heuristic-rules offline analyzer; not calibrated gold labels.",
    }

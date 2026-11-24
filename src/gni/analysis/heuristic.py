"""Offline heuristic six-dimension article analysis (no API)."""

from __future__ import annotations

import re
from typing import Any

from gni.analysis.l3_spans import ChinaSpan
from gni.analysis.relevance import RELEVANCE_WEIGHT_VERSION, RelevanceAssessment
from gni.processing.title_l1 import _fold

TAXONOMY_VERSION = "taxonomy_v0.4"
SCHEMA_VERSION = "article_analysis_v0.2"
PROMPT_VERSION = "heuristic_v0.1"
MODEL_NAME = "heuristic-rules"

TOPIC_KEYWORDS: list[tuple[str, list[str]]] = [
    ("economy_trade", ["trade", "tariff", "export", "import", "investment", "wto", "贸易", "出口", "关税"]),
    ("technology", ["ai", "chip", "semiconductor", "huawei", "tech", "5g", "芯片", "半导体", "科技"]),
    ("security_military", ["military", "navy", "missile", "security", "defense", "pla", "军事", "安全", "国防"]),
    ("international_relations", ["diplomacy", "summit", "bilateral", "alliance", "外交", "峰会", "关系"]),
    ("environment_energy", ["climate", "carbon", "energy", "oil", "climate", "气候", "能源", "碳"]),
    ("politics_governance", ["party", "governance", "election", "policy", "政府", "政策", "治理"]),
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
        if re.search(rf"(?<![a-z0-9]){re.escape(w.casefold())}(?![a-z0-9])", folded) or w in folded:
            n += 1
    return n


def _pick_topic(blob: str) -> tuple[str | None, list[str]]:
    scores: list[tuple[int, str]] = []
    for topic_id, kws in TOPIC_KEYWORDS:
        scores.append((_count_hits(blob, kws), topic_id))
    scores.sort(reverse=True)
    if not scores or scores[0][0] == 0:
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
        "government": "organization",
        "party": "organization",
        "person": "person",
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
        out.append(
            {
                "text": m.get("canonical_name") or eid,
                "type": type_map.get(et, "other"),
                "normalized_id": m.get("entity_id"),
                "confidence": 0.75,
            }
        )
    return out


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
    blob = f"{title or ''}\n{span_blob}"

    level = relevance.relevance_level
    weight = relevance.relevance_weight
    is_relevant = level in {"core", "substantial", "secondary", "incidental"}

    if level in {"none", "uncertain"} or not valid_spans:
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
        primary_topic, secondary_topics = _pick_topic(blob)
        sent = _sentiment(blob)
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
            evidence.append(
                {
                    "field_path": "china_relevance",
                    "quote": s.text_original[:500],
                    "start_offset": s.char_start if s.char_start >= 0 else None,
                    "end_offset": s.char_end if s.char_end >= 0 else None,
                    "paragraph_index": s.paragraph_index,
                    "evidence_type": "relevance",
                    "confidence": s.extraction_confidence,
                }
            )
            if i == 0 and sent.get("label"):
                evidence.append(
                    {
                        "field_path": "sentiment.label",
                        "quote": s.text_original[:500],
                        "start_offset": s.char_start if s.char_start >= 0 else None,
                        "end_offset": s.char_end if s.char_end >= 0 else None,
                        "paragraph_index": s.paragraph_index,
                        "evidence_type": "sentiment",
                        "confidence": 0.45,
                    }
                )
                evidence.append(
                    {
                        "field_path": "stances[0].stance",
                        "quote": s.text_original[:500],
                        "start_offset": s.char_start if s.char_start >= 0 else None,
                        "end_offset": s.char_end if s.char_end >= 0 else None,
                        "paragraph_index": s.paragraph_index,
                        "evidence_type": "stance",
                        "confidence": 0.4,
                    }
                )

    entities = _entities_from_matches(l2_matched_entities)

    return {
        "schema_version": SCHEMA_VERSION,
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
        "sentiment": sent,
        "stances": stances,
        "framing": {
            "primary": frame_primary,
            "secondary": frame_secondary,
            "status": frame_status,
        },
        "entities": entities,
        "claims": [],
        "evidence": evidence,
        "summary": relevance.reasoning_summary,
        "analysis_status": analysis_status,
        "field_status": field_status,
        "confidence": confidence,
        "notes": "Produced by heuristic-rules offline analyzer; not calibrated gold labels.",
    }

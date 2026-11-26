"""Optional DeepSeek LLM provider for structured article analysis."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from gni.analysis.heuristic import SCHEMA_VERSION, TAXONOMY_VERSION, build_structured_analysis
from gni.analysis.l3_spans import ChinaSpan
from gni.analysis.provider import BaseLLMProvider
from gni.analysis.relevance import RELEVANCE_WEIGHT_VERSION, RelevanceAssessment
from gni.core.config import Settings, get_settings
from gni.metrics.taxonomy_v1 import boards_for_topics, normalize_topic_ids, taxonomy_prompt_block

logger = logging.getLogger(__name__)

PROMPT_VERSION = "deepseek_analyze_v1.0"
_VALID_STANCE_LABELS = {"Positive", "Neutral", "Negative", "Unclassified"}


class DeepSeekLLMProvider(BaseLLMProvider):
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        if not self.settings.llm_api_key:
            raise RuntimeError("GNI_LLM_API_KEY is required for DeepSeek provider")

    def generate(self, prompt: str, **kwargs: Any) -> str:
        model = kwargs.get("model") or self.settings.llm_model
        max_tokens = int(kwargs.get("max_tokens") or min(self.settings.per_article_token_limit, 4000))
        url = self.settings.llm_base_url.rstrip("/") + "/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.settings.llm_api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an analyst for Global Narrative Intelligence. "
                        "Return ONLY valid JSON matching the article analysis schema. "
                        "Stance must bind to a target_id. Do not invent quotes not in the text."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "max_tokens": max_tokens,
        }
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(url, headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json()
        return data["choices"][0]["message"]["content"]

    def embed(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("DeepSeek embed is not configured in P1-C")

    def analyze(self, article: dict[str, Any], *, schema: dict[str, Any], prompt_version: str) -> dict[str, Any]:
        prompt = (
            f"schema_version={SCHEMA_VERSION} taxonomy={TAXONOMY_VERSION} prompt_version={prompt_version}\n"
            f"Analyze China-related content and return ONLY valid JSON.\n"
            f"Rules (GNI Statistical Methodology V1.0):\n"
            f"1. Multi-label topics_v1 MUST be based on article body/spans (never title-only). "
            f"An article may match 0, 1, or multiple topics across boards.\n"
            f"2. Evaluate china_stance toward Mainland China (NOT general emotion, NOT quoted interviewee alone). "
            f"stance_label MUST be one of: Positive, Neutral, Negative, Unclassified.\n"
            f"3. If mixed positive and negative without a clear dominant stance, or insufficient evidence, "
            f"set stance_label='Unclassified' and analysis_status='unclassified'.\n"
            f"4. Include stance_evidence as a list of objects with 'quote' copied verbatim from the text.\n"
            f"Required JSON keys: topics_v1 (list of topic IDs), china_stance "
            f"({{stance_label, stance_confidence, stance_evidence, analysis_status}}), "
            f"sentiment, stances, framing, summary.\n"
            f"{taxonomy_prompt_block()}\n"
            f"Title: {article.get('title')}\n"
            f"Language: {article.get('language')}\n"
            f"Relevance hint: {article.get('relevance')}\n"
            f"Spans/Body:\n{article.get('spans_text')}\n"
        )
        raw = self.generate(prompt, max_tokens=min(self.settings.per_article_token_limit, 4000))
        parsed = _extract_json(raw)
        if parsed is None:
            raise ValueError("DeepSeek response was not valid JSON")
        parsed["schema_version"] = SCHEMA_VERSION
        parsed["taxonomy_version"] = TAXONOMY_VERSION
        parsed.setdefault("relevance_weight_version", RELEVANCE_WEIGHT_VERSION)

        # Validate V1.0 multi-label topics & derive boards
        raw_topics = parsed.get("topics_v1")
        if not isinstance(raw_topics, list):
            raw_topics = []
        valid_topics = normalize_topic_ids(raw_topics)
        parsed["topics_v1"] = valid_topics
        parsed["boards_v1"] = boards_for_topics(valid_topics)

        # Validate V1.0 china_stance
        raw_cs = parsed.get("china_stance") if isinstance(parsed.get("china_stance"), dict) else {}
        raw_label = str(raw_cs.get("stance_label") or "").strip()
        label = raw_label if raw_label in _VALID_STANCE_LABELS else "Unclassified"
        ev = raw_cs.get("stance_evidence") if isinstance(raw_cs.get("stance_evidence"), list) else []
        try:
            conf = float(raw_cs.get("stance_confidence", 0.0))
        except (TypeError, ValueError):
            conf = 0.0
        parsed["china_stance"] = {
            "stance_label": label,
            "stance_confidence": max(0.0, min(1.0, conf)),
            "stance_evidence": ev,
            "analysis_status": "classified" if label in {"Positive", "Neutral", "Negative"} else "unclassified",
            "model_version": self.settings.llm_model,
            "prompt_version": prompt_version,
        }
        return parsed


def _extract_json(text: str) -> dict[str, Any] | None:
    text = (text or "").strip()
    if not text:
        return None
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        return None


def estimate_call_cost_usd(*, prompt_chars: int, completion_chars: int = 1500) -> float:
    """Rough DeepSeek chat cost estimate for budget accounting (not billing-accurate)."""
    # ~4 chars/token; assume ~$0.14 / 1M input + $0.28 / 1M output (order-of-magnitude)
    tokens_in = max(1, prompt_chars // 4)
    tokens_out = max(1, completion_chars // 4)
    return (tokens_in * 0.14 + tokens_out * 0.28) / 1_000_000


def analyze_with_fallback(
    *,
    provider_name: str,
    language: str | None,
    title: str | None,
    content_clean: str | None,
    l2_matched_entities: list[dict[str, Any]],
    spans: list[ChinaSpan],
    relevance: RelevanceAssessment,
    settings: Settings | None = None,
) -> tuple[dict[str, Any], str, str, int, float]:
    """
    Returns (structured_result, provider, model_name, token_usage, estimated_cost_usd).
    Falls back to heuristic on DeepSeek failure.
    """
    settings = settings or get_settings()
    if provider_name == "deepseek" and settings.llm_api_key:
        try:
            valid = [s for s in spans if s.validation_status == "valid"]
            spans_text = "\n---\n".join(s.text_original for s in valid[:12])
            article = {
                "title": title,
                "language": language,
                "relevance": {
                    "level": relevance.relevance_level,
                    "weight": relevance.relevance_weight,
                },
                "spans_text": spans_text or (content_clean or "")[:6000],
            }
            est = estimate_call_cost_usd(prompt_chars=len(spans_text) + len(title or ""))
            ds = DeepSeekLLMProvider(settings)
            result = ds.analyze(article, schema={}, prompt_version=PROMPT_VERSION)
            # Ensure required keys exist; fill gaps from heuristic
            heuristic = build_structured_analysis(
                language=language,
                title=title,
                content_clean=content_clean,
                l2_matched_entities=l2_matched_entities,
                spans=spans,
                relevance=relevance,
            )
            for key in (
                "schema_version",
                "taxonomy_version",
                "language",
                "china_relevance",
                "topics",
                "topics_v1",
                "boards_v1",
                "china_stance",
                "sentiment",
                "stances",
                "framing",
                "entities",
                "evidence",
                "field_status",
                "confidence",
            ):
                if key not in result:
                    result[key] = heuristic[key]
            result["schema_version"] = SCHEMA_VERSION
            result.setdefault("relevance_weight_version", RELEVANCE_WEIGHT_VERSION)
            tokens = min(settings.per_article_token_limit, max(100, (len(spans_text) // 4) + 800))
            return result, "deepseek", settings.llm_model, tokens, est
        except Exception:  # noqa: BLE001
            logger.exception("DeepSeek analyze failed; falling back to heuristic")

    result = build_structured_analysis(
        language=language,
        title=title,
        content_clean=content_clean,
        l2_matched_entities=l2_matched_entities,
        spans=spans,
        relevance=relevance,
    )
    return result, "heuristic", "heuristic-rules", 0, 0.0

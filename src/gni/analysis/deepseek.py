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

logger = logging.getLogger(__name__)

PROMPT_VERSION = "deepseek_analyze_v0.1"


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
            f"schema_version={SCHEMA_VERSION} taxonomy={TAXONOMY_VERSION}\n"
            f"Analyze China-related content. Return JSON only.\n"
            f"Title: {article.get('title')}\n"
            f"Language: {article.get('language')}\n"
            f"Relevance hint: {article.get('relevance')}\n"
            f"Spans:\n{article.get('spans_text')}\n"
        )
        raw = self.generate(prompt, max_tokens=min(self.settings.per_article_token_limit, 4000))
        parsed = _extract_json(raw)
        if parsed is None:
            raise ValueError("DeepSeek response was not valid JSON")
        parsed.setdefault("schema_version", SCHEMA_VERSION)
        parsed.setdefault("taxonomy_version", TAXONOMY_VERSION)
        parsed.setdefault("relevance_weight_version", RELEVANCE_WEIGHT_VERSION)
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

"""Optional DeepSeek LLM provider for structured article analysis."""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Any

import httpx

from gni.analysis.heuristic import SCHEMA_VERSION, TAXONOMY_VERSION, build_structured_analysis
from gni.analysis.l3_spans import ChinaSpan
from gni.analysis.provider import BaseLLMProvider
from gni.analysis.relevance import RELEVANCE_WEIGHT_VERSION, RelevanceAssessment
from gni.core.config import Settings, get_settings
from gni.core.contracts import (
    ARTICLE_INTELLIGENCE_VERSION,
    ArticleEntityContract,
    ArticleEventCandidateContract,
    ArticleNarrativeContract,
)
from gni.events.fingerprint import allowed_action_keys, allowed_actor_keys
from gni.metrics.taxonomy_v1 import boards_for_topics, normalize_topic_ids, taxonomy_prompt_block

logger = logging.getLogger(__name__)

PROMPT_VERSION = "deepseek_analyze_v1.2"


def _actor_key_choices() -> str:
    return ", ".join(allowed_actor_keys())


def _action_key_choices() -> str:
    return ", ".join(allowed_action_keys())
_VALID_STANCE_LABELS = {"Positive", "Neutral", "Negative", "Unclassified"}
_VALID_OWNERS = {"media", "quoted_actor", "unclear"}


@dataclass
class LLMCallResult:
    """Structured result from a single LLM JSON call (with usage & timing telemetry)."""

    parsed: dict[str, Any]
    raw_text: str
    provider: str
    model_version: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: int
    estimated_cost_usd: float


def estimate_token_cost_usd(*, prompt_tokens: int, completion_tokens: int) -> float:
    """Rough DeepSeek chat cost estimate from actual token counts."""
    return round((max(0, prompt_tokens) * 0.14 + max(0, completion_tokens) * 0.28) / 1_000_000, 6)


class DeepSeekLLMProvider(BaseLLMProvider):
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        if not self.settings.llm_api_key:
            raise RuntimeError("GNI_LLM_API_KEY is required for DeepSeek provider")

    def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 2500,
        timeout: float = 75.0,
        max_retries: int = 2,
    ) -> LLMCallResult:
        """Generic OpenAI-compatible structured JSON chat call with retries & usage telemetry."""
        chosen_model = model or self.settings.llm_model or "deepseek-chat"
        url = self.settings.llm_base_url.rstrip("/") + "/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.settings.llm_api_key}",
            "Content-Type": "application/json",
        }
        body: dict[str, Any] = {
            "model": chosen_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }
        last_exc: Exception | None = None
        cur_max_tokens = max_tokens
        for attempt in range(max_retries + 1):
            t0 = time.monotonic()
            body["max_tokens"] = cur_max_tokens
            try:
                with httpx.Client(timeout=timeout) as client:
                    resp = client.post(url, headers=headers, json=body)
                    if resp.status_code in {429, 500, 502, 503, 504} and attempt < max_retries:
                        time.sleep(min(4.0, 1.0 * (2**attempt)))
                        continue
                    resp.raise_for_status()
                    data = resp.json()
                latency_ms = int((time.monotonic() - t0) * 1000)
                choice0 = data["choices"][0]
                finish_reason = choice0.get("finish_reason")
                raw_text = str(choice0["message"]["content"] or "")
                parsed = _extract_json(raw_text)
                if parsed is None:
                    logger.warning(
                        "LLM JSON parse failed (attempt=%d finish_reason=%s len=%d max_tokens=%d)",
                        attempt + 1,
                        finish_reason,
                        len(raw_text),
                        cur_max_tokens,
                    )
                    if finish_reason == "length":
                        cur_max_tokens = min(8192, cur_max_tokens * 2)
                    raise ValueError(
                        f"LLM response was not valid JSON object (finish_reason={finish_reason})"
                    )
                usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
                p_tok = int(usage.get("prompt_tokens") or max(1, (len(system_prompt) + len(user_prompt)) // 4))
                c_tok = int(usage.get("completion_tokens") or max(1, len(raw_text) // 4))
                t_tok = int(usage.get("total_tokens") or (p_tok + c_tok))
                model_ver = str(data.get("model") or chosen_model)
                return LLMCallResult(
                    parsed=parsed,
                    raw_text=raw_text,
                    provider="deepseek",
                    model_version=model_ver,
                    prompt_tokens=p_tok,
                    completion_tokens=c_tok,
                    total_tokens=t_tok,
                    latency_ms=latency_ms,
                    estimated_cost_usd=estimate_token_cost_usd(
                        prompt_tokens=p_tok, completion_tokens=c_tok
                    ),
                )
            except (httpx.TimeoutException, httpx.TransportError, ValueError) as exc:
                last_exc = exc
                if attempt < max_retries:
                    time.sleep(min(4.0, 1.0 * (2**attempt)))
                    continue
                raise
            except Exception as exc:
                last_exc = exc
                raise
        raise RuntimeError(f"LLM generate_json failed: {last_exc}")

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
            f"schema_version={SCHEMA_VERSION} intel_version={ARTICLE_INTELLIGENCE_VERSION} "
            f"taxonomy={TAXONOMY_VERSION} prompt_version={prompt_version}\n"
            f"Analyze ONLY China-related content and return ONLY valid JSON.\n"
            f"Rules (GNI Statistical Methodology V1.0 & Intelligence V2.0):\n"
            f"1. Multi-label topics_v1 MUST be based on article body/spans (never title-only). "
            f"An article may match 0, 1, or multiple topics across boards.\n"
            f"2. Evaluate china_stance toward Mainland China (target='china_mainland'). "
            f"Keep Sentiment and Stance independent. MUST set expression_owner to one of: "
            f"'media' (outlet's own framing/editorial voice), 'quoted_actor' (primarily quoted interviewee/official), "
            f"or 'unclear'. Never treat a quoted speaker's view as the media's own stance.\n"
            f"3. stance_label MUST be one of: Positive, Neutral, Negative, Unclassified. "
            f"If mixed without clear dominance, purely quoted without editorial stance, or insufficient evidence, "
            f"set stance_label='Unclassified' and analysis_status='unclassified'.\n"
            f"4. Include stance_evidence as a list of objects with 'quote' copied VERBATIM from the provided text.\n"
            f"5. Extract narratives[] (frame, claim, actor, target, attribution in [mention,quote,support,refute,unclear], "
            f"tone, quote, confidence), key entities[] (entity_id, canonical_name, entity_type, mentions, roles), "
            f"and event_candidates[] (event_relation in [new_event_candidate,existing_event_update,background_reference,unrelated], "
            f"actor, action, object, event_time=null unless explicitly stated in text, location, summary, confidence). "
            f"NEVER fill unknown event_time with published_at.\n"
            f"For each event_candidate also set actor_key to the code matching the actor, chosen ONLY from "
            f"[{_actor_key_choices()}], and action_key to the code matching the action, chosen ONLY from "
            f"[{_action_key_choices()}]. Use null when no listed code fits. Codes must be used verbatim.\n"
            f"Required JSON keys: topics_v1, china_stance ({{target, stance_label, expression_owner, stance_confidence, "
            f"stance_evidence, reasoning, analysis_status}}), sentiment ({{label, sentiment_target, confidence, reasoning}}), "
            f"narratives, entities, event_candidates, stances, framing, summary.\n"
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
        parsed["article_intelligence_version"] = ARTICLE_INTELLIGENCE_VERSION
        parsed["taxonomy_version"] = TAXONOMY_VERSION
        parsed.setdefault("relevance_weight_version", RELEVANCE_WEIGHT_VERSION)

        # Validate V1.0 multi-label topics & derive boards
        raw_topics = parsed.get("topics_v1")
        if not isinstance(raw_topics, list):
            raw_topics = []
        valid_topics = normalize_topic_ids(raw_topics)
        parsed["topics_v1"] = valid_topics
        parsed["boards_v1"] = boards_for_topics(valid_topics)

        # Validate V1.0/V2.0 china_stance (target + expression_owner)
        raw_cs = parsed.get("china_stance") if isinstance(parsed.get("china_stance"), dict) else {}
        raw_label = str(raw_cs.get("stance_label") or "").strip()
        label = raw_label if raw_label in _VALID_STANCE_LABELS else "Unclassified"
        raw_owner = str(raw_cs.get("expression_owner") or "unclear").strip().lower()
        if raw_owner in {"outlet", "editorial", "author"}:
            owner = "media"
        elif raw_owner in {"quoted", "quote", "interviewee", "third_party", "cited"}:
            owner = "quoted_actor"
        else:
            owner = raw_owner if raw_owner in _VALID_OWNERS else "unclear"
        ev = raw_cs.get("stance_evidence") if isinstance(raw_cs.get("stance_evidence"), list) else []
        try:
            conf = float(raw_cs.get("stance_confidence", 0.0))
        except (TypeError, ValueError):
            conf = 0.0
        parsed["china_stance"] = {
            "target": str(raw_cs.get("target") or "china_mainland"),
            "stance_label": label,
            "expression_owner": owner,
            "stance_confidence": max(0.0, min(1.0, conf)),
            "stance_evidence": ev,
            "reasoning": str(raw_cs.get("reasoning") or "").strip(),
            "analysis_status": "classified" if label in {"Positive", "Neutral", "Negative"} else "unclassified",
            "model_version": self.settings.llm_model,
            "prompt_version": prompt_version,
        }

        # Normalize narratives / entities / event_candidates via V2.0 contracts
        raw_nars = parsed.get("narratives") if isinstance(parsed.get("narratives"), list) else []
        norm_nars: list[dict[str, Any]] = []
        for idx, item in enumerate(raw_nars[:8]):
            if not isinstance(item, dict) or not (item.get("claim") or item.get("frame")):
                continue
            item_copy = dict(item)
            item_copy.setdefault("narrative_id", f"nar_{idx}")
            item_copy.setdefault("frame", "unspecified")
            item_copy.setdefault("claim", item_copy["frame"])
            try:
                norm_nars.append(ArticleNarrativeContract.model_validate(item_copy).model_dump())
            except Exception:
                continue
        parsed["narratives"] = norm_nars

        raw_ents = parsed.get("entities") if isinstance(parsed.get("entities"), list) else []
        norm_ents: list[dict[str, Any]] = []
        for idx, item in enumerate(raw_ents[:15]):
            if not isinstance(item, dict):
                continue
            cname = str(item.get("canonical_name") or item.get("text") or "").strip()
            if not cname:
                continue
            item_copy = dict(item)
            item_copy.setdefault("entity_id", str(item.get("normalized_id") or f"ent_{idx}"))
            item_copy["canonical_name"] = cname
            item_copy.setdefault("entity_type", item.get("type") or "other")
            try:
                ed = ArticleEntityContract.model_validate(item_copy).model_dump()
                ed["text"] = ed["canonical_name"]
                ed["type"] = ed["entity_type"]
                norm_ents.append(ed)
            except Exception:
                continue
        if norm_ents:
            parsed["entities"] = norm_ents

        raw_evs = parsed.get("event_candidates") if isinstance(parsed.get("event_candidates"), list) else []
        norm_evs: list[dict[str, Any]] = []
        for item in raw_evs[:5]:
            if not isinstance(item, dict):
                continue
            try:
                norm_evs.append(ArticleEventCandidateContract.model_validate(item).model_dump())
            except Exception:
                continue
        parsed["event_candidates"] = norm_evs
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
                "article_intelligence_version",
                "taxonomy_version",
                "language",
                "china_relevance",
                "topics",
                "topics_v1",
                "boards_v1",
                "topics_structured",
                "china_stance",
                "sentiment",
                "stances",
                "framing",
                "narratives",
                "entities",
                "event_candidates",
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

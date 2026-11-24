"""Optional LLM polish for daily-report narratives only (never invent metrics)."""

from __future__ import annotations

import json
import re
import urllib.request
from typing import Any

from gni.core.config import get_settings

ALLOWED_KEYS = ("attention", "tone", "agenda", "events", "quality")


def _facts_blob(payload: dict[str, Any]) -> dict[str, Any]:
    sections = payload.get("sections") or {}
    return {
        "period": payload.get("period"),
        "disclaimer": payload.get("disclaimer"),
        "attention": {
            "china_article_count": (sections.get("attention") or {}).get("china_article_count"),
            "attention_share": (sections.get("attention") or {}).get("attention_share"),
            "missing_analysis": (sections.get("attention") or {}).get("missing_analysis"),
            "coverage_by_country": (sections.get("attention") or {}).get("coverage_by_country"),
        },
        "tone": sections.get("tone"),
        "agenda": {
            "topics_top": (sections.get("agenda") or {}).get("topics_top"),
            "frames_top": (sections.get("agenda") or {}).get("frames_top"),
        },
        "events_titles": [
            {"title": e.get("title"), "countries": e.get("reporting_countries")}
            for e in (sections.get("events") or [])[:8]
        ],
        "quality": {
            "countries_without_sample": (sections.get("quality") or {}).get(
                "countries_without_sample"
            ),
            "missing_analysis": (sections.get("quality") or {}).get("missing_analysis"),
        },
    }


def _extract_integers(text: str) -> set[str]:
    return set(re.findall(r"\d+(?:\.\d+)?", text))


def _allowed_number_tokens(facts: dict[str, Any]) -> set[str]:
    raw = json.dumps(facts, ensure_ascii=False, default=str)
    return _extract_integers(raw) | {"0", "1", "2", "3", "4", "5", "6", "7", "8", "9"}


def _validate_narratives(narratives: dict[str, Any], facts: dict[str, Any]) -> dict[str, str]:
    allowed_nums = _allowed_number_tokens(facts)
    out: dict[str, str] = {}
    for key in ALLOWED_KEYS:
        val = narratives.get(key)
        if not isinstance(val, str) or not val.strip():
            continue
        text = val.strip()[:500]
        # Reject if narrative invents numbers not present in facts JSON
        for tok in _extract_integers(text):
            if tok not in allowed_nums:
                return {}
        out[key] = text
    return out


def polish_daily_narratives(payload: dict[str, Any]) -> dict[str, str] | None:
    """Call DeepSeek to rewrite narrative one-liners. Returns None if unavailable."""
    settings = get_settings()
    key = settings.llm_api_key
    if not key or (settings.llm_provider or "").lower() not in {"deepseek", "openai", ""}:
        # still try if key present
        if not key:
            return None

    facts = _facts_blob(payload)
    prompt = (
        "你是对华官媒样本日报的编辑。根据下列 JSON 事实，为五个键各写一句中文短评（≤80字）。\n"
        "硬规则：不得发明、改动任何数字或 article/event id；不得给出对华综合分数；"
        "不得把样本说成国家立场或民意；可提示缺口与谨慎。\n"
        "只输出 JSON 对象，键必须是: attention, tone, agenda, events, quality\n\n"
        f"FACTS:\n{json.dumps(facts, ensure_ascii=False, default=str)[:12000]}"
    )
    body = json.dumps(
        {
            "model": settings.llm_model or "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
        }
    ).encode("utf-8")
    base = (settings.llm_base_url or "https://api.deepseek.com").rstrip("/")
    req = urllib.request.Request(
        f"{base}/chat/completions",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        text = data["choices"][0]["message"]["content"]
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            return None
        parsed = json.loads(m.group())
        validated = _validate_narratives(parsed, facts)
        return validated or None
    except Exception:
        return None

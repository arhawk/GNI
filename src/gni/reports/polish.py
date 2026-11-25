"""Optional LLM polish for daily-report narratives only (never invent metrics)."""

from __future__ import annotations

import json
import re
import urllib.request
from typing import Any

from gni.core.config import get_settings

ALLOWED_KEYS = ("executive", "coverage", "tone", "signals", "quality")
FORBIDDEN_IN_NARRATIVE = ("对华总分", "综合舆情指数", "代表民意", "全民舆论", "国家官方立场是")


def _facts_blob(payload: dict[str, Any]) -> dict[str, Any]:
    sections = payload.get("sections") or {}
    summary = sections.get("summary") or {}
    return {
        "period": payload.get("period"),
        "disclaimer": payload.get("disclaimer"),
        "kpis": summary.get("kpis"),
        "comparisons": summary.get("comparisons"),
        "top_changes": summary.get("top_changes"),
        "coverage": {
            "by_country": (sections.get("coverage") or {}).get("by_country"),
            "topics_top": (sections.get("coverage") or {}).get("topics_top"),
            "frames_top": (sections.get("coverage") or {}).get("frames_top"),
        },
        "tone": {
            "overall_sentiment_counts": (sections.get("tone") or {}).get(
                "overall_sentiment_counts"
            ),
            "overall_stance_counts": (sections.get("tone") or {}).get("overall_stance_counts"),
            "by_country_summaries": [
                r.get("summary_text") for r in ((sections.get("tone") or {}).get("by_country") or [])
            ],
        },
        "events_titles": [
            {
                "title": e.get("title"),
                "importance": e.get("importance_score"),
                "countries": (e.get("coverage") or {}).get("countries"),
            }
            for e in (sections.get("major_events") or [])[:8]
        ],
        "signals": [
            {"title": s.get("title"), "severity": s.get("severity")}
            for s in (sections.get("signals") or [])[:5]
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
    return _extract_integers(raw) | {str(i) for i in range(10)}


def _validate_narratives(narratives: dict[str, Any], facts: dict[str, Any]) -> dict[str, str]:
    allowed_nums = _allowed_number_tokens(facts)
    out: dict[str, str] = {}
    for key in ALLOWED_KEYS:
        val = narratives.get(key)
        if not isinstance(val, str) or not val.strip():
            continue
        text = val.strip()[:500]
        for tok in _extract_integers(text):
            if tok not in allowed_nums:
                return {}
        if any(p in text for p in FORBIDDEN_IN_NARRATIVE):
            return {}
        out[key] = text
    return out


def polish_daily_narratives(payload: dict[str, Any]) -> dict[str, str] | None:
    """Call DeepSeek to rewrite narrative strings. Returns None if unavailable."""
    settings = get_settings()
    key = settings.llm_api_key
    if not key:
        return None

    facts = _facts_blob(payload)
    prompt = (
        "你是对华官媒样本「每日情报」编辑。根据 FACTS JSON，为下列键各写一句中文短评：\n"
        "executive(≤120字)、coverage、tone、signals、quality(各≤80字)。\n"
        "硬规则：不得发明或改动任何数字/ID；不得给出对华综合分数；"
        "不得把样本说成国家官方立场或民意；可提示缺口与谨慎。\n"
        "只输出 JSON，键必须是: executive, coverage, tone, signals, quality\n\n"
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

"""Event Fingerprint normalize + rule match scoring (MVP)."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "of",
        "to",
        "in",
        "on",
        "for",
        "with",
        "from",
        "by",
        "as",
        "at",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "its",
        "their",
        "his",
        "her",
        "over",
        "amid",
        "after",
        "before",
        "into",
        "about",
        "says",
        "say",
        "said",
        "new",
        "china",
        "chinese",
        "beijing",
    }
)

ACTOR_ALIASES: dict[str, str] = {
    "china": "china",
    "chinese": "china",
    "beijing": "china",
    "prc": "china",
    "中国": "china",
    "中方": "china",
    "北京": "china",
    "united states": "us",
    "u.s.": "us",
    "u.s": "us",
    "usa": "us",
    "us": "us",
    "washington": "us",
    "white house": "us",
    "美国": "us",
    "美方": "us",
    "华盛顿": "us",
    "russia": "russia",
    "moscow": "russia",
    "kremlin": "russia",
    "俄国": "russia",
    "俄罗斯": "russia",
    "莫斯科": "russia",
    "eu": "eu",
    "european union": "eu",
    "brussels": "eu",
    "欧盟": "eu",
    "germany": "germany",
    "berlin": "germany",
    "德国": "germany",
    "deutschland": "germany",
    "india": "india",
    "new delhi": "india",
    "印度": "india",
    "australia": "australia",
    "canberra": "australia",
    "澳大利亚": "australia",
    "japan": "japan",
    "tokyo": "japan",
    "日本": "japan",
    "uk": "uk",
    "britain": "uk",
    "london": "uk",
    "英国": "uk",
    "france": "france",
    "paris": "france",
    "法国": "france",
}

TIME_WINDOW = timedelta(hours=72)
SAME_THRESHOLD = 0.72
AMBIGUOUS_LOW = 0.45
AMBIGUOUS_HIGH = 0.72


@lru_cache(maxsize=1)
def _action_map() -> dict[str, str]:
    path = Path(__file__).resolve().parents[3] / "configs" / "event_action_synonyms.yaml"
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out: dict[str, str] = {}
    for canon, forms in raw.items():
        key = str(canon).upper()
        out[key.lower()] = key
        for form in forms or []:
            out[str(form).lower()] = key
    return out


def allowed_action_keys() -> list[str]:
    """Canonical ACTION_KEYs the analysis LLM may emit (from configs/event_action_synonyms.yaml)."""
    return sorted(set(_action_map().values()))


def allowed_actor_keys() -> list[str]:
    """Canonical ACTOR_KEYs the analysis LLM may emit (values of ACTOR_ALIASES)."""
    return sorted(set(ACTOR_ALIASES.values()))


def valid_actor_key(raw: Any) -> str | None:
    """Accept an LLM-supplied actor_key only if it is in the controlled vocabulary."""
    if not isinstance(raw, str):
        return None
    key = raw.strip().lower()
    return key if key in set(allowed_actor_keys()) else None


def valid_action_key(raw: Any) -> str | None:
    """Accept an LLM-supplied action_key only if it is in the controlled vocabulary."""
    if not isinstance(raw, str):
        return None
    key = raw.strip().upper()
    return key if key in set(allowed_action_keys()) else None


def tokenize(text: str | None) -> set[str]:
    if not text:
        return set()
    toks = re.findall(r"[a-z0-9\u4e00-\u9fff]+", text.lower())
    return {t for t in toks if t not in STOPWORDS and len(t) > 1}


def normalize_actor(raw: str | None) -> str | None:
    """Map surface form → canonical actor key. Unknown → None (no fake token-sort keys)."""
    if not raw:
        return None
    s = raw.strip().lower()
    if s in ACTOR_ALIASES:
        return ACTOR_ALIASES[s]
    for alias, key in sorted(ACTOR_ALIASES.items(), key=lambda kv: -len(kv[0])):
        if alias in s:
            return key
    return None


def normalize_action(raw: str | None) -> str | None:
    """Map surface form → canonical ACTION_KEY. Unknown → None (no fake UNKNOWN/token keys)."""
    if not raw:
        return None
    amap = _action_map()
    s = raw.strip().lower()
    if s in amap:
        return amap[s]
    for form, canon in sorted(amap.items(), key=lambda kv: -len(kv[0])):
        if form == s or form in s.split() or form in s:
            return canon
    for tok in tokenize(s):
        if tok in amap:
            return amap[tok]
    return None


def normalize_object(raw: str | None) -> str | None:
    if not raw:
        return None
    toks = sorted(tokenize(raw))
    if not toks:
        return raw.strip().lower()[:128]
    return " ".join(toks)[:256]


def fingerprint_hash(
    actor_key: str | None,
    action_key: str | None,
    object_key: str | None,
    event_time: datetime | None = None,
) -> str:
    day = ""
    if event_time:
        et = event_time if event_time.tzinfo else event_time.replace(tzinfo=timezone.utc)
        day = et.astimezone(timezone.utc).strftime("%Y-%m-%d")
    payload = f"{actor_key or ''}|{action_key or ''}|{object_key or ''}|{day}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def object_overlap(a: str | None, b: str | None) -> float:
    ta, tb = tokenize(a), tokenize(b)
    if not ta or not tb:
        # soft credit if both empty / identical strings
        if (a or "").strip() and (a or "").strip().lower() == (b or "").strip().lower():
            return 1.0
        return 0.0
    inter = len(ta & tb)
    union = len(ta | tb)
    return inter / union if union else 0.0


@dataclass
class FingerprintCard:
    article_id: str
    actor: str | None = None
    action: str | None = None
    object: str | None = None
    target: str | None = None
    event_type: str | None = None
    location_label: str | None = None
    location_country_id: str | None = None
    qualifiers: dict[str, Any] = field(default_factory=dict)
    summary: str | None = None
    event_time: datetime | None = None
    published_at: datetime | None = None
    confidence: float = 0.5
    evidence: dict[str, Any] = field(default_factory=dict)
    analysis_id: str | None = None
    article_version_id: str | None = None
    # Standardized keys emitted by the analysis LLM (validated against the controlled vocabulary).
    # When present they take precedence over the alias/synonym dictionaries.
    llm_actor_key: str | None = None
    llm_action_key: str | None = None

    @property
    def actor_key(self) -> str | None:
        return valid_actor_key(self.llm_actor_key) or normalize_actor(self.actor)

    @property
    def action_key(self) -> str | None:
        return valid_action_key(self.llm_action_key) or normalize_action(self.action)

    @property
    def object_key(self) -> str | None:
        return normalize_object(self.object)

    @property
    def is_insufficient(self) -> bool:
        """True when actor/action cannot be grounded in alias/synonym dictionaries."""
        return self.actor_key is None or self.action_key is None

    @property
    def match_time(self) -> tuple[datetime | None, str | None]:
        """Time used only for SAME_EVENT matching tolerance — never as Event.event_time.

        Returns (datetime, time_basis) where basis is event_time | published_at_fallback | None.
        """
        if self.event_time is not None:
            return self.event_time, "event_time"
        if self.published_at is not None:
            return self.published_at, "published_at_fallback"
        return None, None

    @property
    def effective_time(self) -> datetime | None:
        """Deprecated alias for match_time[0]. Do not persist as Event.event_time."""
        return self.match_time[0]

    def to_fingerprint_dict(self) -> dict[str, Any]:
        # Hash day bucket uses true event_time only (empty day if unknown).
        insufficient = self.is_insufficient
        return {
            "actor": self.actor,
            "action": self.action,
            "object": self.object,
            "target": self.target,
            "event_type": self.event_type,
            "location": {
                "label": self.location_label,
                "country_id": self.location_country_id,
            },
            "qualifiers": self.qualifiers,
            "summary": self.summary,
            "event_time": self.event_time.isoformat() if self.event_time else None,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "actor_key": self.actor_key,
            "action_key": self.action_key,
            "llm_actor_key": valid_actor_key(self.llm_actor_key),
            "llm_action_key": valid_action_key(self.llm_action_key),
            "object_key": self.object_key,
            "status": "INSUFFICIENT_INFORMATION" if insufficient else "ok",
            "fingerprint_hash": None
            if insufficient
            else fingerprint_hash(
                self.actor_key, self.action_key, self.object_key, self.event_time
            ),
        }


Relation = str  # SAME_EVENT | RELATED_SUB_EVENT | SAME_TOPIC_DIFFERENT_EVENT | UNRELATED | INSUFFICIENT


def rule_relation(a: FingerprintCard, b: FingerprintCard) -> tuple[Relation, float]:
    """Score two fingerprint cards. Different actors → not SAME."""
    if a.is_insufficient or b.is_insufficient:
        return "INSUFFICIENT", 0.1
    ak_a, ak_b = a.actor_key, b.actor_key
    act_a, act_b = a.action_key, b.action_key
    if not act_a or not act_b or not ak_a or not ak_b:
        return "INSUFFICIENT", 0.2
    if act_a != act_b:
        return "UNRELATED", 0.1

    ta, basis_a = a.match_time
    tb, basis_b = b.match_time
    if ta and tb:
        t1 = ta if ta.tzinfo else ta.replace(tzinfo=timezone.utc)
        t2 = tb if tb.tzinfo else tb.replace(tzinfo=timezone.utc)
        if abs(t1 - t2) > TIME_WINDOW:
            return "SAME_TOPIC_DIFFERENT_EVENT", 0.25
        # record fallback basis on cards for downstream evidence (non-mutating soft note)
        if basis_a == "published_at_fallback" or basis_b == "published_at_fallback":
            a.evidence.setdefault("time_basis", basis_a or "unknown")
            b.evidence.setdefault("time_basis", basis_b or "unknown")

    ov = object_overlap(a.object_key, b.object_key)
    if ak_a and ak_b and ak_a != ak_b:
        # same action/object window but different actors → related/sub at best
        if ov >= 0.4:
            return "RELATED_SUB_EVENT", 0.4 + 0.2 * ov
        return "SAME_TOPIC_DIFFERENT_EVENT", 0.3

    score = 0.35  # shared action
    score += 0.45 * ov
    if ak_a and ak_b and ak_a == ak_b:
        score += 0.2
    elif not ak_a or not ak_b:
        score += 0.05

    if score >= SAME_THRESHOLD:
        return "SAME_EVENT", score
    if AMBIGUOUS_LOW <= score < AMBIGUOUS_HIGH:
        return "INSUFFICIENT", score  # ambiguous → caller may LLM-judge
    if ov >= 0.25:
        return "RELATED_SUB_EVENT", score
    return "SAME_TOPIC_DIFFERENT_EVENT", score


def llm_relation_judge(a: FingerprintCard, b: FingerprintCard) -> Relation | None:
    """Optional LLM judge for ambiguous pairs. Returns None if unavailable."""
    try:
        from gni.core.config import get_settings

        settings = get_settings()
        key = getattr(settings, "deepseek_api_key", None) or getattr(
            settings, "DEEPSEEK_API_KEY", None
        )
        if not key:
            # env fallback
            import os

            key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("GNI_DEEPSEEK_API_KEY")
        if not key:
            return None
    except Exception:
        return None

    # Keep MVP lean: if key present but no client wired, skip rather than fail rebuild
    try:
        import json
        import urllib.request

        prompt = (
            "Compare two event fingerprints. Reply JSON only: "
            '{"relation":"SAME_EVENT|RELATED_SUB_EVENT|SAME_TOPIC_DIFFERENT_EVENT|UNRELATED|INSUFFICIENT"}\n'
            f"A: {json.dumps(a.to_fingerprint_dict(), ensure_ascii=False)}\n"
            f"B: {json.dumps(b.to_fingerprint_dict(), ensure_ascii=False)}"
        )
        body = json.dumps(
            {
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            "https://api.deepseek.com/chat/completions",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        text = payload["choices"][0]["message"]["content"]
        m = re.search(r"\{[^}]+\}", text)
        if not m:
            return None
        rel = json.loads(m.group())["relation"]
        allowed = {
            "SAME_EVENT",
            "RELATED_SUB_EVENT",
            "SAME_TOPIC_DIFFERENT_EVENT",
            "UNRELATED",
            "INSUFFICIENT",
        }
        return rel if rel in allowed else None
    except Exception:
        return None


def resolve_relation(a: FingerprintCard, b: FingerprintCard, *, use_llm: bool = True) -> tuple[Relation, float]:
    rel, score = rule_relation(a, b)
    if rel == "INSUFFICIENT" and AMBIGUOUS_LOW <= score < AMBIGUOUS_HIGH and use_llm:
        judged = llm_relation_judge(a, b)
        if judged:
            return judged, score
    return rel, score

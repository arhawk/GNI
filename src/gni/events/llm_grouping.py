"""Daily batch LLM grouping of fingerprint cards into proto-events.

One LLM call per Shanghai calendar day (split into chunks if a day is very large) receives the
cards of that day and returns groups of card ids. The response is validated strictly:

- every id must be one of the ids we sent (unknown id -> whole batch rejected);
- every card may appear in at most one group (duplicate -> whole batch rejected);
- cards not placed in any group become singleton clusters (insufficient cards are dropped,
  matching the rule-based path).

Any failure (no API key, budget exhausted, HTTP error, invalid JSON, failed validation) falls
back to the rule-based `cluster_fingerprints` for that day, so the pipeline never stalls on the LLM.
Responses are cached on disk keyed by the exact prompt, so re-running a day costs nothing.

Known limitation: grouping is per calendar day (by published_at, Asia/Shanghai). A story that
continues across days is grouped separately on each day and can yield one event per day.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections import defaultdict
from collections.abc import Callable, Sequence
from datetime import timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from gni.events.fingerprint import FingerprintCard
from gni.events.match import FingerprintCluster, cluster_fingerprints

logger = logging.getLogger(__name__)

GROUPING_PROMPT_VERSION = "event_grouping_v1.0"
MAX_CARDS_PER_CALL = 120
GROUPING_MAX_TOKENS = 3000
CACHE_DIR = Path(__file__).resolve().parents[3] / "data" / "event_grouping_cache"
SHANGHAI = ZoneInfo("Asia/Shanghai")

SYSTEM_PROMPT = (
    "You group news event cards into real-world events. Two cards belong to the same group only if they "
    "describe the same specific occurrence: same actor(s), same action, and same object/subject. Sharing a "
    "broad topic (e.g. 'trade', 'Taiwan', 'tariffs') is NOT enough. When unsure, leave the card out. "
    "Return ONLY JSON."
)

CallFn = Callable[[str], "dict[str, Any] | None"]


def _card_line(idx: int, card: FingerprintCard) -> str:
    day = card.published_at.astimezone(SHANGHAI).date().isoformat() if card.published_at else "unknown"
    obj = (card.object or "-")[:120]
    summary = (card.summary or "-")[:160]
    loc = card.location_label or "-"
    return (
        f"[c{idx}] date={day} | actor={card.actor or '-'} | action={card.action or '-'} | "
        f"object={obj} | location={loc} | summary={summary}"
    )


def build_grouping_prompt(cards: Sequence[FingerprintCard]) -> str:
    """Prompt listing every card with a short id (c0, c1, ...). Ids are positional within the call."""
    lines = "\n".join(_card_line(i, c) for i, c in enumerate(cards))
    return (
        "Group the event cards below by real-world event.\n"
        "Rules: a card id may appear in at most one group. Omit cards that match no other card. "
        "Do not invent ids.\n"
        'Reply with JSON only, shaped as {"groups": [{"title": "<short event title>", "card_ids": ["c0", "c3"]}]}. '
        "Only include groups with at least 2 cards.\n\n"
        f"Cards:\n{lines}"
    )


def parse_grouping_response(payload: Any, card_count: int) -> list[list[int]] | None:
    """Validate an LLM grouping payload. Returns groups as card indexes, or None if rejected."""
    if not isinstance(payload, dict):
        return None
    groups = payload.get("groups")
    if not isinstance(groups, list):
        return None
    valid_ids = {f"c{i}" for i in range(card_count)}
    seen: set[str] = set()
    out: list[list[int]] = []
    for group in groups:
        if not isinstance(group, dict):
            return None
        raw_ids = group.get("card_ids")
        if not isinstance(raw_ids, list):
            return None
        idxs: list[int] = []
        for raw in raw_ids:
            cid = str(raw).strip()
            if cid not in valid_ids:
                logger.warning("event grouping: unknown card id %r rejected", cid)
                return None
            if cid in seen:
                logger.warning("event grouping: card id %r assigned twice; batch rejected", cid)
                return None
            seen.add(cid)
            idxs.append(int(cid[1:]))
        if len(idxs) >= 2:
            out.append(idxs)
    return out


def _representative_first(members: list[FingerprintCard]) -> list[FingerprintCard]:
    """Deterministic order: fully keyed cards first, then higher confidence, then article id."""
    return sorted(
        members,
        key=lambda c: (not (c.actor_key and c.action_key), -(c.confidence or 0.0), c.article_id),
    )


def group_cards_with_llm(cards: Sequence[FingerprintCard], *, call: CallFn) -> list[FingerprintCluster] | None:
    """Cluster one day's cards via LLM. Returns None when any chunk fails (caller falls back)."""
    clusters: list[FingerprintCluster] = []
    for start in range(0, len(cards), MAX_CARDS_PER_CALL):
        chunk = list(cards[start : start + MAX_CARDS_PER_CALL])
        payload = call(build_grouping_prompt(chunk))
        groups = parse_grouping_response(payload, len(chunk)) if payload is not None else None
        if groups is None:
            return None
        assigned: set[int] = set()
        for idxs in groups:
            assigned.update(idxs)
            clusters.append(FingerprintCluster(cards=_representative_first([chunk[i] for i in idxs])))
        for i, card in enumerate(chunk):
            if i not in assigned and not card.is_insufficient:
                clusters.append(FingerprintCluster(cards=[card]))
    return clusters


def _day_key(card: FingerprintCard) -> str:
    if card.published_at is None:
        return "unknown"
    ts = card.published_at if card.published_at.tzinfo else card.published_at.replace(tzinfo=timezone.utc)
    return ts.astimezone(SHANGHAI).date().isoformat()


def cluster_cards_daily(
    cards: Sequence[FingerprintCard],
    *,
    call: CallFn | None,
    use_llm: bool = True,
) -> tuple[list[FingerprintCluster], dict[str, int]]:
    """Group cards per Shanghai day with LLM; per-day rule-based fallback when LLM is unavailable/invalid.

    `call=None` runs the legacy global rule clustering (no per-day split, no LLM calls), so the
    rule path is unchanged. Note: with LLM grouping, events are formed within a single day, so a
    story spanning several days can be split across days (see module docstring).
    """
    by_day: dict[str, list[FingerprintCard]] = defaultdict(list)
    for card in cards:
        by_day[_day_key(card)].append(card)

    stats = {"days": len(by_day), "llm_days": 0, "rule_fallback_days": 0}
    if call is None:
        stats["rule_fallback_days"] = len(by_day)
        return cluster_fingerprints(cards, use_llm=use_llm), stats

    clusters: list[FingerprintCluster] = []
    for day in sorted(by_day):
        day_cards = by_day[day]
        grouped = group_cards_with_llm(day_cards, call=call) if call is not None else None
        if grouped is None:
            stats["rule_fallback_days"] += 1
            clusters.extend(cluster_fingerprints(day_cards, use_llm=use_llm))
        else:
            stats["llm_days"] += 1
            clusters.extend(grouped)
    return clusters, stats


def make_cached_llm_call(
    *,
    provider: Any,
    model: str | None,
    cache_dir: Path = CACHE_DIR,
) -> CallFn:
    """Wrap a DeepSeek provider's `generate_json` with an on-disk cache keyed by prompt text."""

    def call(prompt: str) -> dict[str, Any] | None:
        key = hashlib.sha256(
            f"{GROUPING_PROMPT_VERSION}|{model or ''}|{SYSTEM_PROMPT}|{prompt}".encode()
        ).hexdigest()
        path = cache_dir / f"{key}.json"
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                logger.warning("event grouping: corrupt cache file %s; refetching", path.name)
        try:
            result = provider.generate_json(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=prompt,
                model=model,
                temperature=0.0,
                max_tokens=GROUPING_MAX_TOKENS,
            )
        except Exception:  # any provider failure means fallback for this day
            logger.exception("event grouping: LLM call failed; falling back to rules for this day")
            return None
        parsed = result.parsed if isinstance(result.parsed, dict) else None
        if parsed is not None:
            cache_dir.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(parsed, ensure_ascii=False), encoding="utf-8")
        return parsed

    return call

"""Cluster fingerprint cards into proto-events via rule match (+ optional LLM)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from gni.events.fingerprint import FingerprintCard, fingerprint_hash, resolve_relation


@dataclass
class FingerprintCluster:
    cards: list[FingerprintCard] = field(default_factory=list)

    @property
    def article_ids(self) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for c in self.cards:
            if c.article_id not in seen:
                seen.add(c.article_id)
                out.append(c.article_id)
        return out

    @property
    def title(self) -> str:
        best = max(self.cards, key=lambda c: c.confidence)
        return (best.summary or best.object or "Untitled event")[:280]

    @property
    def actor_key(self) -> str | None:
        return self.cards[0].actor_key

    @property
    def action_key(self) -> str | None:
        return self.cards[0].action_key

    @property
    def object_key(self) -> str | None:
        return self.cards[0].object_key

    @property
    def event_time(self) -> datetime | None:
        """True event/announce time only — never fill from published_at."""
        times = [c.event_time for c in self.cards if c.event_time]
        return min(times) if times else None

    @property
    def window_start(self) -> datetime | None:
        """Article coverage window; may use published_at for span only."""
        times: list[datetime] = []
        for c in self.cards:
            t, _ = c.match_time
            if t:
                times.append(t)
        return min(times) if times else None

    @property
    def window_end(self) -> datetime | None:
        times: list[datetime] = []
        for c in self.cards:
            t, _ = c.match_time
            if t:
                times.append(t)
        return max(times) if times else None

    @property
    def location_label(self) -> str | None:
        for c in self.cards:
            if c.location_label:
                return c.location_label
        return None

    @property
    def location_country_id(self) -> str | None:
        for c in self.cards:
            if c.location_country_id:
                return c.location_country_id
        return None

    @property
    def importance_score(self) -> float:
        n = len(self.article_ids)
        conf = sum(c.confidence for c in self.cards) / max(len(self.cards), 1)
        return round(min(1.0, 0.35 + 0.1 * n + 0.3 * conf), 4)

    @property
    def fingerprint_hash(self) -> str:
        return fingerprint_hash(
            self.actor_key, self.action_key, self.object_key, self.event_time
        )

    @property
    def high_confidence(self) -> bool:
        return self.importance_score >= 0.75 and len(self.article_ids) >= 2


def _is_false_merge_pair(a: FingerprintCard, b: FingerprintCard) -> bool:
    """Reject keyword/country-only false merges when explicit actor or action diverge sharply."""
    if a.actor_key and b.actor_key and a.actor_key != b.actor_key:
        # Different primary actors cannot be force-merged unless they share strong object overlap
        toks_a = set((a.object_key or "").split())
        toks_b = set((b.object_key or "").split())
        overlap = len(toks_a & toks_b) / max(len(toks_a | toks_b), 1)
        if overlap < 0.5:
            return True
    if a.action_key and b.action_key and a.action_key != b.action_key:
        toks_a = set((a.object_key or "").split())
        toks_b = set((b.object_key or "").split())
        overlap = len(toks_a & toks_b) / max(len(toks_a | toks_b), 1)
        if overlap < 0.6:
            return True
    return False


def cluster_fingerprints(
    cards: list[FingerprintCard],
    *,
    use_llm: bool = True,
) -> list[FingerprintCluster]:
    """Greedy SAME_EVENT clustering with anti-false-merge guard. Skip INSUFFICIENT cards."""
    clusters: list[FingerprintCluster] = []
    for card in cards:
        if card.is_insufficient:
            continue
        placed = False
        for cl in clusters:
            if _is_false_merge_pair(card, cl.cards[0]):
                continue
            # compare against cluster representative
            rel, _score = resolve_relation(card, cl.cards[0], use_llm=use_llm)
            if rel == "SAME_EVENT":
                cl.cards.append(card)
                placed = True
                break
        if not placed:
            clusters.append(FingerprintCluster(cards=[card]))
    # sort by importance
    clusters.sort(key=lambda c: -c.importance_score)
    return clusters


def cluster_stats(clusters: list[FingerprintCluster]) -> dict[str, Any]:
    return {
        "clusters": len(clusters),
        "articles": len({aid for c in clusters for aid in c.article_ids}),
        "multi_article": sum(1 for c in clusters if len(c.article_ids) >= 2),
    }

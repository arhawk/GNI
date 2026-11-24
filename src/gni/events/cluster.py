"""Rule-based proto-Event clustering (P1-F major-news candidates)."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

STOP = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with", "as", "by",
    "at", "from", "is", "are", "was", "be", "after", "over", "new", "says", "say",
}


def _tokens(title: str | None) -> set[str]:
    words = re.findall(r"[a-z0-9\u4e00-\u9fff\u0400-\u04ff]{2,}", (title or "").casefold())
    return {w for w in words if w not in STOP}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


@dataclass
class ArticleSeed:
    id: str
    title: str | None
    source_id: str
    country_id: str | None
    published_at: datetime | None
    china_relevance_level: str | None
    frame_primary: str | None
    topic_primary: str | None
    sentiment_label: str | None


@dataclass
class ProtoCluster:
    title: str
    article_ids: list[str] = field(default_factory=list)
    country_ids: set[str] = field(default_factory=set)
    source_ids: set[str] = field(default_factory=set)
    frames: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    window_start: datetime | None = None
    window_end: datetime | None = None
    importance_score: float = 0.0
    tokens: set[str] = field(default_factory=set)


def cluster_articles(
    seeds: list[ArticleSeed],
    *,
    similarity: float = 0.35,
    max_gap_hours: int = 72,
) -> list[ProtoCluster]:
    """Greedy title-similarity clustering within a time gap. One cluster = one proto-Event."""
    ordered = sorted(
        seeds,
        key=lambda s: s.published_at or datetime.min.replace(tzinfo=timezone.utc),
    )
    clusters: list[ProtoCluster] = []

    for seed in ordered:
        toks = _tokens(seed.title)
        t = seed.published_at or datetime.now(timezone.utc)
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        placed = False
        for cl in clusters:
            if not cl.tokens:
                continue
            end = cl.window_end or cl.window_start or t
            if abs((t - end).total_seconds()) > max_gap_hours * 3600:
                continue
            if jaccard(toks, cl.tokens) >= similarity:
                cl.article_ids.append(seed.id)
                if seed.country_id:
                    cl.country_ids.add(seed.country_id)
                cl.source_ids.add(seed.source_id)
                if seed.frame_primary:
                    cl.frames.append(seed.frame_primary)
                if seed.topic_primary:
                    cl.topics.append(seed.topic_primary)
                cl.tokens |= toks
                cl.window_end = max(end, t)
                if cl.window_start is None or t < cl.window_start:
                    cl.window_start = t
                placed = True
                break
        if not placed:
            clusters.append(
                ProtoCluster(
                    title=(seed.title or "Untitled event")[:240],
                    article_ids=[seed.id],
                    country_ids={seed.country_id} if seed.country_id else set(),
                    source_ids={seed.source_id},
                    frames=[seed.frame_primary] if seed.frame_primary else [],
                    topics=[seed.topic_primary] if seed.topic_primary else [],
                    window_start=t,
                    window_end=t,
                    tokens=toks,
                )
            )

    for cl in clusters:
        # Importance: more articles + more reporting countries
        cl.importance_score = round(
            min(1.0, 0.25 * len(cl.article_ids) + 0.2 * len(cl.country_ids) + 0.1 * len(cl.source_ids)),
            4,
        )
    # Prefer multi-article clusters for "major" list; keep singles with china titles too
    clusters.sort(key=lambda c: (-c.importance_score, -(len(c.article_ids))))
    return clusters


def dominant(items: list[str]) -> str | None:
    if not items:
        return None
    counts: dict[str, int] = defaultdict(int)
    for i in items:
        counts[i] += 1
    return max(counts.items(), key=lambda x: x[1])[0]

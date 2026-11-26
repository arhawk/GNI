"""Deterministic cross-article Narrative Aggregation (Phase 4d).

Key invariants:
- Distinguishes SAME TOPIC from SAME NARRATIVE: never clusters solely on shared topic_id;
  requires matching canonical_frame AND normalized claim token overlap.
- Retains both supporting_evidence AND counter_evidence (e.g. attribution=='refute' or opposing tone).
- Never infers coordinated propagation from narrative similarity alone.
- Reuses existing NarrativeCluster and EventNarrativeEvidence ORM tables (0 new DB tables).
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from gni.core.contracts import EvidenceSpanRef, NarrativeIntelligenceContract
from gni.infrastructure.models import EventNarrativeEvidence, NarrativeCluster

_STOPWORDS = frozenset(
    {
        "the",
        "and",
        "for",
        "that",
        "with",
        "from",
        "this",
        "into",
        "over",
        "about",
        "china",
        "chinese",
        "beijing",
        "said",
        "says",
        "will",
        "have",
        "has",
        "are",
        "was",
        "were",
    }
)


@dataclass
class ArticleNarrativeInput:
    article_id: str
    country_id: str | None
    published_at: datetime | None
    frame: str
    claim: str
    attribution: str = "mention"  # mention|quote|support|refute|unclear
    tone: str = "unclear"  # positive|neutral|negative|mixed|unclear
    quote: str | None = None
    article_version_id: str | None = None
    topic_ids: tuple[str, ...] = ()


def _claim_tokens(text: str) -> set[str]:
    toks = re.findall(r"[a-z0-9]{3,}|[\u4e00-\u9fff]{2,}", (text or "").casefold())
    return {t for t in toks if t not in _STOPWORDS}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def cluster_narratives(
    items: Iterable[ArticleNarrativeInput],
    *,
    min_claim_jaccard: float = 0.25,
) -> list[NarrativeIntelligenceContract]:
    """Cluster article-level narratives by (canonical_frame, claim similarity).

    Two articles sharing a topic_id with different frames or non-overlapping claims
    remain in separate clusters. Opposing attributions ('refute') on the same claim
    are retained as counter_evidence rather than discarded.
    """
    groups: list[list[ArticleNarrativeInput]] = []
    group_tokens: list[set[str]] = []

    for item in items:
        frame = (item.frame or "").strip().lower()
        claim = (item.claim or "").strip()
        if not frame or not claim:
            continue
        toks = _claim_tokens(claim)
        placed = False
        for idx, grp in enumerate(groups):
            if grp[0].frame.strip().lower() != frame:
                continue
            if _jaccard(toks, group_tokens[idx]) >= min_claim_jaccard:
                grp.append(item)
                group_tokens[idx] = group_tokens[idx] | toks
                placed = True
                break
        if not placed:
            groups.append([item])
            group_tokens.append(set(toks))

    contracts: list[NarrativeIntelligenceContract] = []
    for idx, grp in enumerate(groups):
        frame = grp[0].frame.strip().lower()
        # Pick representative claim from non-refute entries if available
        non_refute = [x for x in grp if x.attribution != "refute"]
        rep = non_refute[0] if non_refute else grp[0]

        tones = Counter(x.tone for x in non_refute if x.tone in {"positive", "negative", "neutral"})
        dominant_tone = tones.most_common(1)[0][0] if tones else None

        supporting: list[EvidenceSpanRef] = []
        counter: list[EvidenceSpanRef] = []
        for j, x in enumerate(grp):
            ev = EvidenceSpanRef(
                evidence_id=f"nar_{idx}_ev_{j}",
                article_id=x.article_id,
                article_version_id=x.article_version_id,
                text_span=(x.quote or x.claim)[:400],
                evidence_type="narrative",
                supports_claim=rep.claim[:240],
                analysis_task="narrative_aggregation",
                validated=bool(x.quote),
            )
            is_opposing = (
                x.attribution == "refute"
                or (dominant_tone == "negative" and x.tone == "positive")
                or (dominant_tone == "positive" and x.tone == "negative")
            )
            if is_opposing:
                counter.append(ev)
            else:
                supporting.append(ev)

        article_ids = sorted({x.article_id for x in grp})
        countries = sorted({(x.country_id or "").strip().upper() for x in grp if (x.country_id or "").strip()})
        times = [x.published_at for x in grp if x.published_at is not None]
        trend = "growing" if len(article_ids) >= 3 else "emerging"
        conf = round(min(0.9, 0.45 + 0.1 * len(article_ids) + (0.1 if len(countries) >= 2 else 0.0)), 4)

        contracts.append(
            NarrativeIntelligenceContract(
                narrative_cluster_id=f"nc_{frame}_{idx}",
                canonical_frame=frame,
                canonical_claim=rep.claim[:280],
                related_articles=article_ids,
                related_countries=countries,
                supporting_evidence=supporting,
                counter_evidence=counter,
                first_observed_at=min(times) if times else None,
                last_observed_at=max(times) if times else None,
                trend_status=trend,  # type: ignore[arg-type]
                confidence=conf,
                record_source="model",
            )
        )
    return contracts


def persist_event_narratives(
    session: Session,
    *,
    event_id: str,
    clusters: list[NarrativeIntelligenceContract],
) -> dict[str, int]:
    """Persist clustered narratives for an Event into NarrativeCluster & EventNarrativeEvidence."""
    existing = list(
        session.scalars(select(NarrativeCluster).where(NarrativeCluster.event_id == event_id)).all()
    )
    existing_ids = [c.id for c in existing]
    if existing_ids:
        for ev_row in session.scalars(
            select(EventNarrativeEvidence).where(
                EventNarrativeEvidence.narrative_cluster_id.in_(existing_ids)
            )
        ).all():
            session.delete(ev_row)
        for c in existing:
            session.delete(c)
        session.flush()

    written_clusters = 0
    written_evidence = 0
    for cl in clusters:
        cid = str(uuid4())
        session.add(
            NarrativeCluster(
                id=cid,
                event_id=event_id,
                label=cl.canonical_claim[:256],
                frame_id=cl.canonical_frame[:64],
                summary=(
                    f"articles={len(cl.related_articles)}, countries={','.join(cl.related_countries)}, "
                    f"supporting={len(cl.supporting_evidence)}, counter={len(cl.counter_evidence)}"
                ),
            )
        )
        written_clusters += 1
        for ev in cl.supporting_evidence + cl.counter_evidence:
            if not ev.article_id:
                continue
            session.add(
                EventNarrativeEvidence(
                    id=str(uuid4()),
                    narrative_cluster_id=cid,
                    article_id=ev.article_id,
                    quote=ev.text_span[:500],
                )
            )
            written_evidence += 1
    session.flush()
    return {"clusters_written": written_clusters, "evidence_written": written_evidence}

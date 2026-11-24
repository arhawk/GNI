"""Extract article event candidates (heuristic + optional LLM)."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from uuid import uuid4

# datetime used for candidate.event_time parse in load_latest_cards

from sqlalchemy import select
from sqlalchemy.orm import Session

from gni.events.fingerprint import FingerprintCard, normalize_action, tokenize
from gni.events.geo import guess_location_from_text
from gni.infrastructure.models import Article, ArticleAnalysis, ArticleEventCandidate
from gni.metrics.definitions import CHINA_INCLUDE_LEVELS
from gni.metrics.service import _latest_analyses

# Patterns: "X announces Y", "X signs Y with Z", Chinese titles
_EN_PATTERNS = [
    re.compile(
        r"(?P<actor>[A-Z][\w\.\-]+(?:\s+[A-Z][\w\.\-]+){0,3})\s+"
        r"(?P<action>announces?|unveils?|signs?|launches?|approves?|sanctions?|"
        r"warns?|accuses?|meets?|visits?|invests?|responds?)\s+"
        r"(?:to\s+|on\s+|against\s+)?(?P<object>.{3,80})",
        re.I,
    ),
    re.compile(
        r"(?P<object>.{3,60})\s*:\s*(?P<actor>[A-Z][\w\.\-]+(?:\s+[A-Z][\w\.\-]+){0,2})\s+"
        r"(?P<action>announces?|unveils?|signs?)",
        re.I,
    ),
]


def _china_spans_from_analysis(structured: dict[str, Any] | None) -> list[str]:
    if not structured:
        return []
    spans = structured.get("china_spans") or structured.get("relevance_spans") or []
    out: list[str] = []
    for s in spans:
        if isinstance(s, str):
            out.append(s)
        elif isinstance(s, dict):
            q = s.get("quote") or s.get("text") or s.get("span")
            if q:
                out.append(str(q))
    return out[:5]


def heuristic_extract(
    *,
    article_id: str,
    title: str,
    published_at: datetime | None,
    spans: list[str] | None = None,
    analysis_id: str | None = None,
    article_version_id: str | None = None,
) -> list[FingerprintCard]:
    """Weak candidates from title (+ china spans). One card per matched pattern, else title fallback."""
    text = title or ""
    for span in spans or []:
        if span and span not in text:
            text = f"{text}. {span}"

    cards: list[FingerprintCard] = []
    for pat in _EN_PATTERNS:
        m = pat.search(title or "")
        if not m:
            continue
        actor = (m.groupdict().get("actor") or "").strip(" .,;:")
        action = (m.groupdict().get("action") or "").strip()
        obj = (m.groupdict().get("object") or "").strip(" .,;:")
        loc_label, loc_cid = guess_location_from_text(text)
        cards.append(
            FingerprintCard(
                article_id=article_id,
                actor=actor or None,
                action=action or None,
                object=obj or None,
                event_type=None,
                location_label=loc_label,
                location_country_id=loc_cid,
                summary=(title or "")[:280],
                published_at=published_at,
                confidence=0.55,
                evidence={"title": title, "match": m.group(0)[:200]},
                analysis_id=analysis_id,
                article_version_id=article_version_id,
            )
        )
        break  # first pattern wins for MVP

    if not cards:
        # Fallback: China + dominant action verb from title, object = remaining tokens
        action_key = None
        for tok in re.findall(r"[A-Za-z\u4e00-\u9fff]+", title or ""):
            ak = normalize_action(tok)
            if ak and ak != "UNKNOWN" and tok.lower() in {
                "announce",
                "announces",
                "announced",
                "unveil",
                "unveils",
                "sign",
                "signs",
                "signed",
                "sanction",
                "sanctions",
                "launch",
                "launches",
                "visit",
                "visits",
                "meet",
                "meets",
                "warn",
                "warns",
                "approve",
                "approves",
                "invest",
                "invests",
                "accuse",
                "accuses",
                "respond",
                "responds",
                "宣布",
                "签署",
                "制裁",
                "访问",
                "会晤",
            }:
                action_key = tok
                break
        toks = tokenize(title)
        obj_toks = sorted(toks - {"china", "chinese", "beijing"})[:8]
        loc_label, loc_cid = guess_location_from_text(text)
        cards.append(
            FingerprintCard(
                article_id=article_id,
                actor="China" if "china" in (title or "").lower() or "chinese" in (title or "").lower() else None,
                action=action_key,
                object=" ".join(obj_toks) if obj_toks else (title or "")[:120],
                location_label=loc_label,
                location_country_id=loc_cid,
                summary=(title or "")[:280],
                published_at=published_at,
                confidence=0.35,
                evidence={"title": title, "mode": "fallback"},
                analysis_id=analysis_id,
                article_version_id=article_version_id,
            )
        )
    return cards


def persist_candidates(session: Session, cards: list[FingerprintCard]) -> int:
    n = 0
    for card in cards:
        session.add(
            ArticleEventCandidate(
                id=str(uuid4()),
                article_id=card.article_id,
                article_version_id=card.article_version_id,
                analysis_id=card.analysis_id,
                fingerprint=card.to_fingerprint_dict(),
                evidence=card.evidence,
                schema_version="event_fingerprint_v0.1",
                prompt_version="heuristic_v0.1",
                confidence=card.confidence,
            )
        )
        n += 1
    return n


def extract_for_articles(
    session: Session,
    *,
    article_ids: list[str] | None = None,
    limit: int = 500,
) -> dict[str, Any]:
    """Extract and append candidates for China-set articles."""
    q = select(Article).where(
        Article.exclude_from_metrics.is_(False),
        Article.china_relevance_level.in_(list(CHINA_INCLUDE_LEVELS)),
    )
    if article_ids:
        q = q.where(Article.id.in_(article_ids))
    articles = list(session.scalars(q.limit(limit)).all())
    analyses = _latest_analyses(session, [a.id for a in articles])
    written = 0
    cards_out: list[FingerprintCard] = []
    for a in articles:
        analysis: ArticleAnalysis | None = analyses.get(a.id)
        structured = (analysis.structured_result if analysis else None) or {}
        spans = _china_spans_from_analysis(structured)
        cards = heuristic_extract(
            article_id=a.id,
            title=a.title or "",
            published_at=a.published_at or a.first_seen_at,
            spans=spans,
            analysis_id=analysis.id if analysis else None,
        )
        written += persist_candidates(session, cards)
        cards_out.extend(cards)
    session.flush()
    return {"articles": len(articles), "candidates_written": written, "cards": cards_out}


def load_latest_cards(session: Session, *, limit_articles: int = 500) -> list[FingerprintCard]:
    """Rebuild cards from latest candidate row per article (or extract on the fly)."""
    articles = list(
        session.scalars(
            select(Article)
            .where(
                Article.exclude_from_metrics.is_(False),
                Article.china_relevance_level.in_(list(CHINA_INCLUDE_LEVELS)),
            )
            .limit(limit_articles)
        ).all()
    )
    analyses = _latest_analyses(session, [a.id for a in articles])
    cards: list[FingerprintCard] = []
    for a in articles:
        rows = list(
            session.scalars(
                select(ArticleEventCandidate)
                .where(ArticleEventCandidate.article_id == a.id)
                .order_by(ArticleEventCandidate.created_at.desc())
                .limit(3)
            ).all()
        )
        if rows:
            for row in rows:
                fp = row.fingerprint or {}
                loc = fp.get("location") or {}
                et = fp.get("event_time")
                event_time = None
                if isinstance(et, str):
                    try:
                        event_time = datetime.fromisoformat(et.replace("Z", "+00:00"))
                    except ValueError:
                        event_time = None
                cards.append(
                    FingerprintCard(
                        article_id=a.id,
                        actor=fp.get("actor"),
                        action=fp.get("action"),
                        object=fp.get("object"),
                        target=fp.get("target"),
                        event_type=fp.get("event_type"),
                        location_label=loc.get("label"),
                        location_country_id=loc.get("country_id"),
                        qualifiers=fp.get("qualifiers") or {},
                        summary=fp.get("summary"),
                        event_time=event_time,
                        published_at=a.published_at or a.first_seen_at,
                        confidence=row.confidence or 0.5,
                        evidence=row.evidence or {},
                        analysis_id=row.analysis_id,
                        article_version_id=row.article_version_id,
                    )
                )
        else:
            analysis = analyses.get(a.id)
            structured = (analysis.structured_result if analysis else None) or {}
            spans = _china_spans_from_analysis(structured)
            cards.extend(
                heuristic_extract(
                    article_id=a.id,
                    title=a.title or "",
                    published_at=a.published_at or a.first_seen_at,
                    spans=spans,
                    analysis_id=analysis.id if analysis else None,
                )
            )
    return cards

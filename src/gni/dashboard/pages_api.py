"""JSON payloads for Trends / Countries / System pages."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from gni.infrastructure.models import Article, Country, Source, SourceHealth
from gni.metrics.definitions import CHINA_INCLUDE_LEVELS
from gni.metrics.service import _latest_analyses


def _aware(t: datetime | None) -> datetime | None:
    if t is None:
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def _day_key(t: datetime) -> str:
    return t.astimezone(timezone.utc).strftime("%Y-%m-%d")


def trends_payload(
    session: Session,
    *,
    days: int = 30,
    country_id: str | None = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)
    sources = {s.id: s for s in session.scalars(select(Source)).all()}
    q = select(Article).where(
        Article.exclude_from_metrics.is_(False),
        Article.china_relevance_level.in_(list(CHINA_INCLUDE_LEVELS)),
    )
    articles = list(session.scalars(q).all())
    if country_id:
        articles = [
            a
            for a in articles
            if (sources.get(a.source_id).country_id if a.source_id in sources else None) == country_id
        ]
    windowed = []
    for a in articles:
        t = _aware(a.published_at or a.first_seen_at)
        if t and start <= t <= now:
            windowed.append((a, t))

    by_day: Counter[str] = Counter()
    sent_by_day: dict[str, Counter[str]] = defaultdict(Counter)
    topics: Counter[str] = Counter()
    analyses = _latest_analyses(session, [a.id for a, _ in windowed])
    for a, t in windowed:
        dk = _day_key(t)
        by_day[dk] += 1
        structured = (analyses[a.id].structured_result if a.id in analyses else None) or {}
        raw_sent = structured.get("sentiment")
        if isinstance(raw_sent, dict):
            label = str(raw_sent.get("label") or "unknown").lower()
        elif isinstance(raw_sent, str) and raw_sent.strip():
            label = raw_sent.strip().lower()
        else:
            label = "unknown"
        sent_by_day[dk][label] += 1
        tp = (structured.get("topics") or {})
        if isinstance(tp, dict) and tp.get("primary"):
            topics[str(tp["primary"])] += 1

    days_sorted = sorted(by_day.keys())
    series = [{"date": d, "china_articles": by_day[d]} for d in days_sorted]
    sentiment_series = [
        {
            "date": d,
            "positive": sent_by_day[d].get("positive", 0),
            "neutral": sent_by_day[d].get("neutral", 0),
            "negative": sent_by_day[d].get("negative", 0),
            "unknown": sent_by_day[d].get("unknown", 0) + sent_by_day[d].get("mixed", 0),
        }
        for d in days_sorted
    ]
    topic_total = sum(topics.values()) or 1
    return {
        "days": days,
        "country_id": country_id,
        "china_article_count": len(windowed),
        "volume_series": series,
        "sentiment_series": sentiment_series,
        "topics_top": [
            {"label": k, "count": v, "share": round(v / topic_total, 4)}
            for k, v in topics.most_common(12)
        ],
        "note": "涉华纳入样本走势；情感与立场分列，此处为情感。",
    }


def countries_list_payload(session: Session) -> dict[str, Any]:
    sources = list(session.scalars(select(Source)).all())
    countries = {c.id: c for c in session.scalars(select(Country)).all()}
    by_c: dict[str, dict[str, Any]] = {}
    for s in sources:
        cid = s.country_id or "UNK"
        blob = by_c.setdefault(
            cid,
            {
                "country_id": cid,
                "name": (countries[cid].name if cid in countries else cid),
                "source_count": 0,
                "active_sources": 0,
            },
        )
        blob["source_count"] += 1
        if s.active_status == "active":
            blob["active_sources"] += 1

    # china article counts (all time light)
    arts = list(
        session.scalars(
            select(Article).where(
                Article.exclude_from_metrics.is_(False),
                Article.china_relevance_level.in_(list(CHINA_INCLUDE_LEVELS)),
            )
        ).all()
    )
    src_map = {s.id: s for s in sources}
    china_counts: Counter[str] = Counter()
    for a in arts:
        src = src_map.get(a.source_id)
        if src and src.country_id:
            china_counts[src.country_id] += 1
    rows = []
    for cid, blob in by_c.items():
        blob["china_article_count"] = china_counts.get(cid, 0)
        rows.append(blob)
    rows.sort(key=lambda x: -x["china_article_count"])
    return {"countries": rows}


def country_detail_payload(session: Session, country_id: str) -> dict[str, Any] | None:
    cid = country_id.upper()
    country = session.get(Country, cid)
    sources = list(session.scalars(select(Source).where(Source.country_id == cid)).all())
    if not country and not sources:
        return None
    src_ids = [s.id for s in sources]
    articles = []
    if src_ids:
        articles = list(
            session.scalars(
                select(Article)
                .where(
                    Article.source_id.in_(src_ids),
                    Article.exclude_from_metrics.is_(False),
                )
                .order_by(Article.published_at.desc())
                .limit(200)
            ).all()
        )
    china = [a for a in articles if (a.china_relevance_level or "") in CHINA_INCLUDE_LEVELS]
    src_by_id = {s.id: s for s in sources}
    analyses = _latest_analyses(session, [a.id for a in china])
    sent: Counter[str] = Counter()
    gov_sent: Counter[str] = Counter()
    stance: Counter[str] = Counter()
    topics: Counter[str] = Counter()
    frames: Counter[str] = Counter()
    for a in china:
        structured = (analyses[a.id].structured_result if a.id in analyses else None) or {}
        src = src_by_id.get(a.source_id)
        lab = ((structured.get("sentiment") or {}).get("label") or "unknown").lower()
        if src and (src.feed_scope or "").upper() == "GOVERNMENT_RELEASES":
            gov_sent[lab] += 1
        else:
            sent[lab] += 1
        from gni.analysis.stance_util import all_stance_labels

        labs = all_stance_labels(structured, media_only=True)
        if labs:
            stance.update(labs)
        else:
            stance["unknown"] += 1
        tp = structured.get("topics") or {}
        fr = structured.get("framing") or {}
        if isinstance(tp, dict) and tp.get("primary"):
            topics[str(tp["primary"])] += 1
        if isinstance(fr, dict) and fr.get("primary"):
            frames[str(fr["primary"])] += 1

    def _bucket(s: Source) -> str:
        scope = (s.feed_scope or "").upper()
        if scope == "GOVERNMENT_RELEASES":
            return "government_comms"
        ownership = (s.ownership_type or "").lower()
        ctrl = (s.government_control_level or "").lower()
        if ownership in {"public", "public_law"} or ctrl == "low":
            return "public_service"
        if ctrl in {"high", "medium"} or ownership in {"government", "state"}:
            return "state_controlled"
        return "other"

    media = []
    for s in sources:
        n = sum(1 for a in china if a.source_id == s.id)
        media.append(
            {
                "source_id": s.id,
                "name": s.name,
                "active_status": s.active_status,
                "china_article_count": n,
                "language": s.language,
                "feed_scope": s.feed_scope,
                "ownership_type": s.ownership_type,
                "government_control_level": s.government_control_level,
                "source_bucket": _bucket(s),
            }
        )
    media.sort(key=lambda x: -x["china_article_count"])

    recent = []
    for a in china[:20]:
        structured = (analyses[a.id].structured_result if a.id in analyses else None) or {}
        recent.append(
            {
                "article_id": a.id,
                "title": a.title,
                "url": a.url,
                "source_id": a.source_id,
                "sentiment": (structured.get("sentiment") or {}).get("label"),
                "published_at": (_aware(a.published_at or a.first_seen_at) or datetime.min.replace(tzinfo=timezone.utc)).isoformat(),
            }
        )

    return {
        "country_id": cid,
        "name": country.name if country else cid,
        "disclaimer": (
            "全球对华监测 · 该国为当前接入国之一；"
            "媒体报道表现 ≠ 国家官方立场或社会民意。来源分区：国家控制 / 公服 / 政府传播。"
        ),
        "media": media,
        "china_article_count": len(china),
        "sentiment_counts": dict(sent),
        "government_sentiment_counts": dict(gov_sent),
        "stance_counts": dict(stance),
        "topics_top": [{"label": k, "count": v} for k, v in topics.most_common(8)],
        "frames_top": [{"label": k, "count": v} for k, v in frames.most_common(8)],
        "recent_articles": recent,
    }


def system_status_payload(session: Session) -> dict[str, Any]:
    sources = list(session.scalars(select(Source)).all())
    health = {h.source_id: h for h in session.scalars(select(SourceHealth)).all()}
    pending = session.scalar(
        select(func.count())
        .select_from(Article)
        .where(
            Article.exclude_from_metrics.is_(False),
            Article.processing_status == "done",
            Article.analysis_status.in_(["pending", "failed"]),
        )
    ) or 0
    total = session.scalar(select(func.count()).select_from(Article)) or 0
    excluded = session.scalar(
        select(func.count()).select_from(Article).where(Article.exclude_from_metrics.is_(True))
    ) or 0
    rows = []
    for s in sources:
        h = health.get(s.id)
        rows.append(
            {
                "source_id": s.id,
                "name": s.name,
                "country_id": s.country_id,
                "active_status": s.active_status,
                "success_count": h.success_count if h else 0,
                "failure_count": h.failure_count if h else 0,
                "last_error": h.error_message if h else None,
                "last_success_at": h.last_success_at.isoformat() if h and h.last_success_at else None,
                "last_failure_at": h.last_failure_at.isoformat() if h and h.last_failure_at else None,
            }
        )
    rows.sort(key=lambda x: (-(x["failure_count"] or 0), x["source_id"]))
    return {
        "totals": {
            "sources": len(sources),
            "active_sources": sum(1 for s in sources if s.active_status == "active"),
            "articles": total,
            "analysis_backlog": pending,
            "excluded": excluded,
        },
        "source_health": rows,
        "notes": [
            "系统页面向运维台账；舆情结论见「异常与预警」情报栏。",
            "源故障与分析积压也会出现在系统运行告警中。",
        ],
    }

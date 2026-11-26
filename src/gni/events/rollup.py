"""Roll article sentiment/stance shares up to events and country China-attitude."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from gni.infrastructure.models import (
    Article,
    CountryChinaAttitudeSnapshot,
    Event,
    EventArticle,
    EventMetricSnapshot,
    Source,
)
from gni.metrics.definitions import CHINA_INCLUDE_LEVELS
from gni.metrics.service import _latest_analyses


def _norm_sentiment(label: str | None) -> str:
    if not label:
        return "unknown"
    s = label.strip().lower()
    if s in {"positive", "pos", "favorable"}:
        return "positive"
    if s in {"negative", "neg", "unfavorable", "critical"}:
        return "negative"
    if s in {"neutral", "neu", "mixed"}:
        return "neutral"
    return "unknown"


def _shares(counter: Counter[str]) -> dict[str, float]:
    total = sum(counter.values()) or 1
    return {k: round(v / total, 4) for k, v in sorted(counter.items())}


def rollup_event_metrics(session: Session, *, event_ids: list[str] | None = None) -> int:
    """Recompute event_metric_snapshots for given events (or all)."""
    q = select(Event)
    if event_ids:
        q = q.where(Event.id.in_(event_ids))
    events = list(session.scalars(q).all())
    sources = {s.id: s for s in session.scalars(select(Source)).all()}
    n = 0
    for event in events:
        links = list(
            session.scalars(select(EventArticle).where(EventArticle.event_id == event.id)).all()
        )
        article_ids = [l.article_id for l in links]
        articles = {
            a.id: a
            for a in session.scalars(select(Article).where(Article.id.in_(article_ids))).all()
        } if article_ids else {}
        analyses = _latest_analyses(session, article_ids)
        sent: Counter[str] = Counter()
        stance: Counter[str] = Counter()
        by_country: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"article_count": 0, "sentiment": Counter(), "stance": Counter()}
        )
        source_ids: set[str] = set()
        country_ids: set[str] = set()
        for aid in article_ids:
            art = articles.get(aid)
            if not art:
                continue
            source_ids.add(art.source_id)
            src = sources.get(art.source_id)
            cid = (src.country_id if src else None) or "UNK"
            country_ids.add(cid)
            structured = (analyses[aid].structured_result if aid in analyses else None) or {}
            from gni.analysis.stance_util import all_stance_labels, primary_stance_label

            sl = _norm_sentiment((structured.get("sentiment") or {}).get("label"))
            # Aggregate all media stances by label; also keep a primary for display compatibility
            st_labels = all_stance_labels(structured, media_only=True)
            if not st_labels:
                st_labels = Counter({primary_stance_label(structured): 1})
            sent[sl] += 1
            stance.update(st_labels)
            by_country[cid]["article_count"] += 1
            by_country[cid]["sentiment"][sl] += 1
            by_country[cid]["stance"].update(st_labels)

        by_country_out = {
            cid: {
                "article_count": blob["article_count"],
                "sentiment_shares": _shares(blob["sentiment"]),
                "stance_shares": _shares(blob["stance"]),
            }
            for cid, blob in by_country.items()
        }
        session.execute(
            delete(EventMetricSnapshot).where(
                EventMetricSnapshot.event_id == event.id,
                EventMetricSnapshot.window == "all",
            )
        )
        session.add(
            EventMetricSnapshot(
                id=str(uuid4()),
                event_id=event.id,
                window="all",
                article_count=len(article_ids),
                source_count=len(source_ids),
                country_count=len(country_ids),
                sentiment_shares=_shares(sent),
                stance_shares=_shares(stance),
                by_country=by_country_out,
            )
        )
        n += 1
    session.flush()
    return n


def rollup_country_china_attitude(
    session: Session,
    *,
    window: str = "30d",
    window_start: datetime | None = None,
    window_end: datetime | None = None,
) -> int:
    """Aggregate China-article sentiment by reporting source country (monitored media sample)."""
    q = select(Article).where(
        Article.exclude_from_metrics.is_(False),
        Article.china_relevance_level.in_(list(CHINA_INCLUDE_LEVELS)),
    )
    if window_start is not None:
        q = q.where(Article.published_at >= window_start)
    if window_end is not None:
        q = q.where(Article.published_at <= window_end)
    articles = list(session.scalars(q).all())
    sources = {s.id: s for s in session.scalars(select(Source)).all()}
    analyses = _latest_analyses(session, [a.id for a in articles])

    buckets: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "positive": 0,
            "neutral": 0,
            "negative": 0,
            "unknown": 0,
            "samples": [],
        }
    )
    for a in articles:
        src = sources.get(a.source_id)
        cid = (src.country_id if src else None) or "UNK"
        structured = (analyses[a.id].structured_result if a.id in analyses else None) or {}
        sent_raw = structured.get("sentiment")
        label = _norm_sentiment(
            sent_raw.get("label") if isinstance(sent_raw, dict) else sent_raw
        )
        buckets[cid][label] = buckets[cid].get(label, 0) + 1
        if len(buckets[cid]["samples"]) < 8:
            buckets[cid]["samples"].append(a.id)

    session.execute(
        delete(CountryChinaAttitudeSnapshot).where(CountryChinaAttitudeSnapshot.window == window)
    )
    n = 0
    for cid, blob in buckets.items():
        counts = {
            "positive": int(blob["positive"]),
            "neutral": int(blob["neutral"]),
            "negative": int(blob["negative"]),
            "unknown": int(blob["unknown"]),
        }
        total = sum(counts.values())
        if total == 0:
            dominant = "none"
        else:
            # ignore unknown for dominant when other signals exist
            ranked = sorted(
                ((k, v) for k, v in counts.items() if k != "unknown" or v == total),
                key=lambda x: -x[1],
            )
            dominant = ranked[0][0] if ranked and ranked[0][1] > 0 else "none"
            if dominant == "unknown" and total > counts["unknown"]:
                dominant = max(
                    (("positive", counts["positive"]), ("neutral", counts["neutral"]), ("negative", counts["negative"])),
                    key=lambda x: x[1],
                )[0]

        session.add(
            CountryChinaAttitudeSnapshot(
                id=str(uuid4()),
                country_id=cid,
                window=window,
                positive_count=counts["positive"],
                neutral_count=counts["neutral"],
                negative_count=counts["negative"],
                unknown_count=counts["unknown"],
                dominant_label=dominant if total else "none",
                sample_article_ids=blob["samples"],
            )
        )
        n += 1
    session.flush()
    return n


def attitude_map_rows(
    session: Session,
    *,
    window: str = "30d",
    all_country_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Build attitude map payloads; countries with no sample are grey / not clickable."""
    from gni.events.geo import centroid

    snaps = {
        s.country_id: s
        for s in session.scalars(
            select(CountryChinaAttitudeSnapshot).where(
                CountryChinaAttitudeSnapshot.window == window
            )
        ).all()
    }
    ids = list(all_country_ids or [])
    if not ids:
        from gni.infrastructure.models import Country

        ids = [c.id for c in session.scalars(select(Country)).all()]
        # ensure snap countries included
        for cid in snaps:
            if cid not in ids:
                ids.append(cid)

    out: list[dict[str, Any]] = []
    for cid in ids:
        c = centroid(cid)
        snap = snaps.get(cid)
        if not snap or (
            snap.positive_count
            + snap.neutral_count
            + snap.negative_count
            + snap.unknown_count
            == 0
        ):
            row = {
                "country_id": cid,
                "label": "none",
                "counts": {"positive": 0, "neutral": 0, "negative": 0, "unknown": 0},
                "clickable": False,
                "layer": "country_china_attitude",
            }
        else:
            row = {
                "country_id": cid,
                "label": snap.dominant_label or "none",
                "counts": {
                    "positive": snap.positive_count,
                    "neutral": snap.neutral_count,
                    "negative": snap.negative_count,
                    "unknown": snap.unknown_count,
                },
                "clickable": True,
                "layer": "country_china_attitude",
            }
        if c:
            row["lat"] = c[0]
            row["lon"] = c[1]
        out.append(row)
    return out


def country_china_attitude_detail(
    session: Session,
    country_id: str,
    *,
    window: str = "30d",
    article_limit: int = 40,
) -> dict[str, Any] | None:
    snap = session.scalar(
        select(CountryChinaAttitudeSnapshot).where(
            CountryChinaAttitudeSnapshot.country_id == country_id,
            CountryChinaAttitudeSnapshot.window == window,
        )
    )
    sample_ids = list((snap.sample_article_ids if snap else None) or [])
    # Expand: fetch more China articles from this country
    sources = list(
        session.scalars(select(Source).where(Source.country_id == country_id)).all()
    )
    source_ids = [s.id for s in sources]
    articles: list[Article] = []
    if source_ids:
        articles = list(
            session.scalars(
                select(Article)
                .where(
                    Article.source_id.in_(source_ids),
                    Article.exclude_from_metrics.is_(False),
                    Article.china_relevance_level.in_(list(CHINA_INCLUDE_LEVELS)),
                )
                .order_by(Article.published_at.desc())
                .limit(article_limit)
            ).all()
        )
    analyses = _latest_analyses(session, [a.id for a in articles])
    src_map = {s.id: s for s in sources}
    article_rows = []
    for a in articles:
        structured = (analyses[a.id].structured_result if a.id in analyses else None) or {}
        article_rows.append(
            {
                "article_id": a.id,
                "title": a.title,
                "url": a.url,
                "source_id": a.source_id,
                "source_name": src_map[a.source_id].name if a.source_id in src_map else a.source_id,
                "sentiment": (structured.get("sentiment") or {}).get("label"),
                "published_at": (a.published_at or a.first_seen_at).isoformat()
                if (a.published_at or a.first_seen_at)
                else None,
            }
        )
    counts = {
        "positive": snap.positive_count if snap else 0,
        "neutral": snap.neutral_count if snap else 0,
        "negative": snap.negative_count if snap else 0,
        "unknown": snap.unknown_count if snap else 0,
    }
    total = sum(counts.values())
    return {
        "country_id": country_id,
        "window": window,
        "label": (snap.dominant_label if snap else "none") if total else "none",
        "counts": counts,
        "clickable": total > 0,
        "disclaimer": "Monitored official/media sample — not the state's official position.",
        "articles": article_rows,
        "sample_article_ids": sample_ids,
    }

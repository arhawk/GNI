"""Daily Intelligence Brief: daily_report_schema_v4 (Global Situation + Intelligence Judgment)."""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from gni.alerts.service import build_alerts_payload
from gni.core.config import get_settings
from gni.events.service import list_events
from gni.infrastructure.models import Article, Event, EventArticle, Source, SourceHealth
from gni.metrics.definitions import (
    CHINA_INCLUDE_LEVELS,
    METHODOLOGY_VERSION,
    METRIC_DEFINITION_VERSION,
    RELEVANCE_WEIGHT_VERSION,
    TAXONOMY_V1_VERSION,
)
from gni.metrics.service import _latest_analyses, run_v1_stat_snapshots
from gni.reports.risk_tagging import (
    MEDIA_TYPE_ZH,
    china_signal_score,
    elevate_risk,
    media_type_bucket,
    risk_from_alert_severity,
    tag_text,
)
from gni.reports.validate import validate_daily_report

MONITOR_DEFAULT = ["US", "RU", "DE", "IN", "AU"]
SCHEMA_VERSION = "daily_report_schema_v4"
MIN_TONE_N = 3
PRIMARY_EVENT_MIN_SCORE = 2.0
PRIMARY_EVENT_CAP = 10
_RISK_SORT = {"high": 0, "medium": 1, "watch": 2, "unmapped": 3}
DISCLAIMER = (
    "全球对华监测产品；当前按接入国/源覆盖统计。"
    "情感条为正面/中立/负面语气分布（≠立场、≠国家态度）；"
    "不等于国家官方立场或社会民意。政府传播源不计入媒体情感主条。"
)

SENT_ZH = {
    "positive": "正面",
    "neutral": "中性",
    "negative": "负面",
    "mixed": "混合",
    "unknown": "未知",
}
STANCE_ZH = {
    "support": "支持",
    "oppose": "反对",
    "criticize": "批评",
    "critical": "批评",
    "endorse": "认可",
    "mixed": "混合",
    "neutral": "中立",
    "unknown": "未表态",
    "ambiguous": "含糊",
}


def _tz() -> ZoneInfo:
    try:
        return ZoneInfo(get_settings().report_timezone or "Asia/Shanghai")
    except Exception:
        return ZoneInfo("Asia/Shanghai")


def resolve_report_day(day: date | str | None = None) -> date:
    tz = _tz()
    if day is None:
        return datetime.now(tz).date()
    if isinstance(day, date) and not isinstance(day, datetime):
        return day
    return date.fromisoformat(str(day)[:10])


def shanghai_day_window(day: date) -> tuple[datetime, datetime]:
    tz = _tz()
    start = datetime.combine(day, time.min, tzinfo=tz).astimezone(timezone.utc)
    end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=tz).astimezone(timezone.utc)
    return start, end


def _aware(t: datetime | None) -> datetime | None:
    if t is None:
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def _in_range(a: Article, start: datetime, end: datetime) -> bool:
    """Strict V1.0 Section 8.1: article statistics use published_at only (never first_seen_at)."""
    t = _aware(a.published_at)
    return bool(t and start <= t < end)


def _norm_sentiment(label: str | None) -> str:
    if not label:
        return "unknown"
    s = str(label).strip().lower()
    if s in {"positive", "pos", "favorable"}:
        return "positive"
    if s in {"negative", "neg", "unfavorable", "critical"}:
        return "negative"
    if s in {"neutral", "neu"}:
        return "neutral"
    if s in {"mixed"}:
        return "mixed"
    return "unknown"


def _sentiment_bar_from_evidence(
    evidence: list[dict[str, Any]],
    sources: dict[str, Source],
) -> dict[str, Any]:
    """Aggregate positive/neutral/negative for UI bars; skip GOVERNMENT_RELEASES."""
    counts: Counter[str] = Counter()
    skipped_gov = 0
    for ev in evidence:
        sid = ev.get("source_id")
        src = sources.get(sid) if isinstance(sid, str) else None
        if src and (src.feed_scope or "").upper() == "GOVERNMENT_RELEASES":
            skipped_gov += 1
            continue
        sl = _norm_sentiment(ev.get("sentiment") if isinstance(ev.get("sentiment"), str) else None)
        if sl in {"positive", "neutral", "negative"}:
            counts[sl] += 1
    total = sum(counts.values()) or 0
    shares = {
        "positive": round(counts["positive"] / total, 4) if total else 0.0,
        "neutral": round(counts["neutral"] / total, 4) if total else 0.0,
        "negative": round(counts["negative"] / total, 4) if total else 0.0,
    }
    return {
        "sentiment_counts": {
            "positive": counts["positive"],
            "neutral": counts["neutral"],
            "negative": counts["negative"],
        },
        "sentiment_shares": shares,
        "sentiment_n": total,
        "sentiment_skipped_government": skipped_gov,
    }


def _stance_label(structured: dict[str, Any]) -> str:
    from gni.analysis.stance_util import primary_stance_label

    return primary_stance_label(structured)


def _topic_primary(structured: dict[str, Any]) -> str | None:
    topics = structured.get("topics") or {}
    if isinstance(topics, dict):
        return topics.get("primary") or topics.get("label")
    return None


def _frame_primary(structured: dict[str, Any]) -> str | None:
    framing = structured.get("framing") or {}
    if isinstance(framing, dict):
        return framing.get("primary") or framing.get("label")
    return None


def _top_n(counter: Counter[str], n: int = 8) -> list[dict[str, Any]]:
    total = sum(counter.values()) or 1
    return [
        {"label": k, "count": v, "share": round(v / total, 4)}
        for k, v in counter.most_common(n)
    ]


def _dominant(counter: dict[str, int] | Counter[str]) -> str | None:
    if not counter:
        return None
    return max(counter.items(), key=lambda x: x[1])[0]


def _country_tone_summary(cid: str, n: int, sent: dict[str, int], stance: dict[str, int]) -> str:
    if n <= 0:
        return f"{cid}：当日无可分析涉华样本，不推断态度。"
    if n < MIN_TONE_N:
        return f"{cid}：当日可分析样本 n={n}（<{MIN_TONE_N}），情感结论不可用，禁止外推。"
    ds = _dominant(sent) or "unknown"
    dst = _dominant(stance) or "unknown"
    return (
        f"{cid} 被监测媒体样本（n={n}）：情感以「{SENT_ZH.get(ds, ds)}」为主，"
        f"对华相关立场标签以「{STANCE_ZH.get(dst, dst)}」居多；情感与立场分列，非国家官方立场。"
    )


def _country_tone_status(n: int) -> str:
    if n <= 0:
        return "no_sample"
    if n < MIN_TONE_N:
        return "unavailable"
    return "ok"


def _event_overview(
    title: str,
    cov: dict[str, Any],
    imp: float | None,
    *,
    risk_level: str | None = None,
    sectors: list[dict[str, str]] | None = None,
    china_score: float | None = None,
) -> str:
    imp_s = f"{imp:.2f}" if imp is not None else "—"
    sector_labels = [
        s.get("label") or s.get("id")
        for s in (sectors or [])
        if (s.get("id") or "") != "unmapped"
    ]
    bits = [
        f"「{title}」",
        f"对华信号 {china_score:.1f}" if china_score is not None else None,
        f"风险 {risk_level or 'unmapped'}",
        f"赛道 {('、'.join(sector_labels) if sector_labels else '未映射')}",
        f"重要性 {imp_s}",
        f"关联文章 {cov.get('article_count', 0)} 篇、"
        f"{cov.get('country_count', 0)} 国、{cov.get('source_count', 0)} 源",
    ]
    return " · ".join(b for b in bits if b)


def _build_judgment_text(
    *,
    major_events: list[dict[str, Any]],
    orphan_headlines: list[dict[str, Any]],
    tone_by_country: list[dict[str, Any]],
    topic_overall: Counter[str],
    missing: int,
    day_total: int,
    china_n: int,
) -> tuple[str, str]:
    """Rule judgment_text + confidence (high|medium|low|unavailable)."""
    parts: list[str] = []
    high_n = sum(1 for m in major_events if m.get("risk_level") == "high")
    sector_n = sum(
        1
        for m in major_events
        if any(sid != "unmapped" for sid in (m.get("sector_ids") or []))
    )
    topic_total = sum(topic_overall.values()) or 0
    top_topic = topic_overall.most_common(1)[0] if topic_overall else None
    taxonomy_low = False
    if top_topic and topic_total:
        label, cnt = top_topic
        share = cnt / topic_total
        if share > 0.6 and label in {"technology", "other_unknown"}:
            taxonomy_low = True
            parts.append(f"议题过度集中于「{label}」（taxonomy 低置信）")
        elif label != "technology":
            parts.append(f"主议题偏「{label}」")
        else:
            parts.append(f"主议题偏「{label}」")
    if high_n or sector_n:
        parts.append(f"高风险事件 {high_n}、已映射赛道事件 {sector_n}")
    tops = sorted(
        major_events,
        key=lambda m: -(m.get("china_signal_score") or 0),
    )[:3]
    tops = [m for m in tops if (m.get("china_signal_score") or 0) >= 2.0]
    if tops:
        parts.append("优先关注：" + "；".join(str(m.get("title") or "")[:56] for m in tops))
    elif orphan_headlines:
        parts.append(
            "指纹外敏感标题：" + str(orphan_headlines[0].get("title") or "")[:56]
        )
    for row in tone_by_country:
        st = row.get("status")
        if st == "ok":
            # short polarity hint only when gated ok
            sc = row.get("sentiment_counts") or {}
            dom = _dominant(sc)
            if dom in {"positive", "negative"}:
                parts.append(
                    f"{row.get('country_id')} 媒体语气偏{SENT_ZH.get(dom, dom)}"
                    f"（n={row.get('n')}）"
                )
        elif st == "unavailable" and int(row.get("n") or 0) > 0:
            parts.append(f"{row.get('country_id')} 样本不足不可外推")

    # Backlog gate disabled: global pending/failed was starving daily confidence.
    # Keep ratio only as a soft note when same-day coverage looks thin.
    day_backlog_note = False
    if day_total > 0 and missing > 0 and (missing / max(1, day_total)) > 0.5:
        # Soft note only — do not force confidence=unavailable.
        parts.append("全库仍有分析积压（不影响当日研判出结论）")
        day_backlog_note = True
    if high_n >= 1 and not taxonomy_low:
        confidence = "high"
    elif china_n < 5 and high_n == 0 and not orphan_headlines:
        confidence = "low"
    else:
        confidence = "medium"
    if day_backlog_note and confidence == "high":
        confidence = "medium"

    if not parts:
        parts.append("当日可研判素材有限，维持常规监测")
    text = "；".join(parts)
    if not text.endswith("。"):
        text += "。"
    return text, confidence


def _china_count_in_window(
    articles: list[Article], start: datetime, end: datetime
) -> int:
    return sum(
        1
        for a in articles
        if _in_range(a, start, end)
        and (a.china_relevance_level or "") in CHINA_INCLUDE_LEVELS
    )


def build_daily_report(
    session: Session,
    *,
    day: date | str | None = None,
    country_scope: list[str] | None = None,
    polish: bool = False,
    analyze: bool = False,
    analyze_tasks: list[str] | None = None,
    force_analyze: bool = False,
    llm_client: Any = None,
    run_v2_assessments: bool = False,
    assessment_tasks: list[str] | None = None,
) -> dict[str, Any]:
    countries = country_scope or list(MONITOR_DEFAULT)
    sources = {s.id: s for s in session.scalars(select(Source)).all()}
    all_articles = list(session.scalars(select(Article)).all())
    articles = [a for a in all_articles if not a.exclude_from_metrics]

    report_day = resolve_report_day(day)
    # When caller asks for "today" and the calendar day is empty, fall back to
    # the most recent day (≤7d) that has china-included articles.
    if day is None:
        for back in range(0, 8):
            cand = report_day - timedelta(days=back)
            c_start, c_end = shanghai_day_window(cand)
            n = _china_count_in_window(articles, c_start, c_end)
            if n > 0 or back == 7:
                report_day = cand
                break

    win_start, win_end = shanghai_day_window(report_day)
    y_start, y_end = shanghai_day_window(report_day - timedelta(days=1))
    week_start, _ = shanghai_day_window(report_day - timedelta(days=7))

    day_articles = [a for a in articles if _in_range(a, win_start, win_end)]
    china_day = [
        a
        for a in day_articles
        if (a.china_relevance_level or "") in CHINA_INCLUDE_LEVELS
    ]
    yesterday_china = _china_count_in_window(articles, y_start, y_end)
    week_china_total = _china_count_in_window(articles, week_start, win_start)
    week_avg = round(week_china_total / 7.0, 2)

    analyses = _latest_analyses(
        session, [a.id for a in day_articles if a.analysis_status == "completed"]
    )

    # Coverage by country / source
    coverage_by_country: list[dict[str, Any]] = []
    countries_without_sample: list[str] = []
    reporting_countries: set[str] = set()
    reporting_sources: set[str] = set()
    source_counts: Counter[str] = Counter()

    for cid in countries:
        src_ids = {sid for sid, s in sources.items() if s.country_id == cid}
        day_c = [a for a in day_articles if a.source_id in src_ids]
        china_c = [
            a for a in day_c if (a.china_relevance_level or "") in CHINA_INCLUDE_LEVELS
        ]
        w_vol = sum(float(a.china_relevance_weight or 0.0) for a in china_c)
        analyzed = sum(1 for a in day_c if a.analysis_status == "completed")
        if china_c:
            reporting_countries.add(cid)
            for a in china_c:
                reporting_sources.add(a.source_id)
                source_counts[a.source_id] += 1
        coverage_by_country.append(
            {
                "country_id": cid,
                "article_count": len(china_c),
                "day_article_count": len(day_c),
                "analyzed_count": analyzed,
                "weighted_volume": round(w_vol, 4),
                "source_count": len(src_ids),
                "href": f"/countries?c={cid}",
            }
        )
        if len(china_c) == 0:
            countries_without_sample.append(cid)

    coverage_by_country.sort(key=lambda r: (-r["article_count"], r["country_id"]))
    by_source: list[dict[str, Any]] = []
    for sid, cnt in source_counts.most_common(15):
        src = sources.get(sid)
        by_source.append(
            {
                "source_id": sid,
                "name": src.name if src else sid,
                "country_id": src.country_id if src else None,
                "article_count": cnt,
            }
        )

    # Tone aggregates + media-type / official-vs-media narrative split
    sent_overall: Counter[str] = Counter()
    stance_overall: Counter[str] = Counter()
    topic_overall: Counter[str] = Counter()
    frame_overall: Counter[str] = Counter()
    sent_by_media_type: dict[str, Counter[str]] = {}
    topic_official: Counter[str] = Counter()
    topic_media: Counter[str] = Counter()
    sentiment_scores: list[float] = []
    by_country_tone: dict[str, dict[str, Any]] = {
        c: {"sentiment_counts": Counter(), "stance_counts": Counter(), "n": 0}
        for c in countries
    }

    for a in china_day:
        if a.id not in analyses:
            continue
        structured = analyses[a.id].structured_result or {}
        src = sources.get(a.source_id)
        cid = (src.country_id if src else None) or "UNK"
        bucket = media_type_bucket(src)
        sl = _norm_sentiment(
            (structured.get("sentiment") or {}).get("label")
            if isinstance(structured.get("sentiment"), dict)
            else (structured.get("sentiment") if isinstance(structured.get("sentiment"), str) else None)
        )
        st = _stance_label(structured)
        tp = _topic_primary(structured)
        fr = _frame_primary(structured)
        is_gov = bucket == "government_agency" or (
            src and (src.feed_scope or "").upper() == "GOVERNMENT_RELEASES"
        )
        sent_obj = structured.get("sentiment") or {}
        if isinstance(sent_obj, dict) and isinstance(sent_obj.get("score"), (int, float)):
            if not is_gov:
                sentiment_scores.append(float(sent_obj["score"]))
        if not is_gov:
            sent_overall[sl] += 1
            sent_by_media_type.setdefault(bucket, Counter())[sl] += 1
        stance_overall[st] += 1
        if tp:
            topic_overall[str(tp)] += 1
            if is_gov:
                topic_official[str(tp)] += 1
            else:
                topic_media[str(tp)] += 1
        if fr:
            frame_overall[str(fr)] += 1
        if cid in by_country_tone and not is_gov:
            by_country_tone[cid]["sentiment_counts"][sl] += 1
            by_country_tone[cid]["stance_counts"][st] += 1
            by_country_tone[cid]["n"] += 1

    tone_by_country: list[dict[str, Any]] = []
    for cid in countries:
        blob = by_country_tone[cid]
        sc = dict(blob["sentiment_counts"])
        stc = dict(blob["stance_counts"])
        n = int(blob["n"])
        tone_status = _country_tone_status(n)
        tone_by_country.append(
            {
                "country_id": cid,
                "n": n,
                "status": tone_status,
                "sentiment_counts": sc,
                "stance_counts": stc,
                "summary_text": _country_tone_summary(cid, n, sc, stc),
                "href": f"/countries?c={cid}",
            }
        )

    missing = int(
        session.scalar(
            select(func.count())
            .select_from(Article)
            .where(
                Article.exclude_from_metrics.is_(False),
                Article.processing_status == "done",
                Article.analysis_status.in_(["pending", "failed"]),
            )
        )
        or 0
    )

    # Major events — importance first; touch day window via event_time / first article / updated
    raw_events = list_events(
        session,
        limit=40,
        window_start=win_start - timedelta(days=7),
        window_end=win_end + timedelta(days=1),
    )
    event_rows = list(session.scalars(select(Event).limit(80)).all())
    event_by_id = {e.id: e for e in event_rows}

    major_events: list[dict[str, Any]] = []
    for e in raw_events:
        eid = e["id"]
        links = list(
            session.scalars(select(EventArticle).where(EventArticle.event_id == eid)).all()
        )
        evidence: list[dict[str, Any]] = []
        countries_reporting: set[str] = set()
        sources_reporting: set[str] = set()
        country_sent: dict[str, Counter[str]] = {}
        country_stance: dict[str, Counter[str]] = {}
        country_frame: dict[str, Counter[str]] = {}
        country_art_n: Counter[str] = Counter()
        first_seen: datetime | None = None

        need_ids = [link.article_id for link in links if link.article_id not in analyses]
        if need_ids:
            analyses.update(_latest_analyses(session, need_ids))

        for link in links:
            art = session.get(Article, link.article_id)
            if not art:
                continue
            src = sources.get(art.source_id)
            cid = src.country_id if src else None
            if cid:
                countries_reporting.add(cid)
                country_art_n[cid] += 1
            sources_reporting.add(art.source_id)
            t = _aware(art.published_at or art.first_seen_at)
            if t and (first_seen is None or t < first_seen):
                first_seen = t
            structured = (
                (analyses[art.id].structured_result if art.id in analyses else None) or {}
            )
            sl = _norm_sentiment(
            (structured.get("sentiment") or {}).get("label")
            if isinstance(structured.get("sentiment"), dict)
            else (structured.get("sentiment") if isinstance(structured.get("sentiment"), str) else None)
        )
            st = _stance_label(structured)
            fr = _frame_primary(structured)
            if cid:
                country_sent.setdefault(cid, Counter())[sl] += 1
                country_stance.setdefault(cid, Counter())[st] += 1
                if fr:
                    country_frame.setdefault(cid, Counter())[str(fr)] += 1
            evidence.append(
                {
                    "article_id": art.id,
                    "title": art.title,
                    "country_id": cid,
                    "source_id": art.source_id,
                    "url": art.url,
                    "sentiment": sl,
                    "stance": st,
                    "published_at": t.isoformat() if t else None,
                    "china_relevance_weight": float(art.china_relevance_weight or 0.0),
                    "china_relevance_level": art.china_relevance_level,
                }
            )

        # Relevance to report day: event_time in day, or first_seen in day, or any evidence published in day
        ev_obj = event_by_id.get(eid)
        event_time = _aware(ev_obj.event_time if ev_obj else None) or (
            datetime.fromisoformat(e["event_time"].replace("Z", "+00:00"))
            if e.get("event_time")
            else None
        )
        touched = False
        if event_time and win_start <= event_time < win_end:
            touched = True
        if first_seen and win_start <= first_seen < win_end:
            touched = True
        for ev in evidence:
            pt = ev.get("published_at")
            if not pt:
                continue
            try:
                pdt = datetime.fromisoformat(str(pt).replace("Z", "+00:00"))
            except ValueError:
                continue
            if win_start <= pdt < win_end:
                touched = True
                break
        if not touched and (e.get("importance_score") or 0) < 0.55:
            continue
        # still include high-importance even if slightly outside day (ongoing)
        if not touched and (e.get("importance_score") or 0) < 0.75:
            continue

        by_country_views = []
        for cid, n in country_art_n.most_common():
            by_country_views.append(
                {
                    "country_id": cid,
                    "article_count": n,
                    "dominant_sentiment": _dominant(country_sent.get(cid) or {}),
                    "dominant_stance": _dominant(country_stance.get(cid) or {}),
                    "frame": _dominant(country_frame.get(cid) or {}),
                    "href": f"/countries?c={cid}",
                }
            )

        cov = {
            "article_count": len(evidence),
            "country_count": len(countries_reporting),
            "source_count": len(sources_reporting),
            "countries": sorted(countries_reporting),
        }
        imp = e.get("importance_score")
        follow_ups = [
            "是否有官方细则或后续声明？",
            "其他监测国媒体是否跟进？",
            "报道框架是否从政策本身转向产业/安全影响？",
        ]
        sent_bar = _sentiment_bar_from_evidence(evidence, sources)
        bucket_counts: Counter[str] = Counter()
        for ev in evidence:
            src = sources.get(ev.get("source_id") or "")
            bucket_counts[media_type_bucket(src)] += 1
        primary_bucket = bucket_counts.most_common(1)[0][0] if bucket_counts else "other"
        primary_country = (
            country_art_n.most_common(1)[0][0] if country_art_n else (sorted(countries_reporting)[0] if countries_reporting else None)
        )
        evidence_titles = [str(ev.get("title") or "") for ev in evidence[:8]]
        tags = tag_text(
            e.get("title"),
            e.get("summary"),
            e.get("event_type"),
            " ".join(evidence_titles),
        )
        weights = [
            float(ev.get("china_relevance_weight") or 0.0) for ev in evidence if ev.get("china_relevance_weight")
        ]
        avg_w = (sum(weights) / len(weights)) if weights else 0.0
        shares = sent_bar["sentiment_shares"]
        neg_share = float(shares.get("negative") or 0)
        dom_sent = "negative" if neg_share >= max(shares.get("positive", 0), shares.get("neutral", 0)) else (
            "positive" if shares.get("positive", 0) >= shares.get("neutral", 0) else "neutral"
        )
        if sent_bar["sentiment_n"] == 0:
            dom_sent = "unknown"
        anomaly_reasons: list[str] = []
        if tags["risk_level"] == "high":
            anomaly_reasons.append("政策/制裁类高风险关键词")
        if sent_bar["sentiment_n"] >= 2 and neg_share >= 0.5:
            anomaly_reasons.append(f"媒体情感负面占比 {neg_share:.0%}")
        if (imp or 0) >= 0.7 and neg_share >= 0.4 and sent_bar["sentiment_n"] >= 1:
            anomaly_reasons.append("高重要性事件伴随偏负面语气")
        if len(countries_reporting) >= 3 and (imp or 0) >= 0.55:
            anomaly_reasons.append("三国及以上同步报道")
        anomaly = {
            "flagged": bool(anomaly_reasons),
            "reasons": anomaly_reasons,
        }
        css = china_signal_score(
            title=e.get("title"),
            evidence_titles=evidence_titles,
            tags=tags,
            anomaly_flagged=bool(anomaly_reasons),
            importance=float(imp) if imp is not None else None,
            avg_china_weight=avg_w,
        )
        timeline = []
        if first_seen:
            timeline.append({"at": first_seen.isoformat(), "label": "first_seen"})
        if event_time:
            timeline.append({"at": event_time.isoformat(), "label": "event_time"})
        for ev in sorted(
            [x for x in evidence if x.get("published_at")],
            key=lambda x: str(x.get("published_at")),
        )[:5]:
            timeline.append(
                {
                    "at": ev.get("published_at"),
                    "label": "article",
                    "article_id": ev.get("article_id"),
                    "country_id": ev.get("country_id"),
                }
            )
        narrative_labels = []
        if e.get("event_type"):
            narrative_labels.append(str(e["event_type"]))
        for t in tags["sectors"]:
            if t["id"] != "unmapped":
                narrative_labels.append(t["label"])
        # Risk-aware follow-ups for high/medium
        if tags["risk_level"] == "high":
            follow_ups = [
                "核对制裁/管制清单是否已生效及覆盖实体",
                "追踪产业供应链与相关上市公司披露",
                "监测他国官媒/政府源是否跟进定性",
            ]
        elif tags["risk_level"] == "medium":
            follow_ups = [
                "是否有官方细则或后续声明？",
                "是否升级为出口管制/安全协议条款？",
                "其他监测国媒体是否跟进？",
            ]
        major_events.append(
            {
                "event_id": eid,
                "title": e["title"],
                "importance_score": imp,
                "china_signal_score": css,
                "avg_china_relevance_weight": round(avg_w, 4),
                "event_type": e.get("event_type"),
                "event_time": event_time.isoformat() if event_time else e.get("event_time"),
                "first_seen_at": first_seen.isoformat() if first_seen else None,
                "status": e.get("status"),
                "overview_text": _event_overview(
                    e["title"],
                    cov,
                    imp,
                    risk_level=tags["risk_level"],
                    sectors=tags["sectors"],
                    china_score=css,
                ),
                "core": {
                    "actor": (ev_obj.actor_key if ev_obj else None),
                    "action": (ev_obj.action_key if ev_obj else None),
                    "object": (ev_obj.object_key if ev_obj else None),
                    "target": "china",
                    "status": e.get("status"),
                },
                "coverage": cov,
                "sentiment_counts": sent_bar["sentiment_counts"],
                "sentiment_shares": sent_bar["sentiment_shares"],
                "sentiment_n": sent_bar["sentiment_n"],
                "sentiment_skipped_government": sent_bar["sentiment_skipped_government"],
                "sentiment_label": dom_sent,
                "primary_country": primary_country,
                "source_bucket": primary_bucket,
                "source_bucket_zh": MEDIA_TYPE_ZH.get(primary_bucket, primary_bucket),
                "narrative_labels": narrative_labels[:6],
                "risk_level": tags["risk_level"],
                "sectors": tags["sectors"],
                "sector_ids": tags["sector_ids"],
                "matched_triggers": tags["matched_triggers"],
                "anomaly": anomaly,
                "timeline": timeline,
                "by_country_views": by_country_views,
                "follow_ups": follow_ups,
                "evidence": evidence[:12],
                "href": f"/events/{eid}",
            }
        )

    major_events.sort(
        key=lambda x: (
            -(x.get("china_signal_score") or 0),
            _RISK_SORT.get(str(x.get("risk_level") or "unmapped"), 9),
            -(x.get("importance_score") or 0),
            -((x.get("coverage") or {}).get("country_count") or 0),
        )
    )
    for m in major_events:
        score = float(m.get("china_signal_score") or 0)
        risk = str(m.get("risk_level") or "unmapped")
        imp_val = float(m.get("importance_score") or 0)
        country_n = int((m.get("coverage") or {}).get("country_count") or 0)
        if score >= PRIMARY_EVENT_MIN_SCORE or risk in {"high", "medium"} or imp_val >= 0.6 or country_n >= 2:
            m["list_tier"] = "primary"
        else:
            m["list_tier"] = "secondary"
    primary_events = [m for m in major_events if m.get("list_tier") == "primary"][:PRIMARY_EVENT_CAP]
    secondary_events = [m for m in major_events if m.get("list_tier") == "secondary"][:8]
    if not primary_events and major_events:
        for m in major_events[:PRIMARY_EVENT_CAP]:
            m["list_tier"] = "primary"
            primary_events.append(m)
        secondary_events = [m for m in major_events if m not in primary_events][:8]
    major_events = primary_events
    high_major = sum(1 for m in major_events if (m.get("importance_score") or 0) >= 0.7)

    # New events first_seen today
    new_events_n = 0
    for m in major_events + secondary_events:
        fs = m.get("first_seen_at")
        if not fs:
            continue
        try:
            fdt = datetime.fromisoformat(str(fs).replace("Z", "+00:00"))
            if win_start <= fdt < win_end:
                new_events_n += 1
        except ValueError:
            pass

    # Orphan sensitive headlines: china_day articles not covered by fingerprint events
    covered_aids: set[str] = set()
    for m in major_events + secondary_events:
        for ev in m.get("evidence") or []:
            aid = ev.get("article_id")
            if aid:
                covered_aids.add(str(aid))
    orphan_headlines: list[dict[str, Any]] = []
    china_sorted = sorted(
        china_day,
        key=lambda a: float(a.china_relevance_weight or 0.0),
        reverse=True,
    )
    for art in china_sorted:
        if str(art.id) in covered_aids:
            continue
        snippet = (art.content_clean or "")[:240]
        tags = tag_text(art.title, snippet)
        risk = tags["risk_level"]
        mapped = [s for s in tags["sector_ids"] if s != "unmapped"]
        if risk not in {"high", "medium"} and not mapped:
            continue
        src = sources.get(art.source_id)
        orphan_headlines.append(
            {
                "article_id": art.id,
                "title": art.title,
                "country_id": src.country_id if src else None,
                "source_id": art.source_id,
                "china_relevance_weight": float(art.china_relevance_weight or 0.0),
                "risk_level": risk,
                "sectors": tags["sectors"],
                "sector_ids": tags["sector_ids"],
                "matched_triggers": tags["matched_triggers"],
                "href": f"/search?q={art.id}",
            }
        )
        if len(orphan_headlines) >= 8:
            break

    # Signals from alert engine (intelligence only) — scoped to report-day window
    signals: list[dict[str, Any]] = []
    try:
        alerts = build_alerts_payload(session, window_start=win_start, window_end=win_end)
        for a in (alerts.get("intelligence") or [])[:8]:
            signals.append(
                {
                    "id": a.get("id"),
                    "subcategory": a.get("subcategory"),
                    "severity": a.get("severity"),
                    "title": a.get("title"),
                    "summary": a.get("summary"),
                    "status": "needs_review",
                    "href": "/alerts",
                    "evidence": a.get("evidence") or {},
                }
            )
    except Exception as exc:  # noqa: BLE001
        signals.append(
            {
                "id": "signals_error",
                "subcategory": "system",
                "severity": "low",
                "title": "信号引擎暂不可用",
                "summary": str(exc)[:200],
                "status": "unconfirmed",
                "href": "/alerts",
                "evidence": {},
            }
        )

    # Synthetic signals from high-score events / orphans (avoid empty signal rail)
    for m in major_events[:5]:
        if m.get("risk_level") not in {"high", "medium"} and (m.get("china_signal_score") or 0) < 4:
            continue
        sub = "policy_risk" if m.get("risk_level") in {"high", "medium"} else "sector_watch"
        signals.append(
            {
                "id": f"synth_event_{m.get('event_id')}",
                "subcategory": sub,
                "severity": "high" if m.get("risk_level") == "high" else "medium",
                "title": m.get("title"),
                "summary": f"对华信号分 {m.get('china_signal_score')} · 风险 {m.get('risk_level')}",
                "status": "needs_review",
                "href": m.get("href") or "/events",
                "evidence": {"event_id": m.get("event_id"), "synthetic": True},
            }
        )
    for oh in orphan_headlines[:4]:
        sub = "policy_risk" if oh.get("risk_level") in {"high", "medium"} else "sector_watch"
        signals.append(
            {
                "id": f"synth_orphan_{oh.get('article_id')}",
                "subcategory": sub,
                "severity": "high" if oh.get("risk_level") == "high" else "medium",
                "title": oh.get("title"),
                "summary": "指纹事件外敏感标题（需复核）",
                "status": "needs_review",
                "href": oh.get("href") or "/search",
                "evidence": {"article_id": oh.get("article_id"), "synthetic": True, "orphan": True},
            }
        )
    # Dedupe by title prefix
    seen_sig: set[str] = set()
    deduped_signals: list[dict[str, Any]] = []
    for sig in signals:
        key = (str(sig.get("title") or "")[:48]).lower()
        if key in seen_sig:
            continue
        seen_sig.add(key)
        deduped_signals.append(sig)
    signals = deduped_signals[:12]

    # Elevate event risk from overlapping alert titles; build anomalies list
    for m in major_events:
        title_l = (m.get("title") or "").lower()
        for sig in signals:
            if (sig.get("severity") or "") != "high":
                continue
            if (sig.get("evidence") or {}).get("synthetic"):
                continue
            st = (sig.get("title") or "").lower()
            if st and (st[:24] in title_l or title_l[:24] in st):
                m["risk_level"] = elevate_risk(m.get("risk_level") or "unmapped", risk_from_alert_severity("high"))
                anom = m.setdefault("anomaly", {"flagged": False, "reasons": []})
                anom["flagged"] = True
                anom.setdefault("reasons", []).append(f"关联高严重度信号：{sig.get('title')}")

    anomalies: list[dict[str, Any]] = []
    for m in major_events:
        if (m.get("anomaly") or {}).get("flagged") or m.get("risk_level") == "high":
            anomalies.append(
                {
                    "kind": "event_anomaly",
                    "event_id": m.get("event_id"),
                    "title": m.get("title"),
                    "risk_level": m.get("risk_level"),
                    "reasons": (m.get("anomaly") or {}).get("reasons")
                    or (["高风险事件"] if m.get("risk_level") == "high" else []),
                    "href": m.get("href"),
                }
            )
    for oh in orphan_headlines:
        anomalies.append(
            {
                "kind": "orphan_headline",
                "article_id": oh.get("article_id"),
                "title": oh.get("title"),
                "risk_level": oh.get("risk_level"),
                "reasons": ["指纹簇外敏感标题"] + list(oh.get("matched_triggers") or [])[:3],
                "href": oh.get("href"),
            }
        )
    for sig in signals:
        if (sig.get("evidence") or {}).get("synthetic"):
            continue
        anomalies.append(
            {
                "kind": "signal",
                "id": sig.get("id"),
                "subcategory": sig.get("subcategory"),
                "severity": sig.get("severity"),
                "title": sig.get("title"),
                "summary": sig.get("summary"),
                "href": sig.get("href") or "/alerts",
            }
        )
    anomalies = anomalies[:12]

    # Overview stats: ingest vs effective vs filtered; media types; crawl
    day_all = [a for a in all_articles if _in_range(a, win_start, win_end)]
    excluded_day = [a for a in day_all if a.exclude_from_metrics]
    dup_day = [a for a in day_all if a.duplicate_of_article_id]
    brief_day = [
        a
        for a in day_all
        if (a.quality_status or "") in {"insufficient_text", "too_short", "rss_stub"}
        or (a.content_clean is None and (a.quality_status or "") == "rss_stub")
    ]
    media_type_counts: Counter[str] = Counter()
    for a in china_day:
        media_type_counts[media_type_bucket(sources.get(a.source_id))] += 1

    health_map = {h.source_id: h for h in session.scalars(select(SourceHealth)).all()}
    crawl_status: list[dict[str, Any]] = []
    for sid, src in sources.items():
        if (src.active_status or "") != "active" or src.country_id not in countries:
            continue
        h = health_map.get(sid)
        fail = int(h.failure_count) if h else 0
        ok_n = int(h.success_count) if h else 0
        err = (h.error_message or "") if h else ""
        status = "ok"
        if fail > ok_n and fail > 0:
            status = "failing"
        elif "429" in err:
            status = "rate_limited"
        elif fail > 0 and ok_n == 0:
            status = "unreachable"
        crawl_status.append(
            {
                "source_id": sid,
                "name": src.name,
                "country_id": src.country_id,
                "status": status,
                "success_count": ok_n,
                "failure_count": fail,
                "last_error": err[:200] if err else None,
            }
        )
    crawl_status.sort(key=lambda r: (0 if r["status"] != "ok" else 1, r["source_id"]))

    sent_mean = round(sum(sentiment_scores) / len(sentiment_scores), 4) if sentiment_scores else None
    # Yesterday score mean (technical baseline)
    y_articles = [
        a
        for a in articles
        if _in_range(a, y_start, y_end) and (a.china_relevance_level or "") in CHINA_INCLUDE_LEVELS
    ]
    y_analyses = _latest_analyses(session, [a.id for a in y_articles if a.analysis_status == "completed"])
    y_scores: list[float] = []
    for a in y_articles:
        if a.id not in y_analyses:
            continue
        src = sources.get(a.source_id)
        if media_type_bucket(src) == "government_agency":
            continue
        structured = y_analyses[a.id].structured_result or {}
        sent_obj = structured.get("sentiment") or {}
        if isinstance(sent_obj, dict) and isinstance(sent_obj.get("score"), (int, float)):
            y_scores.append(float(sent_obj["score"]))
    y_mean = round(sum(y_scores) / len(y_scores), 4) if y_scores else None
    sent_delta = round(sent_mean - y_mean, 4) if sent_mean is not None and y_mean is not None else None

    overview_stats = {
        "connected_countries": countries,
        "media_type_counts": dict(media_type_counts),
        "media_type_counts_zh": {
            MEDIA_TYPE_ZH.get(k, k): v for k, v in media_type_counts.items()
        },
        "ingest": {
            "day_total": len(day_all),
            "day_included": len(day_articles),
            "china_effective": len(china_day),
            "excluded_from_metrics": len(excluded_day),
            "duplicates": len(dup_day),
            "thin_or_stub": len(brief_day),
        },
        "crawl_summary": {
            "active_sources": sum(1 for r in crawl_status if True),
            "failing": sum(1 for r in crawl_status if r["status"] != "ok"),
            "rate_limited": sum(1 for r in crawl_status if r["status"] == "rate_limited"),
        },
        "narrative_split": {
            "official_topics_top": _top_n(topic_official, 5),
            "media_topics_top": _top_n(topic_media, 5),
            "note": "官方口径≈政府传播源；媒体评论≈其余媒体源主题。",
        },
    }

    high_risk_events = [m for m in major_events if m.get("risk_level") == "high"]
    has_high_risk = bool(high_risk_events) or any(
        (s.get("severity") == "high") for s in signals
    )
    risk_banner = {
        "has_high_risk": has_high_risk,
        "high_risk_event_count": len(high_risk_events),
        "text": (
            f"突发高风险：有（{len(high_risk_events)} 件事件 / "
            f"{sum(1 for s in signals if s.get('severity') == 'high')} 条高严重度信号）。"
            if has_high_risk
            else "突发高风险：未见（规则关键词 + 告警严重度初判）。"
        ),
    }

    ops_follow_ups = []
    for m in major_events[:8]:
        if m.get("risk_level") in {"high", "medium"} or (m.get("anomaly") or {}).get("flagged"):
            action = (m.get("follow_ups") or ["追踪官方细则与他国跟进报道"])[0]
            ops_follow_ups.append(
                {
                    "event_id": m.get("event_id"),
                    "title": m.get("title"),
                    "action": action,
                    "href": m.get("href"),
                }
            )
        if len(ops_follow_ups) >= 3:
            break
    for oh in orphan_headlines:
        if len(ops_follow_ups) >= 3:
            break
        ops_follow_ups.append(
            {
                "article_id": oh.get("article_id"),
                "title": oh.get("title"),
                "action": "复核指纹外敏感标题并评估是否建事件",
                "href": oh.get("href"),
            }
        )
    if not ops_follow_ups and major_events:
        ops_follow_ups.append(
            {
                "event_id": major_events[0].get("event_id"),
                "title": major_events[0].get("title"),
                "action": "维持常规监测，关注是否跨国扩散",
                "href": major_events[0].get("href"),
            }
        )

    # Top changes (max 3)
    top_changes: list[dict[str, Any]] = []
    if week_avg > 0 and len(china_day) >= max(3, week_avg * 1.8):
        top_changes.append(
            {
                "title": "涉华报道量相对近 7 日日均偏高",
                "summary": f"今日 {len(china_day)} 篇 vs 近 7 日日均 {week_avg}。",
                "kind": "volume",
                "href": "/trends",
                "evidence": {"china_articles": len(china_day), "week_avg": week_avg},
            }
        )
    if topic_overall:
        top_t = topic_overall.most_common(1)[0]
        top_changes.append(
            {
                "title": f"主议题集中于「{top_t[0]}」",
                "summary": f"已分析样本中该议题 {top_t[1]} 次居首。",
                "kind": "topic",
                "href": "/trends",
                "evidence": {"topic": top_t[0], "count": top_t[1]},
            }
        )
    if signals:
        s0 = signals[0]
        top_changes.append(
            {
                "title": s0.get("title") or "情报预警",
                "summary": s0.get("summary") or "",
                "kind": "alert",
                "href": "/alerts",
                "evidence": s0.get("evidence") or {},
            }
        )
    top_changes = top_changes[:3]

    china_n = len(china_day)
    delta_y = china_n - yesterday_china
    day_total_for_gate = max(int(overview_stats["ingest"]["day_total"] or 0), 1)
    judgment_text, judgment_confidence = _build_judgment_text(
        major_events=major_events,
        orphan_headlines=orphan_headlines,
        tone_by_country=tone_by_country,
        topic_overall=topic_overall,
        missing=missing,
        day_total=day_total_for_gate,
        china_n=china_n,
    )
    overview_text = (
        f"{judgment_text} "
        f"{risk_banner['text']} "
        f"今日涉华有效报道 {china_n} 篇（昨日 {yesterday_china}，"
        f"{'↑' if delta_y > 0 else '↓' if delta_y < 0 else '→'}{abs(delta_y)}；"
        f"近 7 日日均 {week_avg}），覆盖约 {len(reporting_countries)} 国、"
        f"{len(reporting_sources)} 源；主列表事件 {len(major_events)} 个"
        f"（高重要 {high_major}，新发现约 {new_events_n}；次要 {len(secondary_events)}；"
        f"孤儿敏感标题 {len(orphan_headlines)}）。"
        f"研判置信度 {judgment_confidence}。"
        f"采集异常源 {overview_stats['crawl_summary']['failing']}。"
    )

    health_rows = [
        {
            "source_id": h.source_id,
            "success_count": h.success_count,
            "failure_count": h.failure_count,
            "last_error": h.error_message,
        }
        for h in session.scalars(select(SourceHealth).limit(40)).all()
    ]

    connected_countries = len(countries)
    active_sources_n = sum(
        1 for s in sources.values() if (s.active_status or "") == "active" and s.country_id in countries
    )
    disclaimer = (
        f"全球对华监测 · 当前接入 {connected_countries} 国"
        f"（本日有报道 {len(reporting_countries)} 国）· "
        f"活跃源约 {active_sources_n} · 本日引用源 {len(reporting_sources)}。"
        + DISCLAIMER
    )

    v1_snap = run_v1_stat_snapshots(
        session,
        period_start=win_start,
        period_end=win_end,
        persist=False,
    )

    payload: dict[str, Any] = {
        "report_type": "daily",
        "schema_version": SCHEMA_VERSION,
        "methodology_version": METHODOLOGY_VERSION,
        "taxonomy_version": TAXONOMY_V1_VERSION,
        "period": report_day.isoformat(),
        "period_start": win_start.isoformat(),
        "period_end": win_end.isoformat(),
        "timezone": str(_tz()),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "country_scope": countries,
        "target_scope": "china",
        "disclaimer": disclaimer,
        "metric_definition_version": METRIC_DEFINITION_VERSION,
        "relevance_weight_version": RELEVANCE_WEIGHT_VERSION,
        "generator": "rule_brief_v4",
        "article_count": china_n,
        "event_count": len(major_events),
        "connected": {
            "countries": connected_countries,
            "active_sources": active_sources_n,
            "country_ids": list(countries),
        },
        "sections": {
            "v1_stats": v1_snap["by_scope"],
            "summary": {
                "kpis": {
                    "china_articles": china_n,
                    "prev_day_articles": yesterday_china,
                    "delta": delta_y,
                    "reporting_countries": len(reporting_countries),
                    "reporting_sources": len(reporting_sources),
                    "new_events": new_events_n,
                    "major_events": high_major,
                    "day_articles": len(day_articles),
                    "stories": len(major_events),
                    "articles_analyzed": china_n,
                    "sources_cited": len(reporting_sources),
                },
                "comparisons": {
                    "vs_yesterday": {
                        "china_articles": yesterday_china,
                        "delta": delta_y,
                    },
                    "vs_7d_avg": {
                        "china_articles": week_avg,
                        "delta": round(china_n - week_avg, 2),
                    },
                },
                "top_changes": top_changes,
                "overview_text": overview_text,
                "judgment_text": judgment_text,
                "confidence": judgment_confidence,
                "risk_banner": risk_banner,
            },
            "overview_stats": overview_stats,
            "major_events": major_events,
            "secondary_events": secondary_events,
            "orphan_headlines": orphan_headlines,
            "coverage": {
                "by_country": coverage_by_country,
                "by_source": by_source,
                "topics_top": _top_n(topic_overall, 8),
                "frames_top": _top_n(frame_overall, 8),
                "taxonomy_confidence": (
                    "low"
                    if topic_overall
                    and (
                        topic_overall.most_common(1)[0][1] / max(1, sum(topic_overall.values()))
                    )
                    > 0.6
                    else "normal"
                ),
                "note": (
                    f"全球监测覆盖（当前接入 {connected_countries} 国）。"
                    "Article Count 与 Weighted Volume 分列；加权不替代实际篇数。"
                    + (
                        " 当日 >60% 主题落入同一桶，taxonomy 低置信。"
                        if topic_overall
                        and (
                            topic_overall.most_common(1)[0][1]
                            / max(1, sum(topic_overall.values()))
                        )
                        > 0.6
                        else ""
                    )
                ),
            },
            "tone": {
                "overall_stance_counts": dict(stance_overall),
                "by_country": [],
                "min_n": MIN_TONE_N,
                "note": (
                    "日报仅保留对华立场分布（target=china_mainland，口径见 v1_stats）；"
                    "Unclassified 不计入正中负比例分母，引述≠媒体自身立场。"
                ),
            },
            "anomalies": anomalies,
            "signals": signals,
            "ops": {
                "follow_ups": ops_follow_ups,
                "crawl_status": crawl_status[:30],
                "note": "次日跟踪建议 + 采集状态（失败/429/失联）。",
            },
            "quality": {
                "missing_analysis": missing,
                "countries_without_sample": countries_without_sample,
                "source_health_summary": {
                    "rows": len(health_rows),
                    "failing": sum(
                        1
                        for h in health_rows
                        if (h.get("failure_count") or 0) > (h.get("success_count") or 0)
                    ),
                },
                "source_health": health_rows,
                "notes": [
                    "规则组装 facts；LLM 仅可润色叙述。",
                    "RSS latest-N ≠ 完整自然日语料。",
                    f"分析积压 pending/failed ≈ {missing}。",
                    "只抓官媒/公服/政府传播，不代表民间民意；模型打分有误差。",
                    "系统运行告警见异常与预警页 B 栏。",
                ],
            },
        },
        "narratives": {
            "executive": judgment_text,
            "risk": risk_banner["text"],
            "coverage": (
                f"涉华报道量居前："
                + "、".join(
                    f"{r['country_id']}({r['article_count']})"
                    for r in coverage_by_country[:3]
                    if r["article_count"] > 0
                )
                or "各国当日涉华样本不足"
            )
            + "。",
            "tone": f"分国情感门禁 n≥{MIN_TONE_N}；勿外推为国家立场。",
            "signals": (
                f"情报信号 {len(signals)} 条；异动 {len(anomalies)} 条；"
                f"孤儿敏感标题 {len(orphan_headlines)}。"
            ),
            "quality": f"分析积压 {missing}；采集异常源 "
            f"{overview_stats['crawl_summary']['failing']}；"
            f"无样本国家 {countries_without_sample or '无'}；"
            f"研判置信度 {judgment_confidence}。",
        },
    }

    from gni.reports.narrative.runner import (
        load_cached_intelligence,
        run_report_intelligence,
    )

    if analyze:
        payload["intelligence"] = run_report_intelligence(
            session,
            report_type="daily",
            period=payload["period"],
            payload=payload,
            tasks=analyze_tasks,
            force=force_analyze,
            llm_client=llm_client,
        )
    else:
        payload["intelligence"] = load_cached_intelligence(
            session,
            report_type="daily",
            period=payload["period"],
            payload=payload,
        )

    if (payload["intelligence"].get("meta") or {}).get("completed_tasks", 0) > 0:
        payload["generator"] = "rule_brief_v4+llm_intelligence"

    from gni.reports.package_composer import extract_report_visualizations
    from gni.reports.quality_gate import evaluate_report_quality_gate
    from gni.reports.window import resolve_daily_window

    payload["window_spec"] = resolve_daily_window(report_day).to_dict()
    payload["visualizations"] = extract_report_visualizations(payload)
    payload["validation"] = validate_daily_report(payload)
    payload["quality_gate"] = evaluate_report_quality_gate(payload)

    if polish:
        has_intel = (payload["intelligence"].get("meta") or {}).get("completed_tasks", 0) > 0
        if has_intel:
            payload["polish"] = {"applied": False, "reason": "skipped_when_intelligence_present"}
        else:
            from gni.reports.polish import polish_daily_narratives

            polished = polish_daily_narratives(payload)
            if polished:
                if polished.get("executive"):
                    payload["sections"]["summary"]["overview_text"] = polished["executive"]
                payload["narratives"].update(polished)
                payload["generator"] = "rule_brief_v4+llm_narratives"
                payload["polish"] = {"applied": True}
                payload["validation"] = validate_daily_report(payload)
            else:
                payload["polish"] = {"applied": False, "reason": "llm_unavailable_or_rejected"}

    # Phase 6: Attach unified 6-Chapter + Appendix ReportPackageContract (100% backward compatible)
    from gni.reports.daily_package import assemble_daily_report_package

    report_pkg = assemble_daily_report_package(
        session,
        payload=payload,
        run_assessments=run_v2_assessments,
        assessment_tasks=assessment_tasks,
        llm_client=llm_client,
        force=force_analyze,
    )
    payload["report_package"] = report_pkg.model_dump(mode="json")

    return payload


def render_daily_markdown(payload: dict[str, Any]) -> str:
    s = payload.get("sections") or {}
    summary = s.get("summary") or {}
    kpis = summary.get("kpis") or {}
    tone = s.get("tone") or {}
    coverage = s.get("coverage") or {}
    quality = s.get("quality") or {}
    nar = payload.get("narratives") or {}

    lines: list[str] = [
        f"# GNI Daily Brief（{payload.get('period')}）",
        "",
        f"**schema:** `{payload.get('schema_version')}` · **generator:** `{payload.get('generator')}`",
        "",
        f"> {payload.get('disclaimer')}",
        "",
        "## 1. Executive Summary",
        "",
        summary.get("judgment_text") or nar.get("executive") or summary.get("overview_text") or "",
        "",
        f"- 研判置信度: **{summary.get('confidence') or '—'}**",
        f"- 涉华文章: **{kpis.get('china_articles')}**",
        f"- 报道国家: **{kpis.get('reporting_countries')}**",
        f"- 报道媒体: **{kpis.get('reporting_sources')}**",
        f"- 新发现事件: **{kpis.get('new_events')}** · 高重要: **{kpis.get('major_events')}**",
        "",
        "### 今日值得关注",
        "",
    ]
    for ch in summary.get("top_changes") or []:
        lines.append(f"1. **{ch.get('title')}** — {ch.get('summary')}")

    v1 = s.get("v1_stats") or {}
    g = v1.get("global") or {}
    if g:
        def _pct(v: float | None) -> str:
            return f"{v * 100:.1f}%" if isinstance(v, (int, float)) else "—"

        lines += [
            "",
            "## V1.0 统计口径摘要（Article Count · published_at）",
            "",
            f"- 全球唯一涉华文章: **{g.get('article_count', 0)}** 篇 · "
            f"正面 {_pct(g.get('positive_rate'))} ({g.get('positive_count', 0)}) / "
            f"中性 {_pct(g.get('neutral_rate'))} ({g.get('neutral_count', 0)}) / "
            f"负面 {_pct(g.get('negative_rate'))} ({g.get('negative_count', 0)}) · "
            f"Unclassified {g.get('unclassified_count', 0)} · "
            f"立场判定覆盖率 **{_pct(g.get('stance_coverage_rate'))}**",
        ]
        boards = [b for b in (v1.get("boards") or []) if b.get("article_count", 0) > 0]
        if boards:
            b_txt = "；".join(f"{b.get('label_zh') or b.get('scope_id')} {b.get('article_count')} 篇" for b in boards)
            lines.append(f"- 四大板块（板块间允许重叠）: {b_txt}")
        topics = [t for t in (v1.get("topics") or []) if t.get("article_count", 0) > 0][:8]
        if topics:
            t_txt = "；".join(f"{t.get('label_zh') or t.get('scope_id')} {t.get('article_count')} 篇" for t in topics)
            lines.append(f"- 热门议题 Top: {t_txt}")

    lines += ["", "## 2. Major Events", ""]
    for i, ev in enumerate(s.get("major_events") or [], 1):
        lines.append(f"### 事件 {i:02d}：{ev.get('title')}")
        lines.append("")
        lines.append(ev.get("overview_text") or "")
        lines.append("")
        core = ev.get("core") or {}
        lines.append(
            f"- 主体/行动/对象: {core.get('actor')} / {core.get('action')} / {core.get('object')}"
        )
        cov = ev.get("coverage") or {}
        lines.append(
            f"- 覆盖: {cov.get('article_count')} 篇 · {cov.get('country_count')} 国 · "
            f"{cov.get('source_count')} 源"
        )
        lines.append(f"- event_time: {ev.get('event_time')} · first_seen: {ev.get('first_seen_at')}")
        lines.append(f"- 详情: `{ev.get('href')}`")
        for evi in (ev.get("evidence") or [])[:5]:
            lines.append(
                f"  - [{evi.get('country_id')}] {evi.get('title')} · "
                f"{evi.get('sentiment')}/{evi.get('stance')} · `{evi.get('article_id')}`"
            )
        lines.append("")
    lines += ["## 3. Global Coverage", "", coverage.get("note") or "", ""]
    if nar.get("coverage"):
        lines.append(f"*{nar['coverage']}*")
        lines.append("")
    lines.append("| 国家 | 涉华篇数 | 加权量 | 源数 |")
    lines.append("|------|----------|--------|------|")
    for r in coverage.get("by_country") or []:
        lines.append(
            f"| {r['country_id']} | {r['article_count']} | {r.get('weighted_volume')} | "
            f"{r.get('source_count')} |"
        )
    lines += ["", "**主议题**"]
    for t in coverage.get("topics_top") or []:
        lines.append(f"- {t['label']}: {t['count']} ({t['share']})")
    lines += ["", "**主框架**"]
    for t in coverage.get("frames_top") or []:
        lines.append(f"- {t['label']}: {t['count']} ({t['share']})")
    lines += ["", "## 4. Sentiment & Stance", "", tone.get("note") or "", ""]
    for row in tone.get("by_country") or []:
        lines.append(f"- {row.get('summary_text')}")
    lines += ["", "## 5. Emerging Signals", ""]
    for sig in s.get("signals") or []:
        lines.append(
            f"- [{sig.get('status')}] **{sig.get('title')}** — {sig.get('summary')}"
        )
    lines += ["", "## 6. Data Coverage Notes", ""]
    if nar.get("quality"):
        lines.append(f"*{nar['quality']}*")
        lines.append("")
    lines.append(f"- 分析积压: **{quality.get('missing_analysis')}**")
    lines.append(f"- 无样本国家: {quality.get('countries_without_sample')}")
    for note in quality.get("notes") or []:
        lines.append(f"- {note}")
    intel = payload.get("intelligence") or {}
    intel_tasks = intel.get("tasks") or {}
    if intel_tasks:
        lines += ["", "## Intelligence Narrative Analysis (LLM 解读层)", ""]
        lines.append(
            f"- 状态: `{intel.get('status')}` · 模型: `{', '.join((intel.get('meta') or {}).get('model_versions') or []) or '—'}`"
        )
        exec_t = intel_tasks.get("executive_analysis") or {}
        if exec_t.get("summary"):
            lines += ["", "### 综合研判（Executive Judgment）", "", exec_t["summary"], ""]
        if exec_t.get("important_changes"):
            lines.append("- 核心变化: " + "；".join(exec_t["important_changes"]))
        if exec_t.get("main_drivers"):
            lines.append("- 主要驱动: " + "；".join(exec_t["main_drivers"]))
        for f in exec_t.get("findings") or []:
            refs = ", ".join(
                f"{r.get('type')}:{r.get('ref_id')}" for r in (f.get("evidence_refs") or [])
            )
            lines.append(
                f"- **[{f.get('classification')}] {f.get('title')}** ({f.get('confidence')}): "
                f"{f.get('conclusion')} {f'(证据: `{refs}`)' if refs else ''}"
            )
        if exec_t.get("uncertainties"):
            lines.append("- 不确定性: " + "；".join(exec_t["uncertainties"]))
        if exec_t.get("follow_up_questions"):
            lines.append("- 待核查问题: " + "；".join(exec_t["follow_up_questions"]))
        ev_t = intel_tasks.get("event_analysis") or {}
        if ev_t.get("event_interpretations"):
            lines += ["", "### 重点事件深度解读", ""]
            for ei in ev_t["event_interpretations"]:
                lines.append(f"#### {ei.get('title')} (`{ei.get('event_id')}`)")
                if ei.get("what_happened"):
                    lines.append(f"- 发生了什么: {ei['what_happened']}")
                if ei.get("background"):
                    lines.append(f"- 背景: {ei['background']}")
                if ei.get("event_actual_changes") or ei.get("coverage_attention_changes"):
                    lines.append(
                        f"- 事件本体变化 vs 媒体关注变化: {ei.get('event_actual_changes') or '—'} / "
                        f"{ei.get('coverage_attention_changes') or '—'}"
                    )
                if ei.get("country_differences"):
                    lines.append(f"- 各国报道差异: {ei['country_differences']}")
                if ei.get("why_it_matters"):
                    lines.append(f"- 为什么值得关注: {ei['why_it_matters']}")
                if ei.get("what_to_monitor"):
                    lines.append(f"- 后续观察: {'；'.join(ei['what_to_monitor'])}")
                lines.append("")
        sig_t = intel_tasks.get("emerging_signals") or {}
        if sig_t.get("outlook_signals"):
            lines += ["", "### 异动解释与明日监测重点", ""]
            for osig in sig_t["outlook_signals"]:
                lines.append(
                    f"- **{osig.get('signal')}** ({osig.get('confidence')}): "
                    f"{osig.get('reasoning')} · 潜在触发: {osig.get('potential_trigger') or '—'} · "
                    f"不确定性: {osig.get('uncertainty') or '待观察'}"
                )
                if osig.get("what_to_monitor"):
                    lines.append(f"  - 监测指标: {'；'.join(osig['what_to_monitor'])}")

    val = payload.get("validation") or {}
    lines += ["", f"**validation.ok:** {val.get('ok')}", ""]
    return "\n".join(lines)


def write_daily_files(payload: dict[str, Any], *, out_dir: str | None = None) -> dict[str, str]:
    import json
    from pathlib import Path

    root = Path(out_dir) if out_dir else Path(__file__).resolve().parents[3] / "data"
    root.mkdir(parents=True, exist_ok=True)
    period = payload.get("period") or "unknown"
    md_path = root / f"daily_report_{period}.md"
    json_path = root / f"daily_report_{period}.json"
    md_path.write_text(render_daily_markdown(payload), encoding="utf-8")
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    return {"markdown": str(md_path), "json": str(json_path)}

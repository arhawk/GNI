"""Monthly Intelligence Report — rule assembly schema v1 (SPEC-aligned required chapters)."""

from __future__ import annotations

from collections import Counter, defaultdict
from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from gni.alerts.service import build_alerts_payload
from gni.analysis.stance_util import primary_stance_label
from gni.core.config import get_settings
from gni.events.service import list_events
from gni.infrastructure.models import Article, Source
from gni.metrics.definitions import CHINA_INCLUDE_LEVELS, METRIC_DEFINITION_VERSION
from gni.metrics.service import _latest_analyses
from gni.reports.weekly import _in_window, _source_bucket, _upsert_snapshot

SCHEMA_VERSION = "monthly_report_schema_v1"
DISCLAIMER = (
    "全球对华监测月报 · 按当前接入国/源统计报道结构与变化；"
    "禁止外推为国家立场或社会民意。"
)


def _tz() -> ZoneInfo:
    try:
        return ZoneInfo(get_settings().report_timezone or "Asia/Shanghai")
    except Exception:  # noqa: BLE001
        return ZoneInfo("Asia/Shanghai")


def _month_window(month: str | date | None = None) -> tuple[str, datetime, datetime, datetime, datetime]:
    """Return (YYYY-MM, start, end, prev_start, prev_end)."""
    tz = _tz()
    if isinstance(month, date):
        y, m = month.year, month.month
    elif isinstance(month, str) and month:
        y, m = (int(x) for x in month.split("-")[:2])
    else:
        now = datetime.now(tz).date()
        y, m = now.year, now.month
    last_day = monthrange(y, m)[1]
    start = datetime(y, m, 1, tzinfo=tz)
    end = datetime(y, m, last_day, tzinfo=tz) + timedelta(days=1)
    if m == 1:
        py, pm = y - 1, 12
    else:
        py, pm = y, m - 1
    p_last = monthrange(py, pm)[1]
    prev_start = datetime(py, pm, 1, tzinfo=tz)
    prev_end = datetime(py, pm, p_last, tzinfo=tz) + timedelta(days=1)
    return f"{y:04d}-{m:02d}", start, end, prev_start, prev_end


def build_monthly_report(
    session: Session,
    *,
    month: str | date | None = None,
    persist_snapshot: bool = True,
) -> dict[str, Any]:
    period, win_start, win_end, prev_start, prev_end = _month_window(month)
    sources = {s.id: s for s in session.scalars(select(Source)).all()}
    articles = list(session.scalars(select(Article)).all())
    analyses = _latest_analyses(session, [a.id for a in articles])

    def china_in(start: datetime, end: datetime) -> list[Article]:
        out = []
        for a in articles:
            if a.exclude_from_metrics:
                continue
            if a.china_relevance_level not in CHINA_INCLUDE_LEVELS:
                continue
            ts = a.published_at or a.first_seen_at
            if _in_window(ts, start, end):
                out.append(a)
        return out

    this_m = china_in(win_start, win_end)
    last_m = china_in(prev_start, prev_end)

    topic_this: Counter[str] = Counter()
    topic_last: Counter[str] = Counter()
    by_country: Counter[str] = Counter()
    by_bucket: Counter[str] = Counter()
    sent_by_country: dict[str, Counter[str]] = defaultdict(Counter)
    stance_by_country: dict[str, Counter[str]] = defaultdict(Counter)

    for a in this_m:
        src = sources.get(a.source_id)
        cid = src.country_id if src else "??"
        by_country[cid] += 1
        by_bucket[_source_bucket(src)] += 1
        structured = (analyses[a.id].structured_result if a.id in analyses else None) or {}
        topics = structured.get("topics") or {}
        primary_t = topics.get("primary") if isinstance(topics, dict) else None
        if isinstance(primary_t, str):
            topic_this[primary_t] += 1
        if src and src.feed_scope != "GOVERNMENT_RELEASES":
            sentiment = structured.get("sentiment") or {}
            lab = sentiment.get("label") if isinstance(sentiment, dict) else None
            if lab in {"positive", "negative", "neutral", "mixed"}:
                sent_by_country[cid][lab] += 1
            sl = primary_stance_label(structured)
            if sl != "unknown":
                stance_by_country[cid][sl] += 1

    for a in last_m:
        structured = (analyses[a.id].structured_result if a.id in analyses else None) or {}
        topics = structured.get("topics") or {}
        primary_t = topics.get("primary") if isinstance(topics, dict) else None
        if isinstance(primary_t, str):
            topic_last[primary_t] += 1

    topic_mom = []
    for t in sorted(set(topic_this) | set(topic_last), key=lambda x: -topic_this.get(x, 0)):
        cur, prev = topic_this.get(t, 0), topic_last.get(t, 0)
        topic_mom.append({"topic": t, "this_month": cur, "last_month": prev, "delta": cur - prev})

    events = list_events(session, limit=100)
    major = []
    for e in events:
        major.append(
            {
                "id": e.get("id"),
                "title": e.get("title"),
                "status": e.get("status"),
                "importance_score": e.get("importance_score"),
                "article_count": e.get("article_count"),
                "href": f"/events/{e.get('id')}",
            }
        )
    major.sort(key=lambda x: -(x.get("importance_score") or 0))
    major = major[:15]

    try:
        alerts = build_alerts_payload(session, window_start=win_start, window_end=win_end)
        signals = (alerts.get("intelligence") or [])[:12]
    except Exception:  # noqa: BLE001
        signals = []

    overview = (
        f"{period} 监测月涉华报道 {len(this_m)} 篇（上月 {len(last_m)}，"
        f"Δ {len(this_m) - len(last_m)}）；来源分区见 summary.source_buckets。"
        f"格局判断基于当前接入覆盖，随接入扩展而更新。"
    )

    payload: dict[str, Any] = {
        "report_type": "monthly",
        "schema_version": SCHEMA_VERSION,
        "period": period,
        "period_start": win_start.isoformat(),
        "period_end": win_end.isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "disclaimer": DISCLAIMER,
        "metric_definition_version": METRIC_DEFINITION_VERSION,
        "generator": "rule_monthly_v1",
        "article_count": len(this_m),
        "sections": {
            "summary": {
                "overview_text": overview,
                "kpis": {
                    "china_articles": len(this_m),
                    "prev_month_articles": len(last_m),
                    "delta": len(this_m) - len(last_m),
                    "reporting_countries": len(by_country),
                    "major_events": len(major),
                },
                "source_buckets": dict(by_bucket),
                "outlook": "规则 v1 不提供预测分数；持续关注环比上升主题与跨国框架差异。",
            },
            "major_events": major,
            "topic_trends": topic_mom[:20],
            "cross_country_narrative": {
                "by_country_volume": dict(by_country),
                "note": "同事件框架对比细节见事件页；月报汇总国家报道量。",
            },
            "sentiment_stance": {
                "by_country_sentiment": {c: dict(cnt) for c, cnt in sent_by_country.items()},
                "by_country_stance": {c: dict(cnt) for c, cnt in stance_by_country.items()},
                "note": "媒体情感主栏不含 GOVERNMENT_RELEASES。",
            },
            "signals": signals,
            "quality": {
                "window": period,
                "notes": [DISCLAIMER, "Story 仍为 hash MVP，见 docs/STORY_MODEL.md。"],
            },
        },
        "narratives": {
            "executive": overview,
            "outlook": "见 summary.outlook；禁止把样本写成全球舆论。",
        },
    }

    if persist_snapshot:
        _upsert_snapshot(session, "monthly", period, SCHEMA_VERSION, payload)
    return payload

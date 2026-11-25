"""Weekly Intelligence Report — rule assembly schema v1 (SPEC-aligned required chapters)."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from gni.alerts.service import build_alerts_payload
from gni.analysis.stance_util import primary_stance_label
from gni.core.config import get_settings
from gni.events.service import list_events
from gni.infrastructure.models import Article, ReportSnapshot, Source
from gni.metrics.definitions import CHINA_INCLUDE_LEVELS, METRIC_DEFINITION_VERSION
from gni.metrics.service import _latest_analyses

SCHEMA_VERSION = "weekly_report_schema_v1"
DISCLAIMER = (
    "本周报基于 MVP 五国监测样本（官媒/公服/政府传播），"
    "不等于全球舆论或国家立场。Unique Story Count 为 hash MVP。"
)


def _tz() -> ZoneInfo:
    try:
        return ZoneInfo(get_settings().report_timezone or "Asia/Shanghai")
    except Exception:  # noqa: BLE001
        return ZoneInfo("Asia/Shanghai")


def _aware(t: datetime | None) -> datetime | None:
    if t is None:
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def _week_window(end_day: date | None = None) -> tuple[date, datetime, datetime, date, datetime, datetime]:
    """Return (week_end_date, win_start, win_end, prev_end_date, prev_start, prev_end)."""
    tz = _tz()
    today = end_day or datetime.now(tz).date()
    # Week ending on `today` (inclusive), 7 calendar days
    week_start_date = today - timedelta(days=6)
    win_start = datetime(week_start_date.year, week_start_date.month, week_start_date.day, tzinfo=tz)
    win_end = datetime(today.year, today.month, today.day, tzinfo=tz) + timedelta(days=1)
    prev_end_date = week_start_date - timedelta(days=1)
    prev_start_date = prev_end_date - timedelta(days=6)
    prev_start = datetime(
        prev_start_date.year, prev_start_date.month, prev_start_date.day, tzinfo=tz
    )
    prev_end = win_start
    return today, win_start, win_end, prev_end_date, prev_start, prev_end


def _in_window(ts: datetime | None, start: datetime, end: datetime) -> bool:
    t = _aware(ts)
    if t is None:
        return False
    return start <= t.astimezone(start.tzinfo) < end


def _source_bucket(src: Source | None) -> str:
    if not src:
        return "unknown"
    scope = (src.feed_scope or "").upper()
    if scope == "GOVERNMENT_RELEASES":
        return "government_comms"
    ownership = (src.ownership_type or "").lower()
    ctrl = (src.government_control_level or "").lower()
    if ownership in {"public", "public_law"} or ctrl == "low":
        return "public_service"
    if ctrl in {"high", "medium"} or ownership in {"government", "state"}:
        return "state_controlled"
    return "other"


def build_weekly_report(
    session: Session,
    *,
    end_day: date | str | None = None,
    persist_snapshot: bool = True,
) -> dict[str, Any]:
    if isinstance(end_day, str):
        end_day = date.fromisoformat(end_day)
    week_end, win_start, win_end, prev_label, prev_start, prev_end = _week_window(end_day)

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

    this_week = china_in(win_start, win_end)
    last_week = china_in(prev_start, prev_end)

    topic_this: Counter[str] = Counter()
    topic_last: Counter[str] = Counter()
    frame_this: Counter[str] = Counter()
    sent_by_country: dict[str, Counter[str]] = defaultdict(Counter)
    stance_by_country: dict[str, Counter[str]] = defaultdict(Counter)
    by_country: Counter[str] = Counter()
    by_bucket: Counter[str] = Counter()

    for a in this_week:
        src = sources.get(a.source_id)
        cid = src.country_id if src else "??"
        by_country[cid] += 1
        by_bucket[_source_bucket(src)] += 1
        structured = (analyses[a.id].structured_result if a.id in analyses else None) or {}
        topics = structured.get("topics") or {}
        framing = structured.get("framing") or {}
        sentiment = structured.get("sentiment") or {}
        primary_t = topics.get("primary") if isinstance(topics, dict) else None
        primary_f = framing.get("primary") if isinstance(framing, dict) else None
        if isinstance(primary_t, str):
            topic_this[primary_t] += 1
        if isinstance(primary_f, str):
            frame_this[primary_f] += 1
        if src and src.feed_scope != "GOVERNMENT_RELEASES":
            lab = sentiment.get("label") if isinstance(sentiment, dict) else None
            if lab in {"positive", "negative", "neutral", "mixed"}:
                sent_by_country[cid][lab] += 1
            sl = primary_stance_label(structured)
            if sl != "unknown":
                stance_by_country[cid][sl] += 1

    for a in last_week:
        structured = (analyses[a.id].structured_result if a.id in analyses else None) or {}
        topics = structured.get("topics") or {}
        primary_t = topics.get("primary") if isinstance(topics, dict) else None
        if isinstance(primary_t, str):
            topic_last[primary_t] += 1

    topic_trends = []
    all_topics = set(topic_this) | set(topic_last)
    for t in sorted(all_topics, key=lambda x: -topic_this.get(x, 0)):
        cur, prev = topic_this.get(t, 0), topic_last.get(t, 0)
        if prev == 0 and cur > 0:
            status = "new"
        elif cur == 0 and prev > 0:
            status = "fading"
        elif cur > prev:
            status = "rising"
        elif cur < prev:
            status = "falling"
        else:
            status = "stable"
        topic_trends.append(
            {"topic": t, "this_week": cur, "last_week": prev, "delta": cur - prev, "status": status}
        )

    events = list_events(session, limit=80)
    major = []
    for e in events:
        fs = e.get("first_seen_at") or e.get("window_start") or e.get("updated_at")
        try:
            edt = datetime.fromisoformat(str(fs).replace("Z", "+00:00")) if fs else None
        except ValueError:
            edt = None
        if edt and not _in_window(edt, win_start - timedelta(days=14), win_end):
            continue
        major.append(
            {
                "id": e.get("id"),
                "title": e.get("title"),
                "status": e.get("status"),
                "importance_score": e.get("importance_score"),
                "article_count": e.get("article_count"),
                "actor_key": e.get("actor_key"),
                "action_key": e.get("action_key"),
                "first_seen_at": e.get("first_seen_at"),
                "href": f"/events/{e.get('id')}",
            }
        )
    major.sort(key=lambda x: -(x.get("importance_score") or 0))
    major = major[:12]

    evolution = [
        {
            "event_id": m["id"],
            "title": m["title"],
            "event_change_note": "规则 v1：事件本体变化需人工/后续时间线；此处列本周相关事件卡。",
            "coverage_focus_note": f"关联报道约 {m.get('article_count') or 0} 篇。",
            "first_seen_at": m.get("first_seen_at"),
        }
        for m in major[:5]
    ]

    # Cross-country frames for top topics
    cross = []
    for topic, _ in topic_this.most_common(3):
        frames_by_c: dict[str, Counter[str]] = defaultdict(Counter)
        for a in this_week:
            structured = (analyses[a.id].structured_result if a.id in analyses else None) or {}
            topics = structured.get("topics") or {}
            if (topics.get("primary") if isinstance(topics, dict) else None) != topic:
                continue
            src = sources.get(a.source_id)
            cid = src.country_id if src else "??"
            framing = structured.get("framing") or {}
            pf = framing.get("primary") if isinstance(framing, dict) else None
            if isinstance(pf, str):
                frames_by_c[cid][pf] += 1
        cross.append(
            {
                "topic": topic,
                "by_country": {
                    c: [{"frame": f, "count": n} for f, n in cnt.most_common(3)]
                    for c, cnt in frames_by_c.items()
                },
            }
        )

    try:
        alerts = build_alerts_payload(session, window_start=win_start, window_end=win_end)
        signals = (alerts.get("intelligence") or [])[:10]
    except Exception:  # noqa: BLE001
        signals = []

    overview = (
        f"监测周（至 {week_end.isoformat()}）涉华报道 {len(this_week)} 篇"
        f"（上周同期 {len(last_week)}，Δ {len(this_week) - len(last_week)}）；"
        f"覆盖约 {len(by_country)} 国。主题与情感见分章；样本非全球舆论。"
    )

    payload: dict[str, Any] = {
        "report_type": "weekly",
        "schema_version": SCHEMA_VERSION,
        "period": f"{(week_end - timedelta(days=6)).isoformat()}_{week_end.isoformat()}",
        "period_start": win_start.isoformat(),
        "period_end": win_end.isoformat(),
        "prev_period_end": prev_label.isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "disclaimer": DISCLAIMER,
        "metric_definition_version": METRIC_DEFINITION_VERSION,
        "generator": "rule_weekly_v1",
        "article_count": len(this_week),
        "sections": {
            "summary": {
                "overview_text": overview,
                "kpis": {
                    "china_articles": len(this_week),
                    "prev_week_articles": len(last_week),
                    "delta": len(this_week) - len(last_week),
                    "reporting_countries": len(by_country),
                    "major_events": len(major),
                },
                "top_changes": topic_trends[:5],
                "source_buckets": dict(by_bucket),
            },
            "major_events": major,
            "event_evolution": evolution,
            "cross_country_narrative": cross,
            "topic_trends": topic_trends[:15],
            "sentiment_stance": {
                "by_country_sentiment": {c: dict(cnt) for c, cnt in sent_by_country.items()},
                "by_country_stance": {c: dict(cnt) for c, cnt in stance_by_country.items()},
                "note": "政府传播源已排除出媒体情感主统计；立场按 Target 绑定。",
            },
            "signals": signals,
            "quality": {
                "window_days": 7,
                "notes": [
                    "规则组装 schema v1；无 Sankey/社媒曲线。",
                    DISCLAIMER,
                ],
            },
        },
        "narratives": {
            "executive": overview,
            "topics": "主题环比见 Topic Trends；量变≠态度变。",
            "signals": f"本周情报信号 {len(signals)} 条。",
        },
    }

    if persist_snapshot:
        _upsert_snapshot(session, "weekly", payload["period"], SCHEMA_VERSION, payload)
    return payload


def _upsert_snapshot(
    session: Session,
    report_type: str,
    period: str,
    schema_version: str,
    payload: dict[str, Any],
) -> None:
    existing = session.scalar(
        select(ReportSnapshot).where(
            ReportSnapshot.report_type == report_type,
            ReportSnapshot.period == period,
        ).limit(1)
    )
    if existing:
        existing.payload = payload
        existing.schema_version = schema_version
    else:
        session.add(
            ReportSnapshot(
                id=str(uuid4()),
                report_type=report_type,
                period=period,
                schema_version=schema_version,
                payload=payload,
            )
        )
    session.flush()

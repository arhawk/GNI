"""Weekly Intelligence Report — rule assembly schema v1 + V1.0 stats + LLM Intelligence Layer."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from gni.alerts.service import build_alerts_payload
from gni.analysis.stance_util import extract_v1_china_stance, primary_stance_label
from gni.core.config import get_settings
from gni.events.service import list_events
from gni.infrastructure.models import Article, Event, EventArticle, ReportSnapshot, Source
from gni.metrics.definitions import (
    CHINA_INCLUDE_LEVELS,
    METHODOLOGY_VERSION,
    METRIC_DEFINITION_VERSION,
    TAXONOMY_V1_VERSION,
)
from gni.metrics.service import _latest_analyses, run_v1_stat_snapshots
from gni.reports.validate import validate_weekly_report

SCHEMA_VERSION = "weekly_report_schema_v1"
DISCLAIMER = (
    "全球对华监测周报 · 遵循 GNI 统计口径 V1.0（methodology_v1.0）："
    "以唯一文章数（Article Count）为基础单位，按 published_at 与信源所属国家统计；"
    "对华立场三分类不含 Unclassified 分母并同步披露立场判定覆盖率。"
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


def _fmt_pct(rate: float | None) -> float | None:
    return round(float(rate) * 100.0, 1) if isinstance(rate, (int, float)) else None


def build_weekly_report(
    session: Session,
    *,
    end_day: date | str | None = None,
    persist_snapshot: bool = True,
    analyze: bool = False,
    analyze_tasks: list[str] | None = None,
    force_analyze: bool = False,
    llm_client: Any = None,
) -> dict[str, Any]:
    if isinstance(end_day, str):
        end_day = date.fromisoformat(end_day)
    week_end, win_start, win_end, prev_label, prev_start, prev_end = _week_window(end_day)

    sources = {s.id: s for s in session.scalars(select(Source)).all()}
    articles = list(session.scalars(select(Article)).all())
    articles_by_id = {a.id: a for a in articles}
    analyses = _latest_analyses(session, [a.id for a in articles])

    def china_in(start: datetime, end: datetime) -> list[Article]:
        out = []
        for a in articles:
            if a.exclude_from_metrics:
                continue
            if a.china_relevance_level not in CHINA_INCLUDE_LEVELS:
                continue
            if _in_window(a.published_at, start, end):
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

    events = list_events(
        session,
        limit=80,
        window_start=win_start - timedelta(days=14),
        window_end=win_end + timedelta(days=1),
    )
    ev_ids_all = [e["id"] for e in events if e.get("id")]
    db_events = {
        ev.id: ev for ev in session.scalars(select(Event).where(Event.id.in_(ev_ids_all))).all()
    } if ev_ids_all else {}
    links_by_eid: dict[str, list[str]] = defaultdict(list)
    if ev_ids_all:
        for lk in session.scalars(select(EventArticle).where(EventArticle.event_id.in_(ev_ids_all))).all():
            links_by_eid[lk.event_id].append(lk.article_id)

    major = []
    for e in events:
        eid = e.get("id")
        if not eid:
            continue
        ev_obj = db_events.get(eid)
        linked_ids = links_by_eid.get(eid) or []
        ev_articles = [articles_by_id[aid] for aid in linked_ids if aid in articles_by_id]
        this_w_arts = [a for a in ev_articles if _in_window(a.published_at, win_start, win_end)]
        prev_w_arts = [a for a in ev_articles if _in_window(a.published_at, prev_start, prev_end)]

        fs = e.get("first_seen_at") or e.get("window_start") or e.get("updated_at")
        try:
            edt = datetime.fromisoformat(str(fs).replace("Z", "+00:00")) if fs else None
        except ValueError:
            edt = None
        if not this_w_arts and edt and not _in_window(edt, win_start - timedelta(days=14), win_end):
            continue

        countries_set: set[str] = set()
        sources_set: set[str] = set()
        first_by_country: dict[str, str] = {}
        evidence_rows: list[dict[str, Any]] = []
        for art in sorted(
            ev_articles,
            key=lambda a: (_aware(a.published_at) or datetime.min.replace(tzinfo=timezone.utc)),
        ):
            src = sources.get(art.source_id)
            cid = src.country_id if src else None
            if cid:
                countries_set.add(cid)
                if art.published_at and cid not in first_by_country:
                    first_by_country[cid] = art.published_at.isoformat()
            sources_set.add(art.source_id)
            ana = analyses.get(art.id)
            structured = (ana.structured_result if ana else None) or {}
            sver = ana.schema_version if ana else None
            evidence_rows.append(
                {
                    "article_id": art.id,
                    "title": art.title,
                    "country_id": cid,
                    "source_id": art.source_id,
                    "url": art.url,
                    "published_at": art.published_at.isoformat() if art.published_at else None,
                    "stance_label": extract_v1_china_stance(structured, schema_version=sver),
                    "framing": (structured.get("framing") or {}).get("primary")
                    if isinstance(structured.get("framing"), dict)
                    else None,
                }
            )

        major.append(
            {
                "id": eid,
                "event_id": eid,
                "title": e.get("title"),
                "status": e.get("status"),
                "importance_score": e.get("importance_score"),
                "article_count": len(ev_articles) or e.get("article_count") or 0,
                "this_week_articles": len(this_w_arts),
                "prev_week_articles": len(prev_w_arts),
                "actor_key": ev_obj.actor_key if ev_obj else e.get("actor_key"),
                "action_key": ev_obj.action_key if ev_obj else e.get("action_key"),
                "object_key": ev_obj.object_key if ev_obj else None,
                "event_time": ev_obj.event_time.isoformat() if ev_obj and ev_obj.event_time else e.get("event_time"),
                "first_seen_at": e.get("first_seen_at"),
                "coverage": {
                    "article_count": len(ev_articles) or e.get("article_count") or 0,
                    "country_count": len(countries_set),
                    "source_count": len(sources_set),
                    "countries": sorted(countries_set),
                },
                "country_first_reported_at": first_by_country,
                "evidence": evidence_rows[-10:][::-1],
                "href": f"/events/{eid}",
            }
        )
    major.sort(
        key=lambda x: (
            -(x.get("this_week_articles") or 0),
            -(x.get("importance_score") or 0),
            -(x.get("article_count") or 0),
        )
    )
    major = major[:12]

    evolution = [
        {
            "event_id": m["id"],
            "title": m["title"],
            "event_time": m.get("event_time"),
            "first_seen_at": m.get("first_seen_at"),
            "this_week_articles": m.get("this_week_articles", 0),
            "prev_week_articles": m.get("prev_week_articles", 0),
            "countries": (m.get("coverage") or {}).get("countries") or [],
            "country_first_reported_at": m.get("country_first_reported_at") or {},
            "event_change_note": "事件本体变化需结合时间线与 LLM 事件演化分析；此处列确定性报道增量与国别跟进时间。",
            "coverage_focus_note": (
                f"本周关联报道 {m.get('this_week_articles', 0)} 篇"
                f"（上周 {m.get('prev_week_articles', 0)} 篇，累计 {m.get('article_count') or 0} 篇，"
                f"覆盖 {(m.get('coverage') or {}).get('country_count', 0)} 国）。"
            ),
        }
        for m in major[:6]
    ]

    # Cross-country frames for top topics
    cross = []
    for topic, _ in topic_this.most_common(4):
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

    v1_this = run_v1_stat_snapshots(
        session, period_start=win_start, period_end=win_end, persist=False
    )
    v1_prev = run_v1_stat_snapshots(
        session, period_start=prev_start, period_end=prev_end, persist=False
    )

    # 4-week rolling deterministic V1.0 history (honest about missing weeks)
    historical_v1_stats: list[dict[str, Any]] = []
    for offset in range(3, -1, -1):
        hs = win_start - timedelta(days=7 * offset)
        he = win_end - timedelta(days=7 * offset)
        if offset == 0:
            g = (v1_this["by_scope"] or {}).get("global") or {}
        elif offset == 1:
            g = (v1_prev["by_scope"] or {}).get("global") or {}
        else:
            hsnap = run_v1_stat_snapshots(
                session, period_start=hs, period_end=he, persist=False, include_zero_taxonomy=False
            )
            g = (hsnap["by_scope"] or {}).get("global") or {}
        historical_v1_stats.append(
            {
                "label": f"{hs.date().isoformat()}~{(he - timedelta(days=1)).date().isoformat()}",
                "article_count": int(g.get("article_count") or 0),
                "positive_pct": _fmt_pct(g.get("positive_rate")),
                "neutral_pct": _fmt_pct(g.get("neutral_rate")),
                "negative_pct": _fmt_pct(g.get("negative_rate")),
                "stance_coverage_pct": _fmt_pct(g.get("stance_coverage_rate")),
            }
        )

    payload: dict[str, Any] = {
        "report_type": "weekly",
        "schema_version": SCHEMA_VERSION,
        "methodology_version": METHODOLOGY_VERSION,
        "taxonomy_version": TAXONOMY_V1_VERSION,
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
            "v1_stats": v1_this["by_scope"],
            "v1_stats_prev": v1_prev["by_scope"],
            "historical_v1_stats": historical_v1_stats,
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
                "weeks_with_history": sum(1 for w in historical_v1_stats if w["article_count"] > 0),
                "notes": [
                    "规则确定性统计 + 可选 LLM 情报解读层；无社媒公众兴趣曲线。",
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

    from gni.reports.narrative.runner import (
        load_cached_intelligence,
        run_report_intelligence,
    )

    if analyze:
        payload["intelligence"] = run_report_intelligence(
            session,
            report_type="weekly",
            period=payload["period"],
            payload=payload,
            tasks=analyze_tasks,
            force=force_analyze,
            llm_client=llm_client,
        )
    else:
        payload["intelligence"] = load_cached_intelligence(
            session,
            report_type="weekly",
            period=payload["period"],
            payload=payload,
        )

    if (payload["intelligence"].get("meta") or {}).get("completed_tasks", 0) > 0:
        payload["generator"] = "rule_weekly_v1+llm_intelligence"

    payload["validation"] = validate_weekly_report(payload)

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


def render_weekly_markdown(payload: dict[str, Any]) -> str:
    """Render Weekly Intelligence Report to readable Markdown (LLM conclusions first)."""
    s = payload.get("sections") or {}
    intel = payload.get("intelligence") or {}
    tasks = intel.get("tasks") or {}
    exec_t = tasks.get("executive_analysis") or {}
    lines: list[str] = [
        f"# GNI Weekly Intelligence Report（{payload.get('period')}）",
        "",
        f"**schema:** `{payload.get('schema_version')}` · **generator:** `{payload.get('generator')}`",
        "",
        f"> {payload.get('disclaimer')}",
        "",
        "## 1. 周度综合研判（Weekly Executive Summary）",
        "",
        exec_t.get("summary") or (s.get("summary") or {}).get("overview_text") or "",
        "",
    ]
    for f in exec_t.get("findings") or []:
        lines.append(f"- **[{f.get('classification')}] {f.get('title')}** ({f.get('confidence')}): {f.get('conclusion')}")
    if s.get("historical_v1_stats"):
        lines += ["", "## 2. 近 4 周文章级重算序列", "", "| 周期 | 唯一文章数 | 正面% | 中性% | 负面% | 覆盖率% |", "|------|------------|-------|-------|-------|---------|"]
        for row in s["historical_v1_stats"]:
            lines.append(
                f"| {row.get('label')} | {row.get('article_count')} | {row.get('positive_pct')} | "
                f"{row.get('neutral_pct')} | {row.get('negative_pct')} | {row.get('stance_coverage_pct')} |"
            )
    ev_t = tasks.get("event_analysis") or {}
    if ev_t.get("event_interpretations"):
        lines += ["", "## 3. 重点事件演化分析", ""]
        for ei in ev_t["event_interpretations"]:
            lines.append(f"### {ei.get('title')} (`{ei.get('event_id')}`)")
            if ei.get("event_actual_changes"):
                lines.append(f"- 事件本体变化: {ei['event_actual_changes']}")
            if ei.get("coverage_attention_changes"):
                lines.append(f"- 媒体关注变化: {ei['coverage_attention_changes']}")
            if ei.get("country_differences"):
                lines.append(f"- 各国报道差异: {ei['country_differences']}")
            lines.append("")
    sig_t = tasks.get("emerging_signals") or {}
    if sig_t.get("outlook_signals"):
        lines += ["", "## 4. 新兴风险信号与下周监测重点", ""]
        for osig in sig_t["outlook_signals"]:
            lines.append(f"- **{osig.get('signal')}** ({osig.get('confidence')}): {osig.get('reasoning')}")
    lines += ["", f"**validation.ok:** {(payload.get('validation') or {}).get('ok')}", ""]
    return "\n".join(lines)

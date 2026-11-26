"""Monthly Intelligence Report — article-level recomputed V1.0 stats + LLM Intelligence Layer."""

from __future__ import annotations

from calendar import monthrange
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from gni.alerts.service import build_alerts_payload
from gni.analysis.stance_util import (
    extract_v1_boards,
    extract_v1_china_stance,
    extract_v1_topics,
    primary_stance_label,
)
from gni.core.config import get_settings
from gni.events.service import list_events
from gni.infrastructure.models import Article, Event, EventArticle, Source
from gni.metrics.definitions import (
    CHINA_INCLUDE_LEVELS,
    METHODOLOGY_VERSION,
    METRIC_DEFINITION_VERSION,
    TAXONOMY_V1_VERSION,
)
from gni.metrics.service import _latest_analyses, run_v1_stat_snapshots
from gni.reports.validate import validate_monthly_report
from gni.reports.weekly import _aware, _fmt_pct, _in_window, _source_bucket, _upsert_snapshot

SCHEMA_VERSION = "monthly_report_schema_v1"
DISCLAIMER = (
    "全球对华监测月报 · 遵循 GNI 统计口径 V1.0（methodology_v1.0）："
    "以唯一文章数（Article Count）为基础单位，按 published_at 与信源所属国家文章级重算；"
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
    analyze: bool = False,
    analyze_tasks: list[str] | None = None,
    force_analyze: bool = False,
    llm_client: Any = None,
) -> dict[str, Any]:
    period, win_start, win_end, prev_start, prev_end = _month_window(month)
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

    this_m = china_in(win_start, win_end)
    last_m = china_in(prev_start, prev_end)

    topic_this: Counter[str] = Counter()
    topic_last: Counter[str] = Counter()
    frame_this: Counter[str] = Counter()
    frame_last: Counter[str] = Counter()
    by_country: Counter[str] = Counter()
    by_bucket: Counter[str] = Counter()
    sent_by_country: dict[str, Counter[str]] = defaultdict(Counter)
    stance_by_country: dict[str, Counter[str]] = defaultdict(Counter)
    country_frames: dict[str, Counter[str]] = defaultdict(Counter)
    country_topics_v1: dict[str, Counter[str]] = defaultdict(Counter)
    country_boards_v1: dict[str, Counter[str]] = defaultdict(Counter)

    for a in this_m:
        src = sources.get(a.source_id)
        cid = src.country_id if src else "??"
        by_country[cid] += 1
        by_bucket[_source_bucket(src)] += 1
        ana = analyses.get(a.id)
        structured = (ana.structured_result if ana else None) or {}
        sver = ana.schema_version if ana else None
        topics = structured.get("topics") or {}
        framing = structured.get("framing") or {}
        primary_t = topics.get("primary") if isinstance(topics, dict) else None
        primary_f = framing.get("primary") if isinstance(framing, dict) else None
        if isinstance(primary_t, str):
            topic_this[primary_t] += 1
        if isinstance(primary_f, str):
            frame_this[primary_f] += 1
            country_frames[cid][primary_f] += 1
        for tid in extract_v1_topics(structured, schema_version=sver):
            country_topics_v1[cid][tid] += 1
        for bid in extract_v1_boards(structured, schema_version=sver):
            country_boards_v1[cid][bid] += 1
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
        framing = structured.get("framing") or {}
        primary_t = topics.get("primary") if isinstance(topics, dict) else None
        primary_f = framing.get("primary") if isinstance(framing, dict) else None
        if isinstance(primary_t, str):
            topic_last[primary_t] += 1
        if isinstance(primary_f, str):
            frame_last[primary_f] += 1

    topic_mom = []
    for t in sorted(set(topic_this) | set(topic_last), key=lambda x: -topic_this.get(x, 0)):
        cur, prev = topic_this.get(t, 0), topic_last.get(t, 0)
        topic_mom.append({"topic": t, "this_month": cur, "last_month": prev, "delta": cur - prev})

    # Month-window filtered events with full retrospective evidence
    events = list_events(
        session,
        limit=120,
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
        month_arts = [a for a in ev_articles if _in_window(a.published_at, win_start, win_end)]

        ev_time = ev_obj.event_time if ev_obj else None
        ev_created = ev_obj.created_at if ev_obj else None
        touched = bool(month_arts) or _in_window(ev_time, win_start, win_end) or _in_window(ev_created, win_start, win_end)
        if not touched:
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
                "this_month_articles": len(month_arts),
                "actor_key": ev_obj.actor_key if ev_obj else e.get("actor_key"),
                "action_key": ev_obj.action_key if ev_obj else e.get("action_key"),
                "object_key": ev_obj.object_key if ev_obj else None,
                "event_time": ev_time.isoformat() if ev_time else e.get("event_time"),
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
            -(x.get("this_month_articles") or 0),
            -(x.get("importance_score") or 0),
            -(x.get("article_count") or 0),
        )
    )
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

    v1_this = run_v1_stat_snapshots(
        session, period_start=win_start, period_end=win_end, persist=False
    )
    v1_prev = run_v1_stat_snapshots(
        session, period_start=prev_start, period_end=prev_end, persist=False
    )

    # Article-level recomputed 6-month historical sequence (never merge weekly summaries)
    tz = _tz()
    cur_y, cur_m = win_start.year, win_start.month
    month_tuples: list[tuple[int, int]] = []
    yy, mm = cur_y, cur_m
    for _ in range(6):
        month_tuples.append((yy, mm))
        if mm == 1:
            yy, mm = yy - 1, 12
        else:
            mm -= 1
    month_tuples.reverse()

    historical_v1_stats: list[dict[str, Any]] = []
    for my, mmo in month_tuples:
        mlabel = f"{my:04d}-{mmo:02d}"
        if my == cur_y and mmo == cur_m:
            g = (v1_this["by_scope"] or {}).get("global") or {}
        elif my == prev_start.year and mmo == prev_start.month:
            g = (v1_prev["by_scope"] or {}).get("global") or {}
        else:
            last_d = monthrange(my, mmo)[1]
            ms = datetime(my, mmo, 1, tzinfo=tz)
            me = datetime(my, mmo, last_d, tzinfo=tz) + timedelta(days=1)
            hsnap = run_v1_stat_snapshots(
                session, period_start=ms, period_end=me, persist=False, include_zero_taxonomy=False
            )
            g = (hsnap["by_scope"] or {}).get("global") or {}
        historical_v1_stats.append(
            {
                "month": mlabel,
                "article_count": int(g.get("article_count") or 0),
                "positive_pct": _fmt_pct(g.get("positive_rate")),
                "neutral_pct": _fmt_pct(g.get("neutral_rate")),
                "negative_pct": _fmt_pct(g.get("negative_rate")),
                "stance_coverage_pct": _fmt_pct(g.get("stance_coverage_rate")),
            }
        )

    # Deterministic country profiles (monitored media profiles, NOT official state positions)
    prev_c_map = {
        r.get("scope_id"): r
        for r in ((v1_prev["by_scope"] or {}).get("countries") or [])
        if isinstance(r, dict)
    }
    country_profiles: list[dict[str, Any]] = []
    for c_row in (v1_this["by_scope"] or {}).get("countries") or []:
        cid = str(c_row.get("scope_id") or "")
        prev_c = prev_c_map.get(cid)
        cur_n = int(c_row.get("article_count") or 0)
        prev_n = int(prev_c.get("article_count") or 0) if isinstance(prev_c, dict) else 0
        country_profiles.append(
            {
                "country_id": cid,
                "article_count": cur_n,
                "prev_month_count": prev_n,
                "delta": cur_n - prev_n,
                "positive_rate": c_row.get("positive_rate"),
                "neutral_rate": c_row.get("neutral_rate"),
                "negative_rate": c_row.get("negative_rate"),
                "stance_coverage_rate": c_row.get("stance_coverage_rate"),
                "sample_sufficient": cur_n >= 3,
                "top_boards": [
                    {"board_id": k, "count": v}
                    for k, v in country_boards_v1.get(cid, Counter()).most_common(4)
                ],
                "top_topics": [
                    {"topic_id": k, "count": v}
                    for k, v in country_topics_v1.get(cid, Counter()).most_common(5)
                ],
                "top_frames": [
                    {"frame": k, "count": v}
                    for k, v in country_frames.get(cid, Counter()).most_common(4)
                ],
            }
        )

    # Deterministic narrative landscape (dominant / emerging / fading frames)
    dominant_frames = [{"frame": k, "count": v} for k, v in frame_this.most_common(8)]
    emerging_frames = [
        {"frame": k, "this_month": frame_this[k], "last_month": frame_last.get(k, 0)}
        for k in frame_this
        if frame_this[k] > frame_last.get(k, 0)
    ]
    emerging_frames.sort(key=lambda x: -(x["this_month"] - x["last_month"]))
    fading_frames = [
        {"frame": k, "this_month": frame_this.get(k, 0), "last_month": frame_last[k]}
        for k in frame_last
        if frame_last[k] > frame_this.get(k, 0)
    ]
    fading_frames.sort(key=lambda x: -(x["last_month"] - x["this_month"]))
    narrative_landscape = {
        "dominant_frames": dominant_frames,
        "emerging_frames": emerging_frames[:6],
        "fading_frames": fading_frames[:6],
        "by_country_frames": {
            c: [{"frame": f, "count": n} for f, n in cnt.most_common(4)]
            for c, cnt in country_frames.items()
        },
        "note": "仅统计框架出现次数，不代表叙事强度综合分。",
    }

    months_with_history = sum(1 for row in historical_v1_stats if row["article_count"] > 0)
    missing_months = [row["month"] for row in historical_v1_stats if row["article_count"] == 0]

    payload: dict[str, Any] = {
        "report_type": "monthly",
        "schema_version": SCHEMA_VERSION,
        "methodology_version": METHODOLOGY_VERSION,
        "taxonomy_version": TAXONOMY_V1_VERSION,
        "period": period,
        "period_start": win_start.isoformat(),
        "period_end": win_end.isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "disclaimer": DISCLAIMER,
        "metric_definition_version": METRIC_DEFINITION_VERSION,
        "generator": "rule_monthly_v1",
        "article_count": len(this_m),
        "sections": {
            "v1_stats": v1_this["by_scope"],
            "v1_stats_prev": v1_prev["by_scope"],
            "historical_v1_stats": historical_v1_stats,
            "country_profiles": country_profiles,
            "narrative_landscape": narrative_landscape,
            "summary": {
                "overview_text": overview,
                "kpis": {
                    "china_articles": len(this_m),
                    "prev_month_articles": len(last_m),
                    "delta": len(this_m) - len(last_m),
                    "reporting_countries": len(by_country),
                    "major_events": len(major),
                    "months_with_history": months_with_history,
                },
                "source_buckets": dict(by_bucket),
                "outlook": "规则基线不提供预测分数；结构性展望见 LLM 战略信号与条件性展望模块。",
            },
            "major_events": major,
            "topic_trends": topic_mom[:20],
            "cross_country_narrative": {
                "by_country_volume": dict(by_country),
                "by_country_frames": narrative_landscape["by_country_frames"],
                "note": "国别媒体画像与框架对比基于当月文章级数据重算，非国家官方立场。",
            },
            "sentiment_stance": {
                "by_country_sentiment": {c: dict(cnt) for c, cnt in sent_by_country.items()},
                "by_country_stance": {c: dict(cnt) for c, cnt in stance_by_country.items()},
                "note": "媒体情感主栏不含 GOVERNMENT_RELEASES。",
            },
            "signals": signals,
            "quality": {
                "window": period,
                "months_with_history": months_with_history,
                "missing_months": missing_months,
                "notes": [
                    DISCLAIMER,
                    (
                        f"近6个月窗口内有数据月份：{months_with_history}/6"
                        + (f"（缺失：{', '.join(missing_months)}，缺失月份不伪装成趋势）" if missing_months else "")
                    ),
                ],
            },
        },
        "narratives": {
            "executive": overview,
            "outlook": "见 summary.outlook 与 LLM 条件性展望；禁止把样本写成全球舆论。",
        },
    }

    from gni.reports.narrative.runner import (
        load_cached_intelligence,
        run_report_intelligence,
    )

    if analyze:
        payload["intelligence"] = run_report_intelligence(
            session,
            report_type="monthly",
            period=period,
            payload=payload,
            tasks=analyze_tasks,
            force=force_analyze,
            llm_client=llm_client,
        )
    else:
        payload["intelligence"] = load_cached_intelligence(
            session,
            report_type="monthly",
            period=period,
            payload=payload,
        )

    if (payload["intelligence"].get("meta") or {}).get("completed_tasks", 0) > 0:
        payload["generator"] = "rule_monthly_v1+llm_intelligence"

    payload["validation"] = validate_monthly_report(payload)

    if persist_snapshot:
        _upsert_snapshot(session, "monthly", period, SCHEMA_VERSION, payload)
    return payload


def render_monthly_markdown(payload: dict[str, Any]) -> str:
    """Render Monthly Strategic Review to readable Markdown (LLM conclusions first)."""
    s = payload.get("sections") or {}
    intel = payload.get("intelligence") or {}
    tasks = intel.get("tasks") or {}
    exec_t = tasks.get("executive_analysis") or {}
    lines: list[str] = [
        f"# GNI Monthly Strategic Review（{payload.get('period')}）",
        "",
        f"**schema:** `{payload.get('schema_version')}` · **generator:** `{payload.get('generator')}`",
        "",
        f"> {payload.get('disclaimer')}",
        "",
        "## 1. 月度战略总评（Monthly Executive Assessment）",
        "",
        exec_t.get("summary") or (s.get("summary") or {}).get("overview_text") or "",
        "",
    ]
    for f in exec_t.get("findings") or []:
        lines.append(f"- **[{f.get('classification')}] {f.get('title')}** ({f.get('confidence')}): {f.get('conclusion')}")
    if s.get("historical_v1_stats"):
        lines += ["", "## 2. 近 6 个月文章级重算序列", "", "| 月份 | 唯一文章数 | 正面% | 中性% | 负面% | 覆盖率% |", "|------|------------|-------|-------|-------|---------|"]
        for row in s["historical_v1_stats"]:
            lines.append(
                f"| {row.get('month')} | {row.get('article_count')} | {row.get('positive_pct')} | "
                f"{row.get('neutral_pct')} | {row.get('negative_pct')} | {row.get('stance_coverage_pct')} |"
            )
    ev_t = tasks.get("event_analysis") or {}
    if ev_t.get("event_interpretations"):
        lines += ["", "## 3. 月度重大事件回顾", ""]
        for ei in ev_t["event_interpretations"]:
            lines.append(f"### {ei.get('title')} (`{ei.get('event_id')}`)")
            if ei.get("what_happened"):
                lines.append(f"- 过程与影响: {ei['what_happened']}")
            if ei.get("why_it_matters"):
                lines.append(f"- 战略意义: {ei['why_it_matters']}")
            lines.append("")
    sig_t = tasks.get("emerging_signals") or {}
    if sig_t.get("outlook_signals"):
        lines += ["", "## 4. 战略风险信号与下月条件性展望", ""]
        for osig in sig_t["outlook_signals"]:
            lines.append(f"- **{osig.get('signal')}** ({osig.get('confidence')}): {osig.get('reasoning')}")
    lines += ["", f"**validation.ok:** {(payload.get('validation') or {}).get('ok')}", ""]
    return "\n".join(lines)

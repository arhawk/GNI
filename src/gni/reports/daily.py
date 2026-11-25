"""Daily Intelligence Brief: daily_report_schema_v2 (rule facts + optional LLM narratives)."""

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
    METRIC_DEFINITION_VERSION,
    RELEVANCE_WEIGHT_VERSION,
)
from gni.metrics.service import _latest_analyses
from gni.reports.validate import validate_daily_report

MONITOR_DEFAULT = ["US", "RU", "DE", "IN", "AU"]
SCHEMA_VERSION = "daily_report_schema_v2"
DISCLAIMER = (
    "被监测官媒/公共传播样本的对华报道表现；"
    "不等于国家官方立场，也不等于该国社会民意或全民舆论。"
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
    t = _aware(a.published_at or a.first_seen_at)
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


def _stance_label(structured: dict[str, Any]) -> str:
    stances = structured.get("stances") or []
    if stances and isinstance(stances[0], dict):
        raw = (stances[0].get("stance") or "unknown").strip().lower()
        return raw or "unknown"
    return "unknown"


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
    ds = _dominant(sent) or "unknown"
    dst = _dominant(stance) or "unknown"
    return (
        f"{cid} 被监测媒体样本（n={n}）：情感以「{SENT_ZH.get(ds, ds)}」为主，"
        f"对华相关立场标签以「{STANCE_ZH.get(dst, dst)}」居多；情感与立场分列，非国家官方立场。"
    )


def _event_overview(title: str, cov: dict[str, Any], imp: float | None) -> str:
    imp_s = f"{imp:.2f}" if imp is not None else "—"
    return (
        f"「{title}」· 重要性 {imp_s} · "
        f"关联文章 {cov.get('article_count', 0)} 篇、"
        f"{cov.get('country_count', 0)} 国、{cov.get('source_count', 0)} 源。"
    )


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
) -> dict[str, Any]:
    countries = country_scope or list(MONITOR_DEFAULT)
    sources = {s.id: s for s in session.scalars(select(Source)).all()}
    articles = list(
        session.scalars(select(Article).where(Article.exclude_from_metrics.is_(False))).all()
    )

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

    # Tone aggregates
    sent_overall: Counter[str] = Counter()
    stance_overall: Counter[str] = Counter()
    topic_overall: Counter[str] = Counter()
    frame_overall: Counter[str] = Counter()
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
        sl = _norm_sentiment((structured.get("sentiment") or {}).get("label"))
        st = _stance_label(structured)
        tp = _topic_primary(structured)
        fr = _frame_primary(structured)
        sent_overall[sl] += 1
        stance_overall[st] += 1
        if tp:
            topic_overall[str(tp)] += 1
        if fr:
            frame_overall[str(fr)] += 1
        if cid in by_country_tone:
            by_country_tone[cid]["sentiment_counts"][sl] += 1
            by_country_tone[cid]["stance_counts"][st] += 1
            by_country_tone[cid]["n"] += 1

    tone_by_country: list[dict[str, Any]] = []
    for cid in countries:
        blob = by_country_tone[cid]
        sc = dict(blob["sentiment_counts"])
        stc = dict(blob["stance_counts"])
        n = int(blob["n"])
        tone_by_country.append(
            {
                "country_id": cid,
                "n": n,
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
    raw_events = list_events(session, limit=40)
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
            sl = _norm_sentiment((structured.get("sentiment") or {}).get("label"))
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
        major_events.append(
            {
                "event_id": eid,
                "title": e["title"],
                "importance_score": imp,
                "event_type": e.get("event_type"),
                "event_time": event_time.isoformat() if event_time else e.get("event_time"),
                "first_seen_at": first_seen.isoformat() if first_seen else None,
                "status": e.get("status"),
                "overview_text": _event_overview(e["title"], cov, imp),
                "core": {
                    "actor": (ev_obj.actor_key if ev_obj else None),
                    "action": (ev_obj.action_key if ev_obj else None),
                    "object": (ev_obj.object_key if ev_obj else None),
                    "target": "china",
                    "status": e.get("status"),
                },
                "coverage": cov,
                "by_country_views": by_country_views,
                "follow_ups": follow_ups,
                "evidence": evidence[:12],
                "href": f"/events/{eid}",
            }
        )

    major_events.sort(
        key=lambda x: (
            -(x.get("importance_score") or 0),
            -((x.get("coverage") or {}).get("country_count") or 0),
            -((x.get("coverage") or {}).get("article_count") or 0),
        )
    )
    major_events = major_events[:12]
    high_major = sum(1 for m in major_events if (m.get("importance_score") or 0) >= 0.7)

    # New events first_seen today
    new_events_n = 0
    for m in major_events:
        fs = m.get("first_seen_at")
        if not fs:
            continue
        try:
            fdt = datetime.fromisoformat(str(fs).replace("Z", "+00:00"))
            if win_start <= fdt < win_end:
                new_events_n += 1
        except ValueError:
            pass

    # Signals from alert engine (intelligence only)
    signals: list[dict[str, Any]] = []
    try:
        alerts = build_alerts_payload(session)
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
    overview_text = (
        f"监测范围内今日涉华报道 {china_n} 篇（昨日 {yesterday_china}，"
        f"{'↑' if delta_y > 0 else '↓' if delta_y < 0 else '→'}{abs(delta_y)}；"
        f"近 7 日日均 {week_avg}），覆盖约 {len(reporting_countries)} 个国家、"
        f"{len(reporting_sources)} 家媒体；"
        f"列表内重大/相关事件 {len(major_events)} 个（高重要 {high_major}，"
        f"当日新发现约 {new_events_n}）。"
        f"情感与立场见分国摘要；结论仅基于被监测官媒样本。"
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

    payload: dict[str, Any] = {
        "report_type": "daily",
        "schema_version": SCHEMA_VERSION,
        "period": report_day.isoformat(),
        "period_start": win_start.isoformat(),
        "period_end": win_end.isoformat(),
        "timezone": str(_tz()),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "country_scope": countries,
        "target_scope": "china",
        "disclaimer": DISCLAIMER,
        "metric_definition_version": METRIC_DEFINITION_VERSION,
        "relevance_weight_version": RELEVANCE_WEIGHT_VERSION,
        "generator": "rule_brief_v2",
        "article_count": china_n,
        "event_count": len(major_events),
        "sections": {
            "summary": {
                "kpis": {
                    "china_articles": china_n,
                    "reporting_countries": len(reporting_countries),
                    "reporting_sources": len(reporting_sources),
                    "new_events": new_events_n,
                    "major_events": high_major,
                    "day_articles": len(day_articles),
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
            },
            "major_events": major_events,
            "coverage": {
                "by_country": coverage_by_country,
                "by_source": by_source,
                "topics_top": _top_n(topic_overall, 8),
                "frames_top": _top_n(frame_overall, 8),
                "note": "Article Count 与 Weighted Volume 分列；加权不替代实际篇数。",
            },
            "tone": {
                "overall_sentiment_counts": dict(sent_overall),
                "overall_stance_counts": dict(stance_overall),
                "by_country": tone_by_country,
                "note": "情感描述语气，立场绑定对华相关 Target；引述≠媒体自身立场；无综合总分。",
            },
            "signals": signals,
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
                    "系统运行告警见异常与预警页 B 栏，不混入舆情信号主栏。",
                ],
            },
        },
        "narratives": {
            "executive": overview_text,
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
            "tone": "见分国情感/立场摘要；勿外推为国家立场。",
            "signals": f"情报信号 {len(signals)} 条，默认 needs_review。",
            "quality": f"分析积压 {missing}；无样本国家 {countries_without_sample or '无'}。",
        },
    }

    payload["validation"] = validate_daily_report(payload)

    if polish:
        from gni.reports.polish import polish_daily_narratives

        polished = polish_daily_narratives(payload)
        if polished:
            if polished.get("executive"):
                payload["sections"]["summary"]["overview_text"] = polished["executive"]
            payload["narratives"].update(polished)
            payload["generator"] = "rule_brief_v2+llm_narratives"
            payload["polish"] = {"applied": True}
            payload["validation"] = validate_daily_report(payload)
        else:
            payload["polish"] = {"applied": False, "reason": "llm_unavailable_or_rejected"}

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
        summary.get("overview_text") or nar.get("executive") or "",
        "",
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

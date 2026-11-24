"""Daily report: fixed 7-section schema (rule numbers + optional LLM narratives)."""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from gni.core.config import get_settings
from gni.events.service import list_events
from gni.infrastructure.models import Article, EventArticle, Source, SourceHealth
from gni.metrics.definitions import (
    CHINA_INCLUDE_LEVELS,
    METRIC_DEFINITION_VERSION,
    RELEVANCE_WEIGHT_VERSION,
)
from gni.metrics.service import _latest_analyses, run_metrics

MONITOR_DEFAULT = ["US", "RU", "DE", "IN", "AU"]
SCHEMA_VERSION = "daily_report_schema_v1"
DISCLAIMER = (
    "被监测官媒/公共传播样本的对华报道表现；"
    "不等于国家官方立场，也不等于该国社会民意或全民舆论。"
)


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


def _rule_narratives(payload: dict[str, Any]) -> dict[str, str]:
    """Deterministic one-liners from counts (no LLM)."""
    tone = (payload.get("sections") or {}).get("tone") or {}
    by_c = tone.get("by_country") or {}
    # dominant sentiment country among those with samples
    best = None
    best_n = -1
    for cid, blob in by_c.items():
        sc = blob.get("sentiment_counts") or {}
        n = sum(sc.values())
        if n > best_n:
            best_n = n
            dom = max(sc.items(), key=lambda x: x[1])[0] if sc else "unknown"
            best = (cid, dom, n)
    tone_line = (
        f"样本最多的国家为 {best[0]}（n={best[2]}），主导情感标签为 {best[1]}；情感与立场分列，未合成对华总分。"
        if best and best_n > 0
        else "本窗尚无足够分国情感样本，勿外推。"
    )

    agenda = (payload.get("sections") or {}).get("agenda") or {}
    tops = agenda.get("topics_top") or []
    frames = agenda.get("frames_top") or []
    agenda_line = (
        f"主议题首位「{tops[0]['label']}」（{tops[0]['count']}），"
        f"主框架首位「{frames[0]['label']}」（{frames[0]['count']}）。"
        if tops and frames
        else "议题/框架样本不足，仅列出可得标签。"
    )

    att = (payload.get("sections") or {}).get("attention") or {}
    missing = att.get("missing_analysis")
    att_line = (
        f"对华相关约 {att.get('china_article_count')} 篇；"
        f"关注占比 {att.get('attention_share')}；"
        f"分析积压 {missing}，结论仅基于已分析样本。"
    )

    return {
        "attention": att_line,
        "tone": tone_line,
        "agenda": agenda_line,
        "events": "以下事件按时间倒序；每条挂文章证据，用于解释关注与语气变化。",
        "quality": "质量缺口与舆情结论分区；无样本国家不推断态度。",
    }


def build_daily_report(
    session: Session,
    *,
    day: date | str | None = None,
    country_scope: list[str] | None = None,
    polish: bool = False,
) -> dict[str, Any]:
    report_day = resolve_report_day(day)
    countries = country_scope or list(MONITOR_DEFAULT)
    day_start, day_end = shanghai_day_window(report_day)
    now = datetime.now(timezone.utc)
    # Primary analytic window: calendar day in report TZ
    win_start, win_end = day_start, day_end

    sources = {s.id: s for s in session.scalars(select(Source)).all()}
    articles = list(
        session.scalars(select(Article).where(Article.exclude_from_metrics.is_(False))).all()
    )
    day_articles = [a for a in articles if _in_range(a, win_start, win_end)]

    # §2 coverage
    coverage: list[dict[str, Any]] = []
    countries_without_sample: list[str] = []
    for cid in countries:
        src_ids = {sid for sid, s in sources.items() if s.country_id == cid}
        day_c = [a for a in day_articles if a.source_id in src_ids]
        analyzed = sum(1 for a in day_c if a.analysis_status == "completed")
        china_n = sum(
            1
            for a in day_c
            if (a.china_relevance_level or "") in CHINA_INCLUDE_LEVELS
        )
        coverage.append(
            {
                "country_id": cid,
                "article_count": len(day_c),
                "analyzed_count": analyzed,
                "china_article_count": china_n,
                "source_count": len(src_ids),
            }
        )
        if china_n == 0 and analyzed == 0:
            countries_without_sample.append(cid)

    china_day = [
        a
        for a in day_articles
        if (a.china_relevance_level or "") in CHINA_INCLUDE_LEVELS
    ]
    analyses = _latest_analyses(session, [a.id for a in day_articles if a.analysis_status == "completed"])

    # §3 / §4 aggregates on china-included + analyzed
    sent_overall: Counter[str] = Counter()
    stance_overall: Counter[str] = Counter()
    topic_overall: Counter[str] = Counter()
    frame_overall: Counter[str] = Counter()
    by_country_tone: dict[str, dict[str, Any]] = {
        c: {
            "sentiment_counts": Counter(),
            "stance_counts": Counter(),
            "analyzed_china": 0,
        }
        for c in countries
    }
    by_country_agenda: dict[str, dict[str, Counter[str]]] = {
        c: {"topics": Counter(), "frames": Counter()} for c in countries
    }

    china_analyzed_rows: list[tuple[Article, dict[str, Any], str]] = []
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
            by_country_tone[cid]["analyzed_china"] += 1
            if tp:
                by_country_agenda[cid]["topics"][str(tp)] += 1
            if fr:
                by_country_agenda[cid]["frames"][str(fr)] += 1
        china_analyzed_rows.append((a, structured, cid))

    tone_by_country_out = {}
    for cid, blob in by_country_tone.items():
        tone_by_country_out[cid] = {
            "analyzed_china": blob["analyzed_china"],
            "sentiment_counts": dict(blob["sentiment_counts"]),
            "stance_counts": dict(blob["stance_counts"]),
        }

    agenda_by_country_out = {
        cid: {
            "topics_top": _top_n(blob["topics"], 5),
            "frames_top": _top_n(blob["frames"], 5),
        }
        for cid, blob in by_country_agenda.items()
    }

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

    metrics_blob: dict[str, Any] = {}
    attention_share = None
    article_count_metric = None
    try:
        run = run_metrics(session, days=1, target="china", timezone_name="Asia/Shanghai")
        metrics_blob = {"metric_run_id": run.id, "status": run.status}
        research = (run.results or {}).get("research") or {}
        attention_share = (research.get("attention_share") or {}).get("value")
        article_count_metric = (research.get("article_count") or {}).get("value")
        metrics_blob["research_snippet"] = {
            "article_count": article_count_metric,
            "attention_share": attention_share,
            "sentiment_distribution": (research.get("sentiment_distribution") or {}).get("value"),
            "stance_distribution": (research.get("stance_distribution") or {}).get("value"),
            "topic_share": (research.get("topic_share") or {}).get("value"),
            "frame_distribution": (research.get("frame_distribution") or {}).get("value"),
        }
    except Exception as exc:  # noqa: BLE001
        metrics_blob = {"error": str(exc)}

    # §5 events
    events = list_events(session, limit=25)
    event_blocks: list[dict[str, Any]] = []
    for e in events[:15]:
        links = list(
            session.scalars(select(EventArticle).where(EventArticle.event_id == e["id"])).all()
        )
        evidence = []
        countries_reporting: set[str] = set()
        for link in links[:8]:
            art = session.get(Article, link.article_id)
            if not art:
                continue
            src = sources.get(art.source_id)
            cid = src.country_id if src else None
            if cid:
                countries_reporting.add(cid)
            structured = (
                (analyses[art.id].structured_result if art.id in analyses else None) or {}
            )
            # load analysis if missing from day set
            if art.id not in analyses:
                more = _latest_analyses(session, [art.id])
                analyses.update(more)
                structured = (analyses[art.id].structured_result if art.id in analyses else None) or {}
            evidence.append(
                {
                    "article_id": art.id,
                    "title": art.title,
                    "country_id": cid,
                    "source_id": art.source_id,
                    "url": art.url,
                    "sentiment": _norm_sentiment(
                        (structured.get("sentiment") or {}).get("label")
                    ),
                    "stance": _stance_label(structured),
                    "published_at": (_aware(art.published_at or art.first_seen_at) or datetime.min.replace(tzinfo=timezone.utc)).isoformat(),
                }
            )
        first_seen = None
        if evidence:
            first_seen = min(x["published_at"] for x in evidence)
        event_blocks.append(
            {
                "event_id": e["id"],
                "title": e["title"],
                "event_time": e.get("event_time") or e.get("sort_time") or e.get("window_end"),
                "article_count": e.get("article_count") or len(evidence),
                "reporting_countries": sorted(countries_reporting),
                "multi_source": len(countries_reporting) >= 2 or len(evidence) >= 2,
                "first_seen_at": first_seen,
                "evidence": evidence,
            }
        )

    # §6 evidence per country 3–5
    evidence_by_country: dict[str, list[dict[str, Any]]] = {c: [] for c in countries}
    # prefer china analyzed, else any analyzed that day
    ranked = sorted(
        china_analyzed_rows,
        key=lambda row: _aware(row[0].published_at or row[0].first_seen_at)
        or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    for a, structured, cid in ranked:
        if cid not in evidence_by_country:
            continue
        if len(evidence_by_country[cid]) >= 5:
            continue
        evidence_by_country[cid].append(
            {
                "article_id": a.id,
                "title": a.title,
                "url": a.url,
                "source_id": a.source_id,
                "relevance": a.china_relevance_level,
                "sentiment": _norm_sentiment((structured.get("sentiment") or {}).get("label")),
                "stance": _stance_label(structured),
                "topic": _topic_primary(structured),
                "frame": _frame_primary(structured),
            }
        )
    # pad with non-china day titles if empty
    for cid in countries:
        if evidence_by_country[cid]:
            continue
        src_ids = {sid for sid, s in sources.items() if s.country_id == cid}
        for a in sorted(
            [x for x in day_articles if x.source_id in src_ids],
            key=lambda x: _aware(x.published_at or x.first_seen_at)
            or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )[:3]:
            evidence_by_country[cid].append(
                {
                    "article_id": a.id,
                    "title": a.title,
                    "url": a.url,
                    "source_id": a.source_id,
                    "relevance": a.china_relevance_level,
                    "sentiment": None,
                    "stance": None,
                    "topic": None,
                    "frame": None,
                    "note": "title_sample_not_in_china_set",
                }
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
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "country_scope": countries,
        "target_scope": "china",
        "disclaimer": DISCLAIMER,
        "metric_definition_version": METRIC_DEFINITION_VERSION,
        "relevance_weight_version": RELEVANCE_WEIGHT_VERSION,
        "generator": "rule_template_v1",
        "sections": {
            "attention": {
                "window_start": win_start.isoformat(),
                "window_end": win_end.isoformat(),
                "china_article_count": len(china_day),
                "article_count_metric": article_count_metric,
                "attention_share": attention_share,
                "day_article_count": len(day_articles),
                "coverage_by_country": coverage,
                "missing_analysis": missing,
                "metrics": metrics_blob,
            },
            "tone": {
                "overall_sentiment_counts": dict(sent_overall),
                "overall_stance_counts": dict(stance_overall),
                "by_country": tone_by_country_out,
                "note": "Sentiment and stance are separate tables; no composite China score.",
            },
            "agenda": {
                "topics_top": _top_n(topic_overall, 8),
                "frames_top": _top_n(frame_overall, 8),
                "by_country": agenda_by_country_out,
            },
            "events": event_blocks,
            "evidence": evidence_by_country,
            "quality": {
                "missing_analysis": missing,
                "countries_without_sample": countries_without_sample,
                "source_health": health_rows,
                "notes": [
                    "Rule-assembled facts; optional LLM only polishes narratives.",
                    "RSS latest-N ≠ full calendar-day corpus.",
                    f"Pending/failed analysis queue ≈ {missing}.",
                    "Disconnected sources are out of coverage this round.",
                ],
            },
        },
    }
    payload["narratives"] = _rule_narratives(payload)

    if polish:
        from gni.reports.polish import polish_daily_narratives

        polished = polish_daily_narratives(payload)
        if polished:
            payload["narratives"].update(polished)
            payload["generator"] = "rule_template_v1+llm_narratives"
            payload["polish"] = {"applied": True}
        else:
            payload["polish"] = {"applied": False, "reason": "llm_unavailable_or_rejected"}

    return payload


def render_daily_markdown(payload: dict[str, Any]) -> str:
    s = payload.get("sections") or {}
    nar = payload.get("narratives") or {}
    att = s.get("attention") or {}
    tone = s.get("tone") or {}
    agenda = s.get("agenda") or {}
    quality = s.get("quality") or {}

    lines: list[str] = []
    lines.append(f"# GNI 对华舆情日报（{payload.get('period')}）")
    lines.append("")
    lines.append(f"**schema:** `{payload.get('schema_version')}` · **generator:** `{payload.get('generator')}`")
    lines.append("")
    lines.append("## 1. 口径")
    lines.append("")
    lines.append(f"> {payload.get('disclaimer')}")
    lines.append("")
    lines.append("## 2. 今日对华关注")
    lines.append("")
    if nar.get("attention"):
        lines.append(f"*{nar['attention']}*")
        lines.append("")
    lines.append(f"- 对华相关篇数: **{att.get('china_article_count')}**")
    lines.append(f"- 关注占比 (Attention Share): {att.get('attention_share')}")
    lines.append(f"- 当日全部采集篇数: {att.get('day_article_count')}")
    lines.append(f"- 分析积压 (pending/failed): **{att.get('missing_analysis')}**")
    lines.append("")
    lines.append("| 国家 | 当日篇数 | 已分析 | 涉华纳入 | 源数 |")
    lines.append("|------|----------|--------|----------|------|")
    for row in att.get("coverage_by_country") or []:
        lines.append(
            f"| {row['country_id']} | {row['article_count']} | {row['analyzed_count']} | "
            f"{row.get('china_article_count', 0)} | {row.get('source_count', 0)} |"
        )
    lines.append("")
    lines.append("## 3. 语气与立场（分国）")
    lines.append("")
    lines.append(f"> {(tone.get('note') or '')}")
    if nar.get("tone"):
        lines.append("")
        lines.append(f"*{nar['tone']}*")
    lines.append("")
    lines.append("### 情感分布（分国）")
    lines.append("")
    lines.append("| 国家 | 已分析涉华 | positive | neutral | negative | mixed | unknown |")
    lines.append("|------|------------|----------|---------|----------|-------|---------|")
    for cid in payload.get("country_scope") or []:
        blob = (tone.get("by_country") or {}).get(cid) or {}
        sc = blob.get("sentiment_counts") or {}
        lines.append(
            f"| {cid} | {blob.get('analyzed_china', 0)} | {sc.get('positive', 0)} | "
            f"{sc.get('neutral', 0)} | {sc.get('negative', 0)} | {sc.get('mixed', 0)} | "
            f"{sc.get('unknown', 0)} |"
        )
    lines.append("")
    lines.append("### 立场分布（分国，与情感分列）")
    lines.append("")
    lines.append("| 国家 | 立场计数 (raw) |")
    lines.append("|------|----------------|")
    for cid in payload.get("country_scope") or []:
        blob = (tone.get("by_country") or {}).get(cid) or {}
        lines.append(f"| {cid} | {blob.get('stance_counts') or {}} |")
    lines.append("")
    lines.append("## 4. 议题与说法")
    lines.append("")
    if nar.get("agenda"):
        lines.append(f"*{nar['agenda']}*")
        lines.append("")
    lines.append("**主议题 Top**")
    for t in agenda.get("topics_top") or []:
        lines.append(f"- {t['label']}: {t['count']} ({t['share']})")
    lines.append("")
    lines.append("**主框架 Top**")
    for t in agenda.get("frames_top") or []:
        lines.append(f"- {t['label']}: {t['count']} ({t['share']})")
    lines.append("")
    lines.append("## 5. 事件主线（解释为什么变）")
    lines.append("")
    if nar.get("events"):
        lines.append(f"*{nar['events']}*")
        lines.append("")
    for ev in s.get("events") or []:
        multi = "多源" if ev.get("multi_source") else "单源"
        lines.append(
            f"- **{ev.get('title')}** (`{ev.get('event_id')}`) · {ev.get('event_time')} · "
            f"{multi} · countries={ev.get('reporting_countries')}"
        )
        for evi in ev.get("evidence") or []:
            lines.append(
                f"  - [{evi.get('country_id')}] {evi.get('title')} · "
                f"sentiment={evi.get('sentiment')} stance={evi.get('stance')} · "
                f"`{evi.get('article_id')}`"
            )
    lines.append("")
    lines.append("## 6. 代表证据（每国 ≤5，Fact 绑 article_id）")
    lines.append("")
    for cid, rows in (s.get("evidence") or {}).items():
        lines.append(f"### {cid}")
        if not rows:
            lines.append("- （无样本）")
            continue
        for a in rows:
            lines.append(
                f"- {a.get('title')} · `{a.get('article_id')}` · "
                f"sentiment={a.get('sentiment')} stance={a.get('stance')} "
                f"topic={a.get('topic')} frame={a.get('frame')}"
            )
            if a.get("url"):
                lines.append(f"  - {a['url']}")
    lines.append("")
    lines.append("## 7. 质量与限制")
    lines.append("")
    if nar.get("quality"):
        lines.append(f"*{nar['quality']}*")
        lines.append("")
    lines.append(f"- 分析积压: **{quality.get('missing_analysis')}**")
    lines.append(f"- 无涉华分析样本的国家: {quality.get('countries_without_sample')}")
    for note in quality.get("notes") or []:
        lines.append(f"- {note}")
    lines.append("")
    lines.append("### 源健康（摘录）")
    lines.append("")
    lines.append("| source_id | success | failure | error |")
    lines.append("|-----------|---------|---------|-------|")
    for h in (quality.get("source_health") or [])[:20]:
        err = (h.get("last_error") or "")[:40].replace("|", "/")
        lines.append(
            f"| `{h.get('source_id')}` | {h.get('success_count')} | "
            f"{h.get('failure_count')} | {err} |"
        )
    lines.append("")
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

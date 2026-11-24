"""Rule-template daily report (JSON + optional markdown). No LLM polish."""

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


def build_daily_report(
    session: Session,
    *,
    day: date | str | None = None,
    country_scope: list[str] | None = None,
) -> dict[str, Any]:
    report_day = resolve_report_day(day)
    countries = country_scope or list(MONITOR_DEFAULT)
    day_start, day_end = shanghai_day_window(report_day)
    # Rolling 24h ending now (aligned with prior template) + calendar-day coverage
    now = datetime.now(timezone.utc)
    roll_start = now - timedelta(hours=24)

    sources = {s.id: s for s in session.scalars(select(Source)).all()}
    articles = list(
        session.scalars(
            select(Article).where(
                Article.exclude_from_metrics.is_(False),
            )
        ).all()
    )

    def in_range(a: Article, start: datetime, end: datetime) -> bool:
        t = a.published_at or a.first_seen_at
        if not t:
            return False
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        return start <= t < end

    day_articles = [a for a in articles if in_range(a, day_start, day_end)]
    roll_articles = [a for a in articles if in_range(a, roll_start, now)]

    coverage: list[dict[str, Any]] = []
    title_samples: dict[str, list[dict[str, Any]]] = {c: [] for c in countries}
    for cid in countries:
        src_ids = {sid for sid, s in sources.items() if s.country_id == cid}
        day_c = [a for a in day_articles if a.source_id in src_ids]
        analyzed = sum(1 for a in day_c if a.analysis_status == "completed")
        coverage.append(
            {
                "country_id": cid,
                "article_count": len(day_c),
                "analyzed_count": analyzed,
            }
        )
        for a in sorted(
            day_c,
            key=lambda x: x.published_at or x.first_seen_at or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )[:8]:
            title_samples[cid].append(
                {
                    "title": a.title,
                    "source_id": a.source_id,
                    "url": a.url,
                    "article_id": a.id,
                }
            )

    china_roll = [
        a
        for a in roll_articles
        if (a.china_relevance_level or "") in CHINA_INCLUDE_LEVELS
    ]
    analyses = _latest_analyses(session, [a.id for a in china_roll])
    china_rows: list[dict[str, Any]] = []
    sent_counts: Counter[str] = Counter()
    for a in china_roll[:40]:
        src = sources.get(a.source_id)
        structured = (analyses[a.id].structured_result if a.id in analyses else None) or {}
        sentiment = (structured.get("sentiment") or {}).get("label")
        stances = structured.get("stances") or []
        stance = None
        if stances and isinstance(stances[0], dict):
            stance = stances[0].get("stance")
        if sentiment:
            sent_counts[str(sentiment).lower()] += 1
        china_rows.append(
            {
                "country_id": (src.country_id if src else None) or "UNK",
                "relevance": a.china_relevance_level,
                "title": a.title,
                "article_id": a.id,
                "sentiment": sentiment,
                "stance": stance,
                "summary": (structured.get("summary") or structured.get("article_summary") or None),
                "url": a.url,
            }
        )

    missing = session.scalar(
        select(func.count())
        .select_from(Article)
        .where(
            Article.exclude_from_metrics.is_(False),
            Article.processing_status == "done",
            Article.analysis_status.in_(["pending", "failed"]),
        )
    ) or 0

    # Metrics snapshot (best-effort)
    metrics_blob: dict[str, Any] = {}
    try:
        run = run_metrics(session, days=1, target="china", timezone_name="Asia/Shanghai")
        metrics_blob = {
            "metric_run_id": run.id,
            "status": run.status,
            "results": run.results,
        }
    except Exception as exc:  # noqa: BLE001
        metrics_blob = {"error": str(exc)}

    events = list_events(session, limit=20)
    event_blocks: list[dict[str, Any]] = []
    for e in events[:12]:
        links = list(
            session.scalars(select(EventArticle).where(EventArticle.event_id == e["id"])).all()
        )
        evidence = []
        for link in links[:5]:
            art = session.get(Article, link.article_id)
            if not art:
                continue
            src = sources.get(art.source_id)
            evidence.append(
                {
                    "article_id": art.id,
                    "title": art.title,
                    "country_id": src.country_id if src else None,
                    "url": art.url,
                }
            )
        event_blocks.append(
            {
                "event_id": e["id"],
                "title": e["title"],
                "event_time": e.get("event_time") or e.get("sort_time") or e.get("window_end"),
                "article_count": e.get("article_count") or 0,
                "evidence": evidence,
            }
        )

    health_rows = []
    for h in session.scalars(select(SourceHealth).limit(40)).all():
        health_rows.append(
            {
                "source_id": h.source_id,
                "success_count": h.success_count,
                "failure_count": h.failure_count,
                "last_error": h.error_message,
            }
        )

    research = ((metrics_blob.get("results") or {}).get("research") or {}) if isinstance(
        metrics_blob.get("results"), dict
    ) else {}
    article_count_val = (research.get("article_count") or {}).get("value")
    attention = (research.get("attention_share") or {}).get("value")

    return {
        "report_type": "daily",
        "period": report_day.isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "country_scope": countries,
        "target_scope": "china",
        "disclaimer": (
            "Monitored official/media sample for the listed countries — "
            "not an official state position or public-opinion census."
        ),
        "metric_definition_version": METRIC_DEFINITION_VERSION,
        "relevance_weight_version": RELEVANCE_WEIGHT_VERSION,
        "generator": "rule_template_v0.2",
        "overview": {
            "calendar_day_start": day_start.isoformat(),
            "calendar_day_end": day_end.isoformat(),
            "rolling_24h_start": roll_start.isoformat(),
            "rolling_24h_end": now.isoformat(),
            "china_article_count_24h": len(china_roll),
            "article_count_metric": article_count_val,
            "attention_share": attention,
            "sentiment_counts_24h": dict(sent_counts),
            "day_article_count": len(day_articles),
            "metrics": metrics_blob,
        },
        "coverage_by_country": coverage,
        "title_samples": title_samples,
        "china_articles": china_rows[:25],
        "events": event_blocks,
        "missing_analysis": int(missing),
        "source_health": health_rows,
        "quality_notes": [
            "Rule template; facts should link to article_id.",
            "RSS latest-N ≠ full calendar-day corpus.",
            f"Pending/failed analysis queue ≈ {missing}; do not extrapolate full-sample sentiment.",
            "Disconnected sources are out of coverage this round.",
        ],
    }


def render_daily_markdown(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append(f"# GNI 对华叙事日报（{payload.get('period')}）")
    lines.append("")
    lines.append("## 报告元数据")
    lines.append("")
    lines.append(f"- **report_type**: {payload.get('report_type')}")
    lines.append(f"- **period**: {payload.get('period')}（Asia/Shanghai）")
    lines.append(f"- **generated_at**: {payload.get('generated_at')}")
    lines.append(f"- **country_scope**: {', '.join(payload.get('country_scope') or [])}")
    lines.append(f"- **target_scope**: {payload.get('target_scope')}")
    lines.append(f"- **generator**: {payload.get('generator')}")
    lines.append("")
    lines.append(f"> {payload.get('disclaimer')}")
    lines.append("")
    ov = payload.get("overview") or {}
    lines.append("## 1. 概览")
    lines.append("")
    lines.append(f"- 对华相关（滚动约 24h）: **{ov.get('china_article_count_24h')}**")
    lines.append(f"- Attention share: {ov.get('attention_share')}")
    lines.append(f"- 情感分布: {ov.get('sentiment_counts_24h')}")
    lines.append(f"- missing 分析: **{payload.get('missing_analysis')}**")
    lines.append("")
    lines.append("## 2. 当日采集与覆盖")
    lines.append("")
    lines.append("| 国家 | 当日篇数 | 已分析 |")
    lines.append("|------|----------|--------|")
    for row in payload.get("coverage_by_country") or []:
        lines.append(
            f"| {row['country_id']} | {row['article_count']} | {row['analyzed_count']} |"
        )
    lines.append("")
    lines.append("## 3. 事件主线（按时间）")
    lines.append("")
    for ev in payload.get("events") or []:
        lines.append(f"- **{ev.get('title')}** (`{ev.get('event_id')}`)")
        lines.append(f"  - time={ev.get('event_time')} · arts={ev.get('article_count')}")
        for evi in ev.get("evidence") or []:
            lines.append(f"  - evidence: {evi.get('title')} · `{evi.get('article_id')}`")
    lines.append("")
    lines.append("## 4. 对华相关代表文")
    lines.append("")
    for a in payload.get("china_articles") or []:
        lines.append(
            f"- [{a.get('country_id')}/{a.get('relevance')}] {a.get('title')} "
            f"· `{a.get('article_id')}` · sentiment={a.get('sentiment')}"
        )
    lines.append("")
    lines.append("## 5. 质量与限制")
    lines.append("")
    for note in payload.get("quality_notes") or []:
        lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines)


def write_daily_files(payload: dict[str, Any], *, out_dir: str | None = None) -> dict[str, str]:
    from pathlib import Path

    root = Path(out_dir) if out_dir else Path(__file__).resolve().parents[3] / "data"
    root.mkdir(parents=True, exist_ok=True)
    period = payload.get("period") or "unknown"
    md_path = root / f"daily_report_{period}.md"
    json_path = root / f"daily_report_{period}.json"
    import json

    md_path.write_text(render_daily_markdown(payload), encoding="utf-8")
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return {"markdown": str(md_path), "json": str(json_path)}

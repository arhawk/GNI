"""Evidence Preparation & Composite Selection for GNI Report Intelligence Narrative Layer.

Guarantees that:
1. All statistical facts come strictly from deterministic V1.0 analytics (never LLM-computed).
2. Representative events and articles are selected via composite prioritization (important events,
   high-delta topics, country diversity, stance diversity + counter-examples, per-event caps).
3. Every item preserves verifiable DB IDs (article_id, event_id, metric_ref_id, alert_id, url).
4. Historical windows are honest about missing data and never fake trends.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from gni.analysis.stance_util import (
    extract_v1_boards,
    extract_v1_china_stance,
    extract_v1_stance_evidence,
    extract_v1_topics,
)
from gni.infrastructure.models import (
    Article,
    ArticleChinaSpan,
    Event,
    EventArticle,
    EventLocation,
    EventParticipant,
    NarrativeCluster,
    Source,
)
from gni.metrics.service import _latest_analyses, run_v1_stat_snapshots
from gni.metrics.v1_stats import normalize_url_for_dedup
from gni.reports.risk_tagging import media_type_bucket

ARTICLE_CAP_BY_REPORT = {
    "daily": 18,
    "weekly": 28,
    "monthly": 35,
}
EVENT_CAP_BY_REPORT = {
    "daily": 6,
    "weekly": 8,
    "monthly": 10,
}
PER_EVENT_ARTICLE_CAP = 4
PER_EVENT_ARTICLE_CAP_BY_REPORT = {
    "daily": 4,
    "weekly": 6,
    "monthly": 6,
}
MIN_RELIABLE_SAMPLE_N = 3
LOW_COVERAGE_THRESHOLD = 0.7


@dataclass
class EvidenceBundle:
    report_type: str
    period: str
    period_start: str | None
    period_end: str | None
    statistical: dict[str, Any]
    events: list[dict[str, Any]]
    articles: list[dict[str, Any]]
    historical: dict[str, Any]
    alerts: list[dict[str, Any]]
    evidence_hash: str
    counter_examples: list[dict[str, Any]] = field(default_factory=list)
    orphan_articles: list[dict[str, Any]] = field(default_factory=list)
    global_article_count: int = 0
    low_sample_scopes: list[str] = field(default_factory=list)
    allowed_article_ids: set[str] = field(default_factory=set)
    allowed_event_ids: set[str] = field(default_factory=set)
    allowed_metric_ids: set[str] = field(default_factory=set)
    allowed_alert_ids: set[str] = field(default_factory=set)
    allowed_urls: set[str] = field(default_factory=set)
    allowed_numbers: set[str] = field(default_factory=set)
    article_url_map: dict[str, str] = field(default_factory=dict)

    def for_task(self, task_type: str) -> dict[str, Any]:
        """Return a task-focused evidence slice within reasonable prompt token budgets."""
        base = {
            "report_type": self.report_type,
            "period": self.period,
            "period_start": self.period_start,
            "period_end": self.period_end,
            "statistical": self.statistical,
            "historical": self.historical,
            "low_sample_scopes": self.low_sample_scopes,
        }
        if task_type == "executive_analysis":
            base["events"] = [
                {k: v for k, v in ev.items() if k != "articles"}
                | {"representative_articles": (ev.get("articles") or [])[:2]}
                for ev in self.events[:6]
            ]
            base["articles"] = self.articles[:12]
            base["counter_examples"] = self.counter_examples[:4]
            base["alerts"] = self.alerts[:8]
        elif task_type == "event_analysis":
            base["events"] = self.events
            # Include only articles tied to events or high-signal orphans
            ev_aids = {
                a.get("article_id")
                for ev in self.events
                for a in (ev.get("articles") or [])
                if a.get("article_id")
            }
            base["articles"] = [a for a in self.articles if a["article_id"] in ev_aids][:20]
            base["counter_examples"] = self.counter_examples[:3]
        elif task_type == "topic_trend_analysis":
            base["events"] = [
                {
                    "event_id": ev["event_id"],
                    "title": ev["title"],
                    "countries": ev.get("countries"),
                    "article_count": ev.get("article_count"),
                }
                for ev in self.events[:8]
            ]
            base["articles"] = self.articles[:22]
            base["counter_examples"] = self.counter_examples[:4]
        elif task_type == "cross_country_analysis":
            base["events"] = self.events[:6]
            base["articles"] = self.articles
            base["counter_examples"] = self.counter_examples[:4]
        elif task_type == "stance_analysis":
            base["events"] = [
                {
                    "event_id": ev["event_id"],
                    "title": ev["title"],
                    "countries": ev.get("countries"),
                    "article_count": ev.get("article_count"),
                }
                for ev in self.events[:6]
            ]
            base["articles"] = self.articles[:24]
            base["counter_examples"] = self.counter_examples[:4]
        elif task_type == "emerging_signals":
            base["alerts"] = self.alerts[:12]
            base["events"] = [
                {
                    "event_id": ev["event_id"],
                    "title": ev["title"],
                    "status": ev.get("status"),
                    "risk_level": ev.get("risk_level"),
                    "countries": ev.get("countries"),
                    "article_count": ev.get("article_count"),
                    "anomaly_reasons": ev.get("anomaly_reasons"),
                }
                for ev in self.events[:8]
            ]
            base["articles"] = self.articles[:14]
            if self.orphan_articles:
                base["orphan_articles"] = self.orphan_articles[:6]
        else:
            base["events"] = self.events[:6]
            base["articles"] = self.articles[:16]
            base["counter_examples"] = self.counter_examples[:4]
            base["alerts"] = self.alerts[:8]
        return base


def compute_payload_fingerprint(payload: dict[str, Any]) -> str:
    """Fast deterministic hash of a report's core facts (used for cache lookup without LLM/DB overhead)."""
    sections = payload.get("sections") or {}
    v1 = sections.get("v1_stats") or {}
    v1_prev = sections.get("v1_stats_prev") or {}

    def _compact_v1(block: dict[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        g = block.get("global")
        if isinstance(g, dict):
            out["global"] = [
                g.get("article_count"),
                g.get("positive_count"),
                g.get("neutral_count"),
                g.get("negative_count"),
                g.get("unclassified_count"),
                g.get("article_ids") or [],
            ]
        for key in ("countries", "boards", "topics"):
            rows = block.get(key) or []
            out[key] = [
                [
                    r.get("scope_id"),
                    r.get("article_count"),
                    r.get("positive_count"),
                    r.get("neutral_count"),
                    r.get("negative_count"),
                    r.get("unclassified_count"),
                ]
                for r in rows
                if isinstance(r, dict) and (r.get("article_count") or 0) > 0
            ]
        return out

    ev_ids = [
        str(e.get("event_id") or e.get("id") or "")
        for e in (sections.get("major_events") or [])[:12]
        if isinstance(e, dict)
    ]
    core = {
        "report_type": payload.get("report_type"),
        "period": payload.get("period"),
        "article_count": payload.get("article_count"),
        "v1": _compact_v1(v1),
        "v1_prev": _compact_v1(v1_prev),
        "events": ev_ids,
        "signals_n": len(sections.get("signals") or []),
    }
    raw = json.dumps(core, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    raw = str(ts).strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(raw)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _fmt_pct(rate: float | None) -> float | None:
    if not isinstance(rate, (int, float)):
        return None
    return round(float(rate) * 100.0, 1)


def _metric_ref_id(scope_type: str, scope_id: str) -> str:
    return f"metric:{scope_type}:{scope_id}"


def _build_stat_row(
    cur: dict[str, Any],
    prev: dict[str, Any] | None = None,
) -> dict[str, Any]:
    st = str(cur.get("scope_type") or "GLOBAL")
    sid = str(cur.get("scope_id") or "ALL")
    cnt = int(cur.get("article_count") or 0)
    prev_cnt = int(prev.get("article_count") or 0) if isinstance(prev, dict) else None
    delta = (cnt - prev_cnt) if prev_cnt is not None else None
    pct_change = (
        round(((cnt - prev_cnt) / prev_cnt) * 100.0, 1)
        if prev_cnt is not None and prev_cnt > 0
        else None
    )
    neg_cur = cur.get("negative_rate")
    neg_prev = prev.get("negative_rate") if isinstance(prev, dict) else None
    neg_delta_pp = (
        round((float(neg_cur) - float(neg_prev)) * 100.0, 1)
        if isinstance(neg_cur, (int, float)) and isinstance(neg_prev, (int, float))
        else None
    )
    cov = cur.get("stance_coverage_rate")
    limitations: list[str] = []
    if cnt < MIN_RELIABLE_SAMPLE_N:
        limitations.append(f"sample_below_min(n={cnt}<{MIN_RELIABLE_SAMPLE_N})")
    if isinstance(cov, (int, float)) and cov < LOW_COVERAGE_THRESHOLD:
        limitations.append(f"low_stance_coverage({round(cov * 100.0, 1)}%)")
    return {
        "metric_ref_id": _metric_ref_id(st, sid),
        "scope_type": st,
        "scope_id": sid,
        "label_zh": cur.get("label_zh") or sid,
        "board_id": cur.get("board_id"),
        "article_count": cnt,
        "prev_article_count": prev_cnt,
        "article_count_delta": delta,
        "article_count_pct_change": pct_change,
        "positive_count": int(cur.get("positive_count") or 0),
        "neutral_count": int(cur.get("neutral_count") or 0),
        "negative_count": int(cur.get("negative_count") or 0),
        "unclassified_count": int(cur.get("unclassified_count") or 0),
        "positive_pct": _fmt_pct(cur.get("positive_rate")),
        "neutral_pct": _fmt_pct(cur.get("neutral_rate")),
        "negative_pct": _fmt_pct(cur.get("negative_rate")),
        "negative_rate_delta_pp": neg_delta_pp,
        "stance_coverage_pct": _fmt_pct(cov),
        "limitations": limitations,
    }


def _collect_numbers_from_obj(obj: Any, bag: set[str]) -> None:
    if obj is None or isinstance(obj, bool):
        return
    if isinstance(obj, int):
        bag.add(str(obj))
        bag.add(str(abs(obj)))
        bag.add(f"{obj:.1f}")
        bag.add(f"{abs(obj):.1f}")
        return
    if isinstance(obj, float):
        for val in (obj, abs(obj)):
            bag.add(f"{val:g}")
            bag.add(f"{val:.1f}")
            bag.add(f"{val:.2f}")
            bag.add(str(int(round(val))))
            # Also allow rate (0..1) expressed as percentage
            if 0.0 <= val <= 1.0:
                p = val * 100.0
                bag.add(f"{p:.1f}")
                bag.add(f"{p:.2f}")
                bag.add(str(int(round(p))))
        return
    if isinstance(obj, str):
        for m in re.findall(r"\d+(?:\.\d+)?", obj):
            bag.add(m)
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in {"article_ids", "evidence_hash", "id", "article_id", "event_id", "url"}:
                continue
            _collect_numbers_from_obj(v, bag)
        return
    if isinstance(obj, (list, tuple, set)):
        for item in obj:
            _collect_numbers_from_obj(item, bag)


def _compute_historical_evidence(
    session: Session,
    report_type: str,
    payload: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Build honest historical context per report type; never fake missing history."""
    sections = payload.get("sections") or {}
    win_start = _parse_iso(payload.get("period_start"))
    win_end = _parse_iso(payload.get("period_end"))
    v1_prev = sections.get("v1_stats_prev")

    if report_type == "daily":
        summary = sections.get("summary") or {}
        cmp = summary.get("comparisons") or {}
        prev_v1 = v1_prev
        week_v1 = None
        days_with_data = 0
        if win_start is not None:
            if prev_v1 is None:
                y_snap = run_v1_stat_snapshots(
                    session,
                    period_start=win_start - timedelta(days=1),
                    period_end=win_start,
                    persist=False,
                    include_zero_taxonomy=False,
                )
                prev_v1 = y_snap["by_scope"]
            w_snap = run_v1_stat_snapshots(
                session,
                period_start=win_start - timedelta(days=7),
                period_end=win_start,
                persist=False,
                include_zero_taxonomy=False,
            )
            week_v1 = w_snap["by_scope"]
            # Count distinct days with data inside the 7d baseline
            g_w = week_v1.get("global") or {}
            w_aids = g_w.get("article_ids") or []
            if w_aids:
                pubs = session.scalars(
                    select(Article.published_at).where(Article.id.in_(w_aids))
                ).all()
                days_with_data = len({p.date().isoformat() for p in pubs if p is not None})
        w_global = (week_v1 or {}).get("global") or {}
        return (
            {
                "window_kind": "daily_vs_yesterday_and_7d",
                "vs_yesterday": cmp.get("vs_yesterday"),
                "vs_7d_avg": cmp.get("vs_7d_avg"),
                "baseline_7d_total_articles": int(w_global.get("article_count") or 0),
                "baseline_7d_negative_pct": _fmt_pct(w_global.get("negative_rate")),
                "baseline_7d_coverage_pct": _fmt_pct(w_global.get("stance_coverage_rate")),
                "history_days_with_data": days_with_data,
                "history_note": (
                    f"近7日基准中实际有数据的自然日为 {days_with_data} 天；缺失日期不构成趋势。"
                    if days_with_data < 7
                    else "近7日基准覆盖完整。"
                ),
            },
            prev_v1,
        )

    if report_type == "weekly":
        existing_hist = sections.get("historical_v1_stats")
        series: list[dict[str, Any]] = []
        countries_series: dict[str, list[dict[str, Any]]] = defaultdict(list)
        topics_series: dict[str, list[dict[str, Any]]] = defaultdict(list)
        if win_start is not None and win_end is not None:
            for offset in range(3, -1, -1):
                s = win_start - timedelta(days=7 * offset)
                e = win_end - timedelta(days=7 * offset)
                lbl = f"{s.date().isoformat()}~{(e - timedelta(days=1)).date().isoformat()}"
                if offset == 0 and isinstance(sections.get("v1_stats"), dict):
                    by_scope = sections["v1_stats"]
                elif offset == 1 and isinstance(v1_prev, dict):
                    by_scope = v1_prev
                else:
                    snap = run_v1_stat_snapshots(
                        session,
                        period_start=s,
                        period_end=e,
                        persist=False,
                        include_zero_taxonomy=False,
                    )
                    by_scope = snap["by_scope"] or {}
                g = by_scope.get("global") or {}
                series.append(
                    {
                        "label": lbl,
                        "article_count": int(g.get("article_count") or 0),
                        "positive_pct": _fmt_pct(g.get("positive_rate")),
                        "neutral_pct": _fmt_pct(g.get("neutral_rate")),
                        "negative_pct": _fmt_pct(g.get("negative_rate")),
                        "stance_coverage_pct": _fmt_pct(g.get("stance_coverage_rate")),
                    }
                )
                for cr in (by_scope.get("countries") or [])[:6]:
                    if isinstance(cr, dict) and (cr.get("article_count") or 0) > 0:
                        countries_series[str(cr.get("scope_id"))].append(
                            {
                                "label": lbl,
                                "article_count": int(cr.get("article_count") or 0),
                                "negative_pct": _fmt_pct(cr.get("negative_rate")),
                            }
                        )
                for tr in (by_scope.get("topics") or [])[:6]:
                    if isinstance(tr, dict) and (tr.get("article_count") or 0) > 0:
                        topics_series[str(tr.get("scope_id"))].append(
                            {
                                "label": lbl,
                                "article_count": int(tr.get("article_count") or 0),
                                "negative_pct": _fmt_pct(tr.get("negative_rate")),
                            }
                        )
        elif isinstance(existing_hist, list) and existing_hist:
            series = list(existing_hist)
        non_empty = [r for r in series if (r.get("article_count") or 0) > 0]
        missing = [r["label"] for r in series if (r.get("article_count") or 0) == 0]
        return (
            {
                "window_kind": "weekly_4w_series",
                "weeks_series": series,
                "countries_4w_series": dict(countries_series),
                "topics_4w_series": dict(topics_series),
                "weeks_with_data": len(non_empty),
                "missing_weeks": missing,
                "history_note": (
                    f"近4周窗口中仅 {len(non_empty)} 周有数据（缺失：{', '.join(missing)}），不得把缺失周伪装成趋势。"
                    if missing
                    else "近4周历史窗口均有数据。"
                ),
            },
            v1_prev,
        )

    # monthly
    existing_hist = sections.get("historical_v1_stats")
    series = []
    countries_m_series: dict[str, list[dict[str, Any]]] = defaultdict(list)
    topics_m_series: dict[str, list[dict[str, Any]]] = defaultdict(list)
    if win_start is not None:
        # Build up to 6 calendar months ending with current month
        cur_y, cur_m = win_start.year, win_start.month
        months: list[tuple[int, int]] = []
        y, m = cur_y, cur_m
        for _ in range(6):
            months.append((y, m))
            if m == 1:
                y, m = y - 1, 12
            else:
                m -= 1
        months.reverse()
        from calendar import monthrange

        tz = win_start.tzinfo or timezone.utc
        for my, mm in months:
            mlabel = f"{my:04d}-{mm:02d}"
            if my == cur_y and mm == cur_m and isinstance(sections.get("v1_stats"), dict):
                by_scope = sections["v1_stats"]
            else:
                last_day = monthrange(my, mm)[1]
                ms = datetime(my, mm, 1, tzinfo=tz)
                me = datetime(my, mm, last_day, tzinfo=tz) + timedelta(days=1)
                snap = run_v1_stat_snapshots(
                    session,
                    period_start=ms,
                    period_end=me,
                    persist=False,
                    include_zero_taxonomy=False,
                )
                by_scope = snap["by_scope"] or {}
            g = by_scope.get("global") or {}
            series.append(
                {
                    "month": mlabel,
                    "article_count": int(g.get("article_count") or 0),
                    "positive_pct": _fmt_pct(g.get("positive_rate")),
                    "neutral_pct": _fmt_pct(g.get("neutral_rate")),
                    "negative_pct": _fmt_pct(g.get("negative_rate")),
                    "stance_coverage_pct": _fmt_pct(g.get("stance_coverage_rate")),
                }
            )
            for cr in (by_scope.get("countries") or [])[:6]:
                if isinstance(cr, dict) and (cr.get("article_count") or 0) > 0:
                    countries_m_series[str(cr.get("scope_id"))].append(
                        {
                            "month": mlabel,
                            "article_count": int(cr.get("article_count") or 0),
                            "negative_pct": _fmt_pct(cr.get("negative_rate")),
                        }
                    )
            for tr in (by_scope.get("topics") or [])[:6]:
                if isinstance(tr, dict) and (tr.get("article_count") or 0) > 0:
                    topics_m_series[str(tr.get("scope_id"))].append(
                        {
                            "month": mlabel,
                            "article_count": int(tr.get("article_count") or 0),
                            "negative_pct": _fmt_pct(tr.get("negative_rate")),
                        }
                    )
    elif isinstance(existing_hist, list) and existing_hist:
        series = list(existing_hist)
    non_empty = [r for r in series if (r.get("article_count") or 0) > 0]
    missing_m = [r.get("month") or r.get("label") for r in series if (r.get("article_count") or 0) == 0]
    return (
        {
            "window_kind": "monthly_6m_series",
            "months_series": series,
            "countries_6m_series": dict(countries_m_series),
            "topics_6m_series": dict(topics_m_series),
            "months_with_data": len(non_empty),
            "missing_months": missing_m,
            "history_note": (
                f"近6个月窗口中仅 {len(non_empty)} 个月有数据（缺失：{', '.join(str(x) for x in missing_m)}）；"
                "历史样本不足时必须标注 insufficient_history，严禁虚构长期趋势。"
                if missing_m
                else "近6个月均有文章级重算数据。"
            ),
        },
        v1_prev,
    )


def prepare_evidence_bundle(
    session: Session,
    *,
    report_type: str,
    payload: dict[str, Any],
) -> EvidenceBundle:
    """Prepare structured, deduplicated, traceable EvidenceBundle for LLM tasks."""
    sections = payload.get("sections") or {}
    v1_cur = sections.get("v1_stats") or {}
    historical, v1_prev = _compute_historical_evidence(session, report_type, payload)

    # 1. Statistical Evidence (strictly deterministic V1.0)
    prev_countries = {r.get("scope_id"): r for r in ((v1_prev or {}).get("countries") or []) if isinstance(r, dict)}
    prev_boards = {r.get("scope_id"): r for r in ((v1_prev or {}).get("boards") or []) if isinstance(r, dict)}
    prev_topics = {r.get("scope_id"): r for r in ((v1_prev or {}).get("topics") or []) if isinstance(r, dict)}

    global_cur = v1_cur.get("global") if isinstance(v1_cur.get("global"), dict) else None
    global_prev = (v1_prev or {}).get("global") if isinstance((v1_prev or {}).get("global"), dict) else None

    stat_global = _build_stat_row(global_cur, global_prev) if global_cur else None
    stat_countries = [
        _build_stat_row(r, prev_countries.get(r.get("scope_id")))
        for r in (v1_cur.get("countries") or [])
        if isinstance(r, dict)
    ]
    stat_boards = [
        _build_stat_row(r, prev_boards.get(r.get("scope_id")))
        for r in (v1_cur.get("boards") or [])
        if isinstance(r, dict) and ((r.get("article_count") or 0) > 0 or (prev_boards.get(r.get("scope_id")) or {}).get("article_count", 0) > 0)
    ]
    stat_topics = [
        _build_stat_row(r, prev_topics.get(r.get("scope_id")))
        for r in (v1_cur.get("topics") or [])
        if isinstance(r, dict) and ((r.get("article_count") or 0) > 0 or (prev_topics.get(r.get("scope_id")) or {}).get("article_count", 0) > 0)
    ]

    low_sample_scopes: list[str] = []
    allowed_metric_ids: set[str] = set()
    for row in ([stat_global] if stat_global else []) + stat_countries + stat_boards + stat_topics:
        allowed_metric_ids.add(row["metric_ref_id"])
        if row.get("limitations"):
            low_sample_scopes.append(f"{row['metric_ref_id']} ({'; '.join(row['limitations'])})")

    statistical = {
        "methodology_version": payload.get("methodology_version") or "methodology_v1.0",
        "taxonomy_version": payload.get("taxonomy_version") or "taxonomy_v1.0",
        "period": payload.get("period"),
        "global": stat_global,
        "countries": stat_countries,
        "boards": stat_boards,
        "topics": stat_topics,
        "country_profiles": sections.get("country_profiles"),
        "narrative_landscape": sections.get("narrative_landscape"),
        "cross_country_narrative": sections.get("cross_country_narrative"),
        "note": "所有数字均为程序确定性计算；严禁 LLM 重新计算或篡改任何数值。",
    }

    # Preload sources & candidate articles from DB
    sources = {s.id: s for s in session.scalars(select(Source)).all()}
    window_article_ids: list[str] = list((global_cur or {}).get("article_ids") or [])

    # 2. Event Evidence
    raw_events = (sections.get("major_events") or [])[: EVENT_CAP_BY_REPORT.get(report_type, 8)]
    event_ids = [
        str(e.get("event_id") or e.get("id"))
        for e in raw_events
        if e.get("event_id") or e.get("id")
    ]
    db_events = {
        e.id: e for e in session.scalars(select(Event).where(Event.id.in_(event_ids))).all()
    } if event_ids else {}
    event_links_by_eid: dict[str, list[str]] = defaultdict(list)
    event_locs_by_eid: dict[str, list[dict[str, Any]]] = defaultdict(list)
    event_parts_by_eid: dict[str, list[dict[str, Any]]] = defaultdict(list)
    event_narrs_by_eid: dict[str, list[dict[str, Any]]] = defaultdict(list)
    if event_ids:
        for link in session.scalars(
            select(EventArticle).where(EventArticle.event_id.in_(event_ids))
        ).all():
            event_links_by_eid[link.event_id].append(link.article_id)
        for loc in session.scalars(
            select(EventLocation).where(EventLocation.event_id.in_(event_ids))
        ).all():
            event_locs_by_eid[loc.event_id].append(
                {"label": loc.label, "country_id": loc.country_id, "type": loc.location_type}
            )
        for part in session.scalars(
            select(EventParticipant).where(EventParticipant.event_id.in_(event_ids))
        ).all():
            event_parts_by_eid[part.event_id].append(
                {"name": part.participant_name or part.participant_id, "role": part.role}
            )
        for nc in session.scalars(
            select(NarrativeCluster).where(NarrativeCluster.event_id.in_(event_ids))
        ).all():
            event_narrs_by_eid[nc.event_id].append(
                {"label": nc.label, "frame_id": nc.frame_id, "summary": (nc.summary or "")[:160]}
            )

    orphan_aids: list[str] = [
        str(oh.get("article_id"))
        for oh in (sections.get("orphan_headlines") or [])
        if isinstance(oh, dict) and oh.get("article_id")
    ]
    all_candidate_aids: set[str] = set(window_article_ids) | set(orphan_aids)
    for aids in event_links_by_eid.values():
        all_candidate_aids.update(aids)
    for raw_ev in raw_events:
        for evi in raw_ev.get("evidence") or []:
            if isinstance(evi, dict) and evi.get("article_id"):
                all_candidate_aids.add(str(evi["article_id"]))

    db_articles = {
        a.id: a
        for a in session.scalars(select(Article).where(Article.id.in_(list(all_candidate_aids)))).all()
    } if all_candidate_aids else {}
    analyses = _latest_analyses(session, list(db_articles.keys()))

    spans_by_aid: dict[str, list[str]] = defaultdict(list)
    if db_articles:
        for sp in session.scalars(
            select(ArticleChinaSpan)
            .where(ArticleChinaSpan.article_id.in_(list(db_articles.keys())))
            .order_by(ArticleChinaSpan.paragraph_index.asc())
        ).all():
            if sp.validation_status == "valid" and sp.text_original:
                if len(spans_by_aid[sp.article_id]) < 2:
                    spans_by_aid[sp.article_id].append(sp.text_original.strip()[:340])

    # Sort window_article_ids by relevance weight, stance confidence, excerpt richness, and recency
    def _article_rank(aid: str) -> tuple[float, float, int, str]:
        art = db_articles.get(aid)
        if not art:
            return (0.0, 0.0, 0, "")
        ana = analyses.get(aid)
        st = (ana.structured_result if ana else None) or {}
        cs = st.get("china_stance") if isinstance(st.get("china_stance"), dict) else {}
        conf = float(cs.get("stance_confidence") or 0.0) if isinstance(cs.get("stance_confidence"), (int, float)) else 0.0
        has_span = 1 if spans_by_aid.get(aid) else 0
        return (
            float(art.china_relevance_weight or 0.0),
            conf,
            has_span,
            art.published_at.isoformat() if art.published_at else "",
        )

    window_article_ids.sort(key=_article_rank, reverse=True)

    def _article_card(aid: str, *, event_id: str | None = None) -> dict[str, Any] | None:
        art = db_articles.get(aid)
        if not art:
            return None
        src = sources.get(art.source_id)
        ana = analyses.get(aid)
        structured = (ana.structured_result if ana else None) or {}
        sver = ana.schema_version if ana else None
        stance = extract_v1_china_stance(structured, schema_version=sver)
        topics_v1 = extract_v1_topics(structured, schema_version=sver)
        boards_v1 = extract_v1_boards(structured, schema_version=sver)
        stance_ev = extract_v1_stance_evidence(structured, schema_version=sver)
        quotes = [
            str(x.get("quote") or x.get("span_text") or "").strip()[:240]
            for x in stance_ev[:2]
            if isinstance(x, dict) and (x.get("quote") or x.get("span_text"))
        ]
        framing = structured.get("framing")
        frame_primary = framing.get("primary") if isinstance(framing, dict) else None
        cs = structured.get("china_stance") if isinstance(structured.get("china_stance"), dict) else {}
        ai = structured.get("article_intelligence") if isinstance(structured.get("article_intelligence"), dict) else {}
        raw_ev_spans = ai.get("evidence") if isinstance(ai.get("evidence"), list) else (
            structured.get("evidence") if isinstance(structured.get("evidence"), list) else []
        )
        verified_spans: list[dict[str, Any]] = []
        for idx_sp, sp in enumerate(raw_ev_spans[:4]):
            if not isinstance(sp, dict):
                continue
            txt = str(sp.get("text_span") or sp.get("quote") or "").strip()
            if not txt:
                continue
            verified_spans.append(
                {
                    "evidence_id": str(sp.get("evidence_id") or f"{art.id[:8]}_ev_{idx_sp}"),
                    "article_id": art.id,
                    "article_version_id": sp.get("article_version_id") or (ana.article_version_id if ana else None),
                    "text_span": txt[:320],
                    "start_offset": sp.get("start_offset"),
                    "end_offset": sp.get("end_offset"),
                    "validated": bool(sp.get("validated")),
                    "evidence_type": str(sp.get("evidence_type") or "general"),
                }
            )
        raw_nars = structured.get("narratives") if isinstance(structured.get("narratives"), list) else []
        qual = structured.get("quality") if isinstance(structured.get("quality"), dict) else {}
        excerpt = " | ".join(spans_by_aid.get(aid) or []) or (art.content_clean or "")[:650]
        return {
            "article_id": art.id,
            "article_version_id": ana.article_version_id if ana else None,
            "title": art.title,
            "source_id": art.source_id,
            "source_name": src.name if src else art.source_id,
            "source_country": src.country_id if src else None,
            "feed_scope": src.feed_scope if src else None,
            "media_type": media_type_bucket(src),
            "china_relevance_level": art.china_relevance_level,
            "published_at": art.published_at.isoformat() if art.published_at else None,
            "url": art.url,
            "stance_label": stance,
            "expression_owner": str(cs.get("expression_owner") or "unclear"),
            "stance_confidence": cs.get("stance_confidence") if sver in {"article_analysis_v1.0", "article_analysis_v1.1"} else None,
            "sentiment_label": (
                (structured.get("sentiment") or {}).get("label")
                if isinstance(structured.get("sentiment"), dict)
                else None
            ),
            "topics_v1": topics_v1,
            "boards_v1": boards_v1,
            "framing": frame_primary,
            "narratives": raw_nars[:3],
            "stance_quotes": quotes,
            "verified_evidence_spans": verified_spans,
            "quality_flags": list(qual.get("quality_flags") or []),
            "china_excerpt": excerpt[:700],
            "event_id": event_id,
        }

    per_event_cap = PER_EVENT_ARTICLE_CAP_BY_REPORT.get(report_type, PER_EVENT_ARTICLE_CAP)
    events_evidence: list[dict[str, Any]] = []
    event_selected_aids: list[tuple[str, str]] = []  # (aid, event_id)
    for raw_ev in raw_events:
        eid = str(raw_ev.get("event_id") or raw_ev.get("id") or "")
        if not eid:
            continue
        ev_obj = db_events.get(eid)
        linked_ids = list(event_links_by_eid.get(eid) or [])
        for evi in raw_ev.get("evidence") or []:
            if isinstance(evi, dict) and evi.get("article_id") and str(evi["article_id"]) not in linked_ids:
                linked_ids.append(str(evi["article_id"]))

        # Deduplicate by URL & content_hash inside each event, prioritize 1 per country first, then (country, stance)
        raw_cards = [c for aid in linked_ids if (c := _article_card(aid, event_id=eid)) is not None]
        raw_cards.sort(key=lambda c: str(c.get("published_at") or ""), reverse=True)
        cards: list[dict[str, Any]] = []
        ev_seen_urls: set[str] = set()
        ev_seen_hashes: set[str] = set()
        for c in raw_cards:
            uk = normalize_url_for_dedup(c.get("url"))
            art_obj = db_articles.get(c["article_id"])
            ch = (art_obj.content_hash or "").strip() if art_obj else ""
            if uk and uk in ev_seen_urls:
                continue
            if ch and ch in ev_seen_hashes:
                continue
            if uk:
                ev_seen_urls.add(uk)
            if ch:
                ev_seen_hashes.add(ch)
            cards.append(c)

        picked: list[dict[str, Any]] = []
        seen_countries: set[str | None] = set()
        seen_c_st: set[tuple[str | None, str]] = set()
        # Pass 1: ensure at least 1 representative article per reporting country
        for c in cards:
            cid = c.get("source_country")
            if cid and cid not in seen_countries and len(picked) < per_event_cap:
                picked.append(c)
                seen_countries.add(cid)
                seen_c_st.add((cid, c.get("stance_label") or "Unclassified"))
        # Pass 2: stance diversity across countries
        for c in cards:
            key = (c.get("source_country"), c.get("stance_label") or "Unclassified")
            if c not in picked and key not in seen_c_st and len(picked) < per_event_cap:
                picked.append(c)
                seen_c_st.add(key)
        # Pass 3: fill remaining slots
        for c in cards:
            if len(picked) >= per_event_cap:
                break
            if c not in picked:
                picked.append(c)

        for c in picked:
            event_selected_aids.append((c["article_id"], eid))

        countries_in_ev = sorted({c["source_country"] for c in cards if c.get("source_country")})
        # Earliest published_at per country (for follow-up timing distinction)
        first_by_country: dict[str, str] = {}
        for c in sorted(cards, key=lambda x: str(x.get("published_at") or "9999")):
            cid = c.get("source_country")
            pub = c.get("published_at")
            if cid and pub and cid not in first_by_country:
                first_by_country[cid] = pub

        # Build timeline from raw_ev or linked articles
        ev_timeline = raw_ev.get("timeline")
        if not ev_timeline:
            ev_timeline = [
                {
                    "at": c.get("published_at"),
                    "country_id": c.get("source_country"),
                    "article_id": c.get("article_id"),
                }
                for c in sorted(cards, key=lambda x: str(x.get("published_at") or ""))[:6]
                if c.get("published_at")
            ]

        events_evidence.append(
            {
                "event_id": eid,
                "title": raw_ev.get("title") or (ev_obj.title if ev_obj else ""),
                "summary": (ev_obj.summary if ev_obj and ev_obj.summary else "") or (raw_ev.get("summary") or ""),
                "actor": (raw_ev.get("core") or {}).get("actor") if isinstance(raw_ev.get("core"), dict) else (ev_obj.actor_key if ev_obj else raw_ev.get("actor_key")),
                "action": (raw_ev.get("core") or {}).get("action") if isinstance(raw_ev.get("core"), dict) else (ev_obj.action_key if ev_obj else raw_ev.get("action_key")),
                "object": (raw_ev.get("core") or {}).get("object") if isinstance(raw_ev.get("core"), dict) else (ev_obj.object_key if ev_obj else None),
                "event_time": raw_ev.get("event_time") or (ev_obj.event_time.isoformat() if ev_obj and ev_obj.event_time else None),
                "first_seen_at": raw_ev.get("first_seen_at") or (ev_obj.created_at.isoformat() if ev_obj and ev_obj.created_at else None),
                "status": raw_ev.get("status") or (ev_obj.status if ev_obj else None),
                "importance_score": raw_ev.get("importance_score"),
                "article_count": len(cards) or int((raw_ev.get("coverage") or {}).get("article_count") or raw_ev.get("article_count") or 0),
                "this_week_articles": raw_ev.get("this_week_articles"),
                "prev_week_articles": raw_ev.get("prev_week_articles"),
                "this_month_articles": raw_ev.get("this_month_articles"),
                "countries": countries_in_ev,
                "country_first_reported_at": first_by_country,
                "by_country_views": raw_ev.get("by_country_views") or [],
                "timeline": ev_timeline[:6],
                "locations": event_locs_by_eid.get(eid, [])[:3],
                "participants": event_parts_by_eid.get(eid, [])[:5],
                "narrative_clusters": event_narrs_by_eid.get(eid, [])[:3],
                "anomaly_reasons": (raw_ev.get("anomaly") or {}).get("reasons") if isinstance(raw_ev.get("anomaly"), dict) else [],
                "articles": picked,
            }
        )

    # 3. Composite Article Selection (priority: events -> high-delta topics -> country coverage -> stance/counter-example)
    cap = ARTICLE_CAP_BY_REPORT.get(report_type, 24)
    selected_articles: list[dict[str, Any]] = []
    seen_aids: set[str] = set()
    seen_urls: set[str] = set()
    seen_hashes: set[str] = set()

    def _try_add(card: dict[str, Any] | None) -> bool:
        if not card or len(selected_articles) >= cap:
            return False
        aid = card["article_id"]
        if aid in seen_aids:
            return False
        ukey = normalize_url_for_dedup(card.get("url"))
        if ukey and ukey in seen_urls:
            return False
        art_obj = db_articles.get(aid)
        ch = (art_obj.content_hash or "").strip() if art_obj else ""
        if ch and ch in seen_hashes:
            return False
        seen_aids.add(aid)
        if ukey:
            seen_urls.add(ukey)
        if ch:
            seen_hashes.add(ch)
        selected_articles.append(card)
        return True

    # Tier 1: representative articles from top events
    for aid, eid in event_selected_aids:
        _try_add(_article_card(aid, event_id=eid))

    # Tier 2: high-delta topics
    topics_by_delta = sorted(
        stat_topics,
        key=lambda t: (abs(t.get("article_count_delta") or 0), t.get("article_count") or 0),
        reverse=True,
    )
    topic_aids_map = {
        r.get("scope_id"): list(r.get("article_ids") or [])
        for r in (v1_cur.get("topics") or [])
        if isinstance(r, dict)
    }
    for t in topics_by_delta[:5]:
        added_t = 0
        for aid in topic_aids_map.get(t["scope_id"], []):
            if added_t >= 2:
                break
            if _try_add(_article_card(aid)):
                added_t += 1

    # Tier 3: country diversity (ensure each reporting country has representation)
    country_aids_map = {
        r.get("scope_id"): list(r.get("article_ids") or [])
        for r in (v1_cur.get("countries") or [])
        if isinstance(r, dict)
    }
    country_selected_counts = Counter(a.get("source_country") for a in selected_articles)
    for c_row in stat_countries:
        cid = c_row["scope_id"]
        need = max(0, 2 - country_selected_counts.get(cid, 0))
        if need <= 0:
            continue
        for aid in country_aids_map.get(cid, []):
            if need <= 0:
                break
            if _try_add(_article_card(aid)):
                need -= 1

    # Tier 4: stance diversity & representative counter-examples (Positive / Neutral / Negative)
    stance_counts = Counter(a.get("stance_label") for a in selected_articles)
    for target_stance in ("Positive", "Negative", "Neutral"):
        if stance_counts.get(target_stance, 0) >= 2:
            continue
        for aid in window_article_ids:
            if len(selected_articles) >= cap or stance_counts.get(target_stance, 0) >= 2:
                break
            card = _article_card(aid)
            if card and card.get("stance_label") == target_stance:
                if _try_add(card):
                    stance_counts[target_stance] += 1

    # Fill any remaining slots with recent window articles
    for aid in window_article_ids:
        if len(selected_articles) >= cap:
            break
        _try_add(_article_card(aid))

    # Explicit counter-examples contradicting dominant global stance (never sliced off by for_task)
    counter_examples: list[dict[str, Any]] = []
    pos_n = int((stat_global or {}).get("positive_count") or 0)
    neu_n = int((stat_global or {}).get("neutral_count") or 0)
    neg_n = int((stat_global or {}).get("negative_count") or 0)
    dominant_stance = max(
        [("Negative", neg_n), ("Neutral", neu_n), ("Positive", pos_n)],
        key=lambda x: x[1],
    )[0]
    counter_targets = [s for s in ("Positive", "Negative", "Neutral") if s != dominant_stance]
    ce_seen: set[str] = set()
    for aid in window_article_ids:
        if len(counter_examples) >= 4:
            break
        card = _article_card(aid)
        if card and card.get("stance_label") in counter_targets and card["article_id"] not in ce_seen:
            ce_seen.add(card["article_id"])
            counter_examples.append(card)

    orphan_articles: list[dict[str, Any]] = [
        c for aid in orphan_aids[:6] if (c := _article_card(aid)) is not None
    ]

    # 4. Alerts / Anomalies Evidence
    alerts_evidence: list[dict[str, Any]] = []
    allowed_alert_ids: set[str] = set()
    for idx, sig in enumerate(sections.get("signals") or []):
        if not isinstance(sig, dict):
            continue
        aid_str = str(sig.get("id") or f"signal_{idx}")
        allowed_alert_ids.add(aid_str)
        alerts_evidence.append(
            {
                "alert_id": aid_str,
                "subcategory": sig.get("subcategory"),
                "severity": sig.get("severity"),
                "title": sig.get("title"),
                "summary": sig.get("summary"),
                "evidence": sig.get("evidence") or {},
            }
        )
    for idx, anom in enumerate(sections.get("anomalies") or []):
        if not isinstance(anom, dict):
            continue
        aid_str = str(anom.get("id") or anom.get("event_id") or f"anomaly_{idx}")
        allowed_alert_ids.add(aid_str)
        alerts_evidence.append(
            {
                "alert_id": aid_str,
                "kind": anom.get("kind"),
                "severity": anom.get("severity") or anom.get("risk_level"),
                "title": anom.get("title"),
                "reasons": anom.get("reasons") or ([anom.get("summary")] if anom.get("summary") else []),
            }
        )

    # 5. Build allowlists for 3-layer Validator
    allowed_article_ids: set[str] = set(window_article_ids)
    article_url_map: dict[str, str] = {}
    allowed_urls: set[str] = set()
    for a in selected_articles:
        allowed_article_ids.add(a["article_id"])
        if a.get("url"):
            article_url_map[a["article_id"]] = a["url"]
            allowed_urls.add(a["url"])
    for ev in events_evidence:
        for a in ev.get("articles") or []:
            allowed_article_ids.add(a["article_id"])
            if a.get("url"):
                article_url_map[a["article_id"]] = a["url"]
                allowed_urls.add(a["url"])
    for aid, art in db_articles.items():
        allowed_article_ids.add(aid)
        if art.url:
            article_url_map.setdefault(aid, art.url)
            allowed_urls.add(art.url)

    allowed_event_ids = {ev["event_id"] for ev in events_evidence}
    allowed_numbers: set[str] = {str(i) for i in range(10)}  # small ordinals/counts 0-9
    _collect_numbers_from_obj(statistical, allowed_numbers)
    _collect_numbers_from_obj(historical, allowed_numbers)
    _collect_numbers_from_obj(
        [
            {
                "article_count": ev.get("article_count"),
                "countries_n": len(ev.get("countries") or []),
                "importance_score": ev.get("importance_score"),
                "event_time": ev.get("event_time"),
                "first_seen_at": ev.get("first_seen_at"),
            }
            for ev in events_evidence
        ],
        allowed_numbers,
    )
    _collect_numbers_from_obj(
        {
            "period": payload.get("period"),
            "period_start": payload.get("period_start"),
            "period_end": payload.get("period_end"),
            "kpis": (sections.get("summary") or {}).get("kpis"),
            "comparisons": (sections.get("summary") or {}).get("comparisons"),
            "alerts_n": len(alerts_evidence),
            "events_n": len(events_evidence),
        },
        allowed_numbers,
    )

    ev_hash = compute_payload_fingerprint(payload)
    global_count = int((stat_global or {}).get("article_count") or payload.get("article_count") or 0)

    return EvidenceBundle(
        report_type=report_type,
        period=str(payload.get("period") or ""),
        period_start=payload.get("period_start"),
        period_end=payload.get("period_end"),
        statistical=statistical,
        events=events_evidence,
        articles=selected_articles,
        historical=historical,
        alerts=alerts_evidence,
        evidence_hash=ev_hash,
        counter_examples=counter_examples,
        orphan_articles=orphan_articles,
        global_article_count=global_count,
        low_sample_scopes=low_sample_scopes,
        allowed_article_ids=allowed_article_ids,
        allowed_event_ids=allowed_event_ids,
        allowed_metric_ids=allowed_metric_ids,
        allowed_alert_ids=allowed_alert_ids,
        allowed_urls=allowed_urls,
        allowed_numbers=allowed_numbers,
        article_url_map=article_url_map,
    )


# ---------------------------------------------------------------------------
# Phase 5.3: Unified Task-Targeted EvidencePackageContract Builder
# ---------------------------------------------------------------------------

_TASK_LIMITS: dict[str, dict[str, int]] = {
    "overall_situation_assessment": {"articles": 12, "events": 5, "narratives": 5, "evidence": 12},
    "executive_analysis": {"articles": 12, "events": 5, "narratives": 5, "evidence": 12},
    "change_detection_assessment": {"articles": 10, "events": 4, "narratives": 4, "evidence": 10},
    "event_analysis": {"articles": 15, "events": 6, "narratives": 4, "evidence": 15},
    "topic_analysis": {"articles": 12, "events": 4, "narratives": 5, "evidence": 12},
    "country_comparison": {"articles": 14, "events": 4, "narratives": 4, "evidence": 14},
    "narrative_analysis": {"articles": 12, "events": 4, "narratives": 8, "evidence": 14},
    "sentiment_stance_analysis": {"articles": 12, "events": 3, "narratives": 4, "evidence": 14},
    "risk_signal_assessment": {"articles": 10, "events": 5, "narratives": 5, "evidence": 12},
    "outlook_assessment": {"articles": 10, "events": 5, "narratives": 6, "evidence": 12},
    "emerging_signals": {"articles": 10, "events": 5, "narratives": 6, "evidence": 12},
}


def _extract_traceable_evidence_items(
    articles: list[dict[str, Any]],
    *,
    task_type: str,
    limit: int,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for art in articles:
        if len(out) >= limit:
            break
        aid = str(art.get("article_id") or "")
        if not aid:
            continue
        spans = art.get("verified_evidence_spans") or []
        if spans:
            for sp in spans[:2]:
                if len(out) >= limit:
                    break
                ev_id = str(sp.get("evidence_id") or f"{aid[:8]}_ev")
                key = (aid, ev_id)
                if key in seen:
                    continue
                seen.add(key)
                out.append(
                    {
                        "evidence_id": ev_id,
                        "article_id": aid,
                        "article_version_id": sp.get("article_version_id") or art.get("article_version_id"),
                        "text_span": sp.get("text_span") or "",
                        "start_offset": sp.get("start_offset"),
                        "end_offset": sp.get("end_offset"),
                        "validated": bool(sp.get("validated")),
                        "source_name": art.get("source_name"),
                        "source_country": art.get("source_country"),
                        "published_at": art.get("published_at"),
                        "stance_label": art.get("stance_label"),
                        "expression_owner": art.get("expression_owner", "unclear"),
                        "related_topics": list(art.get("topics_v1") or []),
                        "related_event_id": art.get("event_id"),
                        "analysis_task": task_type,
                    }
                )
        else:
            snippet = (art.get("stance_quotes") or [art.get("china_excerpt") or ""])[0]
            if not snippet:
                continue
            ev_id = f"{aid[:8]}_excerpt"
            if (aid, ev_id) in seen:
                continue
            seen.add((aid, ev_id))
            out.append(
                {
                    "evidence_id": ev_id,
                    "article_id": aid,
                    "article_version_id": art.get("article_version_id"),
                    "text_span": str(snippet)[:320],
                    "start_offset": None,
                    "end_offset": None,
                    "validated": False,
                    "source_name": art.get("source_name"),
                    "source_country": art.get("source_country"),
                    "published_at": art.get("published_at"),
                    "stance_label": art.get("stance_label"),
                    "expression_owner": art.get("expression_owner", "unclear"),
                    "related_topics": list(art.get("topics_v1") or []),
                    "related_event_id": art.get("event_id"),
                    "analysis_task": task_type,
                }
            )
    return out


def _compute_change_signals_for_package(bundle: EvidenceBundle) -> list[dict[str, Any]]:
    """Run deterministic Phase 4 multi-factor change detection over bundle metrics."""
    from gni.metrics.changes import detect_volume_change

    signals: list[dict[str, Any]] = []
    hist = bundle.historical or {}
    stat = bundle.statistical or {}
    g = stat.get("global") if isinstance(stat.get("global"), dict) else {}
    cur_n = int(g.get("article_count") or bundle.global_article_count or 0)
    prev_7d = hist.get("vs_7d_avg") if isinstance(hist.get("vs_7d_avg"), dict) else {}
    base_mean = prev_7d.get("china_articles")
    if base_mean is None:
        base_mean = (hist.get("vs_yesterday") or {}).get("china_articles") if isinstance(hist.get("vs_yesterday"), dict) else None

    countries = {a.get("source_country") for a in bundle.articles if a.get("source_country")}
    sources = {a.get("source_id") for a in bundle.articles if a.get("source_id")}
    if base_mean is not None:
        sig = detect_volume_change(
            subject="GLOBAL",
            signal_type="attention_change",
            recent_count=cur_n,
            baseline_mean=float(base_mean),
            min_sample_size=5,
            min_abs_delta=3,
            min_rel_change=0.4,
            country_count=max(1, len(countries)),
            source_count=max(1, len(sources)),
            supporting_articles=[a["article_id"] for a in bundle.articles[:10]],
        )
        if sig is not None:
            signals.append(sig.model_dump(mode="json"))
    return signals


def _collect_narratives_for_package(
    session: Session,
    bundle: EvidenceBundle,
    *,
    limit: int,
) -> list[dict[str, Any]]:
    """Load persisted NarrativeCluster rows or cluster article-level narratives deterministically."""
    from gni.events.narratives import ArticleNarrativeInput, cluster_narratives
    from gni.infrastructure.models import EventNarrativeEvidence, NarrativeCluster

    event_ids = [ev["event_id"] for ev in bundle.events if ev.get("event_id")]
    persisted: list[dict[str, Any]] = []
    if event_ids:
        clusters = list(
            session.scalars(
                select(NarrativeCluster).where(NarrativeCluster.event_id.in_(event_ids)).limit(limit)
            ).all()
        )
        if clusters:
            cids = [c.id for c in clusters]
            ev_rows = list(
                session.scalars(
                    select(EventNarrativeEvidence).where(
                        EventNarrativeEvidence.narrative_cluster_id.in_(cids)
                    )
                ).all()
            )
            by_cid: dict[str, list[dict[str, Any]]] = {}
            for r in ev_rows:
                by_cid.setdefault(r.narrative_cluster_id, []).append(
                    {"article_id": r.article_id, "quote": (r.quote or "")[:240]}
                )
            for c in clusters:
                persisted.append(
                    {
                        "narrative_cluster_id": c.id,
                        "event_id": c.event_id,
                        "canonical_frame": c.frame_id or "unspecified",
                        "canonical_claim": c.label,
                        "summary": c.summary or "",
                        "evidence": by_cid.get(c.id, [])[:5],
                        "source": "db_narrative_cluster",
                    }
                )
            return persisted[:limit]

    # Fallback: deterministic clustering from article-level narratives[] (Phase 3 -> Phase 4d)
    nar_inputs: list[ArticleNarrativeInput] = []
    for art in bundle.articles:
        pub = None
        if art.get("published_at"):
            try:
                pub = datetime.fromisoformat(str(art["published_at"]).replace("Z", "+00:00"))
            except ValueError:
                pub = None
        for n in art.get("narratives") or []:
            if not isinstance(n, dict) or not (n.get("frame") and n.get("claim")):
                continue
            nar_inputs.append(
                ArticleNarrativeInput(
                    article_id=art["article_id"],
                    country_id=art.get("source_country"),
                    published_at=pub,
                    frame=str(n["frame"]),
                    claim=str(n["claim"]),
                    attribution=str(n.get("attribution") or "mention"),
                    tone=str(n.get("tone") or "unclear"),
                    quote=(art.get("stance_quotes") or [None])[0],
                    article_version_id=art.get("article_version_id"),
                    topic_ids=tuple(art.get("topics_v1") or ()),
                )
            )
    clustered = cluster_narratives(nar_inputs)
    return [c.model_dump(mode="json") for c in clustered[:limit]]


def build_task_evidence_package(
    session: Session,
    *,
    task_type: str,
    report_type: str,
    payload: dict[str, Any],
    bundle: EvidenceBundle | None = None,
) -> tuple[Any, EvidenceBundle]:
    """Build a task-targeted EvidencePackageContract alongside the DB-backed EvidenceBundle.

    Never passes full raw articles; binds every evidence item to article_id/evidence_id/
    article_version_id/offsets/source_name/published_at and preserves counter_evidence.
    """
    from gni.core.contracts import EvidencePackageContract

    ev_bundle = bundle or prepare_evidence_bundle(session, report_type=report_type, payload=payload)
    limits = _TASK_LIMITS.get(task_type, {"articles": 12, "events": 5, "narratives": 5, "evidence": 12})

    # Flatten deterministic metric snapshots for package
    stat = ev_bundle.statistical or {}
    metrics_list: list[dict[str, Any]] = []
    if isinstance(stat.get("global"), dict):
        metrics_list.append(stat["global"])
    for k in ("countries", "boards", "topics"):
        for row in (stat.get(k) or []):
            if isinstance(row, dict):
                metrics_list.append(row)

    change_signals = _compute_change_signals_for_package(ev_bundle)
    narratives = _collect_narratives_for_package(session, ev_bundle, limit=limits["narratives"])

    # Task-aware article ordering (keep representative + diverse, never full raw body)
    selected_articles = list(ev_bundle.articles)
    if task_type == "sentiment_stance_analysis":
        selected_articles.sort(
            key=lambda a: (
                0 if a.get("expression_owner") == "quoted_actor" else 1,
                0 if a.get("stance_label") in {"Positive", "Negative"} else 1,
            )
        )
    elif task_type == "country_comparison":
        # Round-robin across countries
        by_c: dict[str, list[dict[str, Any]]] = {}
        for a in selected_articles:
            by_c.setdefault(str(a.get("source_country") or "UNK"), []).append(a)
        rr: list[dict[str, Any]] = []
        while by_c and len(rr) < limits["articles"]:
            for cid in sorted(list(by_c.keys())):
                if by_c[cid]:
                    rr.append(by_c[cid].pop(0))
                if not by_c[cid]:
                    by_c.pop(cid, None)
                if len(rr) >= limits["articles"]:
                    break
        selected_articles = rr
    else:
        selected_articles = selected_articles[: limits["articles"]]

    rep_evidence = _extract_traceable_evidence_items(
        selected_articles,
        task_type=task_type,
        limit=limits["evidence"],
    )
    counter_evidence = _extract_traceable_evidence_items(
        ev_bundle.counter_examples,
        task_type=task_type,
        limit=max(4, limits["evidence"] // 2),
    )

    g_stat = stat.get("global") if isinstance(stat.get("global"), dict) else {}
    stance_cov = g_stat.get("stance_coverage_rate")
    countries_reporting = sorted({a.get("source_country") for a in ev_bundle.articles if a.get("source_country")})
    sources_reporting = sorted({a.get("source_id") for a in ev_bundle.articles if a.get("source_id")})
    quoted_count = sum(1 for a in ev_bundle.articles if a.get("expression_owner") == "quoted_actor")

    limitations: list[str] = []
    if ev_bundle.global_article_count == 0:
        limitations.append("当前统计窗口内无涉华报道（n=0），证据不足，禁止生成无依据研判。")
    elif ev_bundle.global_article_count < MIN_RELIABLE_SAMPLE_N:
        limitations.append(
            f"当前涉华报道样本偏小（n={ev_bundle.global_article_count} < {MIN_RELIABLE_SAMPLE_N}），比例与趋势仅作提示，不作强结论。"
        )
    if stance_cov is not None and float(stance_cov) < 0.5:
        limitations.append(
            f"立场覆盖率偏低（{float(stance_cov):.0%}），未判定（Unclassified）占比较高，正中负比例仅反映已判定样本。"
        )
    if ev_bundle.low_sample_scopes:
        limitations.append(f"存在小样本维度（{len(ev_bundle.low_sample_scopes)} 个），应避免仅凭百分比变化推断重大异常。")
    if quoted_count > 0:
        limitations.append(f"样本含 {quoted_count} 篇以引述对象观点为主的报道，引述观点不得归属为媒体自身立场。")
    limitations.append("多国媒体同时报道同一议题或事件不构成协调传播证据。")

    pkg = EvidencePackageContract(
        package_id=f"evpkg:{report_type}:{ev_bundle.period}:{task_type}:{ev_bundle.evidence_hash[:8]}",
        task_type=task_type,
        period={
            "label": ev_bundle.period,
            "period_start": ev_bundle.period_start,
            "period_end": ev_bundle.period_end,
            "report_type": report_type,
        },
        scope={
            "countries": countries_reporting,
            "sources": sources_reporting,
            "event_ids": [ev["event_id"] for ev in ev_bundle.events[: limits["events"]]],
        },
        metrics=metrics_list,
        current_articles=[
            {
                "article_id": a["article_id"],
                "article_version_id": a.get("article_version_id"),
                "title": a.get("title"),
                "source_id": a.get("source_id"),
                "source_name": a.get("source_name"),
                "source_country": a.get("source_country"),
                "published_at": a.get("published_at"),
                "stance_label": a.get("stance_label"),
                "expression_owner": a.get("expression_owner"),
                "sentiment_label": a.get("sentiment_label"),
                "topics_v1": a.get("topics_v1") or [],
                "framing": a.get("framing"),
                "event_id": a.get("event_id"),
            }
            for a in selected_articles
        ],
        historical_comparison=[
            {"historical": ev_bundle.historical, "change_signals": change_signals, "alerts": ev_bundle.alerts[:8]}
        ],
        events=ev_bundle.events[: limits["events"]],
        narratives=narratives,
        representative_evidence=rep_evidence,
        counter_evidence=counter_evidence,
        coverage={
            "global_article_count": ev_bundle.global_article_count,
            "countries_reporting": len(countries_reporting),
            "sources_reporting": len(sources_reporting),
            "stance_coverage_rate": stance_cov,
            "low_sample_scopes": list(ev_bundle.low_sample_scopes),
            "quoted_actor_articles": quoted_count,
            "is_insufficient_data": ev_bundle.global_article_count == 0,
        },
        limitations=limitations,
    )
    return pkg, ev_bundle


def curate_finding_evidence(
    articles: list[dict[str, Any]],
    *,
    max_refs: int = 3,
    max_per_source: int = 1,
    max_per_event: int = 1,
    include_counter: bool = True,
) -> dict[str, list[dict[str, Any]]]:
    """Deterministically curate 2-3 diverse representative articles + counter-evidence for a finding.

    Enforces:
    - Exact article_id & normalized title/URL deduplication.
    - Country & source diversity (prevents single outlet or single event monopoly).
    - Optional counter-evidence with contrasting China stance.
    """
    seen_ids: set[str] = set()
    seen_titles: set[str] = set()
    source_counts: Counter[str] = Counter()
    event_counts: Counter[str] = Counter()
    country_seen: set[str] = set()

    def _norm_title(t: str) -> str:
        return re.sub(r"\s+", " ", (t or "").strip().lower())[:120]

    def _to_ref(a: dict[str, Any], role: str) -> dict[str, Any]:
        return {
            "article_id": str(a.get("article_id") or a.get("id") or ""),
            "title": str(a.get("title") or "").strip()[:180],
            "source_name": str(a.get("source_name") or a.get("source") or "Unknown"),
            "country_code": str(a.get("country_code") or a.get("source_country") or ""),
            "china_stance": str(a.get("china_stance") or a.get("stance_label") or "Unclassified"),
            "published_at": a.get("published_at"),
            "url": str(a.get("url") or ""),
            "excerpt": str(a.get("excerpt") or a.get("summary") or a.get("key_quote") or "")[:240],
            "role": role,
        }

    # First pass: prefer unseen country + unseen source + unseen event
    selected: list[dict[str, Any]] = []
    remaining: list[dict[str, Any]] = []
    for a in articles:
        if not isinstance(a, dict):
            continue
        aid = str(a.get("article_id") or a.get("id") or "")
        title_key = _norm_title(str(a.get("title") or ""))
        if (aid and aid in seen_ids) or (title_key and title_key in seen_titles):
            continue
        src = str(a.get("source_name") or a.get("source") or "")
        ev_id = str(a.get("event_id") or "")
        cc = str(a.get("country_code") or a.get("source_country") or "")
        if len(selected) < max_refs:
            if (src and source_counts[src] >= max_per_source) or (ev_id and event_counts[ev_id] >= max_per_event):
                remaining.append(a)
                continue
            if cc and cc in country_seen and len(articles) > max_refs:
                remaining.append(a)
                continue
            selected.append(_to_ref(a, "supporting"))
            if aid:
                seen_ids.add(aid)
            if title_key:
                seen_titles.add(title_key)
            if src:
                source_counts[src] += 1
            if ev_id:
                event_counts[ev_id] += 1
            if cc:
                country_seen.add(cc)
        else:
            remaining.append(a)

    # Backfill if strict country diversity left fewer than max_refs
    for a in remaining:
        if len(selected) >= max_refs:
            break
        aid = str(a.get("article_id") or a.get("id") or "")
        title_key = _norm_title(str(a.get("title") or ""))
        if (aid and aid in seen_ids) or (title_key and title_key in seen_titles):
            continue
        src = str(a.get("source_name") or a.get("source") or "")
        if src and source_counts[src] >= max_per_source + 1:
            continue
        selected.append(_to_ref(a, "supporting"))
        if aid:
            seen_ids.add(aid)
        if title_key:
            seen_titles.add(title_key)
        if src:
            source_counts[src] += 1

    # Select up to 2 counter-evidence items with contrasting stance
    counter: list[dict[str, Any]] = []
    if include_counter and selected:
        stance_tally = Counter(
            s["china_stance"] for s in selected if s["china_stance"] in {"Positive", "Neutral", "Negative"}
        )
        dominant = stance_tally.most_common(1)[0][0] if stance_tally else None
        for a in articles:
            if len(counter) >= 2:
                break
            if not isinstance(a, dict):
                continue
            aid = str(a.get("article_id") or a.get("id") or "")
            if aid and aid in seen_ids:
                continue
            st = str(a.get("china_stance") or a.get("stance_label") or "Unclassified")
            if st in {"Positive", "Neutral", "Negative"} and dominant and st != dominant:
                counter.append(_to_ref(a, "counter"))
                if aid:
                    seen_ids.add(aid)

    return {"evidence_refs": selected, "counter_evidence": counter}


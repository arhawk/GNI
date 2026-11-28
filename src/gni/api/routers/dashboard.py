"""Dashboard & legacy Overview endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from gni.api.routers.common import load_cached_assessments, parse_iso
from gni.dashboard.data import MAX_WINDOW_DAYS
from gni.dashboard.overview import overview_payload
from gni.dashboard.pages_api import trends_payload
from gni.infrastructure.db import session_scope
from gni.metrics.definitions import METHODOLOGY_VERSION, TAXONOMY_V1_VERSION
from gni.reports.daily import build_daily_report

router = APIRouter(tags=["dashboard"])


@router.get("/api/overview")
def api_overview(
    days: int = Query(30, ge=1, le=MAX_WINDOW_DAYS),
    start: str | None = Query(None, description="ISO UTC window start"),
    end: str | None = Query(None, description="ISO UTC window end (may be before now)"),
) -> dict[str, Any]:
    start_dt = parse_iso(start)
    end_dt = parse_iso(end)
    try:
        with session_scope() as session:
            return overview_payload(
                session, days=days, window_start=start_dt, window_end=end_dt
            )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/api/dashboard")
def api_dashboard(
    date: str | None = Query(None, description="Optional YYYY-MM-DD in Asia/Shanghai"),
    trend_days: int = Query(14, ge=7, le=90),
) -> dict[str, Any]:
    """Unified Global Intelligence Dashboard payload backed by deterministic V1.0 stats + Daily Report Package."""
    try:
        with session_scope() as session:
            daily = build_daily_report(session, day=date, analyze=False)
            pkg = daily.get("report_package") or {}
            v1 = (daily.get("sections") or {}).get("v1_stats") or {}
            g = v1.get("global") or {}
            summary = (daily.get("sections") or {}).get("summary") or {}
            comparisons = summary.get("comparisons") or {}
            kpis_raw = summary.get("kpis") or {}

            trends = trends_payload(session, days=trend_days)
            cached = load_cached_assessments(session, report_type="daily", period=daily.get("period"))

            ch1 = next(
                (s for s in (pkg.get("sections") or []) if s.get("section_id") == "chapter_1_executive_judgment"),
                None,
            )
            ch5 = next(
                (s for s in (pkg.get("sections") or []) if s.get("section_id") == "chapter_5_emerging_signals"),
                None,
            )
            ch6 = next(
                (s for s in (pkg.get("sections") or []) if s.get("section_id") == "chapter_6_outlook_watchlist"),
                None,
            )

            overall_assess = cached.get("overall_situation_assessment")
            outlook_assess = cached.get("outlook_assessment")

            article_count = int(g.get("article_count") or 0)
            pos = int(g.get("positive_count") or 0)
            neu = int(g.get("neutral_count") or 0)
            neg = int(g.get("negative_count") or 0)
            uncl = int(g.get("unclassified_count") or 0)
            classified = pos + neu + neg

            key_developments = []
            for ev in (daily.get("sections") or {}).get("major_events") or []:
                cov = ev.get("coverage") or {}
                key_developments.append(
                    {
                        "event_id": ev.get("event_id"),
                        "title": ev.get("title"),
                        "event_type": ev.get("event_type"),
                        "event_time": ev.get("event_time"),
                        "status": ev.get("status"),
                        "importance_score": ev.get("importance_score"),
                        "overview_text": ev.get("overview_text"),
                        "countries": cov.get("countries") or [],
                        "country_count": cov.get("country_count") or 0,
                        "source_count": cov.get("source_count") or 0,
                        "article_count": cov.get("article_count") or 0,
                        "representative_articles": (ev.get("evidence") or [])[:3],
                    }
                )

            emerging_facts: list[dict[str, Any]] = []
            emerging_inferences: list[dict[str, Any]] = []
            for sig in (daily.get("sections") or {}).get("signals") or []:
                emerging_facts.append(
                    {
                        "title": sig.get("title"),
                        "summary": sig.get("summary"),
                        "kind": sig.get("subcategory") or "rule_signal",
                        "severity": sig.get("severity"),
                        "classification": "Fact",
                        "evidence": sig.get("evidence"),
                    }
                )
            for finding in (ch5.get("findings") if isinstance(ch5, dict) else []) or []:
                cls = str(finding.get("classification") or "Inference")
                target = emerging_facts if cls == "Fact" else emerging_inferences
                target.append(finding)

            return {
                "meta": {
                    "period": daily.get("period"),
                    "period_start": daily.get("period_start"),
                    "period_end": daily.get("period_end"),
                    "timezone": daily.get("timezone"),
                    "generated_at": daily.get("generated_at") or datetime.now(timezone.utc).isoformat(),
                    "methodology_version": METHODOLOGY_VERSION,
                    "taxonomy_version": TAXONOMY_V1_VERSION,
                    "core_kpi": "Unique Article Count (published_at, source_country)",
                    "report_id": pkg.get("report_id"),
                    "generation_status": pkg.get("generation_status"),
                    "validation_status": pkg.get("validation_status"),
                },
                "executive_overview": {
                    "article_count": article_count,
                    "vs_yesterday": comparisons.get("vs_yesterday"),
                    "vs_7d_avg": comparisons.get("vs_7d_avg"),
                    "reporting_countries": int(kpis_raw.get("reporting_countries") or len(v1.get("countries") or [])),
                    "reporting_sources": int(kpis_raw.get("reporting_sources") or 0),
                    "connected_countries": (daily.get("connected") or {}).get("countries"),
                    "active_sources": (daily.get("connected") or {}).get("active_sources"),
                    "major_events": int(kpis_raw.get("major_events") or 0),
                    "new_events": int(kpis_raw.get("new_events") or 0),
                    "stance_coverage_rate": g.get("stance_coverage_rate"),
                    "stance_distribution": {
                        "target": "china_mainland",
                        "positive_count": pos,
                        "neutral_count": neu,
                        "negative_count": neg,
                        "unclassified_count": uncl,
                        "classified_count": classified,
                        "positive_rate": g.get("positive_rate"),
                        "neutral_rate": g.get("neutral_rate"),
                        "negative_rate": g.get("negative_rate"),
                        "denominator_note": "Positive/Neutral/Negative rates use classified_count (excluding Unclassified); Stance Coverage Rate = classified_count / article_count.",
                    },
                },
                "executive_assessment": {
                    "status": (overall_assess or {}).get("status") or (ch1 or {}).get("status") or "rule_only",
                    "overall_situation": (overall_assess or {}).get("executive_summary")
                    or (ch1 or {}).get("summary")
                    or summary.get("overview_text")
                    or "",
                    "key_findings": (overall_assess or {}).get("key_findings")
                    or (ch1 or {}).get("findings")
                    or [],
                    "observations": (overall_assess or {}).get("observations") or [],
                    "interpretations": (overall_assess or {}).get("interpretations") or [],
                    "most_important_changes": summary.get("top_changes") or [],
                    "watch_items": (outlook_assess or {}).get("watch_items")
                    or (overall_assess or {}).get("watch_items")
                    or (ch6 or {}).get("findings")
                    or [],
                    "evidence_refs": (overall_assess or {}).get("evidence_refs")
                    or (ch1 or {}).get("evidence_refs")
                    or [],
                    "limitations": (overall_assess or {}).get("limitations") or pkg.get("limitations") or [],
                },
                "global_attention": {
                    "volume_trend": trends.get("volume_series") or [],
                    "countries": v1.get("countries") or [],
                    "boards": v1.get("boards") or [],
                    "topics": v1.get("topics") or [],
                    "topic_overlap_note": "Multi-label taxonomy: an article may belong to multiple topics; topic counts cannot be summed to equal global unique article_count.",
                },
                "key_developments": key_developments,
                "emerging_signals": {
                    "observed_facts": emerging_facts,
                    "analytical_inferences": emerging_inferences,
                },
                "daily_report_entry": {
                    "report_id": pkg.get("report_id"),
                    "period": daily.get("period"),
                    "generation_status": pkg.get("generation_status"),
                    "validation_status": pkg.get("validation_status"),
                    "chapter_count": len(pkg.get("sections") or []),
                    "href": "/reports",
                },
                "limitations": pkg.get("limitations") or [],
            }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

"""Dashboard overview payload (decoupled from events.service)."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from gni.dashboard.data import (
    DashboardFilters,
    article_data_range,
    compute_dashboard_metrics,
    monitoring_panel_counts,
    resolve_filter_window,
)
from gni.events.rollup import attitude_map_rows, rollup_country_china_attitude
from gni.events.geo import centroid
from gni.events.service import get_event_detail, list_events
from gni.infrastructure.models import CountryChinaAttitudeSnapshot


def overview_payload(
    session: Session,
    *,
    days: int = 30,
    window_start: datetime | None = None,
    window_end: datetime | None = None,
) -> dict[str, Any]:
    """Dashboard overview: KPIs + dual map layers + trends/topics/anomalies."""
    start_dt = window_start
    end_dt = window_end
    filters = DashboardFilters(days=days, window_start=start_dt, window_end=end_dt)
    start, end = resolve_filter_window(filters)
    span_days = max(1, int(round((end - start).total_seconds() / 86400.0)))
    metrics = compute_dashboard_metrics(session, filters)
    panel = monitoring_panel_counts(session)
    data_min, data_max = article_data_range(session)
    events = list_events(session, limit=30)

    event_pins = []
    for e in events:
        for loc in e.get("locations") or []:
            if loc.get("lat") is not None and loc.get("lon") is not None:
                event_pins.append(
                    {
                        "event_id": e["id"],
                        "title": e["title"],
                        "location_type": loc["location_type"],
                        "lat": loc["lat"],
                        "lon": loc["lon"],
                        "article_count": e.get("article_count"),
                        "importance": e.get("importance_score"),
                        "layer": "event_geography",
                    }
                )

    report_counts: Counter[str] = Counter()
    for e in events:
        detail = get_event_detail(session, e["id"])
        if not detail:
            continue
        for cv in detail["views"]["who_reports"]["countries"]:
            report_counts[cv["country_id"]] += cv["article_count"]
    reporting_pins = []
    for cid, n in report_counts.items():
        c = centroid(cid)
        if c:
            reporting_pins.append(
                {
                    "country_id": cid,
                    "lat": c[0],
                    "lon": c[1],
                    "article_count": n,
                    "layer": "reporting_source",
                }
            )

    existing_att = session.scalar(select(CountryChinaAttitudeSnapshot.id).limit(1))
    if not existing_att:
        rollup_country_china_attitude(
            session, window="30d", window_start=start, window_end=end
        )
    attitude_rows = attitude_map_rows(session, window="30d")

    research = metrics.get("research") or {}
    weighted = metrics.get("weighted") or {}
    ops = metrics.get("operational") or {}

    return {
        "meta": {
            "days": span_days,
            "preset_days": days if start_dt is None and end_dt is None else None,
            "window_start": start.isoformat(),
            "window_end": end.isoformat(),
            "data_min": data_min.isoformat() if data_min else None,
            "data_max": data_max.isoformat() if data_max else None,
            "metric_definition_version": metrics.get("metric_definition_version"),
            "relevance_weight_version": metrics.get("relevance_weight_version"),
            "map_modes": ["event_time_list", "country_china_attitude"],
            "map_modes_note": (
                "Primary board: events newest-first by event_time. "
                "Attitude map: monitored media sample colors — not official state position."
            ),
            "time_window": metrics.get("time_window"),
        },
        "kpis": {
            "total_articles_universe": metrics.get("universe_count"),
            "china_article_count": research.get("article_count", {}).get("value"),
            "weighted_article_volume": weighted.get("weighted_article_volume", {}).get("value"),
            "monitoring_countries": panel["monitoring_countries"],
            "active_sources_registry": panel["active_sources_registry"],
            "china_reporting_countries": ops.get("country_count", {}).get("value"),
            "china_reporting_sources": ops.get("source_count", {}).get("value"),
            "country_count": ops.get("country_count", {}).get("value"),
            "source_count": ops.get("source_count", {}).get("value"),
            "major_events": len(events),
            "alerts": 0,
        },
        "maps": {
            "event_geography": event_pins,
            "country_china_attitude": attitude_rows,
            "reporting_source": reporting_pins,
        },
        "topics": research.get("topic_share", {}).get("value") or {},
        "sentiment": research.get("sentiment_distribution", {}).get("value") or {},
        "events": events[:15],
        "anomalies": {
            "note": "Rule alerts land in P1-F; listing proto-events by importance for now.",
            "items": [
                {
                    "kind": "major_proto_event",
                    "event_id": e["id"],
                    "title": e["title"],
                    "importance_score": e["importance_score"],
                    "article_count": e["article_count"],
                }
                for e in events[:8]
            ],
        },
        "views_raw_weighted": metrics.get("views"),
    }

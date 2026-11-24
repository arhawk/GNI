"""Streamlit UI helpers for GNI dashboard."""

from __future__ import annotations

from typing import Any

import streamlit as st

from datetime import datetime, timedelta, timezone

from gni.dashboard.data import NAV_PAGES, PRESET_DAYS, DashboardFilters
from gni.metrics.definitions import (
    CHINA_INCLUDE_LEVELS,
    METRIC_DEFINITION_VERSION,
    RELEVANCE_WEIGHT_VERSION,
)


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
          --gni-ink: #14213d;
          --gni-accent: #c45c26;
          --gni-muted: #5c6b7a;
          --gni-panel: #f3f0ea;
          --gni-line: #d9d2c5;
        }
        .stApp { background: linear-gradient(180deg, #f7f4ee 0%, #ebe6dc 100%); }
        h1, h2, h3 { color: var(--gni-ink) !important; font-family: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif !important; }
        div[data-testid="stMetric"] {
          background: #fffdf8;
          border: 1px solid var(--gni-line);
          padding: 0.75rem 1rem;
          border-radius: 2px;
        }
        .gni-meta { color: var(--gni-muted); font-size: 0.85rem; margin-bottom: 0.75rem; }
        .gni-section-note { color: var(--gni-muted); font-size: 0.9rem; margin-top: -0.4rem; margin-bottom: 1rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_filters(
    *,
    countries: list[dict[str, str]],
    sources: list[dict[str, Any]],
) -> tuple[str, DashboardFilters]:
    st.sidebar.title("GNI Monitor")
    st.sidebar.caption("Official-media narrative monitoring")
    page = st.sidebar.radio("Navigation", NAV_PAGES, index=0)

    st.sidebar.markdown("---")
    st.sidebar.subheader("Global filters")
    preset_labels = {1: "1 day", 7: "1 week", 30: "1 month", 90: "3 months", 365: "1 year"}
    days = st.sidebar.selectbox(
        "Time window",
        list(PRESET_DAYS),
        index=list(PRESET_DAYS).index(30),
        format_func=lambda d: preset_labels.get(d, f"{d} days"),
    )
    end_date = st.sidebar.date_input(
        "Window end (UTC date)",
        value=datetime.now(timezone.utc).date(),
        help="Drag observation window by changing end; start = end − duration.",
    )
    country_ids = [c["id"] for c in countries]
    selected_countries = st.sidebar.multiselect(
        "Countries",
        options=country_ids,
        default=[],
        format_func=lambda i: next((c["name"] for c in countries if c["id"] == i), i),
    )
    source_ids = [s["id"] for s in sources]
    selected_sources = st.sidebar.multiselect(
        "Sources",
        options=source_ids,
        default=[],
        format_func=lambda i: next((s["name"] for s in sources if s["id"] == i), i),
    )
    target = st.sidebar.selectbox("Target", ["china"], index=0)
    rel_opts = sorted(CHINA_INCLUDE_LEVELS | {"incidental", "none", "uncertain"})
    relevance_levels = st.sidebar.multiselect(
        "China Relevance Level",
        options=rel_opts,
        default=sorted(CHINA_INCLUDE_LEVELS),
    )
    sentiments = st.sidebar.multiselect(
        "Sentiment",
        ["positive", "negative", "neutral", "mixed"],
        default=[],
    )
    stances = st.sidebar.multiselect(
        "Stance",
        ["supportive", "opposing", "critical", "cautious", "neutral", "mixed", "no_explicit_stance"],
        default=[],
    )
    frames = st.sidebar.multiselect(
        "Frame (primary)",
        [
            "competition_rivalry",
            "security_threat",
            "economic_impact",
            "cooperation",
            "governance_ideology",
            "development_innovation",
            "human_rights",
            "international_order",
            "other_unknown",
        ],
        default=[],
    )
    topics = st.sidebar.multiselect(
        "Topic (primary)",
        [
            "politics_governance",
            "economy_trade",
            "technology",
            "security_military",
            "international_relations",
            "society_culture",
            "environment_energy",
            "other_unknown",
        ],
        default=[],
    )
    analysis_statuses = st.sidebar.multiselect(
        "Analysis status",
        ["completed", "needs_review", "insufficient_evidence", "failed", "pending"],
        default=[],
    )

    end_dt = datetime(
        end_date.year, end_date.month, end_date.day, 23, 59, 59, tzinfo=timezone.utc
    )
    start_dt = end_dt - timedelta(days=int(days))
    filters = DashboardFilters(
        days=int(days),
        window_start=start_dt,
        window_end=end_dt,
        countries=selected_countries,
        source_ids=selected_sources,
        target=target,
        relevance_levels=relevance_levels or sorted(CHINA_INCLUDE_LEVELS),
        sentiments=sentiments,
        stances=stances,
        frames=frames,
        topics=topics,
        analysis_statuses=analysis_statuses,
        timezone_label="UTC",
    )
    return page, filters


def metric_meta_line(metrics: dict[str, Any], filters: DashboardFilters) -> None:
    tw = metrics.get("time_window") or {}
    research = metrics.get("research") or {}
    ac = research.get("article_count") or {}
    wv = (metrics.get("weighted") or {}).get("weighted_article_volume") or {}
    att = research.get("attention_share") or {}
    st.markdown(
        f'<div class="gni-meta">'
        f'Window {tw.get("start") or "—"} → {tw.get("end") or "—"} ({filters.timezone_label}) · '
        f'n={ac.get("value")} · weighted={wv.get("value")} · '
        f'denom={att.get("denominator")} · '
        f'{METRIC_DEFINITION_VERSION} · {RELEVANCE_WEIGHT_VERSION}'
        f"</div>",
        unsafe_allow_html=True,
    )


def show_attention_share(att: dict[str, Any]) -> None:
    if att.get("status") != "available" or att.get("value") is None:
        st.warning(
            "Attention Share unavailable — denominator unreliable or empty "
            f"(status={att.get('status')}). Formal value not shown."
        )
        return
    st.metric("Attention Share", f"{float(att['value']) * 100:.1f}%")


def distribution_bars(title: str, counts: dict[str, Any], *, note: str) -> None:
    st.subheader(title)
    st.caption(note)
    if not counts:
        st.info("No data in current filters.")
        return
    import pandas as pd

    df = pd.DataFrame({"label": list(counts.keys()), "count": list(counts.values())})
    df = df.sort_values("count", ascending=False)
    st.bar_chart(df.set_index("label"))


def empty_p1f_placeholder(feature: str) -> None:
    st.info(
        f"**{feature}** — Phase 1-E shows an empty placeholder list. "
        "Rule engines and generators arrive in **P1-F**."
    )
    st.dataframe(
        [{"id": "—", "status": "pending_p1f", "note": f"No {feature.lower()} yet"}],
        use_container_width=True,
        hide_index=True,
    )

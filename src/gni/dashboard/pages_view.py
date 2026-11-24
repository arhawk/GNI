"""Dashboard page renderers."""

from __future__ import annotations

from typing import Any

import streamlit as st

from gni.dashboard.data import (
    DashboardFilters,
    ArticleCard,
    country_breakdown,
    get_article_detail,
    list_article_cards,
    load_source_health,
)
from gni.dashboard.ui import (
    distribution_bars,
    empty_p1f_placeholder,
    metric_meta_line,
    show_attention_share,
)


def page_overview(session, filters: DashboardFilters, metrics: dict[str, Any]) -> None:
    st.title("Overview")
    st.markdown(
        '<p class="gni-section-note">What is happening now in monitored official media coverage of China?</p>',
        unsafe_allow_html=True,
    )
    metric_meta_line(metrics, filters)

    research = metrics["research"]
    weighted = metrics["weighted"]
    ops = metrics["operational"]

    from gni.dashboard.data import monitoring_panel_counts

    panel = monitoring_panel_counts(session)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Article Count (raw)", research["article_count"]["value"])
    c2.metric("Weighted Volume", weighted["weighted_article_volume"]["value"])
    c3.metric("Monitoring countries", panel["monitoring_countries"])
    c4.metric("Active sources (registry)", panel["active_sources_registry"])

    c3b, c4b = st.columns(2)
    c3b.metric("China-set countries", ops["country_count"]["value"])
    c4b.metric("China-set sources", ops["source_count"]["value"])

    c5, c6, c7, c8 = st.columns(4)
    with c5:
        show_attention_share(research["attention_share"])
    np_r = weighted["np_ratio"]
    c6.metric(
        "N/P Ratio (weighted)",
        np_r["value"] if np_r["status"] == "ok" else "N/A",
    )
    c7.metric(
        "Weighted Sentiment Score",
        weighted["weighted_sentiment_score"]["value"]
        if weighted["weighted_sentiment_score"]["status"] == "ok"
        else "N/A",
    )
    c8.metric("News candidates / Alerts", "0 / 0")
    st.caption("Major-news candidates and alerts: placeholders until P1-F.")

    st.subheader("Sentiment vs Stance (separate)")
    left, right = st.columns(2)
    with left:
        sent = research["sentiment_distribution"]["value"].get("counts") or {}
        distribution_bars("Sentiment (raw counts)", sent, note="Not merged with stance.")
    with right:
        stance_counts = research["stance_distribution"]["value"].get("counts") or {}
        distribution_bars("Stance (target-bound)", stance_counts, note="Keys are target|stance.")

    st.subheader("Raw vs Weighted")
    r1, r2 = st.columns(2)
    with r1:
        st.markdown("**Raw view**")
        st.write(
            {
                "article_count": metrics["views"]["raw"]["article_count"],
                "sentiment": metrics["views"]["raw"]["sentiment_distribution"],
            }
        )
    with r2:
        st.markdown("**Weighted view**")
        st.write(
            {
                "weighted_article_volume": metrics["views"]["weighted"]["weighted_article_volume"],
                "weighted_sentiment_score": metrics["views"]["weighted"]["weighted_sentiment_score"],
                "np_ratio": metrics["views"]["weighted"]["np_ratio"],
            }
        )

    st.subheader("Country ranking")
    ranking = country_breakdown(session, filters)
    if ranking:
        import pandas as pd

        df = pd.DataFrame(ranking)[["country_id", "article_count", "weighted_volume", "weighted_sentiment_score"]]
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.bar_chart(df.set_index("country_id")[["article_count", "weighted_volume"]])
    else:
        st.info("No country data.")

    st.subheader("Quality strip (ops — not narrative conclusions)")
    q1, q2 = st.columns(2)
    q1.metric(
        "Ingestion success",
        f"{ops['ingestion_success_rate']['value']}"
        if ops["ingestion_success_rate"]["status"] == "ok"
        else "N/A",
    )
    q2.metric(
        "Extraction success",
        f"{ops['article_extraction_success_rate']['value']}"
        if ops["article_extraction_success_rate"]["status"] == "ok"
        else "N/A",
    )

    st.subheader("Recent China-related articles")
    cards = list_article_cards(session, filters, china_only=True, limit=15)
    _article_table(cards)


def page_countries(session, filters: DashboardFilters, metrics: dict[str, Any]) -> None:
    st.title("Countries")
    st.markdown(
        '<p class="gni-section-note">How do monitored outlets in each country cover China?</p>',
        unsafe_allow_html=True,
    )
    metric_meta_line(metrics, filters)

    ranking = country_breakdown(session, filters)
    if not ranking:
        st.warning("No countries in scope.")
        return

    options = [r["country_id"] for r in ranking]
    default = filters.countries[0] if filters.countries else options[0]
    pick = st.selectbox("Focus country", options, index=options.index(default) if default in options else 0)
    focus = DashboardFilters(
        days=filters.days,
        window_start=filters.window_start,
        window_end=filters.window_end,
        countries=[pick],
        source_ids=filters.source_ids,
        target=filters.target,
        relevance_levels=filters.relevance_levels,
        sentiments=filters.sentiments,
        stances=filters.stances,
        frames=filters.frames,
        topics=filters.topics,
        analysis_statuses=filters.analysis_statuses,
        timezone_label=filters.timezone_label,
    )
    from gni.dashboard.data import compute_dashboard_metrics

    m = compute_dashboard_metrics(session, focus)
    metric_meta_line(m, focus)

    a, b, c = st.columns(3)
    a.metric("Article Count", m["research"]["article_count"]["value"])
    b.metric("Weighted Volume", m["weighted"]["weighted_article_volume"]["value"])
    with c:
        show_attention_share(m["research"]["attention_share"])

    left, right = st.columns(2)
    with left:
        distribution_bars(
            "Sentiment (raw)",
            m["research"]["sentiment_distribution"]["value"].get("counts") or {},
            note="Separate from stance.",
        )
        distribution_bars(
            "Topic share (primary)",
            m["research"]["topic_share"]["value"].get("counts") or {},
            note="Primary topic only.",
        )
    with right:
        distribution_bars(
            "Stance (target-bound)",
            m["research"]["stance_distribution"]["value"].get("counts") or {},
            note="Not mixed into sentiment chart.",
        )
        distribution_bars(
            "Frame (primary)",
            m["research"]["frame_distribution"]["value"].get("counts") or {},
            note="taxonomy_v0.4 primary-only.",
        )

    st.subheader("Source contribution")
    cards = list_article_cards(session, focus, china_only=True, limit=100)
    from collections import Counter

    contrib = Counter(c.source_name or c.source_id for c in cards)
    distribution_bars("Articles by source", dict(contrib), note=f"Country={pick}")

    st.subheader("Articles")
    _article_table(cards[:30])


def page_news(_session, _filters: DashboardFilters, _metrics: dict[str, Any]) -> None:
    st.title("News & Events")
    st.markdown(
        '<p class="gni-section-note">Phase 1: rule/similarity candidate clusters (not a full event graph).</p>',
        unsafe_allow_html=True,
    )
    empty_p1f_placeholder("Major news candidates")


def page_articles(session, filters: DashboardFilters, metrics: dict[str, Any]) -> None:
    st.title("Articles")
    st.markdown(
        '<p class="gni-section-note">Filterable article library with evidence drill-down.</p>',
        unsafe_allow_html=True,
    )
    metric_meta_line(metrics, filters)
    cards = list_article_cards(session, filters, china_only=True, limit=200)
    _article_table(cards)

    ids = [c.id for c in cards]
    if not ids:
        return
    selected = st.selectbox(
        "Open article detail",
        options=ids,
        format_func=lambda i: next((f"{(c.title or '')[:80]} [{c.country_id}]" for c in cards if c.id == i), i),
    )
    detail = get_article_detail(session, selected)
    if not detail:
        st.error("Article not found.")
        return
    art = detail["article"]
    st.markdown(f"### {art.get('title') or '(untitled)'}")
    st.write(
        {
            "source": detail["source"],
            "level": art.get("china_relevance_level"),
            "weight": art.get("china_relevance_weight"),
            "url": art.get("url"),
            "analysis_status": art.get("analysis_status"),
        }
    )
    st.subheader("China spans (L3)")
    if detail["spans"]:
        st.dataframe(detail["spans"], use_container_width=True, hide_index=True)
    else:
        st.caption("No validated spans stored.")
    st.subheader("Structured analysis")
    st.json(detail["analysis"].get("structured_result") or {})
    st.caption(
        f"provider={detail['analysis'].get('provider')} · "
        f"schema={detail['analysis'].get('schema_version')} · "
        f"weight={detail['analysis'].get('relevance_weight_version')}"
    )


def page_reports(_session, _filters: DashboardFilters, _metrics: dict[str, Any]) -> None:
    st.title("Reports")
    empty_p1f_placeholder("Reports")


def page_alerts(_session, _filters: DashboardFilters, _metrics: dict[str, Any]) -> None:
    st.title("Alerts")
    st.markdown("#### Narrative alerts")
    empty_p1f_placeholder("Narrative alerts")
    st.markdown("#### Quality / ops alerts")
    empty_p1f_placeholder("Quality alerts")
    st.caption("Quality and narrative alerts stay in separate sections.")


def page_sources(session, filters: DashboardFilters, metrics: dict[str, Any]) -> None:
    st.title("Sources & Quality")
    st.markdown(
        '<p class="gni-section-note">Operational quality — separated from narrative conclusions.</p>',
        unsafe_allow_html=True,
    )
    metric_meta_line(metrics, filters)
    ops = metrics["operational"]
    a, b, c = st.columns(3)
    a.metric("Source count (China set)", ops["source_count"]["value"])
    b.metric(
        "Ingestion success rate",
        ops["ingestion_success_rate"]["value"]
        if ops["ingestion_success_rate"]["status"] == "ok"
        else "N/A",
    )
    c.metric(
        "Extraction success rate",
        ops["article_extraction_success_rate"]["value"]
        if ops["article_extraction_success_rate"]["status"] == "ok"
        else "N/A",
    )
    st.subheader("Source health")
    rows = load_source_health(session)
    if filters.countries:
        rows = [r for r in rows if r["country_id"] in filters.countries]
    if filters.source_ids:
        rows = [r for r in rows if r["source_id"] in filters.source_ids]
    st.dataframe(rows, use_container_width=True, hide_index=True)
    st.info("Token/cost rollups appear after LLM analysis runs; narrative KPIs stay on Overview.")


def page_research(_session, filters: DashboardFilters, metrics: dict[str, Any]) -> None:
    st.title("Research")
    st.markdown(
        '<p class="gni-section-note">Phase 1 placeholder for deeper cross-country research views.</p>',
        unsafe_allow_html=True,
    )
    metric_meta_line(metrics, filters)
    st.write(
        {
            "target": filters.target,
            "metric_definition_version": metrics.get("metric_definition_version"),
            "universe_count": metrics.get("universe_count"),
            "note": "Heatmaps / open research agent → later phases.",
        }
    )


def _article_table(cards: list[ArticleCard]) -> None:
    if not cards:
        st.info("No articles match current filters.")
        return
    rows = [
        {
            "title": (c.title or "")[:100],
            "country": c.country_id,
            "source": c.source_name or c.source_id,
            "published_at": c.published_at.isoformat() if c.published_at else None,
            "level": c.china_relevance_level,
            "weight": c.china_relevance_weight,
            "sentiment": c.sentiment_label,
            "stance": ", ".join(c.stance_labels) if c.stance_labels else None,
            "topic": c.topic_primary,
            "frame": c.frame_primary,
            "url": c.url,
        }
        for c in cards
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)

"""GNI Streamlit dashboard entrypoint (P1-E)."""

from __future__ import annotations

import streamlit as st

from gni.dashboard.data import compute_dashboard_metrics, load_countries, load_sources
from gni.dashboard.pages_view import (
    page_alerts,
    page_articles,
    page_countries,
    page_news,
    page_overview,
    page_reports,
    page_research,
    page_sources,
)
from gni.dashboard.ui import inject_styles, render_sidebar_filters
from gni.infrastructure.db import ensure_schema, session_scope


def main() -> None:
    st.set_page_config(
        page_title="GNI Monitor",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    inject_styles()
    ensure_schema()

    with session_scope() as session:
        countries = load_countries(session)
        sources = load_sources(session)
        page, filters = render_sidebar_filters(countries=countries, sources=sources)
        metrics = compute_dashboard_metrics(session, filters)

        if page == "Overview":
            page_overview(session, filters, metrics)
        elif page == "Countries":
            page_countries(session, filters, metrics)
        elif page == "News & Events":
            page_news(session, filters, metrics)
        elif page == "Articles":
            page_articles(session, filters, metrics)
        elif page == "Reports":
            page_reports(session, filters, metrics)
        elif page == "Alerts":
            page_alerts(session, filters, metrics)
        elif page == "Sources & Quality":
            page_sources(session, filters, metrics)
        else:
            page_research(session, filters, metrics)


if __name__ == "__main__":
    main()

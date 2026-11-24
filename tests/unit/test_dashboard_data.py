"""Dashboard data layer tests (no Streamlit runtime required)."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from gni.core.config import get_settings
from gni.dashboard.data import (
    NAV_PAGES,
    DashboardFilters,
    compute_dashboard_metrics,
    get_article_detail,
    list_article_cards,
    load_countries,
    load_sources,
)
from gni.infrastructure.db import ensure_schema, reset_engine, session_scope
from gni.infrastructure.models import Article, Country, Organization, Source


@pytest.fixture()
def db(tmp_path, monkeypatch):
    db_path = tmp_path / "p1e.sqlite"
    monkeypatch.setenv("GNI_DATABASE_URL", f"sqlite:///{db_path}")
    get_settings.cache_clear()
    reset_engine()
    ensure_schema()
    yield
    reset_engine()
    get_settings.cache_clear()


def _seed(session):
    session.merge(Country(id="US", code="US", name="United States"))
    session.merge(Country(id="JP", code="JP", name="Japan"))
    session.merge(Organization(id="org_e", country_id="US", name="Org", organization_type="media"))
    session.merge(
        Source(
            id="src_e",
            organization_id="org_e",
            country_id="US",
            name="Test Source",
            source_type="news",
            access_method="rss",
            adapter_type="rss_adapter",
            active_status="active",
            language="en",
        )
    )
    now = datetime.now(timezone.utc)
    aid = str(uuid4())
    session.add(
        Article(
            id=aid,
            source_id="src_e",
            title="China trade talks",
            url=f"https://example.test/{aid}",
            language="en",
            processing_status="done",
            quality_status="processed",
            exclude_from_metrics=False,
            china_relevance_level="substantial",
            china_relevance_weight=0.65,
            analysis_status="completed",
            content_hash="h1",
            published_at=now,
            first_seen_at=now,
        )
    )
    return aid


def test_nav_has_eight_pages():
    assert len(NAV_PAGES) == 8
    assert NAV_PAGES[0] == "Overview"
    assert "Articles" in NAV_PAGES
    assert "Sources & Quality" in NAV_PAGES


def test_dashboard_metrics_and_cards(db):
    with session_scope() as session:
        aid = _seed(session)
        session.flush()
        countries = load_countries(session)
        sources = load_sources(session)
        assert any(c["id"] == "US" for c in countries)
        assert any(s["id"] == "src_e" for s in sources)

        filters = DashboardFilters(days=30, countries=["US"], target="china")
        metrics = compute_dashboard_metrics(session, filters)
        assert metrics["research"]["article_count"]["value"] == 1
        assert "views" in metrics
        assert "raw" in metrics["views"] and "weighted" in metrics["views"]

        cards = list_article_cards(session, filters, china_only=True)
        assert len(cards) == 1
        assert cards[0].id == aid

        detail = get_article_detail(session, aid)
        assert detail is not None
        assert detail["article"]["title"] == "China trade talks"


def test_attention_unavailable_empty_window(db):
    with session_scope() as session:
        filters = DashboardFilters(days=1, countries=["ZZ"])
        metrics = compute_dashboard_metrics(session, filters)
        assert metrics["research"]["attention_share"]["status"] == "unavailable"

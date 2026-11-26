"""Offline analyze service with SQLite."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from gni.analysis.service import analyze_article, run_analysis
from gni.infrastructure.db import ensure_schema, reset_engine, session_scope
from gni.infrastructure.models import Article, ArticleVersion, Country, Organization, Source
from gni.processing.title_l1 import load_dictionary


@pytest.fixture()
def db(tmp_path, monkeypatch):
    db_path = tmp_path / "p1c.sqlite"
    monkeypatch.setenv("GNI_DATABASE_URL", f"sqlite:///{db_path}")
    # Clear settings cache
    from gni.core.config import get_settings

    get_settings.cache_clear()
    reset_engine()
    load_dictionary.cache_clear()
    ensure_schema()
    yield
    reset_engine()
    get_settings.cache_clear()


def _seed_article(session: Session, *, body: str, title: str) -> Article:
    session.merge(Country(id="US", code="US", name="United States"))
    session.merge(
        Organization(
            id="org_test",
            country_id="US",
            name="Test Org",
            organization_type="media",
        )
    )
    session.merge(
        Source(
            id="src_test",
            organization_id="org_test",
            country_id="US",
            name="Test Source",
            source_type="news",
            access_method="rss",
            adapter_type="rss_adapter",
            active_status="active",
            language="en",
        )
    )
    article = Article(
        id=str(uuid4()),
        source_id="src_test",
        title=title,
        url=f"https://example.test/{uuid4()}",
        content_clean=body,
        language="en",
        processing_status="done",
        quality_status="processed",
        title_screening_label="explicit_relevant",
        title_screening_priority="P1",
        analysis_status="pending",
        processed_at=datetime.now(timezone.utc),
        first_seen_at=datetime.now(timezone.utc),
    )
    session.add(article)
    session.flush()
    session.add(
        ArticleVersion(
            id=str(uuid4()),
            article_id=article.id,
            version_no=1,
            extraction_method="test",
            content_clean=body,
            language="en",
            char_count=len(body),
            quality_status="ok",
        )
    )
    session.flush()
    return article


def test_analyze_article_persists_l2_spans_relevance(db):
    body = (
        "China announced new rules on advanced chip exports this week. "
        "Chinese officials said the policy protects national security. "
        "Markets reacted as supply chains adjusted across Asia."
    )
    with session_scope() as session:
        article = _seed_article(session, body=body, title="China chip export rules")
        detail = analyze_article(session, article, provider="heuristic")
        assert detail["ok"] is True
        assert detail["fulltext_screening"] == "china_related"
        assert detail["span_count"] >= 1
        assert detail["relevance_level"] in {"core", "substantial", "secondary", "incidental"}
        assert article.china_relevance_level == detail["relevance_level"]
        assert article.analysis_status in {"completed", "needs_review", "insufficient_evidence"}


def test_run_analysis_batch(db):
    body = (
        "Trade tensions with China dominate the editorial. "
        "Chinese Government negotiators remain cautious while tariffs stay in place."
    )
    with session_scope() as session:
        _seed_article(session, body=body, title="China trade editorial")
        run = run_analysis(session, limit=5, provider="heuristic")
        assert run.status in {"success", "partial"}
        assert run.schema_version == "article_analysis_v1.0"
        assert run.relevance_weight_version == "provisional_v0.3"
        assert (run.stats or {}).get("ok", 0) >= 1

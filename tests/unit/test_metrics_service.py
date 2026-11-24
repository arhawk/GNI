"""metric_runs persistence smoke test."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from gni.core.config import get_settings
from gni.infrastructure.db import ensure_schema, reset_engine, session_scope
from gni.infrastructure.models import Article, Country, Organization, Source
from gni.metrics.service import metric_run_to_dict, run_metrics


@pytest.fixture()
def db(tmp_path, monkeypatch):
    db_path = tmp_path / "p1d.sqlite"
    monkeypatch.setenv("GNI_DATABASE_URL", f"sqlite:///{db_path}")
    get_settings.cache_clear()
    reset_engine()
    ensure_schema()
    yield
    reset_engine()
    get_settings.cache_clear()


def test_run_metrics_persists(db):
    with session_scope() as session:
        session.merge(Country(id="US", code="US", name="United States"))
        session.merge(
            Organization(id="org_m", country_id="US", name="Org", organization_type="media")
        )
        session.merge(
            Source(
                id="src_m",
                organization_id="org_m",
                country_id="US",
                name="Src",
                source_type="news",
                access_method="rss",
                adapter_type="rss_adapter",
                active_status="active",
                language="en",
            )
        )
        session.add(
            Article(
                id=str(uuid4()),
                source_id="src_m",
                title="China trade",
                url=f"https://example.test/{uuid4()}",
                language="en",
                processing_status="done",
                quality_status="processed",
                exclude_from_metrics=False,
                china_relevance_level="substantial",
                china_relevance_weight=0.65,
                analysis_status="completed",
                content_hash="abc",
                published_at=datetime.now(timezone.utc),
                first_seen_at=datetime.now(timezone.utc),
            )
        )
        session.add(
            Article(
                id=str(uuid4()),
                source_id="src_m",
                title="Local sports",
                url=f"https://example.test/{uuid4()}",
                language="en",
                processing_status="done",
                quality_status="processed",
                exclude_from_metrics=False,
                china_relevance_level="none",
                china_relevance_weight=0.0,
                analysis_status="completed",
                content_hash="def",
                published_at=datetime.now(timezone.utc),
                first_seen_at=datetime.now(timezone.utc),
            )
        )
        run = run_metrics(session, days=30, country="US")
        payload = metric_run_to_dict(run)
        assert payload["status"] == "success"
        assert payload["results"]["research"]["article_count"]["value"] == 1
        assert payload["results"]["research"]["attention_share"]["status"] == "available"
        assert payload["results"]["research"]["attention_share"]["denominator"] == 2
        assert "views" in payload["results"]
        assert payload["metric_definition_version"] == "metrics_v0.4"

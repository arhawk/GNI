"""Per-country analyze selection cap."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from gni.analysis.service import _select_articles_for_analysis
from gni.core.config import get_settings
from gni.infrastructure.db import ensure_schema, reset_engine, session_scope
from gni.infrastructure.models import Article, Country, Organization, Source


@pytest.fixture()
def db(tmp_path, monkeypatch):
    db_path = tmp_path / "pc.sqlite"
    monkeypatch.setenv("GNI_DATABASE_URL", f"sqlite:///{db_path}")
    get_settings.cache_clear()
    reset_engine()
    ensure_schema()
    yield
    reset_engine()
    get_settings.cache_clear()


def test_per_country_cap(db):
    now = datetime.now(timezone.utc)
    with session_scope() as session:
        for cid in ("US", "DE", "RU"):
            session.merge(Country(id=cid, code=cid, name=cid))
            session.merge(
                Organization(
                    id=f"org_{cid}",
                    country_id=cid,
                    name=cid,
                    organization_type="media",
                )
            )
            session.merge(
                Source(
                    id=f"src_{cid}",
                    organization_id=f"org_{cid}",
                    country_id=cid,
                    name=cid,
                    source_type="news",
                    access_method="rss",
                    adapter_type="rss_adapter",
                    active_status="active",
                    language="en",
                )
            )
            for i in range(5):
                aid = str(uuid4())
                session.add(
                    Article(
                        id=aid,
                        source_id=f"src_{cid}",
                        title=f"{cid} story {i}",
                        url=f"https://example.test/{aid}",
                        language="en",
                        processing_status="done",
                        quality_status="processed",
                        exclude_from_metrics=False,
                        analysis_status="pending",
                        content_hash=aid[:16],
                        first_seen_at=now,
                        published_at=now,
                    )
                )
        session.flush()
        picked, counts = _select_articles_for_analysis(
            session,
            limit=100,
            source_id=None,
            article_id=None,
            reanalyze=False,
            per_country=2,
            articles_remaining=100,
        )
        assert len(picked) == 6
        assert counts == {"DE": 2, "RU": 2, "US": 2}

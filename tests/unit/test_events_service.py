"""P1-F proto-Event persistence and API payload shape."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from gni.core.config import get_settings
from gni.events.service import get_event_detail, list_events, overview_payload, rebuild_proto_events
from gni.infrastructure.db import ensure_schema, reset_engine, session_scope
from gni.infrastructure.models import Article, Country, EventLocation, Organization, Source


@pytest.fixture()
def db(tmp_path, monkeypatch):
    db_path = tmp_path / "events.sqlite"
    monkeypatch.setenv("GNI_DATABASE_URL", f"sqlite:///{db_path}")
    get_settings.cache_clear()
    reset_engine()
    ensure_schema()
    yield
    reset_engine()
    get_settings.cache_clear()


def _seed_two_articles(session):
    session.merge(Country(id="US", code="US", name="United States"))
    session.merge(Country(id="DE", code="DE", name="Germany"))
    session.merge(Organization(id="org_us", country_id="US", name="OrgUS", organization_type="media"))
    session.merge(Organization(id="org_de", country_id="DE", name="OrgDE", organization_type="media"))
    for sid, cid, name in (("src_us", "US", "US Wire"), ("src_de", "DE", "DE Wire")):
        session.merge(
            Source(
                id=sid,
                organization_id=f"org_{cid.lower()}",
                country_id=cid,
                name=name,
                source_type="news",
                access_method="rss",
                adapter_type="rss_adapter",
                active_status="active",
                language="en",
            )
        )
    now = datetime.now(timezone.utc)
    ids = []
    for sid, title in (
        ("src_us", "China trade talks resume in Brussels"),
        ("src_de", "China trade talks resume amid tariffs"),
    ):
        aid = str(uuid4())
        ids.append(aid)
        session.add(
            Article(
                id=aid,
                source_id=sid,
                title=title,
                url=f"https://example.test/{aid}",
                language="en",
                processing_status="done",
                quality_status="processed",
                exclude_from_metrics=False,
                china_relevance_level="substantial",
                china_relevance_weight=0.65,
                analysis_status="completed",
                content_hash=aid[:16],
                published_at=now,
                first_seen_at=now,
            )
        )
    return ids


def test_rebuild_proto_no_forced_coords(db):
    with session_scope() as session:
        _seed_two_articles(session)
        session.flush()
        # Legacy title path never invents EVENT_LOCATION coords
        stats = rebuild_proto_events(
            session, min_articles=1, limit=20, legacy_title=True
        )
        assert stats["created"] >= 1
        assert stats["path"] == "legacy_title"
        events = list_events(session, limit=20)
        assert events
        assert all(e["has_physical_location"] is False for e in events)
        from sqlalchemy import func, select

        n_loc = session.scalar(select(func.count()).select_from(EventLocation)) or 0
        assert n_loc == 0

        detail = get_event_detail(session, events[0]["id"])
        assert detail is not None
        assert detail["views"]["where"]["note"]
        assert "who_reports" in detail["views"]
        assert "how_they_frame" in detail["views"]
        assert isinstance(detail["timeline"], list)
        for pin in detail["views"]["who_reports"]["reporting_map"]:
            assert pin["layer"] == "reporting_source"

        overview = overview_payload(session, days=30)
        assert overview["meta"]["map_modes"] == [
            "event_time_list",
            "country_china_attitude",
        ]
        assert overview["kpis"]["major_events"] >= 1
        assert overview["maps"]["event_geography"] == []
        assert "country_china_attitude" in overview["maps"]

"""Event lifecycle: active / dormant / closed derived from last linked article activity."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from gni.core.config import Settings, get_settings
from gni.events.fingerprint import FingerprintCard
from gni.events.lifecycle import classify_lifecycle, refresh_event_lifecycle
from gni.events.match import FingerprintCluster
from gni.events.service import _persist_fingerprint_cluster, list_events
from gni.infrastructure.db import ensure_schema, reset_engine, session_scope
from gni.infrastructure.models import (
    Article,
    Country,
    Event,
    EventArticle,
    EventRevision,
    Organization,
    Source,
)

NOW = datetime(2026, 11, 28, 12, 0, tzinfo=UTC)


@pytest.fixture()
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("GNI_DATABASE_URL", f"sqlite:///{tmp_path / 'lifecycle.sqlite'}")
    get_settings.cache_clear()
    reset_engine()
    ensure_schema()
    yield
    reset_engine()
    get_settings.cache_clear()


def _settings() -> Settings:
    return Settings(event_dormant_days=14, event_closed_days=90)


# ---- pure rule -------------------------------------------------------------


@pytest.mark.parametrize(
    ("age", "status", "expected"),
    [
        (0.5, "active", "active"),
        (14.0, "active", "active"),  # boundary: <= dormant_days stays active
        (14.01, "active", "dormant"),
        (90.0, "dormant", "dormant"),  # boundary: <= closed_days is dormant
        (90.01, "dormant", "closed"),
        (3.0, "proto", "proto"),  # recent low-confidence tier is kept
        (30.0, "proto", "dormant"),
        (3.0, "dormant", "active"),  # reactivation
        (3.0, "closed", "active"),  # reactivation from archive
        (None, "active", None),  # no linked articles: leave alone
        (3.0, "locked", None),  # manual states are never rewritten
        (200.0, "locked", None),
        (200.0, "merged", None),
        (200.0, "confirmed", None),
    ],
)
def test_classify_lifecycle_boundaries(age, status, expected):
    assert classify_lifecycle(age, status, dormant_days=14, closed_days=90) == expected


# ---- database behaviour ----------------------------------------------------


def _seed_source(session) -> str:
    session.merge(Country(id="US", code="US", name="United States"))
    session.merge(
        Organization(id="org_us", country_id="US", name="OrgUS", organization_type="media")
    )
    session.merge(
        Source(
            id="src_us",
            organization_id="org_us",
            country_id="US",
            name="US Wire",
            source_type="news",
            access_method="rss",
            adapter_type="rss_adapter",
            active_status="active",
            language="en",
        )
    )
    return "src_us"


def _article(session, source_id: str, when: datetime, title: str = "China talks") -> str:
    aid = str(uuid4())
    session.add(
        Article(
            id=aid,
            source_id=source_id,
            title=title,
            url=f"https://example.test/{aid}",
            language="en",
            processing_status="done",
            quality_status="processed",
            exclude_from_metrics=False,
            content_hash=aid[:16],
            published_at=when,
            first_seen_at=when,
        )
    )
    return aid


def _event(session, event_id: str, status: str, article_ids: list[str]) -> None:
    session.add(
        Event(
            id=event_id,
            title=f"event {status}",
            status=status,
            importance_score=0.5,
            schema_version="event_v0.2",
            fingerprint_hash=event_id.replace("-", "")[:32],
        )
    )
    for aid in article_ids:
        session.add(
            EventArticle(id=str(uuid4()), event_id=event_id, article_id=aid, relation="covers")
        )


def test_refresh_transitions_and_audit_rows(db):
    with session_scope() as session:
        src = _seed_source(session)
        recent = _article(session, src, NOW - timedelta(days=3))
        old = _article(session, src, NOW - timedelta(days=30))
        ancient = _article(session, src, NOW - timedelta(days=200))
        session.flush()
        _event(session, "11111111-1111-1111-1111-111111111111", "proto", [recent])
        _event(session, "22222222-2222-2222-2222-222222222222", "active", [old])
        _event(session, "33333333-3333-3333-3333-333333333333", "active", [ancient])
        _event(session, "44444444-4444-4444-4444-444444444444", "locked", [ancient])
        _event(session, "55555555-5555-5555-5555-555555555555", "merged", [])
        session.flush()

        stats = refresh_event_lifecycle(session, now=NOW, settings=_settings())

        status = {e.id: e.status for e in session.scalars(select(Event)).all()}
        assert status["11111111-1111-1111-1111-111111111111"] == "proto"
        assert status["22222222-2222-2222-2222-222222222222"] == "dormant"
        assert status["33333333-3333-3333-3333-333333333333"] == "closed"
        assert status["44444444-4444-4444-4444-444444444444"] == "locked"
        assert status["55555555-5555-5555-5555-555555555555"] == "merged"
        assert stats["transitions"] == {"dormant": 1, "archive": 1}

        revisions = session.scalars(
            select(EventRevision).where(
                EventRevision.event_id == "33333333-3333-3333-3333-333333333333"
            )
        ).all()
        assert [r.action for r in revisions] == ["archive"]
        assert revisions[0].payload["from"] == "active"
        assert revisions[0].payload["to"] == "closed"
        assert revisions[0].actor == "system:lifecycle"

        # Idempotent: a second pass changes nothing and writes no new audit rows.
        again = refresh_event_lifecycle(session, now=NOW, settings=_settings())
        assert again["transitions"] == {}


def test_new_article_reactivates_dormant_event(db):
    with session_scope() as session:
        src = _seed_source(session)
        old = _article(session, src, NOW - timedelta(days=40))
        session.flush()
        _event(session, "66666666-6666-6666-6666-666666666666", "active", [old])
        session.flush()
        refresh_event_lifecycle(session, now=NOW, settings=_settings())
        assert session.get(Event, "66666666-6666-6666-6666-666666666666").status == "dormant"

        fresh = _article(session, src, NOW - timedelta(hours=2), title="China talks resume")
        session.add(
            EventArticle(
                id=str(uuid4()),
                event_id="66666666-6666-6666-6666-666666666666",
                article_id=fresh,
                relation="covers",
            )
        )
        session.flush()
        refresh_event_lifecycle(session, now=NOW, settings=_settings())

        assert session.get(Event, "66666666-6666-6666-6666-666666666666").status == "active"
        actions = [
            r.action
            for r in session.scalars(
                select(EventRevision).where(
                    EventRevision.event_id == "66666666-6666-6666-6666-666666666666"
                )
            ).all()
        ]
        assert sorted(actions) == ["dormant", "reactivate"]


def test_list_events_hides_closed_and_merged_by_default(db):
    with session_scope() as session:
        src = _seed_source(session)
        recent = _article(session, src, datetime.now(UTC) - timedelta(days=1))
        old = _article(session, src, datetime.now(UTC) - timedelta(days=400))
        session.flush()
        _event(session, "77777777-7777-7777-7777-777777777777", "active", [recent])
        _event(session, "88888888-8888-8888-8888-888888888888", "closed", [old])
        _event(session, "99999999-9999-9999-9999-999999999999", "merged", [])
        session.flush()

        default_ids = {e["id"] for e in list_events(session, limit=20)}
        all_ids = {e["id"] for e in list_events(session, limit=20, include_closed=True)}
        assert default_ids == {"77777777-7777-7777-7777-777777777777"}
        assert all_ids == {
            "77777777-7777-7777-7777-777777777777",
            "88888888-8888-8888-8888-888888888888",
            "99999999-9999-9999-9999-999999999999",
        }


def test_rebuild_upsert_keeps_dormant_status_and_widens_window(db):
    with session_scope() as session:
        src = _seed_source(session)
        old = _article(session, src, NOW - timedelta(days=40))
        session.flush()
        card_old = FingerprintCard(
            article_id=old,
            actor="United States",
            action="announces",
            object="export controls",
            event_time=None,
            published_at=NOW - timedelta(days=40),
            confidence=0.9,
            summary="US announces export controls",
        )
        eid, _ = _persist_fingerprint_cluster(session, FingerprintCluster(cards=[card_old]))
        session.flush()
        refresh_event_lifecycle(session, now=NOW, settings=_settings())
        ev = session.get(Event, eid)
        assert ev.status == "dormant"
        wide_end = ev.window_end

        # A later rebuild that only sees a newer-but-still-old cluster must not reset status.
        card_mid = FingerprintCard(
            article_id=old,
            actor="United States",
            action="announces",
            object="export controls",
            event_time=None,
            published_at=NOW - timedelta(days=35),
            confidence=0.9,
            summary="US announces export controls",
        )
        _persist_fingerprint_cluster(session, FingerprintCluster(cards=[card_mid]))
        session.flush()
        ev = session.get(Event, eid)
        assert ev.status == "dormant"
        # window_end never shrinks when a cluster covers less time than before.
        assert ev.window_end is not None and wide_end is not None
        assert ev.window_end.replace(tzinfo=UTC) >= wide_end.replace(tzinfo=UTC)

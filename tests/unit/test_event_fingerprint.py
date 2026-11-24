"""Event Fingerprint normalize, rule match, and rollup shares."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from gni.core.config import get_settings
from gni.events.fingerprint import (
    FingerprintCard,
    normalize_action,
    normalize_actor,
    normalize_object,
    object_overlap,
    rule_relation,
)
from gni.events.match import cluster_fingerprints
from gni.events.rollup import _shares
from gni.events.service import overview_payload, rebuild_proto_events
from gni.infrastructure.db import ensure_schema, reset_engine, session_scope
from gni.infrastructure.models import Article, Country, Organization, Source
from collections import Counter


def test_normalize_action_synonyms():
    assert normalize_action("announces") == "ANNOUNCE"
    assert normalize_action("宣布") == "ANNOUNCE"
    assert normalize_action("signed") == "SIGN"


def test_normalize_actor_aliases():
    assert normalize_actor("Beijing") == "china"
    assert normalize_actor("United States") == "us"
    assert normalize_actor("Washington") == "us"


def test_object_overlap_and_different_actor_not_same():
    assert object_overlap("trade talks tariffs", "trade talks amid tariffs") > 0.4
    now = datetime.now(timezone.utc)
    a = FingerprintCard(
        article_id="1",
        actor="China",
        action="announces",
        object="export controls chips",
        published_at=now,
    )
    b = FingerprintCard(
        article_id="2",
        actor="United States",
        action="announces",
        object="export controls chips",
        published_at=now,
    )
    rel, _ = rule_relation(a, b)
    assert rel != "SAME_EVENT"


def test_same_actor_action_object_within_window():
    now = datetime.now(timezone.utc)
    a = FingerprintCard(
        article_id="1",
        actor="China",
        action="announces",
        object="belt road investment fund",
        published_at=now,
    )
    b = FingerprintCard(
        article_id="2",
        actor="Beijing",
        action="unveil",
        object="belt road investment fund",
        published_at=now + timedelta(hours=12),
    )
    rel, score = rule_relation(a, b)
    assert rel == "SAME_EVENT"
    assert score >= 0.72


def test_cluster_merges_same_event():
    now = datetime.now(timezone.utc)
    cards = [
        FingerprintCard(
            article_id="a1",
            actor="US",
            action="sanctions",
            object="chinese firms",
            published_at=now,
            confidence=0.6,
            summary="US sanctions Chinese firms",
        ),
        FingerprintCard(
            article_id="a2",
            actor="United States",
            action="sanction",
            object="chinese firms entities",
            published_at=now + timedelta(hours=5),
            confidence=0.6,
            summary="US sanctions more Chinese firms",
        ),
        FingerprintCard(
            article_id="a3",
            actor="Germany",
            action="visit",
            object="beijing officials",
            published_at=now,
            confidence=0.5,
            summary="Germany visits Beijing",
        ),
    ]
    clusters = cluster_fingerprints(cards, use_llm=False)
    assert len(clusters) >= 2
    multi = [c for c in clusters if len(c.article_ids) >= 2]
    assert multi, "expected US sanctions articles to merge"


def test_shares_equal_article():
    assert _shares(Counter({"positive": 2, "negative": 2})) == {
        "negative": 0.5,
        "positive": 0.5,
    }


@pytest.fixture()
def db(tmp_path, monkeypatch):
    db_path = tmp_path / "fp.sqlite"
    monkeypatch.setenv("GNI_DATABASE_URL", f"sqlite:///{db_path}")
    get_settings.cache_clear()
    reset_engine()
    ensure_schema()
    yield
    reset_engine()
    get_settings.cache_clear()


def _seed(session):
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
    for sid, title in (
        ("src_us", "China announces new export rules in Beijing"),
        ("src_de", "China announces export rules amid trade talks"),
    ):
        aid = str(uuid4())
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


def test_fingerprint_rebuild_and_overview_modes(db):
    with session_scope() as session:
        _seed(session)
        session.flush()
        stats = rebuild_proto_events(session, min_articles=1, limit=20, use_llm=False)
        assert stats["path"] == "fingerprint"
        assert stats["created"] >= 1
        payload = overview_payload(session, days=30)
        assert "event_geography" in payload["meta"]["map_modes"]
        assert "country_china_attitude" in payload["meta"]["map_modes"]
        assert "country_china_attitude" in payload["maps"]
        # Brussels/Beijing place hint may create pins; without coords events still listed
        assert isinstance(payload["events"], list)

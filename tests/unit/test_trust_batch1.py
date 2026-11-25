"""Batch-1 data-trust fixes: three times, relevance split, L2 gate, stable event id, stance."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from gni.analysis.l2_fulltext import screen_fulltext
from gni.analysis.relevance import assess_relevance
from gni.analysis.stance_util import all_stance_labels, primary_stance_label
from gni.core.config import get_settings
from gni.events.fingerprint import FingerprintCard, fingerprint_hash
from gni.events.match import FingerprintCluster
from gni.events.service import _persist_fingerprint_cluster, _stable_event_id
from gni.infrastructure.db import ensure_schema, reset_engine, session_scope
from gni.infrastructure.models import Article, Country, Event, Organization, Source
from sqlalchemy import select


@pytest.fixture()
def db(tmp_path, monkeypatch):
    db_path = tmp_path / "trust.sqlite"
    monkeypatch.setenv("GNI_DATABASE_URL", f"sqlite:///{db_path}")
    get_settings.cache_clear()
    reset_engine()
    ensure_schema()
    yield
    reset_engine()
    get_settings.cache_clear()


def test_cluster_event_time_not_filled_from_published_at():
    pub = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)
    card = FingerprintCard(
        article_id="a1",
        actor="US",
        action="sanctions",
        object="semiconductors",
        event_time=None,
        published_at=pub,
        confidence=0.8,
    )
    cl = FingerprintCluster(cards=[card])
    assert cl.event_time is None
    assert card.match_time[0] == pub
    assert card.match_time[1] == "published_at_fallback"
    assert fingerprint_hash(card.actor_key, card.action_key, card.object_key, None) == card.to_fingerprint_dict()[
        "fingerprint_hash"
    ]


def test_stance_aggregates_all_targets_not_first_only():
    structured = {
        "stances": [
            {"target": "china_gov", "stance": "critical", "speaker_type": "media"},
            {"target": "china_firm", "stance": "support", "speaker_type": "media"},
            {"target": "china_gov", "stance": "oppose", "speaker_type": "quoted"},
        ]
    }
    labels = all_stance_labels(structured, media_only=True)
    assert labels["critical"] == 1
    assert labels["support"] == 1
    assert "oppose" not in labels
    assert primary_stance_label(structured) in {"critical", "support"}


def test_relevance_features_separate_share_from_weight():
    body = (
        "Intro paragraph without entities here.\n\n"
        "China announced new export rules today for the industry and supply chains.\n\n"
        "Closing notes about markets overall."
    )
    l2 = screen_fulltext(body, title="China export rules")
    rel = assess_relevance(l2, title="China export rules", span_count=1, valid_span_count=1, span_char_total=40, body_char_total=len(body))
    assert rel.assessment_version.startswith("provisional_v0.3")
    assert "paragraph_hit_share" in (rel.features or {})
    assert rel.features.get("note")


def test_soft_or_entity_signal_not_always_hard_drop():
    body = ("Officials in Beijing said the country would review the proposal. ") * 8
    l2 = screen_fulltext(body, title="Regional update")
    assert l2.label in {"china_related", "possible_china", "uncertain"}


def test_stable_event_id_deterministic():
    fp = "abc123fingerprint"
    assert _stable_event_id(fp) == _stable_event_id(fp)


def test_persist_fingerprint_reuses_id_and_null_event_time(db):
    pub = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)
    aid = str(uuid4())
    with session_scope() as session:
        session.merge(Country(id="US", code="US", name="United States"))
        session.merge(Organization(id="org_us", country_id="US", name="OrgUS", organization_type="media"))
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
        session.add(
            Article(
                id=aid,
                source_id="src_us",
                title="US announces export controls",
                url=f"https://example.test/{aid}",
                language="en",
                processing_status="done",
                quality_status="processed",
                exclude_from_metrics=False,
                content_hash=aid[:16],
                published_at=pub,
                first_seen_at=pub,
            )
        )
        session.flush()
        card = FingerprintCard(
            article_id=aid,
            actor="United States",
            action="announces",
            object="export controls",
            event_time=None,
            published_at=pub,
            confidence=0.9,
            summary="US announces export controls",
        )
        cl = FingerprintCluster(cards=[card])
        eid1, created1 = _persist_fingerprint_cluster(session, cl)
        session.flush()
        eid2, created2 = _persist_fingerprint_cluster(session, cl)
        session.flush()
        assert eid1 == eid2
        assert created1 is True
        assert created2 is False
        ev = session.scalar(select(Event).where(Event.id == eid1))
        assert ev is not None
        assert ev.event_time is None
        assert ev.fingerprint_hash == cl.fingerprint_hash

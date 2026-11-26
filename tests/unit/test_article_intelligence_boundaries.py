"""Phase 3 boundary tests: 9 required article-level edge cases."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from gni.analysis.service import analyze_article
from gni.analysis.stance_util import extract_v1_china_stance, extract_v1_expression_owner
from gni.core.contracts import ArticleIntelligenceContract
from gni.infrastructure.models import (
    Article,
    ArticleAnalysis,
    ArticleVersion,
    Base,
    Country,
    Organization,
    Source,
)


@pytest.fixture
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with SessionLocal() as session:
        session.add(Country(id="US", code="US", name="United States"))
        session.add(Organization(id="org_us", country_id="US", name="Wire Org"))
        session.add(
            Source(
                id="src_us",
                organization_id="org_us",
                country_id="US",
                name="Test Wire",
                source_type="public_service",
                active_status="active",
            )
        )
        session.flush()
        yield session


def _run_one(
    session: Session,
    *,
    title: str,
    body: str,
    quality_status: str = "ok",
) -> tuple[Article, ArticleVersion, ArticleAnalysis, ArticleIntelligenceContract]:
    art = Article(
        id=str(uuid4()),
        source_id="src_us",
        title=title,
        url=f"https://example.com/{uuid4()}",
        content_original=body,
        content_clean=body,
        language="en",
        published_at=datetime(2026, 11, 26, 9, 0, tzinfo=timezone.utc),
        quality_status=quality_status,
        processing_status="done",
        analysis_status="pending",
    )
    session.add(art)
    ver = ArticleVersion(
        id=str(uuid4()),
        article_id=art.id,
        version_no=1,
        content_clean=body,
        char_count=len(body),
        quality_status=quality_status,
    )
    session.add(ver)
    session.flush()

    res = analyze_article(session, art, provider="heuristic", allow_llm=False)
    assert res["ok"] is True
    session.flush()

    ana = session.scalar(select(ArticleAnalysis).where(ArticleAnalysis.article_id == art.id))
    assert ana is not None
    contract = ArticleIntelligenceContract.model_validate(ana.structured_result["article_intelligence"])
    return art, ver, ana, contract


def test_case1_non_china_article(db_session: Session) -> None:
    _, _, ana, contract = _run_one(
        db_session,
        title="European central bank holds interest rates steady",
        body=(
            "Frankfurt policymakers decided to keep benchmark interest rates unchanged this quarter "
            "as eurozone inflation cooled toward the two percent target across Germany and France."
        ),
    )
    assert contract.relevance.is_china_related is False
    assert contract.relevance.china_relevance_level == "none"
    assert extract_v1_china_stance(ana.structured_result) == "Unclassified"
    assert contract.topics == []


def test_case2_weak_incidental_china_article(db_session: Session) -> None:
    filler = (
        "Global coffee prices surged in Brazil and Vietnam after severe drought hit major farming regions "
        "across Minas Gerais and the Central Highlands, tightening arabica and robusta export inventories.\n\n"
    )
    body = (
        filler * 8
        + "One brief market note also mentioned rising demand from coffee chains in China."
    )
    _, _, _, contract = _run_one(
        db_session,
        title="Drought in Brazil pushes global coffee prices higher",
        body=body,
    )
    assert contract.relevance.is_china_related is True
    assert contract.relevance.china_relevance_level in {"incidental", "secondary"}
    assert len(contract.evidence) >= 1


def test_case3_multi_topic_article(db_session: Session) -> None:
    body = (
        "Beijing announced new semiconductor export responses while expanding electric vehicle battery exports to Europe.\n\n"
        "Meanwhile China's navy conducted drills near the Taiwan Strait, prompting diplomatic talks with Washington."
    )
    _, _, ana, contract = _run_one(
        db_session,
        title="China faces chip curbs, EV tariff talks and Taiwan Strait tensions",
        body=body,
    )
    topics_v1 = ana.structured_result["topics_v1"]
    boards_v1 = ana.structured_result["boards_v1"]
    assert len(topics_v1) >= 2
    assert len(topics_v1) == len(set(topics_v1))  # deduplicated
    assert len(boards_v1) >= 2  # spans multiple boards
    assert len(contract.topics) == len(topics_v1)


def test_case4_mixed_positive_negative_article_is_unclassified(db_session: Session) -> None:
    body = (
        "China achieved a major breakthrough in green energy cooperation with European partners.\n\n"
        "However, critics warned of a serious threat and sanctions over industrial subsidies in Beijing."
    )
    _, _, ana, contract = _run_one(
        db_session,
        title="China green tech draws both praise and sanctions warnings",
        body=body,
    )
    assert contract.stance[0].stance_label == "Unclassified"
    assert extract_v1_china_stance(ana.structured_result) == "Unclassified"
    assert contract.quality.classification_quality == "unclassified"


def test_case5_heavily_quoted_article_isolates_quoted_actor_stance(db_session: Session) -> None:
    body = (
        "A spokesperson said in a statement that \"China poses a severe threat and faces new sanctions.\"\n\n"
        "According to officials who told reporters on Tuesday, \"Beijing's policy creates risk for global trade.\""
    )
    _, _, ana, contract = _run_one(
        db_session,
        title="Officials comment on China trade risk",
        body=body,
    )
    assert contract.stance[0].expression_owner == "quoted_actor"
    assert extract_v1_expression_owner(ana.structured_result) == "quoted_actor"
    # Quoted third-party view MUST NOT be counted as media's own stance
    assert extract_v1_china_stance(ana.structured_result) == "Unclassified"
    assert "quoted_actor_stance_excluded_from_media" in contract.quality.quality_flags
    assert contract.quality.needs_review is True


def test_case6_missing_or_short_body_flags_insufficient_quality(db_session: Session) -> None:
    _, _, _, contract = _run_one(
        db_session,
        title="China brief update",
        body="China brief.",
        quality_status="rss_stub",
    )
    assert contract.quality.extraction_quality == "insufficient"
    assert "short_or_missing_body" in contract.quality.quality_flags
    assert contract.quality.needs_review is True


def test_case7_unspecified_event_time_never_filled_with_published_at(db_session: Session) -> None:
    body = (
        "Washington announces new tariff measures targeting Chinese solar panel imports across North America.\n\n"
        "Beijing officials reviewed the trade impact on domestic solar manufacturers."
    )
    _, _, _, contract = _run_one(
        db_session,
        title="Washington announces new tariff measures on Chinese solar panels",
        body=body,
    )
    assert len(contract.events) >= 1
    for ev in contract.events:
        assert ev.event_time is None


def test_case8_multi_event_article_extracts_multiple_candidates(db_session: Session) -> None:
    body = (
        "Washington imposes stricter semiconductor export controls on Chinese chipmakers.\n\n"
        "Beijing announces retaliatory export limits on gallium and germanium minerals.\n\n"
        "Brussels launches an anti-subsidy probe into Chinese electric vehicles."
    )
    _, _, _, contract = _run_one(
        db_session,
        title="US, China and EU take separate trade actions",
        body=body,
    )
    assert len(contract.events) >= 2
    actors = {e.actor.lower() for e in contract.events}
    assert len(actors) >= 2


def test_case9_contradictory_narratives_preserved_with_evidence_offsets(db_session: Session) -> None:
    body = (
        "Supporters praised China for breakthrough green energy cooperation and mutual benefit across Asia.\n\n"
        "However, analysts refuted that claim and warned of strategic threat and coercive sanctions risks from Beijing."
    )
    _, ver, _, contract = _run_one(
        db_session,
        title="Competing narratives over China's green energy role",
        body=body,
    )
    assert len(contract.narratives) >= 2
    attributions = {n.attribution for n in contract.narratives}
    tones = {n.tone for n in contract.narratives}
    assert "refute" in attributions
    assert len(tones) >= 2
    # Verified offsets slice exact original text in ArticleVersion
    verified = [e for e in contract.evidence if e.validated]
    assert len(verified) >= 2
    for ev in verified:
        assert ev.article_version_id == ver.id
        assert body[ev.start_offset : ev.end_offset] == ev.text_span

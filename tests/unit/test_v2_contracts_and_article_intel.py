"""Phase 2 & 3 tests: V2.0 unified data contracts + Article Intelligence traceability & quality."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from gni.analysis.deepseek import DeepSeekLLMProvider
from gni.analysis.l3_spans import ChinaSpan
from gni.analysis.relevance import RelevanceAssessment
from gni.analysis.service import (
    analyze_article,
    run_analysis,
    validate_and_enrich_article_intelligence,
)
from gni.analysis.stance_util import extract_v1_china_stance, extract_v1_expression_owner
from gni.core.config import Settings
from gni.core.contracts import (
    ARTICLE_INTELLIGENCE_VERSION,
    ArticleIntelligenceContract,
    EventIntelligenceContract,
    EvidencePackageContract,
    MetricSnapshotContract,
    NarrativeIntelligenceContract,
    ReportPackageContract,
    ReportSectionContract,
    SignalRecordContract,
)
from gni.infrastructure.models import (
    Article,
    ArticleAnalysis,
    ArticleVersion,
    Base,
    Country,
    Organization,
    Source,
)
from gni.reports.narrative.assessment_validator import Finding, OutlookSignal


@pytest.fixture
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with SessionLocal() as session:
        yield session


def _seed_article(
    session: Session,
    *,
    title: str,
    body: str,
    language: str = "en",
    quality_status: str = "ok",
) -> tuple[Article, ArticleVersion]:
    if not session.get(Country, "US"):
        session.add(Country(id="US", code="US", name="United States"))
    if not session.get(Organization, "org_us"):
        session.add(Organization(id="org_us", country_id="US", name="Test Org"))
    if not session.get(Source, "src_us"):
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
    art = Article(
        id=str(uuid4()),
        source_id="src_us",
        title=title,
        url=f"https://example.com/{uuid4()}",
        content_original=body,
        content_clean=body,
        language=language,
        published_at=datetime(2026, 11, 26, 8, 0, tzinfo=timezone.utc),
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
    return art, ver


def test_v2_logical_contracts_validation_and_defaults() -> None:
    """All 7 V2.0 contracts validate cleanly with explicit NULL/Unclassified semantics."""
    now = datetime(2026, 11, 26, 12, 0, tzinfo=timezone.utc)

    ev = EventIntelligenceContract(
        event_id="ev_1",
        canonical_title="US announces semiconductor export controls on China",
        actors=["US", "China"],
        action="announce",
        object="semiconductor export controls",
        event_time=None,  # Explicitly allowed NULL when unknown
        status="emerging",
    )
    assert ev.event_time is None

    nar = NarrativeIntelligenceContract(
        narrative_cluster_id="nc_1",
        canonical_frame="competition_rivalry",
        canonical_claim="Semiconductor export controls reshape China chip supply chains",
        related_articles=["a1"],
        related_countries=["US"],
        trend_status="growing",
    )
    assert nar.trend_status == "growing"

    met = MetricSnapshotContract(
        metric_run_id="mr_1",
        period_start=now,
        period_end=now,
        granularity="daily",
        scope="GLOBAL",
        metric_name="article_count",
        metric_value=12,
        generated_at=now,
    )
    assert met.calculation_version == "methodology_v1.0"

    sig = SignalRecordContract(
        signal_id="sig_1",
        signal_type="topic_shift",
        subject="semiconductor_export_controls",
        observation="Coverage increased across 3 countries.",
        alternative_explanation="Seasonal earnings release coincidence.",
    )
    assert sig.review_status == "auto"

    pkg = EvidencePackageContract(package_id="pkg_1", task_type="executive_analysis")
    assert pkg.schema_version == "evidence_v2.0"

    rep = ReportPackageContract(
        report_id="daily:2026-11-26",
        report_type="daily",
        sections=[ReportSectionContract(section_id="executive_judgment", title="Executive Judgment")],
    )
    assert rep.sections[0].section_id == "executive_judgment"

    # NarrativeTaskOutput backward-compatible extensions
    f = Finding(
        title="Chip controls watch",
        conclusion="May widen if allied rules align.",
        classification="outlook",
        supporting_metrics=["metric:TOPIC:semiconductor_export_controls"],
    )
    assert f.classification == "Outlook"
    osig = OutlookSignal(
        signal="Export control diffusion",
        observation_object="semiconductor_export_controls",
        alternative_explanation="Routine annual review.",
        alternative_scenario="Controls remain limited to legacy nodes.",
    )
    assert osig.alternative_explanation == "Routine annual review."


def test_single_article_produces_complete_traceable_intelligence(db_session: Session) -> None:
    """Acceptance: one article produces full, traceable ArticleIntelligenceContract with verified offsets."""
    body = (
        "Washington announces new semiconductor export controls targeting China chipmakers in Beijing.\n\n"
        "The U.S. Commerce Department warned of national security threat and imposed stricter sanctions "
        "on advanced semiconductor equipment shipped to China and Huawei.\n\n"
        "Industry analysts noted the tariff and export control measures deepen technology competition."
    )
    art, ver = _seed_article(
        db_session,
        title="Washington announces new semiconductor export controls on China",
        body=body,
    )
    res = analyze_article(db_session, art, provider="heuristic", allow_llm=False)
    assert res["ok"] is True
    db_session.flush()

    ana = db_session.scalar(select(ArticleAnalysis).where(ArticleAnalysis.article_id == art.id))
    assert ana is not None
    sr = ana.structured_result or {}
    assert sr["article_intelligence_version"] == ARTICLE_INTELLIGENCE_VERSION
    assert "article_intelligence" in sr

    # Validate against canonical Pydantic V2.0 contract
    contract = ArticleIntelligenceContract.model_validate(sr["article_intelligence"])
    assert contract.article_id == art.id
    assert contract.relevance.is_china_related is True
    assert len(contract.topics) >= 1
    assert contract.sentiment.sentiment_label == "negative"
    assert len(contract.stance) == 1
    assert contract.stance[0].target == "china_mainland"
    assert contract.stance[0].stance_label == "Negative"
    assert contract.stance[0].expression_owner == "media"
    assert len(contract.narratives) >= 1
    assert len(contract.entities) >= 1
    assert len(contract.events) >= 1
    assert contract.events[0].event_time is None  # Never filled from published_at

    # Evidence traceability: every validated span slices back to exact text in content_clean
    assert len(contract.evidence) >= 1
    verified = [e for e in contract.evidence if e.validated]
    assert len(verified) >= 1
    for ev in verified:
        assert ev.article_id == art.id
        assert ev.article_version_id == ver.id
        assert ev.start_offset is not None and ev.end_offset is not None
        assert body[ev.start_offset : ev.end_offset] == ev.text_span

    assert contract.quality.completeness >= 0.8
    assert contract.quality.extraction_quality == "ok"


def test_quoted_actor_stance_and_hallucinated_quote_validation(db_session: Session) -> None:
    """Cross-field guard: quoted_actor stance is excluded from media V1.0 stance; fabricated quotes flag needs_review."""
    body = (
        "China's Ministry of Commerce issued a statement today on electric vehicle tariffs.\n\n"
        "A European trade representative said in a statement that \"China poses a serious threat to local automakers.\""
    )
    art, ver = _seed_article(
        db_session,
        title="EU official comments on China EV tariffs",
        body=body,
    )
    fake_llm_output = {
        "schema_version": "article_analysis_v1.0",
        "taxonomy_version": "taxonomy_v1.0",
        "topics_v1": ["tariffs_trade_war"],
        "boards_v1": ["economy_tech"],
        "china_stance": {
            "target": "china_mainland",
            "stance_label": "Negative",
            "expression_owner": "quoted_actor",
            "stance_confidence": 0.82,
            "stance_evidence": [{"quote": "THIS QUOTE DOES NOT EXIST IN THE ARTICLE"}],
            "reasoning": "Quoted representative criticized China.",
            "analysis_status": "classified",
        },
        "sentiment": {"label": "negative", "sentiment_target": "china_mainland", "confidence": 0.7},
        "narratives": [],
        "entities": [],
        "event_candidates": [],
        "evidence": [],
    }
    enriched = validate_and_enrich_article_intelligence(
        fake_llm_output,
        article=art,
        article_version_id=ver.id,
        content_clean=body,
        spans=[
            ChinaSpan(
                paragraph_index=0,
                char_start=0,
                char_end=82,
                text_original=body[:82],
                validation_status="valid",
            )
        ],
        relevance=RelevanceAssessment(relevance_level="core", relevance_weight=0.9),
        provider="deepseek",
        model_name="deepseek-chat",
        prompt_version="deepseek_analyze_v1.1",
        token_usage=500,
    )

    # 1. Unverified quote and quoted_actor stance must both trigger quality flags & needs_review
    q = enriched["quality"]
    assert q["needs_review"] is True
    assert "unverified_stance_quote" in q["quality_flags"]
    assert "quoted_actor_stance_excluded_from_media" in q["quality_flags"]

    # 2. Strict V1.0 reader MUST NOT count quoted_actor as media stance
    assert extract_v1_expression_owner(enriched) == "quoted_actor"
    assert extract_v1_china_stance(enriched) == "Unclassified"


def test_deepseek_analyze_parses_v2_narratives_entities_events(monkeypatch: pytest.MonkeyPatch) -> None:
    """DeepSeek analyze() normalizes expression_owner, narratives, entities, and event_candidates."""
    settings = Settings(llm_api_key="test-key", llm_model="deepseek-chat")
    ds = DeepSeekLLMProvider(settings)

    mock_json = """{
      "topics_v1": ["semiconductor_export_controls", "tech_competition"],
      "china_stance": {
        "target": "china_mainland",
        "stance_label": "Negative",
        "expression_owner": "media",
        "stance_confidence": 0.85,
        "stance_evidence": [{"quote": "Beijing faces tighter chip curbs"}],
        "reasoning": "Editorial framing stresses strategic risk."
      },
      "sentiment": {"label": "negative", "sentiment_target": "china_mainland", "confidence": 0.8, "reasoning": "Critical tone."},
      "narratives": [{
        "frame": "security_threat",
        "claim": "Chip restrictions are necessary to curb China's military AI.",
        "actor": "US administration",
        "target": "china_mainland",
        "attribution": "support",
        "tone": "negative",
        "confidence": 0.8
      }],
      "entities": [{
        "canonical_name": "U.S. Commerce Department",
        "entity_type": "government_agency",
        "mentions": ["Commerce Department"],
        "roles": ["regulator"]
      }],
      "event_candidates": [{
        "event_relation": "new_event_candidate",
        "actor": "US",
        "action": "impose",
        "object": "chip export controls",
        "event_time": null,
        "location": "Washington",
        "summary": "US imposes new chip export controls on China.",
        "confidence": 0.85
      }],
      "stances": [],
      "framing": {"primary": "security_threat", "secondary": [], "status": "known"},
      "summary": "US tightens chip curbs."
    }"""
    monkeypatch.setattr(ds, "generate", lambda prompt, **kw: mock_json)

    parsed = ds.analyze(
        {"title": "Chip curbs", "language": "en", "relevance": {}, "spans_text": "Beijing faces tighter chip curbs."},
        schema={},
        prompt_version="deepseek_analyze_v1.1",
    )
    assert parsed["china_stance"]["expression_owner"] == "media"
    assert parsed["china_stance"]["target"] == "china_mainland"
    assert len(parsed["narratives"]) == 1
    assert parsed["narratives"][0]["attribution"] == "support"
    assert len(parsed["entities"]) == 1
    assert parsed["entities"][0]["entity_type"] == "government_agency"
    assert len(parsed["event_candidates"]) == 1
    assert parsed["event_candidates"][0]["event_time"] is None


def test_reanalyze_legacy_selects_only_pre_v1_articles(db_session: Session) -> None:
    """run_analysis(reanalyze_legacy=True) targets only non-v1.0 articles without touching v1.0 ones."""
    body = "China trade and semiconductor policy continues to evolve in Beijing across multiple sectors today." * 2
    art_legacy, _ = _seed_article(db_session, title="Legacy China article", body=body)
    art_v1, _ = _seed_article(db_session, title="Modern China article", body=body)
    art_legacy.analysis_status = "completed"
    art_v1.analysis_status = "completed"

    db_session.add(
        ArticleAnalysis(
            id=str(uuid4()),
            article_id=art_legacy.id,
            provider="heuristic",
            model_name="old",
            prompt_version="heuristic_v0.1",
            schema_version="article_analysis_v0.2",
            structured_result={},
        )
    )
    db_session.add(
        ArticleAnalysis(
            id=str(uuid4()),
            article_id=art_v1.id,
            provider="heuristic",
            model_name="new",
            prompt_version="heuristic_v1.1",
            schema_version="article_analysis_v1.0",
            structured_result={},
        )
    )
    db_session.flush()

    run = run_analysis(db_session, limit=10, provider="heuristic", reanalyze_legacy=True)
    assert run.stats["attempted"] == 1
    assert run.stats["ok"] == 1
    # Legacy article now has a newer v1.0 analysis row; v1 article untouched (still 1 row)
    legacy_rows = db_session.scalars(
        select(ArticleAnalysis).where(ArticleAnalysis.article_id == art_legacy.id)
    ).all()
    v1_rows = db_session.scalars(
        select(ArticleAnalysis).where(ArticleAnalysis.article_id == art_v1.id)
    ).all()
    assert len(legacy_rows) == 2
    assert len(v1_rows) == 1

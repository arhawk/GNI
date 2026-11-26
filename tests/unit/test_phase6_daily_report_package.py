"""Phase 6 tests: Unified 6-Chapter Daily Report Package, Snapshot Persistence & API Compatibility."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from gni.core.contracts import ReportPackageContract
from gni.infrastructure.models import Base, ReportSnapshot
from gni.reports.daily import build_daily_report
from gni.reports.daily_package import (
    REQUIRED_DAILY_CHAPTER_IDS,
    get_daily_report_snapshot,
    regenerate_daily_report,
    render_daily_brief_markdown,
    save_daily_report_snapshot,
)
from tests.unit.test_phase5_assessment_engine import _GroundedMockLLM, _seed_monitoring_corpus


@pytest.fixture
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with SessionLocal() as session:
        yield session


def test_daily_brief_e2e_six_chapters_snapshot_and_markdown(db_session: Session) -> None:
    """E2E: Monitoring Data -> Evidence Package -> Assessment Tasks -> 6-Chapter ReportPackage -> Snapshot & Markdown."""
    meta = _seed_monitoring_corpus(db_session)
    mock_llm = _GroundedMockLLM(article_id=meta["article_ids"][0], event_id=meta["event_id"])

    payload = build_daily_report(
        db_session,
        day=meta["day"],
        analyze=False,
        run_v2_assessments=True,
        assessment_tasks=[
            "overall_situation_assessment",
            "event_analysis",
            "topic_analysis",
            "change_detection_assessment",
            "narrative_analysis",
            "outlook_assessment",
        ],
        llm_client=mock_llm,
        force_analyze=True,
    )

    # 1. Backward-compatible legacy keys still intact
    assert payload["report_type"] == "daily"
    assert "v1_stats" in payload["sections"]
    assert "report_package" in payload

    # 2. Validate ReportPackageContract & all 6 chapters + appendix
    pkg = ReportPackageContract.model_validate(payload["report_package"])
    assert pkg.report_id == f"daily:{meta['day']}"
    assert pkg.validation_status in {"passed", "needs_review"}
    assert [s.section_id for s in pkg.sections] == list(REQUIRED_DAILY_CHAPTER_IDS)
    assert len(pkg.assessment_results) == 6
    assert "metric:GLOBAL:ALL" in pkg.metric_snapshot_refs
    assert pkg.methodology["time_basis_articles"] == "published_at"
    assert pkg.methodology["time_basis_events"] == "event_time_nullable"

    # Chapter 3 deterministic metrics match global count exactly
    ch3 = next(s for s in pkg.sections if s.section_id == "chapter_3_global_situation")
    g_met = next(m for m in ch3.metrics if m.get("scope_type") == "GLOBAL")
    assert g_met["article_count"] == 3
    assert ch3.source_kind == "deterministic_metrics"

    # Chapter 2 carries event evidence; Chapter 6 carries conditional outlook watch item
    ch2 = next(s for s in pkg.sections if s.section_id == "chapter_2_key_developments")
    assert any(r.get("type") == "event" for r in ch2.evidence_refs)
    ch6 = next(s for s in pkg.sections if s.section_id == "chapter_6_outlook_watchlist")
    assert any(f.get("classification") == "Outlook" for f in ch6.findings)

    # 3. Markdown rendering covers all 6 chapters + appendix
    md = render_daily_brief_markdown(pkg)
    assert "Chapter 1 — Executive Judgment" in md
    assert "Chapter 2 — Key Developments" in md
    assert "Chapter 3 — Global Situation" in md
    assert "Chapter 4 — Key Changes & Anomalies" in md
    assert "Chapter 5 — Emerging Signals" in md
    assert "Chapter 6 — Outlook & Watchlist" in md
    assert "Appendix — Statistics, Representative Articles, Coverage & Methodology" in md

    # 4. Save, query, and regenerate ReportSnapshot
    snap = save_daily_report_snapshot(db_session, payload)
    assert snap.period == meta["day"]
    loaded = get_daily_report_snapshot(db_session, meta["day"])
    assert loaded is not None
    assert loaded["report_package"]["report_id"] == pkg.report_id

    regen = regenerate_daily_report(
        db_session,
        day=meta["day"],
        run_v2_assessments=True,
        assessment_tasks=["overall_situation_assessment"],
        llm_client=mock_llm,
    )
    assert regen["report_package"]["report_id"] == pkg.report_id
    all_snaps = db_session.scalars(
        select(ReportSnapshot).where(ReportSnapshot.report_type == "daily", ReportSnapshot.period == meta["day"])
    ).all()
    assert len(all_snaps) == 1  # Upserted cleanly without duplicate clutter


def test_daily_brief_zero_data_edge_case(db_session: Session) -> None:
    payload = build_daily_report(db_session, day="2026-11-26", analyze=False)
    pkg = ReportPackageContract.model_validate(payload["report_package"])
    assert pkg.generation_status == "insufficient_data"
    assert pkg.validation_status in {"passed", "needs_review"}
    assert [s.section_id for s in pkg.sections] == list(REQUIRED_DAILY_CHAPTER_IDS)


def test_api_daily_report_and_v2_analyze_compatibility(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Existing /api/reports/daily & /api/reports/daily/analyze remain backward compatible and expose report_package."""
    db_file = tmp_path / f"gni_p6_{uuid4().hex}.db"
    monkeypatch.setenv("GNI_DATABASE_URL", f"sqlite:///{db_file}")
    from gni.core.config import get_settings
    from gni.infrastructure.db import ensure_schema, reset_engine, session_scope

    get_settings.cache_clear()
    reset_engine()
    ensure_schema()

    with session_scope() as s:
        meta = _seed_monitoring_corpus(s)

    from gni.api.app import app

    client = TestClient(app)
    r_get = client.get(f"/api/reports/daily?date={meta['day']}")
    assert r_get.status_code == 200
    body = r_get.json()
    assert "report_package" in body
    assert len(body["report_package"]["sections"]) == 7

    # Trigger v2 analyze without API key -> degrades gracefully and persists ReportSnapshot
    monkeypatch.setenv("GNI_LLM_API_KEY", "")
    get_settings.cache_clear()
    r_post = client.post(
        "/api/reports/daily/analyze",
        json={
            "period": meta["day"],
            "engine": "v2",
            "tasks": ["overall_situation_assessment"],
            "save_snapshot": True,
        },
    )
    assert r_post.status_code == 200
    pbody = r_post.json()
    assert pbody["report_package"]["report_id"] == f"daily:{meta['day']}"

    with session_scope() as s:
        saved = get_daily_report_snapshot(s, meta["day"])
        assert saved is not None

    get_settings.cache_clear()
    reset_engine()

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
from gni.reports.package_composer import (
    DAILY_CHAPTER_DEFS,
    get_report_snapshot,
    render_report_package_markdown,
    save_report_snapshot,
)
from tests.unit.test_phase5_assessment_engine import _GroundedMockLLM, _seed_monitoring_corpus

REQUIRED_DAILY_CHAPTER_IDS = tuple(ch_id for ch_id, _, _ in DAILY_CHAPTER_DEFS)


@pytest.fixture
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with SessionLocal() as session:
        yield session


def test_daily_brief_e2e_six_chapters_snapshot_and_markdown(db_session: Session) -> None:
    """E2E: Monitoring Data -> Orchestrator -> Canonical Assessments -> 6-Chapter ReportPackage -> Snapshot & Markdown."""
    meta = _seed_monitoring_corpus(db_session)
    mock_llm = _GroundedMockLLM(article_id=meta["article_ids"][0], event_id=meta["event_id"])

    payload = build_daily_report(
        db_session,
        day=meta["day"],
        analyze=True,
        analyze_tasks=[
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

    assert payload["report_type"] == "daily"
    assert "v1_stats" in payload["sections"]
    assert "report_package" in payload
    assert "assessments" in payload
    assert "assessments_meta" in payload
    assert "intelligence" not in payload

    pkg = ReportPackageContract.model_validate(payload["report_package"])
    assert pkg.report_id == f"daily:{meta['day']}"
    assert pkg.validation_status in {"passed", "needs_review"}
    assert [s.section_id for s in pkg.sections] == list(REQUIRED_DAILY_CHAPTER_IDS)
    assert len(pkg.assessment_results) == 6

    md = render_report_package_markdown(pkg)
    assert "1. Executive Judgment" in md
    assert "2. Key Developments" in md
    assert "6. Outlook & Watchlist" in md
    assert "7. Data Coverage & Methodology" in md

    snap = save_report_snapshot(db_session, "daily", payload)
    assert snap.period == meta["day"]
    loaded = get_report_snapshot(db_session, "daily", meta["day"])
    assert loaded is not None
    assert loaded["report_package"]["report_id"] == pkg.report_id

    # Upserting snapshot cleanly updates in place without duplicates
    save_report_snapshot(db_session, "daily", payload)
    all_snaps = db_session.scalars(
        select(ReportSnapshot).where(ReportSnapshot.report_type == "daily", ReportSnapshot.period == meta["day"])
    ).all()
    assert len(all_snaps) == 1


def test_daily_brief_zero_data_edge_case(db_session: Session) -> None:
    payload = build_daily_report(db_session, day="2026-11-26", analyze=False)
    pkg = ReportPackageContract.model_validate(payload["report_package"])
    assert pkg.generation_status == "insufficient_data"
    assert pkg.validation_status in {"passed", "needs_review"}
    assert [s.section_id for s in pkg.sections] == list(REQUIRED_DAILY_CHAPTER_IDS)


def test_api_daily_report_and_canonical_package_routes(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """API /api/reports/daily & /api/reports/daily/package expose unified Canonical ReportPackage."""
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
    r1 = client.get(f"/api/reports/daily?date={meta['day']}")
    assert r1.status_code == 200
    body = r1.json()
    assert "report_package" in body
    assert "assessments" in body
    assert "assessments_meta" in body

    r2 = client.get(f"/api/reports/daily/package?date={meta['day']}&format=json")
    assert r2.status_code == 200
    assert r2.json()["report_package"]["report_id"] == f"daily:{meta['day']}"

    r3 = client.get(f"/api/reports/daily/package?date={meta['day']}&format=markdown")
    assert r3.status_code == 200
    assert "1. Executive Judgment" in r3.text

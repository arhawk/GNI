"""Unit tests for priority analysis queue, trailing-month report, and reports calendar API."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from gni.analysis.service import _select_articles_for_analysis
from gni.api.app import app
from gni.core.config import get_settings
from gni.infrastructure.db import reset_engine
from gni.infrastructure.models import Article, Base, Country, Organization, Source
from gni.reports.monthly import _month_window, build_monthly_report


def _seed_base(session: Session) -> None:
    session.add(Country(id="US", code="US", name="United States"))
    session.add(Organization(id="org_us", country_id="US", name="US Test Org", organization_type="media"))
    session.add(
        Source(
            id="src_us",
            organization_id="org_us",
            country_id="US",
            name="US Test Wire",
            source_type="media",
        )
    )
    session.flush()


def test_select_articles_prioritizes_china_and_newest_first() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        _seed_base(session)
        rows = [
            Article(
                id="a_nomatch_new",
                source_id="src_us",
                url="https://example.com/1",
                canonical_url="https://example.com/1",
                title="Local weather",
                processing_status="done",
                analysis_status="pending",
                title_screening_label="no_match",
                published_at=datetime(2026, 11, 26, 12, 0, tzinfo=timezone.utc),
                first_seen_at=datetime(2026, 11, 26, 12, 0, tzinfo=timezone.utc),
            ),
            Article(
                id="a_explicit_old",
                source_id="src_us",
                url="https://example.com/2",
                canonical_url="https://example.com/2",
                title="China tariff old",
                processing_status="done",
                analysis_status="pending",
                title_screening_label="explicit_relevant",
                published_at=datetime(2026, 11, 24, 8, 0, tzinfo=timezone.utc),
                first_seen_at=datetime(2026, 11, 24, 8, 0, tzinfo=timezone.utc),
            ),
            Article(
                id="a_explicit_new",
                source_id="src_us",
                url="https://example.com/3",
                canonical_url="https://example.com/3",
                title="China tariff new",
                processing_status="done",
                analysis_status="pending",
                title_screening_label="explicit_relevant",
                published_at=datetime(2026, 11, 26, 10, 0, tzinfo=timezone.utc),
                first_seen_at=datetime(2026, 11, 26, 10, 0, tzinfo=timezone.utc),
            ),
            Article(
                id="a_likely_new",
                source_id="src_us",
                url="https://example.com/4",
                canonical_url="https://example.com/4",
                title="Beijing trade talks",
                processing_status="done",
                analysis_status="pending",
                title_screening_label="likely_relevant",
                published_at=datetime(2026, 11, 26, 11, 0, tzinfo=timezone.utc),
                first_seen_at=datetime(2026, 11, 26, 11, 0, tzinfo=timezone.utc),
            ),
            Article(
                id="a_uncertain",
                source_id="src_us",
                url="https://example.com/5",
                canonical_url="https://example.com/5",
                title="Asia supply chain",
                processing_status="done",
                analysis_status="pending",
                title_screening_label="uncertain",
                published_at=datetime(2026, 11, 26, 9, 0, tzinfo=timezone.utc),
                first_seen_at=datetime(2026, 11, 26, 9, 0, tzinfo=timezone.utc),
            ),
        ]
        session.add_all(rows)
        session.commit()

        picked, _ = _select_articles_for_analysis(
            session,
            limit=5,
            source_id=None,
            article_id=None,
            reanalyze=False,
            per_country=None,
            articles_remaining=10,
        )
        assert [a.id for a in picked] == [
            "a_explicit_new",
            "a_explicit_old",
            "a_likely_new",
            "a_uncertain",
            "a_nomatch_new",
        ]

        picked_pc, counts = _select_articles_for_analysis(
            session,
            limit=3,
            source_id=None,
            article_id=None,
            reanalyze=False,
            per_country=3,
            articles_remaining=10,
        )
        assert [a.id for a in picked_pc] == [
            "a_explicit_new",
            "a_explicit_old",
            "a_likely_new",
        ]
        assert counts == {"US": 3}


def test_monthly_report_trailing_end_day() -> None:
    period, start, end, prev_start, prev_end = _month_window(end_day="2026-11-26")
    assert period == "2026-10-28_2026-11-26"
    assert (end - start).days == 30
    assert (prev_end - prev_start).days == 30
    assert prev_end == start

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        _seed_base(session)
        session.add(
            Article(
                id="a_in_30d",
                source_id="src_us",
                url="https://example.com/in30",
                canonical_url="https://example.com/in30",
                title="China trade in window",
                processing_status="done",
                analysis_status="completed",
                china_relevance_level="core",
                published_at=datetime(2026, 11, 25, 10, 0, tzinfo=timezone.utc),
                first_seen_at=datetime(2026, 11, 25, 10, 0, tzinfo=timezone.utc),
            )
        )
        session.commit()
        rep = build_monthly_report(session, end_day="2026-11-26", persist_snapshot=False)
        assert rep["period"] == "2026-10-28_2026-11-26"
        assert rep["sections"]["summary"]["kpis"]["china_articles"] == 1


def test_reports_calendar_endpoint(tmp_path: Path, monkeypatch) -> None:
    db_file = tmp_path / "cal.db"
    monkeypatch.setenv("GNI_DATABASE_URL", f"sqlite:///{db_file}")
    monkeypatch.setenv("GNI_REPORT_TIMEZONE", "Asia/Shanghai")
    get_settings.cache_clear()
    reset_engine()

    engine = create_engine(f"sqlite:///{db_file}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        _seed_base(session)
        session.add_all(
            [
                # 2026-11-25 18:00 UTC == 2026-11-26 02:00 Asia/Shanghai
                Article(
                    id="c1",
                    source_id="src_us",
                    url="https://example.com/c1",
                    canonical_url="https://example.com/c1",
                    title="China headline",
                    china_relevance_level="core",
                    published_at=datetime(2026, 11, 25, 18, 0, tzinfo=timezone.utc),
                ),
                Article(
                    id="c2",
                    source_id="src_us",
                    url="https://example.com/c2",
                    canonical_url="https://example.com/c2",
                    title="Other headline",
                    china_relevance_level="none",
                    published_at=datetime(2026, 11, 26, 4, 0, tzinfo=timezone.utc),
                ),
                Article(
                    id="c3_excluded",
                    source_id="src_us",
                    url="https://example.com/c3",
                    canonical_url="https://example.com/c3",
                    title="Excluded",
                    exclude_from_metrics=True,
                    published_at=datetime(2026, 11, 26, 5, 0, tzinfo=timezone.utc),
                ),
            ]
        )
        session.commit()

    client = TestClient(app)
    r = client.get("/api/reports/calendar?month=2026-11")
    assert r.status_code == 200
    body = r.json()
    assert body["month"] == "2026-11"
    assert len(body["days"]) == 30
    day26 = next(d for d in body["days"] if d["date"] == "2026-11-26")
    assert day26["total_articles"] == 2
    assert day26["china_articles"] == 1

    get_settings.cache_clear()
    reset_engine()

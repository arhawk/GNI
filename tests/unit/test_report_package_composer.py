"""Unit tests for Task 4: Evidence Curation, Unified ReportPackage (Weekly/Monthly), Visualizations & Markdown."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from gni.infrastructure.models import Article, Base, Country, Organization, Source
from gni.reports.monthly import build_monthly_report
from gni.reports.narrative.evidence import curate_finding_evidence
from gni.reports.package_composer import render_report_package_markdown
from gni.reports.weekly import build_weekly_report


def test_evidence_curator_dedup_diversity_and_counter_evidence() -> None:
    pool = [
        {"article_id": "a1", "title": "China EV tariffs rise", "source_name": "Reuters", "country_code": "US", "china_stance": "Negative", "event_id": "ev1"},
        {"article_id": "a1", "title": "China EV tariffs rise", "source_name": "Reuters", "country_code": "US", "china_stance": "Negative", "event_id": "ev1"},  # dup id
        {"article_id": "a2", "title": "China EV tariffs rise 2", "source_name": "Reuters", "country_code": "US", "china_stance": "Negative", "event_id": "ev1"},  # same source & event
        {"article_id": "a3", "title": "EU weighs China trade", "source_name": "FT", "country_code": "GB", "china_stance": "Negative", "event_id": "ev2"},
        {"article_id": "a4", "title": "Japan chips & China", "source_name": "Nikkei", "country_code": "JP", "china_stance": "Neutral", "event_id": "ev3"},
        {"article_id": "a5", "title": "ASEAN welcomes China green investment", "source_name": "Straits Times", "country_code": "SG", "china_stance": "Positive", "event_id": "ev4"},
    ]
    res = curate_finding_evidence(pool, max_refs=3, max_per_source=1, max_per_event=1, include_counter=True)
    refs = res["evidence_refs"]
    assert len(refs) == 3
    # Distinct countries & distinct sources & no duplicate IDs
    assert len({r["article_id"] for r in refs}) == 3
    assert len({r["country_code"] for r in refs}) == 3
    assert len({r["source_name"] for r in refs}) == 3
    # Counter-evidence picks contrasting stance (not Negative)
    assert len(res["counter_evidence"]) >= 1
    assert all(c["china_stance"] != "Negative" for c in res["counter_evidence"])


def test_weekly_and_monthly_unified_packages_and_markdown() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(Country(id="US", code="US", name="United States"))
        session.add(Organization(id="org_us", country_id="US", name="Org US"))
        session.add(Source(id="src_us", organization_id="org_us", country_id="US", name="Wire", source_type="media"))
        session.add(
            Article(
                id="art-1",
                source_id="src_us",
                url="https://example.com/1",
                canonical_url="https://example.com/1",
                title="China industrial policy update",
                china_relevance_level="core",
                published_at=datetime(2026, 11, 25, 6, 0, tzinfo=timezone.utc),
            )
        )
        session.commit()

        w = build_weekly_report(session, end_day="2026-11-26", persist_snapshot=False)
        assert len(w["report_package"]["sections"]) == 9
        assert "trend_line" in w["visualizations"]
        assert "stance_stacked" in w["visualizations"]
        w_md = render_report_package_markdown(w["report_package"])
        assert "Weekly Executive Assessment" in w_md

        m = build_monthly_report(session, month="2026-11", persist_snapshot=False)
        assert len(m["report_package"]["sections"]) == 9
        m_md = render_report_package_markdown(m["report_package"])
        assert "Monthly Executive Assessment" in m_md
        # Monthly baseline < 6 months limitation must be stated honestly
        appendix = m["report_package"]["sections"][-1]
        assert any("6 个月" in lim or "口径" in lim for lim in appendix["limitations"])


def test_event_timeline_reads_article_count_and_countries_from_coverage() -> None:
    """Regression: daily major_events store counts under coverage.*; timeline must not show 0 篇 / empty countries."""
    from gni.reports.package_composer import extract_report_visualizations

    payload = {
        "sections": {
            "v1_stats": {"global": {"article_count": 3}},
            "major_events": [
                {
                    "event_id": "ev-1",
                    "title": "Megaspeed probe",
                    "event_time": None,
                    "coverage": {"article_count": 4, "country_count": 2, "countries": ["US", "SG"]},
                },
                {
                    "event_id": "ev-2",
                    "title": "Top-level fallback",
                    "article_count": 2,
                    "countries": ["IN"],
                },
            ],
        }
    }
    items = extract_report_visualizations(payload)["event_timeline"]["items"]
    assert items[0]["article_count"] == 4
    assert items[0]["countries"] == ["US", "SG"]
    assert items[1]["article_count"] == 2
    assert items[1]["countries"] == ["IN"]

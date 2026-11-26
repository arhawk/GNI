"""Canonical Assessment Layer Tests: differentiated prompts, 3-layer validator, caching, retry & API routes."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from gni.analysis.deepseek import LLMCallResult
from gni.infrastructure.models import Article, ArticleAnalysis, Base, Country, Organization, Source
from gni.reports.daily import build_daily_report
from gni.reports.monthly import build_monthly_report
from gni.reports.narrative.assessment import (
    ASSESSMENT_TASK_SPECS,
    effective_prompt_version,
)
from gni.reports.narrative.assessment_validator import (
    EvidenceRef,
    NarrativeTaskOutput,
    validate_task_output,
)
from gni.reports.narrative.evidence import EvidenceBundle
from gni.reports.weekly import build_weekly_report


def test_prompts_differentiated_across_daily_weekly_monthly() -> None:
    """Every canonical task has distinct prompt_version namespaces across daily, weekly, and monthly."""
    for spec in ASSESSMENT_TASK_SPECS.values():
        pv_d = effective_prompt_version(spec, "daily")
        pv_w = effective_prompt_version(spec, "weekly")
        pv_m = effective_prompt_version(spec, "monthly")
        assert len({pv_d, pv_w, pv_m}) == 3


def test_three_layer_validator_numeric_evidence_reasoning() -> None:
    bundle = EvidenceBundle(
        report_type="daily",
        period="2026-11-26",
        period_start="2026-11-26T00:00:00+08:00",
        period_end="2026-11-27T00:00:00+08:00",
        statistical={"global": {"article_count": 10}},
        events=[],
        articles=[],
        historical={},
        alerts=[],
        evidence_hash="h1",
        global_article_count=10,
        allowed_article_ids={"art-1"},
        allowed_event_ids={"ev-1"},
        allowed_metric_ids={"metric:GLOBAL:ALL"},
        allowed_numbers={"10", "50", "50.0"},
    )
    out = NarrativeTaskOutput.model_validate(
        {
            "task_type": "overall_situation_assessment",
            "summary": "监测显示共 10 篇涉华报道，综合舆情指数升至 99。",
            "findings": [
                {
                    "title": "坏事实",
                    "conclusion": "报道量上升说明立场恶化，代表全民民意。",
                    "classification": "Fact",
                    "evidence_refs": [{"type": "article", "ref_id": "fake-id"}],
                    "confidence": "high",
                },
                {
                    "title": "好事实",
                    "conclusion": "监测窗口内共 10 篇报道。",
                    "classification": "Fact",
                    "evidence_refs": [{"type": "article", "ref_id": "art-1"}],
                    "confidence": "high",
                },
            ],
        }
    )
    validated, vres = validate_task_output(out, bundle)
    assert not vres["ok"]
    assert len(validated.findings) >= 1


def test_evidence_ref_string_shorthand_coercion() -> None:
    ref = EvidenceRef.model_validate("article:art-123")
    assert ref.type == "article"
    assert ref.ref_id == "art-123"
    mref = EvidenceRef.model_validate("metric:GLOBAL:ALL")
    assert mref.type == "metric"
    assert mref.ref_id == "metric:GLOBAL:ALL"


def test_api_reports_get_and_analyze_route(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_file = tmp_path / f"gni_nar_{uuid4().hex}.db"
    monkeypatch.setenv("GNI_DATABASE_URL", f"sqlite:///{db_file}")
    from gni.core.config import get_settings
    from gni.infrastructure.db import ensure_schema, reset_engine, session_scope

    get_settings.cache_clear()
    reset_engine()
    ensure_schema()

    with session_scope() as session:
        session.add(Country(id="US", code="US", name="United States"))
        session.add(Organization(id="o1", country_id="US", name="Org"))
        session.add(Source(id="s1", organization_id="o1", country_id="US", name="Wire", source_type="media"))
        session.add(
            Article(
                id="a1",
                source_id="s1",
                url="https://e.com/1",
                canonical_url="https://e.com/1",
                title="China trade brief",
                china_relevance_level="core",
                published_at=datetime(2026, 11, 26, 4, 0, tzinfo=timezone.utc),
            )
        )
        session.commit()

    from gni.api.app import app

    client = TestClient(app)
    for url in (
        "/api/reports/daily?date=2026-11-26",
        "/api/reports/weekly?end=2026-11-26",
        "/api/reports/monthly?month=2026-11",
    ):
        resp = client.get(url)
        assert resp.status_code == 200
        body = resp.json()
        assert "assessments" in body
        assert "assessments_meta" in body
        assert "report_package" in body
        assert "quality_gate" in body
        assert "intelligence" not in body

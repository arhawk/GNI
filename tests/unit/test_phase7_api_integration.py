"""Phase 7 API Integration & Frontend-Backend Data Consistency Tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from gni.infrastructure.db import ensure_schema, session_scope
from gni.infrastructure.models import (
    Article,
    ArticleAnalysis,
    Country,
    Event,
    EventArticle,
    EventNarrativeEvidence,
    NarrativeCluster,
    Organization,
    Source,
)


def _seed_phase7_fixture(tmp_path: Path, monkeypatch) -> dict[str, str]:
    db_file = tmp_path / "phase7_test.db"
    monkeypatch.setenv("GNI_DATABASE_URL", f"sqlite:///{db_file}")
    monkeypatch.setenv("GNI_DEEPSEEK_API_KEY", "")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")

    from gni.core.config import get_settings
    from gni.infrastructure.db import reset_engine

    get_settings.cache_clear()
    reset_engine()
    ensure_schema()

    now = datetime(2026, 11, 25, 10, 0, tzinfo=timezone.utc)
    a1_id = str(uuid4())
    a2_id = str(uuid4())
    a3_id = str(uuid4())
    ev_id = str(uuid4())
    nc_id = str(uuid4())
    ev_span_id = f"ev:{a1_id}:0"

    body1 = "US officials announced new tariffs on Chinese electric vehicles and semiconductors."
    span1 = "new tariffs on Chinese electric vehicles"
    start1 = body1.index(span1)
    end1 = start1 + len(span1)

    with session_scope() as session:
        session.add_all(
            [
                Country(id="US", code="US", name="United States"),
                Country(id="DE", code="DE", name="Germany"),
                Organization(id="org-us", name="US Media Group", country_id="US"),
                Organization(id="org-de", name="DE Media Group", country_id="DE"),
                Source(
                    id="src-us-1",
                    organization_id="org-us",
                    name="US Daily",
                    country_id="US",
                    source_type="media",
                    adapter_type="rss",
                    active_status="active",
                ),
                Source(
                    id="src-de-1",
                    organization_id="org-de",
                    name="DE Zeit",
                    country_id="DE",
                    source_type="media",
                    adapter_type="rss",
                    active_status="active",
                ),
            ]
        )
        session.flush()

        session.add_all(
            [
                Article(
                    id=a1_id,
                    source_id="src-us-1",
                    url="https://us.example.com/a1",
                    canonical_url="https://us.example.com/a1",
                    title="US announces tariffs on China EVs and chips",
                    content_original=body1,
                    content_clean=body1,
                    published_at=now - timedelta(hours=2),
                    language="en",
                    china_relevance_level="core",
                    exclude_from_metrics=False,
                ),
                Article(
                    id=a2_id,
                    source_id="src-de-1",
                    url="https://de.example.com/a2",
                    canonical_url="https://de.example.com/a2",
                    title="German auto group responds to China EV competition",
                    content_original="German automakers discussed China EV supply chains and trade cooperation.",
                    content_clean="German automakers discussed China EV supply chains and trade cooperation.",
                    published_at=now - timedelta(hours=1),
                    language="en",
                    china_relevance_level="core",
                    exclude_from_metrics=False,
                ),
                Article(
                    id=a3_id,
                    source_id="src-de-1",
                    url="https://de.example.com/a3",
                    canonical_url="https://de.example.com/a3",
                    title="Legacy article without V1 stance",
                    content_original="Brief note mentioning China market.",
                    content_clean="Brief note mentioning China market.",
                    published_at=now - timedelta(hours=3),
                    language="en",
                    china_relevance_level="substantial",
                    exclude_from_metrics=False,
                ),
            ]
        )
        session.flush()

        session.add_all(
            [
                ArticleAnalysis(
                    id=str(uuid4()),
                    article_id=a1_id,
                    schema_version="article_analysis_v1.1",
                    prompt_version="p1",
                    structured_result={
                        "sentiment": {"label": "negative"},
                        "topics_v1": ["tariffs_trade_war", "semiconductors_export_controls"],
                        "china_stance": {
                            "stance_label": "Negative",
                            "stance_confidence": 0.88,
                            "expression_owner": "media",
                            "stance_evidence": [{"quote": span1}],
                        },
                        "article_intelligence": {
                            "china_stance": {
                                "stance_label": "Negative",
                                "expression_owner": "media",
                            },
                            "sentiment": {"label": "negative"},
                            "narratives": [
                                {"label": "EV Tariff Escalation", "frame": "trade_competition", "claim": "Tariffs target China EVs"}
                            ],
                            "evidence": [
                                {
                                    "evidence_id": ev_span_id,
                                    "text_span": span1,
                                    "start_offset": start1,
                                    "end_offset": end1,
                                    "validated": True,
                                    "analysis_task": "china_stance",
                                    "expression_owner": "media",
                                }
                            ],
                        },
                    },
                ),
                ArticleAnalysis(
                    id=str(uuid4()),
                    article_id=a2_id,
                    schema_version="article_analysis_v1.1",
                    prompt_version="p1",
                    structured_result={
                        "sentiment": {"label": "neutral"},
                        "topics_v1": ["tariffs_trade_war"],
                        "china_stance": {
                            "stance_label": "Positive",
                            "stance_confidence": 0.76,
                            "expression_owner": "media",
                            "stance_evidence": [{"quote": "trade cooperation"}],
                        },
                        "article_intelligence": {
                            "china_stance": {
                                "stance_label": "Positive",
                                "expression_owner": "media",
                            },
                            "sentiment": {"label": "neutral"},
                            "narratives": [
                                {"label": "EV Tariff Escalation", "frame": "cooperation", "claim": "Automakers seek cooperation"}
                            ],
                            "evidence": [],
                        },
                    },
                ),
                ArticleAnalysis(
                    id=str(uuid4()),
                    article_id=a3_id,
                    schema_version="v0.1",
                    prompt_version="legacy",
                    structured_result={"sentiment": {"label": "positive"}},
                ),
            ]
        )

        # Event with event_time = None to verify strict event_time handling
        session.add(
            Event(
                id=ev_id,
                title="US-EU China EV Tariff Debate",
                summary="Cross-country coverage of China EV tariffs.",
                event_type="trade_policy",
                status="active",
                importance_score=0.85,
                event_time=None,
                window_start=now - timedelta(hours=4),
                window_end=now,
                has_physical_location=False,
            )
        )
        session.flush()
        session.add_all(
            [
                EventArticle(id=str(uuid4()), event_id=ev_id, article_id=a1_id),
                EventArticle(id=str(uuid4()), event_id=ev_id, article_id=a2_id),
            ]
        )
        session.add(
            NarrativeCluster(
                id=nc_id,
                event_id=ev_id,
                label="EV Tariff Escalation",
                frame_id="trade_competition",
                summary="Debate over tariffs on Chinese EVs.",
            )
        )
        session.flush()
        session.add_all(
            [
                EventNarrativeEvidence(
                    id=str(uuid4()),
                    narrative_cluster_id=nc_id,
                    article_id=a1_id,
                    quote=span1,
                ),
                EventNarrativeEvidence(
                    id=str(uuid4()),
                    narrative_cluster_id=nc_id,
                    article_id=a2_id,
                    quote="[counter] trade cooperation",
                ),
            ]
        )

    return {
        "a1_id": a1_id,
        "a2_id": a2_id,
        "a3_id": a3_id,
        "ev_id": ev_id,
        "nc_id": nc_id,
        "ev_span_id": ev_span_id,
        "day": "2026-11-25",
    }


def test_phase7_all_domain_routers_and_data_consistency(tmp_path: Path, monkeypatch):
    ids = _seed_phase7_fixture(tmp_path, monkeypatch)
    from gni.api.app import app

    client = TestClient(app)

    # 1. Dashboard & Daily Report Package consistency
    dash = client.get(f"/api/dashboard?date={ids['day']}").json()
    daily = client.get(f"/api/reports/daily?date={ids['day']}").json()
    v1_global = daily["sections"]["v1_stats"]["global"]

    assert dash["executive_overview"]["article_count"] == v1_global["article_count"] == 3
    st = dash["executive_overview"]["stance_distribution"]
    # 2 classified (1 Negative, 1 Positive) + 1 Unclassified (v0.1)
    assert st["classified_count"] == 2
    assert st["unclassified_count"] == 1
    assert abs(dash["executive_overview"]["stance_coverage_rate"] - (2 / 3)) < 1e-3
    # Denominator excludes Unclassified: 1/2 = 0.5 Positive, 1/2 = 0.5 Negative
    assert abs(st["positive_rate"] - 0.5) < 1e-3
    assert abs(st["negative_rate"] - 0.5) < 1e-3
    assert abs((st["positive_rate"] + st["neutral_rate"] + st["negative_rate"]) - 1.0) < 1e-3

    # Country counts sum to global unique count (1 US + 2 DE = 3)
    country_sum = sum(c["article_count"] for c in dash["global_attention"]["countries"])
    assert country_sum == 3

    # 2. Topics API: multi-label overlap allowed (a1 has 2 topics, a2 has 1 -> sum=3 on 2 classified articles)
    topics = client.get("/api/topics?days=30").json()
    assert topics["meta"]["global_unique_article_count"] == 3
    t_map = {t["topic_id"]: t for t in topics["topics"]}
    assert t_map["tariffs_trade_war"]["article_count"] == 2
    assert t_map["semiconductors_export_controls"]["article_count"] == 1
    t_detail = client.get("/api/topics/tariffs_trade_war?days=30").json()
    assert len(t_detail["articles"]) == 2
    assert len(t_detail["related_events"]) == 1
    assert client.get("/api/topics/nonexistent_topic").status_code == 404

    # 3. Country comparison with sample-size warning & Sentiment vs Stance split
    cmp_res = client.get("/api/countries/compare?countries=US,DE&days=30").json()
    assert len(cmp_res["countries"]) == 2
    us = next(c for c in cmp_res["countries"] if c["country_id"] == "US")
    de = next(c for c in cmp_res["countries"] if c["country_id"] == "DE")
    assert us["article_count"] == 1 and us["small_sample_warning"] is True
    assert de["article_count"] == 2 and de["stance"]["unclassified_count"] == 1

    # 4. Event detail: strict event_time (unknown when null, NOT replaced by published_at)
    ev_detail = client.get(f"/api/events/{ids['ev_id']}").json()
    assert ev_detail["event_timeline"][0]["event_time"] is None
    assert ev_detail["event_timeline"][0]["time_status"] == "unknown"
    assert len(ev_detail["coverage_timeline"]) == 2
    assert len(ev_detail["cross_country_interpretation"]) == 2
    assert len(ev_detail["evidence_segments"]) >= 1

    # 5. Narratives API with supporting & counter evidence
    narr = client.get("/api/narratives?days=30").json()
    assert len(narr["narratives"]) == 1
    n0 = narr["narratives"][0]
    assert len(n0["supporting_evidence"]) == 1
    assert len(n0["counter_evidence"]) == 1
    n_det = client.get(f"/api/narratives/{ids['nc_id']}?days=30").json()
    assert n_det["narrative"]["narrative_id"] == ids["nc_id"]

    # 6. Sentiment & Stance strict separation + expression_owner split
    ss = client.get("/api/sentiment-stance?days=30").json()
    assert ss["meta"]["stance_target"] == "china_mainland"
    assert ss["sentiment"]["overall_counts"]["negative"] == 1
    assert ss["sentiment"]["overall_counts"]["neutral"] == 1
    assert ss["sentiment"]["overall_counts"]["positive"] == 1
    assert ss["stance"]["expression_owner_counts"]["media"] == 2

    # 7. Articles Explorer pagination, filtering & published_at descending order
    art_page = client.get("/api/articles?page=1&page_size=2").json()
    assert art_page["pagination"]["total"] == 3
    assert art_page["pagination"]["total_pages"] == 2
    assert len(art_page["items"]) == 2
    # a2 (now-1h) must come before a1 (now-2h)
    assert art_page["items"][0]["article_id"] == ids["a2_id"]
    assert art_page["items"][1]["article_id"] == ids["a1_id"]

    filtered = client.get("/api/articles?country=US&stance=Negative").json()
    assert filtered["pagination"]["total"] == 1
    assert filtered["items"][0]["article_id"] == ids["a1_id"]

    # 8. Direct Evidence Ref lookup & offset traceability
    ev_lookup = client.get(f"/api/evidence/{ids['ev_span_id']}").json()
    assert ev_lookup["article_id"] == ids["a1_id"]
    assert ev_lookup["evidence"]["validated"] is True
    s_off = ev_lookup["evidence"]["start_offset"]
    e_off = ev_lookup["evidence"]["end_offset"]
    assert ev_lookup["article"]["content_excerpt"][s_off:e_off] == ev_lookup["evidence"]["text_span"]
    assert client.get("/api/evidence/does-not-exist").status_code == 404

    # 9. Assessments, Outlook, Reports list, Package JSON & Markdown
    assess_list = client.get("/api/assessments").json()
    assert assess_list["total_tasks"] == 9
    outlook = client.get(f"/api/outlook?date={ids['day']}").json()
    assert "disclaimer" in outlook["meta"]

    # Save snapshot via v2 analyze and verify reports/list & package markdown
    client.post(
        "/api/reports/daily/analyze",
        json={"period": ids["day"], "engine": "v2", "tasks": ["overall_situation_assessment"], "save_snapshot": True},
    )
    rep_list = client.get("/api/reports/list?report_type=daily").json()
    assert rep_list["total"] >= 1
    pkg_json = client.get(f"/api/reports/daily/package?date={ids['day']}&from_snapshot=true").json()
    assert pkg_json["report_package"]["report_id"] == f"daily:{ids['day']}"
    pkg_md = client.get(f"/api/reports/daily/package?date={ids['day']}&format=markdown")
    assert pkg_md.status_code == 200
    assert "Daily Intelligence Brief" in pkg_md.text

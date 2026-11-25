"""Daily Intel Fix Pass: tagging, ranking, tone gate, judgment."""

from __future__ import annotations

from collections import Counter

from gni.reports.daily import MIN_TONE_N, _build_judgment_text, _country_tone_status, _country_tone_summary
from gni.reports.risk_tagging import _cfg, china_signal_score, tag_text


def setup_function() -> None:
    _cfg.cache_clear()


def test_tag_blacklist_solomon_nvidia_diversion():
    blacklist = tag_text("US adds Chinese firms to entity list blacklist")
    assert blacklist["risk_level"] == "high"
    assert "trade" in blacklist["sector_ids"] or "semiconductors" in blacklist["sector_ids"]

    solomon = tag_text("Australia cancels Solomon Islands security pact with China")
    assert solomon["risk_level"] in {"high", "medium"}
    assert "geopolitics" in solomon["sector_ids"]

    nvidia = tag_text("Nvidia chips diverted to China via third country", "export control diversion")
    assert nvidia["risk_level"] == "high"
    assert "semiconductors" in nvidia["sector_ids"]


def test_china_signal_ranks_risk_over_weak_ai_coop():
    high = china_signal_score(
        title="US sanctions blacklist hits semiconductor exporters to China",
        evidence_titles=["Entity list expanded"],
        tags=tag_text("US sanctions blacklist semiconductor China"),
        anomaly_flagged=True,
        importance=0.5,
        avg_china_weight=0.8,
    )
    weak = china_signal_score(
        title="Regional chess tournament opens amid tech partnership talks",
        evidence_titles=["Local sports page"],
        tags=tag_text("Regional chess tournament opens amid tech partnership talks"),
        anomaly_flagged=False,
        importance=0.9,
        avg_china_weight=0.1,
    )
    assert high > weak
    assert high >= 5.0


def test_tone_n1_unavailable():
    assert _country_tone_status(1) == "unavailable"
    assert _country_tone_status(0) == "no_sample"
    assert _country_tone_status(MIN_TONE_N) == "ok"
    text = _country_tone_summary("US", 1, {"negative": 1}, {"oppose": 1})
    assert "不可用" in text
    assert "负面为主" not in text


def test_judgment_backlog_unavailable():
    text, conf = _build_judgment_text(
        major_events=[],
        orphan_headlines=[],
        tone_by_country=[{"country_id": "US", "n": 1, "status": "unavailable"}],
        topic_overall=Counter({"other_unknown": 1}),
        missing=80,
        day_total=100,
        china_n=10,
    )
    assert conf == "unavailable"
    assert "分析覆盖不足" in text


def test_heuristic_chess_not_technology():
    from gni.analysis.heuristic import _pick_topic

    # Avoid substring traps (e.g. "pla" inside "players"); bare ai/tech must not map.
    primary, _ = _pick_topic(
        "Local chess club wins regional tournament after an earthquake. "
        "Bare words tech and ai alone must not force technology."
    )
    assert primary == "other_unknown"


def test_validate_v4_requires_judgment():
    from gni.reports.validate import validate_daily_report

    base = {
        "schema_version": "daily_report_schema_v4",
        "report_type": "daily",
        "period": "2026-11-25",
        "disclaimer": "test",
        "sections": {
            "summary": {
                "kpis": {"china_articles": 0},
                "overview_text": "x",
                "judgment_text": "主议题偏 geopolitics；样本不足不可外推。",
                "confidence": "medium",
                "risk_banner": {"has_high_risk": False, "high_risk_event_count": 0, "text": "ok"},
            },
            "overview_stats": {},
            "major_events": [],
            "coverage": {},
            "tone": {},
            "anomalies": [],
            "signals": [],
            "ops": {},
            "quality": {},
        },
        "narratives": {},
    }
    assert validate_daily_report(base)["ok"]

    bad = {
        **base,
        "sections": {
            **base["sections"],
            "summary": {"kpis": {"china_articles": 0}, "overview_text": "x"},
        },
    }
    v = validate_daily_report(bad)
    assert not v["ok"]
    assert any("judgment" in e or "confidence" in e for e in v["errors"])

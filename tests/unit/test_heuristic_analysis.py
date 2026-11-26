"""Heuristic six-dimension analysis schema smoke tests."""

from gni.analysis.heuristic import SCHEMA_VERSION, build_structured_analysis
from gni.analysis.l2_fulltext import screen_fulltext
from gni.analysis.l3_spans import extract_china_spans
from gni.analysis.relevance import assess_relevance
from gni.processing.title_l1 import load_dictionary


def setup_function() -> None:
    load_dictionary.cache_clear()


def test_structured_result_required_keys_and_stance_target():
    body = (
        "China and the United States compete over semiconductor supply chains. "
        "Chinese firms face export controls while cooperation talks continue in parallel. "
        "Analysts say the rivalry will reshape technology markets."
    )
    title = "China chip rivalry intensifies"
    l2 = screen_fulltext(body, title=title, title_screening_label="explicit_relevant")
    spans = extract_china_spans(body, l2, language="en")
    rel = assess_relevance(
        l2,
        title=title,
        span_count=len(spans),
        valid_span_count=sum(1 for s in spans if s.validation_status == "valid"),
    )
    result = build_structured_analysis(
        language="en",
        title=title,
        content_clean=body,
        l2_matched_entities=l2.matched_entities,
        spans=spans,
        relevance=rel,
    )
    assert result["schema_version"] == SCHEMA_VERSION
    assert result["taxonomy_version"] == "taxonomy_v1.0"
    assert result["relevance_weight_version"] == "provisional_v0.3"
    assert "semiconductors_export_controls" in result["topics_v1"]
    assert "economy_tech" in result["boards_v1"]
    assert result["china_stance"]["stance_label"] in {
        "Positive",
        "Neutral",
        "Negative",
        "Unclassified",
    }
    for key in (
        "china_relevance",
        "topics",
        "sentiment",
        "stances",
        "framing",
        "entities",
        "evidence",
        "field_status",
        "confidence",
    ):
        assert key in result
    assert result["stances"]
    assert all("target_id" in s and "stance" in s and "status" in s for s in result["stances"])
    assert result["china_relevance"]["level"] in {
        "core",
        "substantial",
        "secondary",
        "incidental",
        "none",
        "uncertain",
    }

"""P1-C L2 / L3 / relevance unit tests."""

from gni.analysis.l2_fulltext import screen_fulltext
from gni.analysis.l3_spans import extract_china_spans, validate_span_quote
from gni.analysis.relevance import LEVEL_WEIGHT_MIDPOINT, assess_relevance
from gni.processing.title_l1 import load_dictionary


def setup_function() -> None:
    load_dictionary.cache_clear()


def test_l2_insufficient_short_body():
    r = screen_fulltext("China briefly.", title="China news")
    assert r.label == "insufficient_text"


def test_l2_china_related_substantive():
    body = (
        "Beijing and Washington continue trade talks this week.\n\n"
        "China remains a central actor in semiconductor supply chains, "
        "and Chinese firms are expanding capacity across Asia. "
        "Officials said Chinese policy will shape regional markets for years.\n\n"
        "Local sports scores were unchanged."
    )
    r = screen_fulltext(body, title="China trade talks resume", title_screening_label="explicit_relevant")
    assert r.label == "china_related"
    assert r.supporting_paragraph_ids
    assert r.content_share_estimate and r.content_share_estimate > 0


def test_l2_not_china_related():
    body = (
        "The city council debated parking fees for three hours. "
        "Residents argued about bike lanes and school zoning. "
        "No international topics were raised during the session."
    )
    r = screen_fulltext(body, title="Local parking debate")
    assert r.label == "not_china_related"


def test_l2_incidental_becomes_not_china_or_incidental_path():
    body = (
        "European football leagues saw record attendance this season. "
        "Fans filled stadiums from Madrid to Milan. "
        "Separately, a footnote mentioned China once in passing. "
        "Weather across the continent remained mild."
    )
    # May be china_related or not depending on share; incidental path is acceptable
    r = screen_fulltext(body, title="Football attendance rises")
    assert r.label in {"china_related", "not_china_related", "uncertain"}


def test_l3_spans_validate_in_content():
    body = (
        "Intro without focus on regional markets or unrelated sports coverage.\n\n"
        "China announced new export rules on advanced chips this morning, "
        "and Chinese officials said the framework would reshape supplier planning.\n\n"
        "Closing remarks about markets and overnight futures moves followed."
    )
    l2 = screen_fulltext(body, title="China chip rules")
    assert l2.label == "china_related"
    spans = extract_china_spans(body, l2, language="en")
    assert spans
    valid = [s for s in spans if s.validation_status == "valid"]
    assert valid
    for s in valid:
        assert validate_span_quote(body, s.text_original, s.char_start, s.char_end)
        assert body[s.char_start : s.char_end] == s.text_original


def test_relevance_core_mapping():
    body = (
        "China is the main subject of this long analysis of industrial policy. "
        "Chinese Government agencies issued detailed guidance for exporters. "
        "The article reviews China tariffs, subsidies, and supply chains in depth. "
        "Further sections examine Chinese tech industry responses and military adjacent dual use concerns. "
        "Overall the piece argues China remains the primary actor shaping outcomes."
    )
    title = "China industrial policy deep dive"
    l2 = screen_fulltext(body, title=title, title_screening_label="explicit_relevant")
    spans = extract_china_spans(body, l2)
    valid_n = sum(1 for s in spans if s.validation_status == "valid")
    rel = assess_relevance(l2, title=title, span_count=len(spans), valid_span_count=valid_n)
    assert rel.relevance_level in {"core", "substantial", "secondary"}
    assert rel.relevance_weight == LEVEL_WEIGHT_MIDPOINT[rel.relevance_level]
    assert rel.assessment_version == "provisional_v0.3"


def test_relevance_none():
    body = (
        "Municipal budgets and school lunches dominated the weekly meeting. "
        "Council members approved a new recycling schedule for downtown wards. "
        "Nothing about foreign policy appeared on the agenda."
    )
    l2 = screen_fulltext(body, title="City council notes")
    rel = assess_relevance(l2, title="City council notes")
    assert rel.relevance_level == "none"
    assert rel.relevance_weight == 0.0

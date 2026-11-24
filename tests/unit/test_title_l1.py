"""L1 title screening rules."""

from gni.processing.title_l1 import load_dictionary, screen_title


def setup_function() -> None:
    load_dictionary.cache_clear()


def test_explicit_china_in_title():
    r = screen_title("China and the US discuss trade tariffs")
    assert r.label == "explicit_relevant"
    assert r.priority == "P1"
    assert any(m["entity_id"] == "china_country" for m in r.matched_entities)


def test_indirect_metonym():
    r = screen_title("Asian giant expands EV exports overseas")
    assert r.label == "explicit_relevant"
    assert any(m["entity_id"] == "china_indirect" for m in r.matched_entities)


def test_russian_china():
    r = screen_title("Китай и Россия обсудили энергетику")
    assert r.label == "explicit_relevant"


def test_german_chinese():
    r = screen_title("Chinesische Unternehmen investieren in Europa")
    assert r.label in {"explicit_relevant", "likely_relevant"}


def test_asia_broad_likely():
    r = screen_title("Asia faces new climate financing debate")
    assert r.label == "likely_relevant"
    assert r.priority == "P2"


def test_company_likely():
    r = screen_title("Huawei unveils new chip roadmap")
    assert r.label == "likely_relevant"
    assert r.priority == "P2"


def test_no_match():
    r = screen_title("Local city council debates parking fees")
    assert r.label == "no_match"
    assert r.priority == "P3"


def test_beijing_ambiguous_uncertain():
    r = screen_title("Beijing hosts winter sports festival")
    # geography beijing alone is ambiguous scope -> uncertain
    assert r.label == "uncertain"

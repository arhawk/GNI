"""L1 title screening rules."""

from gni.processing.title_l1 import screen_title


def test_explicit_china_in_title():
    r = screen_title("China and the US discuss trade tariffs")
    assert r.label == "explicit_relevant"
    assert r.priority == "P1"
    assert any(m["entity_id"] == "china_country" for m in r.matched_entities)


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
    assert r.label in {"uncertain", "likely_relevant", "explicit_relevant"}
    # geography beijing alone is ambiguous scope -> uncertain
    assert r.label == "uncertain"

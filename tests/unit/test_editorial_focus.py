"""Unit tests: active seed sources must declare international/China editorial focus."""

from __future__ import annotations

from pathlib import Path

import pytest

from gni.sources.editorial_focus import (
    ACTIVE_EDITORIAL_DENYLIST,
    EDITORIAL_FOCUS_INTERNATIONAL_OR_CHINA,
    passes_editorial_focus,
    score_titles,
    title_is_china,
    title_is_intl_or_china,
)
from gni.sources.seed import DEFAULT_SEED, load_seed_file

SEED = Path(DEFAULT_SEED)


def test_china_and_intl_keyword_helpers():
    assert title_is_china("Beijing warns on Taiwan")
    assert title_is_china("МИД КНР отказался комментировать")
    assert title_is_intl_or_china("NATO summit opens in Berlin")
    assert title_is_intl_or_china("पश्चिम एशिया में हाल के घटनाक्रम")
    assert not title_is_intl_or_china("Local school lunch programme expands")


def test_score_titles_ratio():
    titles = [
        "China trade talks resume",
        "Local council budget vote",
        "UN Security Council meets on Ukraine",
        "City metro fare hike",
    ]
    s = score_titles(titles)
    assert s["n"] == 4
    assert s["china"] == 1
    assert s["intl_or_china"] == 2
    assert s["rate"] == pytest.approx(0.5)


def test_passes_editorial_focus_desk_threshold():
    # Explicit Asia desk may pass at ≥0.20
    titles = ["China sea code talks"] + ["Local weather"] * 4
    ok, detail = passes_editorial_focus(
        titles,
        source_id="de_dw_asia",
        name="DW Asia",
        feed_url="https://rss.dw.com/rdf/rss-en-asia",
    )
    assert detail["desk"] is True
    assert ok is True
    assert detail["rate"] == pytest.approx(0.2)


def test_active_sources_declare_editorial_focus_and_avoid_denylist():
    data = load_seed_file(SEED)
    sources = data.get("sources") or []
    active = [s for s in sources if s.get("active_status") == "active"]
    assert active, "expected at least one active source in seed"

    missing_focus = []
    denylist_hits = []
    for row in active:
        sid = row["source_id"]
        if sid in ACTIVE_EDITORIAL_DENYLIST:
            denylist_hits.append(sid)
        focus = row.get("editorial_focus") or (row.get("config") or {}).get("editorial_focus")
        if focus != EDITORIAL_FOCUS_INTERNATIONAL_OR_CHINA:
            missing_focus.append(sid)

    assert not denylist_hits, f"denylisted source_ids still active: {denylist_hits}"
    assert not missing_focus, (
        f"active sources missing editorial_focus={EDITORIAL_FOCUS_INTERNATIONAL_OR_CHINA}: "
        f"{missing_focus}"
    )


def test_active_panel_has_target_countries():
    data = load_seed_file(SEED)
    active = [s for s in data["sources"] if s.get("active_status") == "active"]
    by_country: dict[str, list[str]] = {}
    for s in active:
        by_country.setdefault(s["country_id"], []).append(s["source_id"])
    for code in ("US", "RU", "DE", "IN", "AU"):
        assert code in by_country, f"no active source for {code}"
        assert 1 <= len(by_country[code]) <= 3, by_country

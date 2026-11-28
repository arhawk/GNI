"""Unit tests: active seed sources must declare international/China editorial focus."""

from __future__ import annotations

from pathlib import Path

import pytest

from gni.sources.editorial_focus import (
    ACTIVE_EDITORIAL_DENYLIST,
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


def test_active_sources_avoid_denylist():
    data = load_seed_file(SEED)
    sources = data.get("sources") or []
    active = [s for s in sources if s.get("active_status") == "active"]
    assert active, "expected at least one active source in seed"

    denylist_hits = [
        row["source_id"]
        for row in active
        if row["source_id"] in ACTIVE_EDITORIAL_DENYLIST
    ]
    assert not denylist_hits, f"denylisted source_ids still active: {denylist_hits}"


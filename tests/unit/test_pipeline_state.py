"""Data-layer pipeline_state helpers."""

from types import SimpleNamespace

import pytest

from gni.infrastructure.pipeline_state import (
    ALL_STATES,
    RAW_STORED,
    set_pipeline_state,
)


def test_all_states_cover_lifecycle():
    assert "DISCOVERED" in ALL_STATES
    assert "AVAILABLE_FOR_ANALYTICS" in ALL_STATES
    assert len(ALL_STATES) == 10


def test_set_pipeline_state_ok():
    article = SimpleNamespace()
    set_pipeline_state(article, RAW_STORED)
    assert article.pipeline_state == RAW_STORED


def test_set_pipeline_state_rejects_unknown():
    article = SimpleNamespace()
    with pytest.raises(ValueError, match="unknown"):
        set_pipeline_state(article, "NOT_A_STATE")

"""Article pipeline_state constants (data-layer lifecycle). See docs/DATA_LAYERS.md."""

from __future__ import annotations

DISCOVERED = "DISCOVERED"
RAW_STORED = "RAW_STORED"
NORMALIZED = "NORMALIZED"
DEDUPLICATED = "DEDUPLICATED"
TITLE_SCREENED = "TITLE_SCREENED"
FULLTEXT_SCREENED = "FULLTEXT_SCREENED"
EXTRACTION_COMPLETED = "EXTRACTION_COMPLETED"
ANALYSIS_COMPLETED = "ANALYSIS_COMPLETED"
EVENT_LINKED = "EVENT_LINKED"
AVAILABLE_FOR_ANALYTICS = "AVAILABLE_FOR_ANALYTICS"

ALL_STATES: frozenset[str] = frozenset(
    {
        DISCOVERED,
        RAW_STORED,
        NORMALIZED,
        DEDUPLICATED,
        TITLE_SCREENED,
        FULLTEXT_SCREENED,
        EXTRACTION_COMPLETED,
        ANALYSIS_COMPLETED,
        EVENT_LINKED,
        AVAILABLE_FOR_ANALYTICS,
    }
)

# Relevance levels that qualify for analytics dashboards / metrics inclusion.
ANALYTICS_RELEVANCE_LEVELS: frozenset[str] = frozenset({"core", "substantial", "secondary"})


def set_pipeline_state(article: object, state: str) -> None:
    """Set articles.pipeline_state if the attribute exists."""
    if state not in ALL_STATES:
        raise ValueError(f"unknown pipeline_state: {state}")
    setattr(article, "pipeline_state", state)

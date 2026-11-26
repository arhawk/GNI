"""Metric definition versions and inclusion rules (metrics_v0.4)."""

from __future__ import annotations

METRIC_DEFINITION_VERSION = "metrics_v0.4"
METHODOLOGY_VERSION = "methodology_v1.0"
TAXONOMY_V1_VERSION = "taxonomy_v1.0"
V1_ANALYSIS_VERSION = "article_analysis_v1.0"
STANCE_LABELS_V1 = ("Positive", "Neutral", "Negative")
UNCLASSIFIED_LABEL = "Unclassified"
RELEVANCE_WEIGHT_VERSION = "provisional_v0.3"
DEDUPLICATION_METHOD = "content_hash_then_title_hash_v1"

# Core research inclusion (provisional): incidental excluded by default
CHINA_INCLUDE_LEVELS = frozenset({"core", "substantial", "secondary"})

SENTIMENT_SCORE_MAP: dict[str, float] = {
    "positive": 0.60,
    "neutral": 0.0,
    "negative": -0.60,
}
# mixed / unknown / null → excluded from Weighted Sentiment Score denominator

ARTICLE_COUNT_V = "article_count_v1"
UNIQUE_STORY_COUNT_V = "unique_story_count_v1"
ATTENTION_SHARE_V = "attention_share_v1"
SENTIMENT_DIST_V = "sentiment_distribution_v1"
STANCE_DIST_V = "stance_distribution_v1"
FRAME_DIST_V = "frame_distribution_v1"
TOPIC_SHARE_V = "topic_share_v1"
WEIGHTED_VOLUME_V = "weighted_article_volume_v1"
WEIGHTED_SENT_SCORE_V = "weighted_sentiment_score_v1"
WEIGHTED_SENT_DIST_V = "weighted_sentiment_distribution_v1"
NP_RATIO_V = "np_ratio_v1"
SENTIMENT_COVERAGE_V = "sentiment_coverage_v1"
SOURCE_COUNT_V = "source_count_v1"
COUNTRY_COUNT_V = "country_count_v1"
INGESTION_SUCCESS_V = "ingestion_success_rate_v1"
EXTRACTION_SUCCESS_V = "article_extraction_success_rate_v1"

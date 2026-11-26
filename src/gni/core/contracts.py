"""Unified Pydantic v2 logical data contracts for GNI V2.0 Architecture.

Covers the 7 core logical contracts without requiring destructive DB table rewrites:
1. ArticleIntelligenceContract (stored in ArticleAnalysis.structured_result + spans/relevance)
2. EventIntelligenceContract
3. NarrativeIntelligenceContract
4. MetricSnapshotContract
5. SignalRecordContract
6. EvidencePackageContract
7. ReportPackageContract (with ReportSectionContract)

All contracts enforce explicit NULL / Unclassified semantics, version fields,
and traceable evidence references.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Unified V2.0 contract version constants
ARTICLE_INTELLIGENCE_VERSION = "article_intel_v2.0"
EVENT_INTELLIGENCE_VERSION = "event_intel_v2.0"
NARRATIVE_INTELLIGENCE_VERSION = "narrative_intel_v2.0"
METRIC_SNAPSHOT_CONTRACT_VERSION = "methodology_v1.0"
EVIDENCE_PACKAGE_VERSION = "evidence_v2.0"
ASSESSMENT_SCHEMA_VERSION = "assessment_v2.0"
REPORT_PACKAGE_VERSION = "report_package_v2.0"

StanceLabelV1 = Literal["Positive", "Neutral", "Negative", "Unclassified"]
ExpressionOwner = Literal["media", "quoted_actor", "unclear"]
NarrativeAttribution = Literal["mention", "quote", "support", "refute", "unclear"]
EventRelationType = Literal[
    "new_event_candidate",
    "existing_event_update",
    "background_reference",
    "unrelated",
]
EventLifecycleStatus = Literal[
    "emerging",
    "ongoing",
    "escalating",
    "de_escalating",
    "resolved",
    "dormant",
    "uncertain",
]
NarrativeTrendStatus = Literal[
    "emerging",
    "growing",
    "stable",
    "declining",
    "fragmented",
    "shifting",
]
SignalType = Literal[
    "attention_change",
    "topic_shift",
    "narrative_emergence",
    "narrative_diffusion",
    "event_escalation",
    "cross_country_divergence",
    "sentiment_shift",
    "stance_shift",
]


def _clamp01(value: Any, default: float = 0.0) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    return round(max(0.0, min(1.0, v)), 4)


def _norm_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        s = value.strip()
        return [s] if s else []
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    return [str(value).strip()]


# ---------------------------------------------------------------------------
# 1. Article Intelligence Contract
# ---------------------------------------------------------------------------


class EvidenceSpanRef(BaseModel):
    """Original-text traceable evidence span bound to a specific ArticleVersion."""

    model_config = ConfigDict(extra="ignore")

    evidence_id: str
    article_id: str | None = None
    article_version_id: str | None = None
    text_span: str
    start_offset: int | None = None
    end_offset: int | None = None
    paragraph_index: int | None = None
    evidence_type: str = "general"  # relevance|topic|sentiment|stance|narrative|entity|event
    supports_claim: str = ""
    analysis_task: str = "article_intelligence"
    validated: bool = False


class ArticleRelevanceContract(BaseModel):
    model_config = ConfigDict(extra="ignore")

    is_china_related: bool | None = None
    china_relevance_level: str = "uncertain"
    china_relevance_score: float | None = None
    relevant_passages: list[str] = Field(default_factory=list)
    relevance_reason: str = ""


class ArticleTopicContract(BaseModel):
    model_config = ConfigDict(extra="ignore")

    topic_id: str
    topic_name: str = ""
    sector_id: str = ""
    relevance: Literal["primary", "secondary", "supporting"] = "primary"
    evidence_refs: list[str] = Field(default_factory=list)


class ArticleSentimentContract(BaseModel):
    model_config = ConfigDict(extra="ignore")

    sentiment_label: Literal["positive", "neutral", "negative", "mixed", "unknown"] | None = None
    sentiment_target: str = "china_mainland"
    evidence_refs: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    reasoning: str = ""

    @field_validator("confidence", mode="before")
    @classmethod
    def _v_conf(cls, v: Any) -> float:
        return _clamp01(v)


class ArticleStanceContract(BaseModel):
    model_config = ConfigDict(extra="ignore")

    target: str = "china_mainland"
    stance_label: StanceLabelV1 = "Unclassified"
    expression_owner: ExpressionOwner = "unclear"
    evidence_refs: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    reasoning: str = ""

    @field_validator("confidence", mode="before")
    @classmethod
    def _v_conf(cls, v: Any) -> float:
        return _clamp01(v)

    @field_validator("expression_owner", mode="before")
    @classmethod
    def _v_owner(cls, v: Any) -> str:
        raw = str(v or "unclear").strip().lower()
        if raw in {"media", "outlet", "editorial", "author"}:
            return "media"
        if raw in {"quoted_actor", "quoted", "quote", "interviewee", "third_party", "cited"}:
            return "quoted_actor"
        return "unclear"


class ArticleNarrativeContract(BaseModel):
    model_config = ConfigDict(extra="ignore")

    narrative_id: str
    frame: str
    claim: str
    actor: str = ""
    target: str = "china_mainland"
    attribution: NarrativeAttribution = "unclear"
    tone: Literal["positive", "neutral", "negative", "mixed", "unclear"] = "unclear"
    evidence_refs: list[str] = Field(default_factory=list)
    confidence: float = 0.5

    @field_validator("attribution", mode="before")
    @classmethod
    def _v_attr(cls, v: Any) -> str:
        raw = str(v or "unclear").strip().lower()
        if raw in {"mention", "mentioned"}:
            return "mention"
        if raw in {"quote", "quoted", "cited"}:
            return "quote"
        if raw in {"support", "supports", "endorse", "endorses"}:
            return "support"
        if raw in {"refute", "refutes", "rebut", "challenges", "reject"}:
            return "refute"
        return "unclear"

    @field_validator("tone", mode="before")
    @classmethod
    def _v_tone(cls, v: Any) -> str:
        raw = str(v or "unclear").strip().lower()
        if raw in {"positive", "neutral", "negative", "mixed"}:
            return raw
        return "unclear"

    @field_validator("confidence", mode="before")
    @classmethod
    def _v_conf(cls, v: Any) -> float:
        return _clamp01(v, default=0.5)


class ArticleEntityContract(BaseModel):
    model_config = ConfigDict(extra="ignore")

    entity_id: str
    canonical_name: str
    entity_type: Literal[
        "country",
        "government_agency",
        "political_figure",
        "international_org",
        "company",
        "organization",
        "person",
        "location",
        "policy",
        "other",
    ] = "other"
    mentions: list[str] = Field(default_factory=list)
    roles: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)

    @field_validator("mentions", "roles", "evidence_refs", mode="before")
    @classmethod
    def _v_lists(cls, v: Any) -> list[str]:
        return _norm_str_list(v)


class ArticleEventCandidateContract(BaseModel):
    model_config = ConfigDict(extra="ignore")

    event_id: str | None = None
    event_relation: EventRelationType = "new_event_candidate"
    actor: str = ""
    action: str = ""
    object: str = ""
    event_time: str | None = None  # Never filled from published_at when unknown
    location: str | None = None
    summary: str = ""
    event_evidence_refs: list[str] = Field(default_factory=list)
    confidence: float = 0.5

    @field_validator("event_relation", mode="before")
    @classmethod
    def _v_rel(cls, v: Any) -> str:
        raw = str(v or "new_event_candidate").strip().lower()
        if raw in {
            "new_event_candidate",
            "existing_event_update",
            "background_reference",
            "unrelated",
        }:
            return raw
        return "new_event_candidate"

    @field_validator("confidence", mode="before")
    @classmethod
    def _v_conf(cls, v: Any) -> float:
        return _clamp01(v, default=0.5)


class ArticleQualityContract(BaseModel):
    model_config = ConfigDict(extra="ignore")

    completeness: float = 0.0
    language_quality: Literal["ok", "unknown", "poor"] = "ok"
    extraction_quality: Literal["ok", "stub", "insufficient", "failed"] = "ok"
    classification_quality: Literal["high", "medium", "low", "unclassified"] = "medium"
    needs_review: bool = False
    quality_flags: list[str] = Field(default_factory=list)

    @field_validator("completeness", mode="before")
    @classmethod
    def _v_comp(cls, v: Any) -> float:
        return _clamp01(v)

    @field_validator("quality_flags", mode="before")
    @classmethod
    def _v_flags(cls, v: Any) -> list[str]:
        return _norm_str_list(v)


class ArticleAnalysisMetadataContract(BaseModel):
    model_config = ConfigDict(extra="ignore")

    record_source: Literal["model", "human_override", "hybrid"] = "model"
    human_reviewed_by: str | None = None
    human_reviewed_at: str | None = None
    model_name: str = ""
    model_version: str = ""
    prompt_version: str = ""
    analysis_version: str = ARTICLE_INTELLIGENCE_VERSION
    schema_version: str = "article_analysis_v1.0"
    taxonomy_version: str = "taxonomy_v1.0"
    article_version_id: str | None = None
    processed_at: str | None = None
    token_usage: int = 0
    processing_status: str = "completed"


class ArticleIntelligenceContract(BaseModel):
    """Unified V2.0 Article Intelligence object."""

    model_config = ConfigDict(extra="ignore")

    article_id: str
    analysis_version: str = ARTICLE_INTELLIGENCE_VERSION
    relevance: ArticleRelevanceContract
    topics: list[ArticleTopicContract] = Field(default_factory=list)
    sentiment: ArticleSentimentContract = Field(default_factory=ArticleSentimentContract)
    stance: list[ArticleStanceContract] = Field(default_factory=list)
    narratives: list[ArticleNarrativeContract] = Field(default_factory=list)
    entities: list[ArticleEntityContract] = Field(default_factory=list)
    events: list[ArticleEventCandidateContract] = Field(default_factory=list)
    evidence: list[EvidenceSpanRef] = Field(default_factory=list)
    quality: ArticleQualityContract = Field(default_factory=ArticleQualityContract)
    analysis_metadata: ArticleAnalysisMetadataContract = Field(
        default_factory=ArticleAnalysisMetadataContract
    )


# ---------------------------------------------------------------------------
# 2. Event Intelligence Contract
# ---------------------------------------------------------------------------


class EventIntelligenceContract(BaseModel):
    model_config = ConfigDict(extra="ignore")

    event_id: str
    canonical_title: str
    description: str = ""
    actors: list[str] = Field(default_factory=list)
    action: str | None = None
    object: str | None = None
    event_type: str | None = None
    event_time: datetime | None = None  # NULL if unknown; never substituted with published_at
    location: dict[str, Any] | None = None
    status: EventLifecycleStatus = "uncertain"
    article_ids: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    confidence: float = 0.5
    record_source: Literal["model", "human_override", "hybrid"] = "model"
    schema_version: str = EVENT_INTELLIGENCE_VERSION


# ---------------------------------------------------------------------------
# 3. Narrative Intelligence Contract
# ---------------------------------------------------------------------------


class NarrativeIntelligenceContract(BaseModel):
    model_config = ConfigDict(extra="ignore")

    narrative_cluster_id: str
    canonical_frame: str
    canonical_claim: str
    related_articles: list[str] = Field(default_factory=list)
    related_countries: list[str] = Field(default_factory=list)
    supporting_evidence: list[EvidenceSpanRef] = Field(default_factory=list)
    counter_evidence: list[EvidenceSpanRef] = Field(default_factory=list)
    first_observed_at: datetime | None = None
    last_observed_at: datetime | None = None
    trend_status: NarrativeTrendStatus = "emerging"
    confidence: float = 0.5
    record_source: Literal["model", "human_override", "hybrid"] = "model"
    schema_version: str = NARRATIVE_INTELLIGENCE_VERSION


# ---------------------------------------------------------------------------
# 4. Metric Snapshot Contract
# ---------------------------------------------------------------------------


class MetricSnapshotContract(BaseModel):
    model_config = ConfigDict(extra="ignore")

    metric_run_id: str
    period_start: datetime
    period_end: datetime
    granularity: Literal["daily", "weekly", "monthly", "custom"] = "daily"
    scope: str  # GLOBAL | COUNTRY | BOARD | TOPIC | MEDIA
    metric_name: str
    dimension: str = ""
    dimension_value: str = ""
    metric_value: float | int | None = None
    comparison_value: float | int | None = None
    calculation_version: str = METRIC_SNAPSHOT_CONTRACT_VERSION
    generated_at: datetime


# ---------------------------------------------------------------------------
# 5. Signal Record Contract
# ---------------------------------------------------------------------------


class SignalRecordContract(BaseModel):
    model_config = ConfigDict(extra="ignore")

    signal_id: str
    signal_type: SignalType
    subject: str
    observation: str
    trigger_metrics: dict[str, Any] = Field(default_factory=dict)
    supporting_articles: list[str] = Field(default_factory=list)
    supporting_events: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    first_detected_at: datetime | None = None
    last_updated_at: datetime | None = None
    status: Literal["open", "monitoring", "escalated", "dismissed", "resolved"] = "open"
    confidence: Literal["high", "medium", "low"] = "medium"
    assessment: str = ""
    alternative_explanation: str = ""
    review_status: Literal["auto", "reviewed", "confirmed", "rejected"] = "auto"


# ---------------------------------------------------------------------------
# 6. Evidence Package Contract
# ---------------------------------------------------------------------------


class EvidencePackageContract(BaseModel):
    model_config = ConfigDict(extra="ignore")

    package_id: str
    task_type: str
    period: dict[str, Any] = Field(default_factory=dict)
    scope: dict[str, Any] = Field(default_factory=dict)
    metrics: list[dict[str, Any]] = Field(default_factory=list)
    current_articles: list[dict[str, Any]] = Field(default_factory=list)
    historical_comparison: list[dict[str, Any]] = Field(default_factory=list)
    events: list[dict[str, Any]] = Field(default_factory=list)
    narratives: list[dict[str, Any]] = Field(default_factory=list)
    representative_evidence: list[dict[str, Any]] = Field(default_factory=list)
    counter_evidence: list[dict[str, Any]] = Field(default_factory=list)
    coverage: dict[str, Any] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)
    schema_version: str = EVIDENCE_PACKAGE_VERSION


# ---------------------------------------------------------------------------
# 6b. Unified Assessment Result Contract (Phase 5.2)
# ---------------------------------------------------------------------------


class AssessmentResultContract(BaseModel):
    """Unified output contract for all 9 V2.0 Assessment Tasks.

    Strictly separates:
    - observations: direct facts grounded in EvidencePackage (Fact)
    - interpretations: analytical explanations of facts & relations (Inference)
    - hypotheses: tentative hypotheses requiring further verification (Hypothesis)
    """

    model_config = ConfigDict(extra="ignore")

    task_type: str
    task_version: str = "v2.0"
    report_type: str | None = None
    period: str | None = None
    evidence_hash: str | None = None
    executive_summary: str = ""
    key_findings: list[dict[str, Any]] = Field(default_factory=list)
    observations: list[dict[str, Any]] = Field(default_factory=list)
    interpretations: list[dict[str, Any]] = Field(default_factory=list)
    hypotheses: list[dict[str, Any]] = Field(default_factory=list)
    evidence_refs: list[dict[str, Any]] = Field(default_factory=list)
    supporting_metrics: list[str] = Field(default_factory=list)
    counter_evidence: list[dict[str, Any]] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"] = "low"
    confidence_note: str = "Subjective model confidence only; must not be interpreted as empirical accuracy."
    limitations: list[str] = Field(default_factory=list)
    watch_items: list[dict[str, Any]] = Field(default_factory=list)
    # Task-specific structured details (e.g., 7-part event_interpretations, country_comparisons, outlook_signals)
    details: dict[str, Any] = Field(default_factory=dict)
    status: Literal["completed", "needs_review", "insufficient_data", "degraded", "failed"] = "completed"
    validation_result: dict[str, Any] = Field(default_factory=dict)
    generated_at: str | None = None
    model_version: str | None = None
    prompt_version: str | None = None
    schema_version: str = ASSESSMENT_SCHEMA_VERSION
    methodology_version: str = "methodology_v1.0"
    taxonomy_version: str = "taxonomy_v1.0"
    metadata: dict[str, Any] = Field(
        default_factory=lambda: {"schema_version": ASSESSMENT_SCHEMA_VERSION}
    )


# ---------------------------------------------------------------------------
# 7. Report Package Contract
# ---------------------------------------------------------------------------


class ReportSectionContract(BaseModel):
    model_config = ConfigDict(extra="ignore")

    section_id: str
    title: str
    source_kind: Literal["llm_assessment", "deterministic_metrics", "hybrid"] = "hybrid"
    summary: str = ""
    findings: list[dict[str, Any]] = Field(default_factory=list)
    evidence_refs: list[dict[str, Any]] = Field(default_factory=list)
    metrics: list[dict[str, Any]] = Field(default_factory=list)
    visualizations: list[dict[str, Any]] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    assessment_task_types: list[str] = Field(default_factory=list)
    status: Literal["completed", "partial", "needs_review", "rule_only", "insufficient_data", "failed"] = "completed"


class ReportPackageContract(BaseModel):
    model_config = ConfigDict(extra="ignore")

    report_id: str
    report_type: Literal["daily", "weekly", "monthly"]
    period: dict[str, Any] = Field(default_factory=dict)
    period_start: str | None = None
    period_end: str | None = None
    generated_at: str | None = None
    metric_run_id: str | None = None
    metric_snapshot_refs: list[str] = Field(default_factory=list)
    assessment_refs: list[dict[str, Any]] = Field(default_factory=list)
    assessment_results: list[dict[str, Any]] = Field(default_factory=list)
    sections: list[ReportSectionContract] = Field(default_factory=list)
    evidence_refs: list[dict[str, Any]] = Field(default_factory=list)
    methodology: dict[str, Any] = Field(default_factory=dict)
    coverage: dict[str, Any] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)
    generation_status: Literal["completed", "partial", "needs_review", "rule_only", "insufficient_data", "failed"] = "completed"
    validation_status: Literal["passed", "needs_review", "failed"] = "passed"
    validation_notes: list[str] = Field(default_factory=list)
    generation_metadata: dict[str, Any] = Field(
        default_factory=lambda: {"report_schema_version": REPORT_PACKAGE_VERSION}
    )

"""Unified Pydantic v2 schemas for GNI Report Intelligence Narrative Layer."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _norm_classification(value: Any) -> str:
    raw = str(value or "Inference").strip().lower()
    if raw in {"fact", "facts", "事实"}:
        return "Fact"
    if raw in {"hypothesis", "hypotheses", "假设", "待验证"}:
        return "Hypothesis"
    if raw in {"outlook", "展望", "条件性展望"}:
        return "Outlook"
    return "Inference"


def _norm_confidence(value: Any) -> str:
    raw = str(value or "medium").strip().lower()
    if raw in {"high", "高"}:
        return "high"
    if raw in {"low", "低"}:
        return "low"
    return "medium"


def _norm_ref_type(value: Any) -> str:
    raw = str(value or "article").strip().lower()
    if raw in {"metric", "stat", "snapshot", "kpi"}:
        return "metric"
    if raw in {"event", "story"}:
        return "event"
    if raw in {"alert", "signal"}:
        return "alert"
    return "article"


def _norm_persistence(value: Any) -> str:
    raw = str(value or "insufficient_history").strip().lower()
    if raw in {"short_term", "short", "短期", "短期波动"}:
        return "short_term"
    if raw in {"ongoing", "sustained", "persistent", "持续", "持续趋势"}:
        return "ongoing"
    return "insufficient_history"


def _ensure_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        s = value.strip()
        return [s] if s else []
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    return [str(value).strip()]


class EvidenceRef(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: Literal["metric", "article", "event", "alert"] = "article"
    ref_id: str
    label: str = ""
    url: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _coerce_from_str(cls, data: Any) -> Any:
        if isinstance(data, str):
            raw = data.strip()
            if raw.startswith("metric:"):
                return {"type": "metric", "ref_id": raw, "label": raw}
            for prefix in ("article:", "event:", "alert:"):
                if raw.startswith(prefix):
                    kind = prefix[:-1]
                    rid = raw[len(prefix) :].strip()
                    return {"type": kind, "ref_id": rid, "label": rid}
            return {"type": "article", "ref_id": raw, "label": raw}
        return data

    @field_validator("type", mode="before")
    @classmethod
    def _v_type(cls, v: Any) -> str:
        return _norm_ref_type(v)

    @field_validator("ref_id", mode="before")
    @classmethod
    def _v_ref_id(cls, v: Any) -> str:
        return str(v or "").strip()


class Finding(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str
    conclusion: str
    classification: Literal["Fact", "Inference", "Hypothesis", "Outlook"] = "Inference"
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    supporting_metrics: list[str] = Field(default_factory=list)
    counter_evidence: list[EvidenceRef] = Field(default_factory=list)
    reasoning: str = ""
    confidence: Literal["high", "medium", "low"] = "medium"
    limitations: list[str] = Field(default_factory=list)
    needs_review: bool = False
    validation_notes: list[str] = Field(default_factory=list)

    @field_validator("classification", mode="before")
    @classmethod
    def _v_cls(cls, v: Any) -> str:
        return _norm_classification(v)

    @field_validator("confidence", mode="before")
    @classmethod
    def _v_conf(cls, v: Any) -> str:
        return _norm_confidence(v)

    @field_validator("limitations", "validation_notes", "supporting_metrics", mode="before")
    @classmethod
    def _v_str_list(cls, v: Any) -> list[str]:
        return _ensure_str_list(v)


class EventInterpretation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    event_id: str
    title: str
    background: str = ""
    what_happened: str = ""
    event_actual_changes: str = ""
    coverage_attention_changes: str = ""
    country_followup_timing: str = ""
    country_differences: str = ""
    media_viewpoints: list[str] = Field(default_factory=list)
    current_status: str = ""
    why_it_matters: str = ""
    what_to_monitor: list[str] = Field(default_factory=list)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"] = "medium"
    limitations: list[str] = Field(default_factory=list)
    needs_review: bool = False

    @field_validator("confidence", mode="before")
    @classmethod
    def _v_conf(cls, v: Any) -> str:
        return _norm_confidence(v)

    @field_validator("media_viewpoints", "what_to_monitor", "limitations", mode="before")
    @classmethod
    def _v_lists(cls, v: Any) -> list[str]:
        return _ensure_str_list(v)


class TopicTrendItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    topic_id: str
    topic_label: str = ""
    attention_change: str = ""
    stance_change: str = ""
    topic_structure_change: str = ""
    drivers: list[str] = Field(default_factory=list)
    persistence: Literal["short_term", "ongoing", "insufficient_history"] = "insufficient_history"
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"] = "medium"
    limitations: list[str] = Field(default_factory=list)
    needs_review: bool = False

    @field_validator("persistence", mode="before")
    @classmethod
    def _v_pers(cls, v: Any) -> str:
        return _norm_persistence(v)

    @field_validator("confidence", mode="before")
    @classmethod
    def _v_conf(cls, v: Any) -> str:
        return _norm_confidence(v)

    @field_validator("drivers", "limitations", mode="before")
    @classmethod
    def _v_lists(cls, v: Any) -> list[str]:
        return _ensure_str_list(v)


class CountryFrameEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")

    country_id: str
    main_frame: str = ""
    unique_angle: str = ""
    sample_note: str = ""
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)


class CrossCountryItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    subject_type: Literal["event", "topic", "overall"] = "topic"
    subject_id: str = ""
    subject_label: str = ""
    common_focus: str = ""
    country_frames: list[CountryFrameEntry] = Field(default_factory=list)
    major_differences: str = ""
    emerging_or_shifting: str = ""
    insufficient_sample_countries: list[str] = Field(default_factory=list)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"] = "medium"
    needs_review: bool = False

    @field_validator("subject_type", mode="before")
    @classmethod
    def _v_stype(cls, v: Any) -> str:
        raw = str(v or "topic").strip().lower()
        return raw if raw in {"event", "topic", "overall"} else "topic"

    @field_validator("confidence", mode="before")
    @classmethod
    def _v_conf(cls, v: Any) -> str:
        return _norm_confidence(v)

    @field_validator("insufficient_sample_countries", mode="before")
    @classmethod
    def _v_insufficient(cls, v: Any) -> list[str]:
        return _ensure_str_list(v)


class StanceInterpretation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    scope_type: str = "GLOBAL"
    scope_id: str = "ALL"
    scope_label: str = ""
    rate_vs_count_note: str = ""
    drivers: list[str] = Field(default_factory=list)
    coverage_limitation: str = ""
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"] = "medium"
    needs_review: bool = False

    @field_validator("confidence", mode="before")
    @classmethod
    def _v_conf(cls, v: Any) -> str:
        return _norm_confidence(v)

    @field_validator("drivers", mode="before")
    @classmethod
    def _v_drivers(cls, v: Any) -> list[str]:
        return _ensure_str_list(v)


class OutlookSignal(BaseModel):
    model_config = ConfigDict(extra="ignore")

    signal: str
    observation_object: str = ""
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    trigger_metrics: list[str] = Field(default_factory=list)
    reasoning: str = ""
    confidence: Literal["high", "medium", "low"] = "medium"
    what_to_monitor: list[str] = Field(default_factory=list)
    potential_trigger: str = ""
    alternative_explanation: str = ""
    alternative_scenario: str = ""
    uncertainty: str = ""
    needs_review: bool = False

    @field_validator("confidence", mode="before")
    @classmethod
    def _v_conf(cls, v: Any) -> str:
        return _norm_confidence(v)

    @field_validator("what_to_monitor", "trigger_metrics", mode="before")
    @classmethod
    def _v_mon(cls, v: Any) -> list[str]:
        return _ensure_str_list(v)


class NarrativeTaskOutput(BaseModel):
    """Unified structured analysis task output across Tasks A-F and Daily/Weekly/Monthly."""

    model_config = ConfigDict(extra="ignore")

    task_type: str
    report_type: Literal["daily", "weekly", "monthly"] = "daily"
    status: Literal["completed", "degraded", "needs_review", "failed", "insufficient_data"] = "completed"
    summary: str = ""
    findings: list[Finding] = Field(default_factory=list)
    important_changes: list[str] = Field(default_factory=list)
    main_drivers: list[str] = Field(default_factory=list)
    event_interpretations: list[EventInterpretation] = Field(default_factory=list)
    topic_trends: list[TopicTrendItem] = Field(default_factory=list)
    cross_country: list[CrossCountryItem] = Field(default_factory=list)
    stance_analyses: list[StanceInterpretation] = Field(default_factory=list)
    outlook_signals: list[OutlookSignal] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "important_changes",
        "main_drivers",
        "uncertainties",
        "follow_up_questions",
        mode="before",
    )
    @classmethod
    def _v_lists(cls, v: Any) -> list[str]:
        return _ensure_str_list(v)

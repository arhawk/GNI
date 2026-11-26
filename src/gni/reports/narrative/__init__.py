"""Canonical Assessment Engine, Evidence Preparation, and 3-Layer Validation for GNI reports."""

from gni.reports.narrative.assessment import (
    ASSESSMENT_TASK_SPECS,
    CANONICAL_ASSESSMENT_TASKS,
    AssessmentTaskSpec,
    effective_prompt_version,
    get_assessment_task_spec,
    resolve_task_type,
    run_assessment_suite,
    run_assessment_task,
)
from gni.reports.narrative.assessment_validator import (
    EvidenceRef,
    EventInterpretation,
    Finding,
    NarrativeTaskOutput,
    OutlookSignal,
    TopicTrendItem,
    validate_task_output,
)
from gni.reports.narrative.evidence import (
    EvidenceBundle,
    curate_finding_evidence,
    prepare_evidence_bundle,
)
from gni.reports.narrative.llm_client import JsonLLMClient

__all__ = [
    "ASSESSMENT_TASK_SPECS",
    "AssessmentTaskSpec",
    "CANONICAL_ASSESSMENT_TASKS",
    "EvidenceBundle",
    "EvidenceRef",
    "EventInterpretation",
    "Finding",
    "JsonLLMClient",
    "NarrativeTaskOutput",
    "OutlookSignal",
    "TopicTrendItem",
    "curate_finding_evidence",
    "effective_prompt_version",
    "get_assessment_task_spec",
    "prepare_evidence_bundle",
    "resolve_task_type",
    "run_assessment_suite",
    "run_assessment_task",
    "validate_task_output",
]

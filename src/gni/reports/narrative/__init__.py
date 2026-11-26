"""LLM Intelligence Narrative Layer for GNI Daily / Weekly / Monthly reports."""

from gni.reports.narrative.evidence import EvidenceBundle, prepare_evidence_bundle
from gni.reports.narrative.prompts import (
    REPORT_TASK_ORDER,
    TaskPromptSpec,
    get_task_prompt_spec,
    list_report_tasks,
)
from gni.reports.narrative.runner import (
    load_cached_intelligence,
    run_report_intelligence,
)
from gni.reports.narrative.schemas import (
    EvidenceRef,
    EventInterpretation,
    Finding,
    NarrativeTaskOutput,
    OutlookSignal,
    TopicTrendItem,
)
from gni.reports.narrative.validator import validate_task_output

__all__ = [
    "EvidenceBundle",
    "EvidenceRef",
    "EventInterpretation",
    "Finding",
    "NarrativeTaskOutput",
    "OutlookSignal",
    "REPORT_TASK_ORDER",
    "TaskPromptSpec",
    "TopicTrendItem",
    "get_task_prompt_spec",
    "list_report_tasks",
    "load_cached_intelligence",
    "prepare_evidence_bundle",
    "run_report_intelligence",
    "validate_task_output",
]

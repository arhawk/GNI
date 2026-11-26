"""Shared API router utilities: time windows, article intelligence projection, assessment lookup."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from gni.analysis.stance_util import (
    extract_v1_china_stance,
    extract_v1_stance_evidence,
    extract_v1_topics,
)
from gni.dashboard.data import article_data_range
from gni.infrastructure.models import Article, ArticleAnalysis, ReportNarrativeTask, Source
from gni.metrics.definitions import UNCLASSIFIED_LABEL
from gni.core.contracts import AssessmentResultContract
from gni.reports.narrative.assessment import (
    CANONICAL_ASSESSMENT_TASKS,
    get_assessment_task_spec,
)


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"invalid datetime: {value}") from e


def as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def resolve_window(
    session: Session,
    *,
    days: int = 30,
    start: str | None = None,
    end: str | None = None,
) -> tuple[datetime, datetime]:
    start_dt = parse_iso(start)
    end_dt = parse_iso(end)
    if start_dt and end_dt:
        if start_dt >= end_dt:
            raise HTTPException(status_code=400, detail="start must be earlier than end")
        return start_dt, end_dt
    if end_dt is None:
        _, data_max = article_data_range(session)
        end_dt = as_utc(data_max) or datetime.now(timezone.utc)
        # Include articles at exact data_max since v1_stats uses [start, end)
        end_dt = end_dt + timedelta(seconds=1)
    if start_dt is None:
        start_dt = end_dt - timedelta(days=max(1, days))
    return start_dt, end_dt


def extract_expression_owner(structured: dict[str, Any]) -> str:
    intel = structured.get("article_intelligence")
    if isinstance(intel, dict):
        stance_obj = intel.get("china_stance")
        if isinstance(stance_obj, dict) and stance_obj.get("expression_owner"):
            return str(stance_obj["expression_owner"])
    cs = structured.get("china_stance")
    if isinstance(cs, dict) and cs.get("expression_owner"):
        return str(cs["expression_owner"])
    return "unknown"


def extract_sentiment_label(structured: dict[str, Any]) -> str:
    intel = structured.get("article_intelligence")
    if isinstance(intel, dict):
        sent = intel.get("sentiment")
        if isinstance(sent, dict) and sent.get("label"):
            return str(sent["label"]).lower()
    sent = structured.get("sentiment")
    if isinstance(sent, dict) and sent.get("label"):
        return str(sent["label"]).lower()
    if isinstance(sent, str) and sent.strip():
        return sent.strip().lower()
    return "unknown"


def extract_verified_evidence(
    article: Article,
    source: Source | None,
    analysis: ArticleAnalysis | None,
) -> list[dict[str, Any]]:
    structured = (analysis.structured_result if analysis else None) or {}
    schema_ver = analysis.schema_version if analysis else None
    intel = structured.get("article_intelligence") if isinstance(structured.get("article_intelligence"), dict) else {}
    out: list[dict[str, Any]] = []
    if isinstance(intel.get("evidence"), list):
        for idx, ev in enumerate(intel["evidence"]):
            if not isinstance(ev, dict):
                continue
            span = str(ev.get("text_span") or ev.get("quote") or "").strip()
            if not span:
                continue
            out.append(
                {
                    "evidence_id": str(ev.get("evidence_id") or f"ev:{article.id}:{idx}"),
                    "article_id": article.id,
                    "article_version_id": ev.get("article_version_id") or intel.get("article_version_id"),
                    "text_span": span,
                    "start_offset": ev.get("start_offset"),
                    "end_offset": ev.get("end_offset"),
                    "validated": bool(ev.get("validated", False)),
                    "source_field": ev.get("source_field") or "body",
                    "analysis_task": ev.get("analysis_task") or "china_stance",
                    "expression_owner": ev.get("expression_owner") or extract_expression_owner(structured),
                    "source_name": source.name if source else article.source_id,
                    "source_country": source.country_id if source else None,
                    "published_at": article.published_at.isoformat() if article.published_at else None,
                }
            )
    if not out:
        for idx, ev in enumerate(extract_v1_stance_evidence(structured, schema_version=schema_ver)):
            span = str(ev.get("quote") or ev.get("span_text") or "").strip()
            if not span:
                continue
            out.append(
                {
                    "evidence_id": f"ev:{article.id}:stance:{idx}",
                    "article_id": article.id,
                    "article_version_id": None,
                    "text_span": span,
                    "start_offset": ev.get("start_offset"),
                    "end_offset": ev.get("end_offset"),
                    "validated": False,
                    "source_field": "stance_evidence",
                    "analysis_task": "china_stance",
                    "expression_owner": extract_expression_owner(structured),
                    "source_name": source.name if source else article.source_id,
                    "source_country": source.country_id if source else None,
                    "published_at": article.published_at.isoformat() if article.published_at else None,
                }
            )
    return out


def extract_article_narratives(structured: dict[str, Any]) -> list[dict[str, Any]]:
    intel = structured.get("article_intelligence")
    raw = None
    if isinstance(intel, dict) and isinstance(intel.get("narratives"), list):
        raw = intel["narratives"]
    elif isinstance(structured.get("narratives"), list):
        raw = structured["narratives"]
    if not raw:
        return []
    out: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, dict):
            label = str(item.get("label") or item.get("name") or item.get("claim") or "").strip()
            if label:
                out.append(
                    {
                        "label": label,
                        "frame": item.get("frame") or item.get("narrative_frame"),
                        "claim": item.get("claim") or item.get("summary") or label,
                    }
                )
        elif isinstance(item, str) and item.strip():
            out.append({"label": item.strip(), "frame": None, "claim": item.strip()})
    return out


def project_article_summary(
    article: Article,
    source: Source | None,
    analysis: ArticleAnalysis | None,
    *,
    event_ids: list[str] | None = None,
) -> dict[str, Any]:
    structured = (analysis.structured_result if analysis else None) or {}
    schema_ver = analysis.schema_version if analysis else None
    stance = extract_v1_china_stance(structured, schema_version=schema_ver)
    topics = extract_v1_topics(structured, schema_version=schema_ver)
    sentiment = extract_sentiment_label(structured)
    owner = extract_expression_owner(structured)
    ev = extract_verified_evidence(article, source, analysis)
    narratives = extract_article_narratives(structured)
    cs = structured.get("china_stance") if isinstance(structured.get("china_stance"), dict) else {}
    conf = cs.get("stance_confidence") if schema_ver in {"article_analysis_v1.0", "article_analysis_v1.1"} else None
    return {
        "article_id": article.id,
        "title": article.title,
        "url": article.url,
        "source_id": article.source_id,
        "source_name": source.name if source else article.source_id,
        "source_country": source.country_id if source else None,
        "published_at": article.published_at.isoformat() if article.published_at else None,
        "language": article.language,
        "china_relevance_level": article.china_relevance_level,
        "sentiment_label": sentiment,
        "stance_label": stance or UNCLASSIFIED_LABEL,
        "stance_target": "china_mainland",
        "stance_confidence": conf if isinstance(conf, (int, float)) else None,
        "expression_owner": owner,
        "topics_v1": topics,
        "narratives": narratives,
        "event_ids": event_ids or [],
        "evidence_count": len(ev),
        "evidence_preview": ev[:2],
        "analysis_schema_version": schema_ver,
    }


def load_cached_assessments(
    session: Session,
    *,
    report_type: str = "daily",
    period: str | None = None,
) -> dict[str, dict[str, Any]]:
    """Return latest cached AssessmentResultContract dicts keyed by canonical task_type."""
    stmt = (
        select(ReportNarrativeTask)
        .where(ReportNarrativeTask.report_type == report_type)
        .order_by(desc(ReportNarrativeTask.updated_at))
    )
    if period:
        stmt = stmt.where(ReportNarrativeTask.period == period)
    rows = list(session.scalars(stmt).all())
    by_task: dict[str, dict[str, Any]] = {}
    for row in rows:
        try:
            spec = get_assessment_task_spec(row.task_type)
            canonical = spec.task_type
        except KeyError:
            canonical = row.task_type
        if canonical in by_task:
            continue
        vo = row.validated_output if isinstance(row.validated_output, dict) else {}
        vr = row.validation_result if isinstance(row.validation_result, dict) else {}
        if vo.get("task_type") and isinstance(vo.get("observations"), list):
            by_task[canonical] = vo
        else:
            findings = vo.get("findings") if isinstance(vo.get("findings"), list) else []
            obs = [f for f in findings if isinstance(f, dict) and f.get("classification") == "Fact"]
            interps = [f for f in findings if isinstance(f, dict) and f.get("classification") == "Inference"]
            hyps = [
                f
                for f in findings
                if isinstance(f, dict) and f.get("classification") in {"Hypothesis", "Outlook"}
            ]
            ev_refs: list[dict[str, Any]] = []
            for f in findings:
                if isinstance(f, dict) and isinstance(f.get("evidence_refs"), list):
                    ev_refs.extend(r for r in f["evidence_refs"] if isinstance(r, dict))
            res = AssessmentResultContract(
                task_type=canonical,
                executive_summary=str(vo.get("summary") or vo.get("executive_summary") or ""),
                key_findings=[f for f in findings if isinstance(f, dict)],
                observations=obs,
                interpretations=interps,
                hypotheses=hyps,
                evidence_refs=ev_refs,
                limitations=[str(x) for x in (vo.get("limitations") or []) if str(x).strip()],
                watch_items=list(vo.get("watch_items") or []),
                details={k: v for k, v in vo.items() if k not in {"summary", "findings", "limitations", "watch_items"}},
                status=row.status or "completed",
                validation_result=vr,
                metadata={
                    "report_type": row.report_type,
                    "period": row.period,
                    "prompt_version": row.prompt_version,
                    "model_version": row.model_version,
                    "provider": row.provider,
                    "cached_at": row.updated_at.isoformat() if row.updated_at else None,
                },
            )
            by_task[canonical] = res.model_dump(mode="json")
    return by_task


def list_canonical_assessment_names() -> list[str]:
    return list(CANONICAL_ASSESSMENT_TASKS)

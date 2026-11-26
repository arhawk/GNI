"""Sentiment & Stance (strictly separated) and Conditional Outlook & Watchlist endpoints."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Query
from sqlalchemy import select

from gni.api.routers.common import (
    as_utc,
    extract_expression_owner,
    extract_sentiment_label,
    load_cached_assessments,
    project_article_summary,
    resolve_window,
)
from gni.analysis.stance_util import extract_v1_china_stance
from gni.infrastructure.db import session_scope
from gni.infrastructure.models import Article, Source
from gni.metrics.definitions import (
    METHODOLOGY_VERSION,
    TAXONOMY_V1_VERSION,
    UNCLASSIFIED_LABEL,
)
from gni.metrics.service import _latest_analyses, run_v1_stat_snapshots
from gni.reports.daily import build_daily_report

router = APIRouter(tags=["sentiment-stance", "outlook"])


@router.get("/api/sentiment-stance")
def api_sentiment_stance(
    days: int = Query(30, ge=1, le=365),
    start: str | None = Query(None),
    end: str | None = Query(None),
) -> dict[str, Any]:
    """Strictly separate Sentiment vs China Stance (target=china_mainland) across Global/Country/Source/Topic/History."""
    with session_scope() as session:
        p_start, p_end = resolve_window(session, days=days, start=start, end=end)
        v1 = run_v1_stat_snapshots(
            session,
            period_start=p_start,
            period_end=p_end,
            persist=False,
            include_source_scope=True,
        )
        by_scope = v1.get("by_scope") or {}
        global_row = by_scope.get("global") or {}
        article_ids = list(global_row.get("article_ids") or [])

        articles = (
            list(session.scalars(select(Article).where(Article.id.in_(article_ids))).all())
            if article_ids
            else []
        )
        sources = {s.id: s for s in session.scalars(select(Source)).all()}
        analyses = _latest_analyses(session, [a.id for a in articles])

        sent_overall: Counter[str] = Counter()
        sent_by_country: dict[str, Counter[str]] = defaultdict(Counter)
        sent_by_source: dict[str, Counter[str]] = defaultdict(Counter)
        owner_counts: Counter[str] = Counter()
        history_by_day: dict[str, dict[str, int]] = defaultdict(
            lambda: {
                "article_count": 0,
                "sentiment_positive": 0,
                "sentiment_neutral": 0,
                "sentiment_negative": 0,
                "sentiment_unknown": 0,
                "stance_positive": 0,
                "stance_neutral": 0,
                "stance_negative": 0,
                "stance_unclassified": 0,
            }
        )

        for a in articles:
            ana = analyses.get(a.id)
            structured = (ana.structured_result if ana else None) or {}
            schema_ver = ana.schema_version if ana else None
            sent = extract_sentiment_label(structured)
            stance = extract_v1_china_stance(structured, schema_version=schema_ver) or UNCLASSIFIED_LABEL
            owner = extract_expression_owner(structured)
            src = sources.get(a.source_id)
            cid = src.country_id if src and src.country_id else "UNKNOWN"
            sname = src.name if src else a.source_id

            sent_overall[sent] += 1
            sent_by_country[cid][sent] += 1
            sent_by_source[sname][sent] += 1
            owner_counts[owner] += 1

            dt = as_utc(a.published_at)
            if dt:
                day_key = dt.strftime("%Y-%m-%d")
                bucket = history_by_day[day_key]
                bucket["article_count"] += 1
                if sent in {"positive", "neutral", "negative"}:
                    bucket[f"sentiment_{sent}"] += 1
                else:
                    bucket["sentiment_unknown"] += 1
                if stance == "Positive":
                    bucket["stance_positive"] += 1
                elif stance == "Neutral":
                    bucket["stance_neutral"] += 1
                elif stance == "Negative":
                    bucket["stance_negative"] += 1
                else:
                    bucket["stance_unclassified"] += 1

        articles_sorted = sorted(
            articles,
            key=lambda x: as_utc(x.published_at) or (p_start - timedelta(days=1)),
            reverse=True,
        )
        rep_articles = [
            project_article_summary(a, sources.get(a.source_id), analyses.get(a.id))
            for a in articles_sorted[:20]
        ]

        cached = load_cached_assessments(session, report_type="daily")
        return {
            "meta": {
                "period_start": p_start.isoformat(),
                "period_end": p_end.isoformat(),
                "days": days,
                "methodology_version": METHODOLOGY_VERSION,
                "taxonomy_version": TAXONOMY_V1_VERSION,
                "stance_target": "china_mainland",
                "rules": [
                    "Sentiment（情感表达）与 Stance（对华立场，target=china_mainland）严格分开统计与展示。",
                    "Unclassified 保留在文章总量中，但不进入 Positive/Neutral/Negative 比例分母。",
                    "Stance Coverage Rate = (Positive + Neutral + Negative) / Unique Article Count。",
                    "媒体自身立场 (media) 与引用对象立场 (quoted_actor) 区分标注。",
                ],
            },
            "sentiment": {
                "overall_counts": dict(sent_overall),
                "by_country": [
                    {"country_id": cid, "counts": dict(cnt), "total": sum(cnt.values())}
                    for cid, cnt in sorted(sent_by_country.items(), key=lambda x: -sum(x[1].values()))
                ],
                "by_source": [
                    {"source_name": sname, "counts": dict(cnt), "total": sum(cnt.values())}
                    for sname, cnt in sorted(sent_by_source.items(), key=lambda x: -sum(x[1].values()))[:15]
                ],
            },
            "stance": {
                "target": "china_mainland",
                "global": global_row,
                "by_country": by_scope.get("countries") or [],
                "by_source": by_scope.get("sources") or [],
                "by_topic": by_scope.get("topics") or [],
                "expression_owner_counts": dict(owner_counts),
            },
            "history": [
                {"date": d, **history_by_day[d]} for d in sorted(history_by_day.keys())
            ],
            "representative_articles": rep_articles,
            "assessment": cached.get("sentiment_stance_analysis"),
        }


@router.get("/api/outlook")
def api_outlook(
    date: str | None = Query(None, description="Optional YYYY-MM-DD in Asia/Shanghai"),
) -> dict[str, Any]:
    """Conditional Outlook & Watchlist strictly separating Fact / Trend / Conditional Inference / Hypothesis."""
    with session_scope() as session:
        daily = build_daily_report(session, day=date, analyze=False)
        period = daily.get("period")
        cached = load_cached_assessments(session, report_type="daily", period=period)
        outlook = cached.get("outlook_assessment") or load_cached_assessments(session, report_type="daily").get("outlook_assessment")
        pkg = daily.get("report_package") or {}
        ch6 = next(
            (s for s in (pkg.get("sections") or []) if s.get("section_id") == "chapter_6_outlook_watchlist"),
            None,
        )

        items: list[dict[str, Any]] = []
        if outlook:
            details = outlook.get("details") if isinstance(outlook.get("details"), dict) else {}
            raw_list = details.get("watchlist") or details.get("outlook_items") or outlook.get("watch_items") or []
            for idx, item in enumerate(raw_list):
                if isinstance(item, dict):
                    items.append(
                        {
                            "id": f"outlook:{idx}",
                            "observation_object": item.get("observation_object") or item.get("title") or item.get("item") or "观察项",
                            "current_evidence": item.get("current_evidence") or item.get("summary") or "",
                            "possible_development": item.get("possible_development") or item.get("conditional_development") or "",
                            "trigger_condition": item.get("trigger_condition") or item.get("potential_trigger") or "",
                            "alternative_scenario": item.get("alternative_scenario") or "",
                            "uncertainty": item.get("uncertainty") or "待进一步证据验证",
                            "classification": item.get("classification") or "Outlook",
                            "related_events": item.get("related_events") or [],
                            "related_topics": item.get("related_topics") or [],
                            "evidence_refs": item.get("evidence_refs") or [],
                        }
                    )
                elif isinstance(item, str) and item.strip():
                    items.append(
                        {
                            "id": f"outlook:{idx}",
                            "observation_object": item.strip(),
                            "current_evidence": "",
                            "possible_development": "",
                            "trigger_condition": "",
                            "alternative_scenario": "",
                            "uncertainty": "条件性观察项，非确定性预测",
                            "classification": "Outlook",
                            "related_events": [],
                            "related_topics": [],
                            "evidence_refs": [],
                        }
                    )

        return {
            "meta": {
                "period": period,
                "status": (outlook or {}).get("status") or (ch6 or {}).get("status") or "not_run",
                "disclaimer": (
                    "所有展望均为基于当前证据的条件性情景与观察清单，不是确定性预测；"
                    "请严格区分已发生事实 (Fact)、当前趋势 (Trend)、条件性推断 (Inference) 与未验证假设 (Hypothesis)。"
                ),
            },
            "executive_summary": (outlook or {}).get("executive_summary") or (ch6 or {}).get("summary") or "",
            "observations": (outlook or {}).get("observations") or [],
            "interpretations": (outlook or {}).get("interpretations") or [],
            "hypotheses": (outlook or {}).get("hypotheses") or [],
            "watchlist": items,
            "evidence_refs": (outlook or {}).get("evidence_refs") or (ch6 or {}).get("evidence_refs") or [],
            "limitations": (outlook or {}).get("limitations") or pkg.get("limitations") or [],
        }

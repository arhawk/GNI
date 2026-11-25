"""Rule-based alert generators: intelligence (A) vs system (B)."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from gni.infrastructure.models import (
    AnalysisRun,
    Article,
    Event,
    EventArticle,
    Source,
    SourceHealth,
)
from gni.metrics.definitions import CHINA_INCLUDE_LEVELS
from gni.metrics.service import _latest_analyses

MAJOR_KEYWORDS = (
    "sanction",
    "sanctions",
    "tariff",
    "embargo",
    "military",
    "missile",
    "blockade",
    "export control",
    "entity list",
    "制裁",
    "关税",
    "军演",
)


@lru_cache(maxsize=1)
def _thresholds() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[3] / "configs" / "alert_thresholds.yaml"
    if path.exists():
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(t: datetime | None) -> datetime | None:
    if t is None:
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def _article_time(a: Article) -> datetime | None:
    return _aware(a.published_at or a.first_seen_at)


def _alert(
    *,
    category: str,
    subcategory: str,
    severity: str,
    title: str,
    summary: str,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": str(uuid4()),
        "category": category,  # intelligence | system
        "subcategory": subcategory,
        "severity": severity,  # high | medium | low
        "title": title,
        "summary": summary,
        "detected_at": _now().isoformat(),
        "evidence": evidence or {},
    }


def _china_articles(session: Session) -> list[Article]:
    return list(
        session.scalars(
            select(Article).where(
                Article.exclude_from_metrics.is_(False),
                Article.china_relevance_level.in_(list(CHINA_INCLUDE_LEVELS)),
            )
        ).all()
    )


def generate_intelligence_alerts(session: Session) -> list[dict[str, Any]]:
    th = _thresholds()
    now = _now()
    sources = {s.id: s for s in session.scalars(select(Source)).all()}
    articles = _china_articles(session)
    out: list[dict[str, Any]] = []

    # 1. Volume spike by country
    vs = th.get("volume_spike") or {}
    recent_h = int(vs.get("recent_hours", 24))
    base_d = int(vs.get("baseline_days", 7))
    min_n = int(vs.get("min_recent_count", 3))
    growth = float(vs.get("growth_ratio", 2.0))
    recent_start = now - timedelta(hours=recent_h)
    base_start = now - timedelta(days=base_d) - timedelta(hours=recent_h)
    base_end = recent_start

    recent_by: Counter[str] = Counter()
    base_by: Counter[str] = Counter()
    for a in articles:
        t = _article_time(a)
        if not t:
            continue
        cid = (sources.get(a.source_id).country_id if a.source_id in sources else None) or "UNK"
        if t >= recent_start:
            recent_by[cid] += 1
        elif base_start <= t < base_end:
            base_by[cid] += 1

    for cid, n in recent_by.items():
        if n < min_n:
            continue
        daily_mean = (base_by.get(cid, 0) / max(base_d, 1)) or 0.5
        if daily_mean <= 0:
            daily_mean = 0.5
        ratio = n / daily_mean
        if ratio >= (1 + growth) or (daily_mean < 1 and n >= min_n * 2):
            out.append(
                _alert(
                    category="intelligence",
                    subcategory="volume_spike",
                    severity="high" if ratio >= 4 else "medium",
                    title=f"{cid} 对华报道量异常升高",
                    summary=f"近 {recent_h}h 涉华 {n} 篇，约为基线日均 {daily_mean:.1f} 的 {ratio:.1f} 倍。",
                    evidence={"country_id": cid, "recent": n, "baseline_daily_mean": round(daily_mean, 2), "ratio": round(ratio, 2)},
                )
            )

    # 2. Sentiment shift + Stance shift (separate; never mix into one "negative" rate)
    from gni.analysis.stance_util import all_stance_labels, sentiment_label

    att = th.get("attitude_shift") or {}
    rh = int(att.get("recent_hours", 48))
    bd = int(att.get("baseline_days", 7))
    min_s = int(att.get("min_sample", 3))
    rise = float(att.get("negative_share_rise", 0.25))
    r0 = now - timedelta(hours=rh)
    b0 = now - timedelta(days=bd) - timedelta(hours=rh)
    analyses = _latest_analyses(session, [a.id for a in articles])

    def sentiment_neg_share(rows: list[Article]) -> tuple[float, int]:
        neg = 0
        n = 0
        for a in rows:
            if a.id not in analyses:
                continue
            structured = analyses[a.id].structured_result or {}
            n += 1
            if sentiment_label(structured) == "negative":
                neg += 1
        return (neg / n if n else 0.0), n

    def critical_stance_share(rows: list[Article]) -> tuple[float, int]:
        """Media stance only; opposing/critical/oppose toward any target."""
        hit = 0
        n = 0
        for a in rows:
            if a.id not in analyses:
                continue
            structured = analyses[a.id].structured_result or {}
            labels = all_stance_labels(structured, media_only=True)
            if not labels:
                continue
            n += 1
            if any(k in {"critical", "opposing", "oppose", "negative"} for k in labels):
                hit += 1
        return (hit / n if n else 0.0), n

    by_c_recent: dict[str, list[Article]] = defaultdict(list)
    by_c_base: dict[str, list[Article]] = defaultdict(list)
    for a in articles:
        t = _article_time(a)
        if not t:
            continue
        cid = (sources.get(a.source_id).country_id if a.source_id in sources else None) or "UNK"
        if t >= r0:
            by_c_recent[cid].append(a)
        elif b0 <= t < r0:
            by_c_base[cid].append(a)

    for cid, rows in by_c_recent.items():
        share_r, n_r = sentiment_neg_share(rows)
        share_b, n_b = sentiment_neg_share(by_c_base.get(cid, []))
        if n_r >= min_s and share_r - share_b >= rise and share_r >= 0.35:
            out.append(
                _alert(
                    category="intelligence",
                    subcategory="sentiment_shift",
                    severity="high" if share_r >= 0.6 else "medium",
                    title=f"{cid} 对华报道情感负面占比上升",
                    summary=(
                        f"近窗情感 negative 占比 {share_r:.0%}（n={n_r}），"
                        f"基线 {share_b:.0%}（n={n_b}）。未混入立场标签。"
                    ),
                    evidence={
                        "country_id": cid,
                        "recent_neg_sentiment_share": round(share_r, 3),
                        "baseline_neg_sentiment_share": round(share_b, 3),
                    },
                )
            )
        st_r, sn_r = critical_stance_share(rows)
        st_b, sn_b = critical_stance_share(by_c_base.get(cid, []))
        if sn_r >= min_s and st_r - st_b >= rise and st_r >= 0.35:
            out.append(
                _alert(
                    category="intelligence",
                    subcategory="stance_shift",
                    severity="high" if st_r >= 0.6 else "medium",
                    title=f"{cid} 对华相关立场批判/反对占比上升",
                    summary=(
                        f"近窗媒体自身批判/反对立场占比 {st_r:.0%}（n={sn_r}），"
                        f"基线 {st_b:.0%}（n={sn_b}）。按 Target 聚合，不含引述观点。"
                    ),
                    evidence={
                        "country_id": cid,
                        "recent_critical_stance_share": round(st_r, 3),
                        "baseline_critical_stance_share": round(st_b, 3),
                    },
                )
            )

    # 3. Narrative / topic-frame shift
    ns = th.get("narrative_shift") or {}
    nrh = int(ns.get("recent_hours", 48))
    nbd = int(ns.get("baseline_days", 7))
    nmin = int(ns.get("min_count", 3))
    srise = float(ns.get("share_rise", 0.2))
    nr0 = now - timedelta(hours=nrh)
    nb0 = now - timedelta(days=nbd) - timedelta(hours=nrh)

    def topic_frame_counts(rows: list[Article]) -> tuple[Counter[str], Counter[str]]:
        tc: Counter[str] = Counter()
        fc: Counter[str] = Counter()
        for a in rows:
            if a.id not in analyses:
                continue
            structured = analyses[a.id].structured_result or {}
            topics = structured.get("topics") or {}
            framing = structured.get("framing") or {}
            if isinstance(topics, dict) and topics.get("primary"):
                tc[str(topics["primary"])] += 1
            if isinstance(framing, dict) and framing.get("primary"):
                fc[str(framing["primary"])] += 1
        return tc, fc

    recent_rows = [a for a in articles if (t := _article_time(a)) and t >= nr0]
    base_rows = [a for a in articles if (t := _article_time(a)) and nb0 <= t < nr0]
    rtc, rfc = topic_frame_counts(recent_rows)
    btc, bfc = topic_frame_counts(base_rows)
    rt_total = sum(rtc.values()) or 1
    bt_total = sum(btc.values()) or 1
    for label, cnt in rtc.most_common(5):
        if cnt < nmin:
            continue
        share_r = cnt / rt_total
        share_b = btc.get(label, 0) / bt_total
        if share_r - share_b >= srise:
            out.append(
                _alert(
                    category="intelligence",
                    subcategory="narrative_shift",
                    severity="medium",
                    title=f"议题「{label}」占比上升",
                    summary=f"近窗占比 {share_r:.0%}（{cnt}），基线 {share_b:.0%}。",
                    evidence={"topic": label, "recent_share": round(share_r, 3), "baseline_share": round(share_b, 3)},
                )
            )
    rf_total = sum(rfc.values()) or 1
    bf_total = sum(bfc.values()) or 1
    for label, cnt in rfc.most_common(3):
        if cnt < nmin:
            continue
        share_r = cnt / rf_total
        share_b = bfc.get(label, 0) / bf_total
        if share_r - share_b >= srise:
            out.append(
                _alert(
                    category="intelligence",
                    subcategory="narrative_shift",
                    severity="medium",
                    title=f"叙事框架「{label}」强化",
                    summary=f"近窗框架占比 {share_r:.0%}（{cnt}），基线 {share_b:.0%}。",
                    evidence={"frame": label, "recent_share": round(share_r, 3)},
                )
            )

    # 4. Major events
    me = th.get("major_event") or {}
    min_imp = float(me.get("min_importance", 0.7))
    min_arts = int(me.get("min_articles", 2))
    events = list(session.scalars(select(Event).order_by(Event.importance_score.desc()).limit(40)).all())
    for e in events:
        art_n = session.scalar(
            select(func.count()).select_from(EventArticle).where(EventArticle.event_id == e.id)
        ) or 0
        title_l = (e.title or "").lower()
        kw = any(k in title_l for k in MAJOR_KEYWORDS) if me.get("keyword_boost", True) else False
        score = e.importance_score or 0
        if score >= min_imp or (kw and art_n >= min_arts) or art_n >= max(min_arts, 3):
            out.append(
                _alert(
                    category="intelligence",
                    subcategory="major_event",
                    severity="high" if score >= 0.8 or kw else "medium",
                    title=f"重大涉华事件候选：{(e.title or '')[:80]}",
                    summary=f"importance={score} · 关联文章 {art_n}" + (" · 关键词命中" if kw else ""),
                    evidence={"event_id": e.id, "article_count": art_n, "importance": score},
                )
            )

    # 5. Transnational diffusion
    tn = th.get("transnational") or {}
    min_c = int(tn.get("min_countries", 3))
    for e in events[:30]:
        links = list(session.scalars(select(EventArticle).where(EventArticle.event_id == e.id)).all())
        cids: set[str] = set()
        for link in links:
            art = session.get(Article, link.article_id)
            if not art:
                continue
            src = sources.get(art.source_id)
            if src and src.country_id:
                cids.add(src.country_id)
        if len(cids) >= min_c:
            out.append(
                _alert(
                    category="intelligence",
                    subcategory="transnational",
                    severity="high" if len(cids) >= 4 else "medium",
                    title=f"跨国扩散：{(e.title or '')[:70]}",
                    summary=f"同一事件在 {len(cids)} 个监测国出现：{', '.join(sorted(cids))}",
                    evidence={"event_id": e.id, "countries": sorted(cids)},
                )
            )

    return out


def generate_system_alerts(session: Session) -> list[dict[str, Any]]:
    th = _thresholds()
    now = _now()
    out: list[dict[str, Any]] = []
    sources = list(session.scalars(select(Source).where(Source.active_status == "active")).all())
    health = {h.source_id: h for h in session.scalars(select(SourceHealth)).all()}

    sf = th.get("source_failure") or {}
    min_fail = int(sf.get("min_failures", 2))
    fail_rate = float(sf.get("failure_rate", 0.5))
    for s in sources:
        h = health.get(s.id)
        if not h:
            continue
        total = (h.success_count or 0) + (h.failure_count or 0)
        rate = (h.failure_count or 0) / total if total else 0
        if (h.failure_count or 0) >= min_fail and rate >= fail_rate:
            out.append(
                _alert(
                    category="system",
                    subcategory="source_failure",
                    severity="high" if rate >= 0.8 else "medium",
                    title=f"数据源故障：{s.id}",
                    summary=f"失败 {h.failure_count} / 成功 {h.success_count}（失败率 {rate:.0%}）。{h.error_message or ''}",
                    evidence={"source_id": s.id, "country_id": s.country_id},
                )
            )

    stall_h = int(th.get("collection_stall_hours", 36))
    cutoff = now - timedelta(hours=stall_h)
    for s in sources:
        last = session.scalar(
            select(func.max(Article.first_seen_at)).where(Article.source_id == s.id)
        )
        last_a = _aware(last)
        if last_a is None or last_a < cutoff:
            out.append(
                _alert(
                    category="system",
                    subcategory="collection_stall",
                    severity="medium",
                    title=f"采集停滞：{s.id}",
                    summary=f"超过 {stall_h}h 无新文章（last={last_a.isoformat() if last_a else 'never'}）。",
                    evidence={"source_id": s.id, "country_id": s.country_id},
                )
            )

    backlog = int(th.get("analysis_backlog", 50))
    pending = session.scalar(
        select(func.count())
        .select_from(Article)
        .where(
            Article.exclude_from_metrics.is_(False),
            Article.processing_status == "done",
            Article.analysis_status.in_(["pending", "failed"]),
        )
    ) or 0
    if pending >= backlog:
        out.append(
            _alert(
                category="system",
                subcategory="analysis_backlog",
                severity="high" if pending >= backlog * 2 else "medium",
                title="分析积压过高",
                summary=f"待分析/失败文章约 {pending} 篇（阈值 {backlog}）。",
                evidence={"pending_or_failed": pending},
            )
        )

    model_min = int(th.get("model_fail_min", 5))
    failed_arts = session.scalar(
        select(func.count())
        .select_from(Article)
        .where(Article.analysis_status == "failed")
    ) or 0
    failed_runs = session.scalar(
        select(func.count())
        .select_from(AnalysisRun)
        .where(AnalysisRun.status.in_(["failed", "partial"]))
    ) or 0
    if failed_arts >= model_min or failed_runs >= model_min:
        out.append(
            _alert(
                category="system",
                subcategory="model_failure",
                severity="medium",
                title="分析/模型异常偏多",
                summary=f"analysis_status=failed 文章 {failed_arts}；异常 analysis_run {failed_runs}。",
                evidence={"failed_articles": failed_arts, "failed_runs": failed_runs},
            )
        )

    qrate = float(th.get("quality_exclude_rate", 0.35))
    total_a = session.scalar(select(func.count()).select_from(Article)) or 0
    excluded = session.scalar(
        select(func.count()).select_from(Article).where(Article.exclude_from_metrics.is_(True))
    ) or 0
    if total_a >= 20 and excluded / total_a >= qrate:
        out.append(
            _alert(
                category="system",
                subcategory="data_quality",
                severity="low",
                title="排除/重复比例偏高",
                summary=f"exclude_from_metrics={excluded}/{total_a}（{excluded / total_a:.0%}）。",
                evidence={"excluded": excluded, "total": total_a},
            )
        )

    return out

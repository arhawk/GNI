"""3-Layer Report Narrative Validator (Numeric / Evidence / Reasoning).

Enforces GNI Section 8 rules:
- 8.1 Numeric Validation: reject/downgrade statistics not present in deterministic EvidenceBundle.
- 8.2 Evidence Validation: verify every article_id, event_id, metric_ref_id, alert_id, and URL
      against DB-backed EvidenceBundle; Facts must have >= 1 valid evidence ref.
- 8.3 Reasoning Validation: catch forbidden conflations (volume=stance, media=official stance,
      quoted speaker=media stance, event_time=published_at, causation overclaim, Hypothesis as Fact,
      low-sample overconfidence).

On violation, never fabricates content — downgrades, drops ungrounded items, or marks needs_review.
"""

from __future__ import annotations

import re
from typing import Any

from gni.reports.narrative.evidence import EvidenceBundle, MIN_RELIABLE_SAMPLE_N
from gni.reports.narrative.schemas import EvidenceRef, NarrativeTaskOutput

# Numeric token pattern: captures numbers & percentages (skips pure 4-digit years 2020-2035)
_NUM_RE = re.compile(r"(?<![A-Za-z0-9_/-])(\d+(?:\.\d+)?)(%)?")

# 8.3 Reasoning rule patterns: (code, compiled_regex, severity, explanation)
_REASONING_RULES: list[tuple[str, re.Pattern[str], str, str]] = [
    (
        "composite_score_claim",
        re.compile(r"(对华总分|综合舆情指数|对华总评分|综合情感分)"),
        "drop",
        "禁止输出未经验证的综合舆情评分或对华总分",
    ),
    (
        "media_as_official_stance",
        re.compile(
            r"(?<!并非)(?<!不是)(?<!不代表)(?<!非)(国家官方立场(?:已|是|转向)|代表(?:该国|全民)?民意|全民舆论(?:已|转向)|政府真实意图(?:是|为))"
        ),
        "downgrade",
        "不得将媒体样本表述为国家官方立场、政府真实意图或全民民意",
    ),
    (
        "volume_as_attitude",
        re.compile(
            r"(报道量(?:增长|上升|增加|激增)[^。；\n]{0,12}(?:说明|表明|意味着|等于)[^。；\n]{0,10}(?:立场|态度)(?:恶化|转负|变差))"
        ),
        "downgrade",
        "不得将报道量变化直接写成对华立场或态度恶化",
    ),
    (
        "quoted_as_media_stance",
        re.compile(r"(?:引述|受访者|被引用人物)(?:的)?观点(?:直接)?(?:代表|等同于|即)(?:该)?媒体立场"),
        "downgrade",
        "不得将被引用人物观点直接写成媒体自身立场",
    ),
    (
        "time_confusion",
        re.compile(r"(发布时间(?:即|等于)事件发生时间|首次发现(?:即|等于)当日新发生)"),
        "downgrade",
        "不得混淆事件发生时间、文章发布时间与首次发现时间",
    ),
    (
        "causation_overclaim",
        re.compile(r"(直接证明了?因果|必然导致|决定性地造成|毫无疑问地引发)"),
        "downgrade",
        "不得将相关性直接写成绝对因果关系",
    ),
]

_CERTAINTY_RE = re.compile(r"(必然发生|一定会|肯定将|已成定局|毫无疑问将)")
_CONDITIONAL_HINTS = ("若", "如果", "可能", "或", "待观察", "有待", "取决于", "需关注", "潜在", "假设")


def _is_allowed_number(num_str: str, is_pct: bool, allowed: set[str]) -> bool:
    if num_str in allowed:
        return True
    try:
        val = float(num_str)
    except ValueError:
        return True
    # Allow calendar years 2020-2035 or tiny integers 0-9 (unless explicitly a % rate)
    if not is_pct and (2020 <= val <= 2035 or (val.is_integer() and 0 <= val <= 9)):
        return True
    # Allow 1-decimal or integer rounded forms present in allowlist
    for candidate in (f"{val:.1f}", f"{val:.2f}", str(int(round(val)))):
        if candidate in allowed:
            return True
    if is_pct:
        # e.g. 25% when 0.25 or 25.0 is allowed
        ratio = val / 100.0
        for candidate in (f"{ratio:.2f}", f"{ratio:.4f}", f"{val:.1f}", str(int(round(val)))):
            if candidate in allowed:
                return True
    return False


def _find_ungrounded_numbers(text: str, allowed: set[str]) -> list[str]:
    if not text:
        return []
    # Mask ISO dates like 2026-11-26 and times 12:30 before scanning
    cleaned = re.sub(r"\b\d{4}-\d{1,2}-\d{1,2}(?:[T ]\d{2}:\d{2}(?::\d{2})?)?\b", " ", text)
    cleaned = re.sub(r"\bV\d+(?:\.\d+)?\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"近\s*[3467]\s*(?:日|天|周|个月|月)", " ", cleaned)
    cleaned = re.sub(r"\b(?:15|4)\s*(?:个)?(?:议题|大板块|板块)\b", " ", cleaned)
    bad: list[str] = []
    for m in _NUM_RE.finditer(cleaned):
        num_str, pct = m.group(1), bool(m.group(2))
        if not _is_allowed_number(num_str, pct, allowed):
            tok = f"{num_str}{'%' if pct else ''}"
            if tok not in bad:
                bad.append(tok)
    return bad


def _filter_evidence_refs(
    refs: list[EvidenceRef],
    bundle: EvidenceBundle,
    issues: list[str],
    context: str,
) -> list[EvidenceRef]:
    valid: list[EvidenceRef] = []
    seen: set[tuple[str, str]] = set()
    for ref in refs:
        rid = (ref.ref_id or "").strip()
        if not rid:
            issues.append(f"{context}: empty evidence ref_id removed")
            continue
        ok = False
        url = None
        eff_type = ref.type
        if eff_type == "article":
            if rid in bundle.allowed_article_ids:
                ok = True
                url = bundle.article_url_map.get(rid)
            elif rid in bundle.allowed_event_ids:
                # Bare UUID coerced as article that actually matches a valid DB event_id
                eff_type = "event"
                ok = True
            elif rid in bundle.allowed_alert_ids:
                eff_type = "alert"
                ok = True
        elif eff_type == "event":
            if rid in bundle.allowed_event_ids:
                ok = True
        elif eff_type == "metric":
            if rid in bundle.allowed_metric_ids:
                ok = True
        elif eff_type == "alert":
            if rid in bundle.allowed_alert_ids:
                ok = True

        if not ok:
            issues.append(f"{context}: invalid {ref.type} ref_id '{rid}' removed")
            continue

        # Never trust LLM-invented URLs
        if ref.url and ref.url not in bundle.allowed_urls:
            issues.append(f"{context}: unverified URL stripped on ref '{rid}'")

        key = (eff_type, rid)
        if key not in seen:
            seen.add(key)
            valid.append(
                EvidenceRef(
                    type=eff_type,
                    ref_id=rid,
                    label=ref.label or rid,
                    url=url,
                )
            )
    return valid


def _check_reasoning_text(text: str) -> list[tuple[str, str, str]]:
    hits: list[tuple[str, str, str]] = []
    if not text:
        return hits
    for code, pat, sev, msg in _REASONING_RULES:
        if pat.search(text):
            hits.append((code, sev, msg))
    return hits


def validate_task_output(
    output: NarrativeTaskOutput,
    bundle: EvidenceBundle,
) -> tuple[NarrativeTaskOutput, dict[str, Any]]:
    """Run 3-layer validation on a single task output. Mutates a copy and returns (validated, report)."""
    out = output.model_copy(deep=True)
    numeric_issues: list[str] = []
    evidence_issues: list[str] = []
    reasoning_issues: list[str] = []
    dropped_count = 0
    downgraded_count = 0

    low_global = bundle.global_article_count < MIN_RELIABLE_SAMPLE_N
    has_low_scopes = bool(bundle.low_sample_scopes)

    # Check top-level summary
    sum_bad_nums = _find_ungrounded_numbers(out.summary, bundle.allowed_numbers)
    if sum_bad_nums:
        numeric_issues.append(f"summary: ungrounded numbers {sum_bad_nums}")
    for code, sev, msg in _check_reasoning_text(out.summary):
        reasoning_issues.append(f"summary[{code}]: {msg}")
        if sev == "drop":
            out.summary = ""

    # 1. Validate findings
    kept_findings = []
    for idx, f in enumerate(out.findings):
        ctx = f"finding[{idx}]"
        f.evidence_refs = _filter_evidence_refs(f.evidence_refs, bundle, evidence_issues, ctx)

        blob = f"{f.title} {f.conclusion} {f.reasoning}"
        bad_nums = _find_ungrounded_numbers(blob, bundle.allowed_numbers)
        r_hits = _check_reasoning_text(blob)

        should_drop = any(sev == "drop" for _, sev, _ in r_hits)
        if should_drop:
            for code, _, msg in r_hits:
                reasoning_issues.append(f"{ctx}[{code}]: {msg} (dropped)")
            dropped_count += 1
            continue

        if bad_nums:
            numeric_issues.append(f"{ctx}: ungrounded numbers {bad_nums}")
            f.needs_review = True
            f.validation_notes.append(f"未在确定性统计中核验的数字: {', '.join(bad_nums)}")
            if len(bad_nums) >= 3 and not f.evidence_refs:
                dropped_count += 1
                out.uncertainties.append(f"已剔除未核验数字结论：{f.title}")
                continue
            if f.classification == "Fact":
                f.classification = "Inference"
                downgraded_count += 1

        if f.classification == "Fact" and not f.evidence_refs:
            evidence_issues.append(f"{ctx}: Fact missing valid evidence_refs -> downgraded to Hypothesis")
            f.classification = "Hypothesis"
            f.confidence = "low"
            f.needs_review = True
            f.validation_notes.append("缺少有效证据引用，已从 Fact 降级为 Hypothesis")
            downgraded_count += 1

        for code, _, msg in r_hits:
            reasoning_issues.append(f"{ctx}[{code}]: {msg}")
            f.needs_review = True
            f.validation_notes.append(msg)
            if f.classification == "Fact":
                f.classification = "Inference"
                downgraded_count += 1

        if f.classification == "Hypothesis" and _CERTAINTY_RE.search(f.conclusion):
            reasoning_issues.append(f"{ctx}[hypothesis_as_certainty]: Hypothesis uses absolute certainty phrasing")
            f.needs_review = True
            f.validation_notes.append("假设性结论使用了绝对化表述，已标记复核")

        if low_global and f.confidence == "high":
            f.confidence = "low"
            downgraded_count += 1
            if not any("样本" in lim for lim in f.limitations):
                f.limitations.append(f"当期全球样本量较小 (n={bundle.global_article_count})，结论强度已自动下调")
        elif has_low_scopes and f.confidence == "high" and not f.limitations:
            f.limitations.append("部分国家或议题存在低样本或低立场覆盖率限制")

        kept_findings.append(f)
    out.findings = kept_findings

    # 2. Validate event interpretations
    kept_events = []
    for idx, ev in enumerate(out.event_interpretations):
        ctx = f"event[{idx}:{ev.event_id}]"
        if ev.event_id not in bundle.allowed_event_ids:
            evidence_issues.append(f"{ctx}: unknown event_id '{ev.event_id}' dropped")
            dropped_count += 1
            continue
        ev.evidence_refs = _filter_evidence_refs(ev.evidence_refs, bundle, evidence_issues, ctx)
        if not any(r.type == "event" and r.ref_id == ev.event_id for r in ev.evidence_refs):
            ev.evidence_refs.insert(0, EvidenceRef(type="event", ref_id=ev.event_id, label=ev.title))
        blob = f"{ev.background} {ev.what_happened} {ev.event_actual_changes} {ev.coverage_attention_changes} {ev.why_it_matters}"
        bad_nums = _find_ungrounded_numbers(blob, bundle.allowed_numbers)
        if bad_nums:
            numeric_issues.append(f"{ctx}: ungrounded numbers {bad_nums}")
            ev.needs_review = True
        for code, _, msg in _check_reasoning_text(blob):
            reasoning_issues.append(f"{ctx}[{code}]: {msg}")
            ev.needs_review = True
        if low_global and ev.confidence == "high":
            ev.confidence = "medium"
            downgraded_count += 1
        kept_events.append(ev)
    out.event_interpretations = kept_events

    # 3. Validate topic trends
    for idx, t in enumerate(out.topic_trends):
        ctx = f"topic_trend[{idx}:{t.topic_id}]"
        t.evidence_refs = _filter_evidence_refs(t.evidence_refs, bundle, evidence_issues, ctx)
        blob = f"{t.attention_change} {t.stance_change} {t.topic_structure_change}"
        bad_nums = _find_ungrounded_numbers(blob, bundle.allowed_numbers)
        if bad_nums:
            numeric_issues.append(f"{ctx}: ungrounded numbers {bad_nums}")
            t.needs_review = True
        for code, _, msg in _check_reasoning_text(blob):
            reasoning_issues.append(f"{ctx}[{code}]: {msg}")
            t.needs_review = True
        # Honest history gate: if monthly/weekly history is thin, don't claim "ongoing" without data
        months_n = bundle.historical.get("months_with_data")
        weeks_n = bundle.historical.get("weeks_with_data")
        if t.persistence == "ongoing" and (
            (isinstance(months_n, int) and months_n < 2)
            or (isinstance(weeks_n, int) and weeks_n < 2)
        ):
            t.persistence = "insufficient_history"
            t.limitations.append("历史周期样本不足，已降级为 insufficient_history")
            downgraded_count += 1

    # 4. Validate cross-country items
    for idx, cc in enumerate(out.cross_country):
        ctx = f"cross_country[{idx}]"
        cc.evidence_refs = _filter_evidence_refs(cc.evidence_refs, bundle, evidence_issues, ctx)
        for cf in cc.country_frames:
            cf.evidence_refs = _filter_evidence_refs(
                cf.evidence_refs, bundle, evidence_issues, f"{ctx}.{cf.country_id}"
            )
        blob = f"{cc.common_focus} {cc.major_differences} {cc.emerging_or_shifting}"
        for code, _, msg in _check_reasoning_text(blob):
            reasoning_issues.append(f"{ctx}[{code}]: {msg}")
            cc.needs_review = True

    # 5. Validate stance analyses
    for idx, sa in enumerate(out.stance_analyses):
        ctx = f"stance[{idx}:{sa.scope_id}]"
        sa.evidence_refs = _filter_evidence_refs(sa.evidence_refs, bundle, evidence_issues, ctx)
        blob = f"{sa.rate_vs_count_note} {sa.coverage_limitation}"
        bad_nums = _find_ungrounded_numbers(blob, bundle.allowed_numbers)
        if bad_nums:
            numeric_issues.append(f"{ctx}: ungrounded numbers {bad_nums}")
            sa.needs_review = True
        for code, _, msg in _check_reasoning_text(blob):
            reasoning_issues.append(f"{ctx}[{code}]: {msg}")
            sa.needs_review = True

    # 6. Validate outlook signals (enforce conditional phrasing)
    for idx, sig in enumerate(out.outlook_signals):
        ctx = f"outlook[{idx}]"
        sig.evidence_refs = _filter_evidence_refs(sig.evidence_refs, bundle, evidence_issues, ctx)
        blob = f"{sig.signal} {sig.reasoning} {sig.potential_trigger}"
        bad_nums = _find_ungrounded_numbers(blob, bundle.allowed_numbers)
        if bad_nums:
            numeric_issues.append(f"{ctx}: ungrounded numbers {bad_nums}")
            sig.needs_review = True
        if _CERTAINTY_RE.search(blob):
            reasoning_issues.append(f"{ctx}[outlook_non_conditional]: outlook uses absolute certainty language")
            sig.needs_review = True
            sig.uncertainty = (
                (sig.uncertainty + "；" if sig.uncertainty else "")
                + "该项为条件性观察判断，非既定预测"
            )
        elif not any(h in (sig.signal + sig.reasoning + sig.uncertainty) for h in _CONDITIONAL_HINTS):
            sig.uncertainty = (
                (sig.uncertainty + "；" if sig.uncertainty else "")
                + "需视后续事件与媒体跟进情况动态验证"
            )
        if low_global and sig.confidence == "high":
            sig.confidence = "low"
            downgraded_count += 1

    total_issues = len(numeric_issues) + len(evidence_issues) + len(reasoning_issues)
    needs_review = total_issues > 0
    if dropped_count > 0 and not out.findings and not out.event_interpretations and not out.outlook_signals:
        out.status = "degraded"
    elif needs_review:
        out.status = "needs_review"
    elif bundle.global_article_count == 0:
        out.status = "insufficient_data"
    else:
        out.status = "completed"

    validation_summary = {
        "ok": total_issues == 0,
        "status": out.status,
        "needs_review": needs_review,
        "numeric_issues": numeric_issues,
        "evidence_issues": evidence_issues,
        "reasoning_issues": reasoning_issues,
        "dropped_count": dropped_count,
        "downgraded_count": downgraded_count,
    }
    out.meta["validation_summary"] = validation_summary
    return out, validation_summary

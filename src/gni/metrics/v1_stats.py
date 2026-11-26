"""Deterministic V1.0 statistical aggregation engine (no DB I/O, no LLM).

Implements docs/STATISTICAL_METHODOLOGY_V1.md (methodology_v1.0):
- Unique Article Count only (no manual weights, no Unique Story/Event core metrics).
- Strictly published_at for time windowing (never first_seen_at).
- Strictly source_country for country attribution.
- Fixed 4 boards x 15 topics multi-label taxonomy with intra-board deduplication.
- China-related stance 3-class (Positive/Neutral/Negative) + Unclassified status.
- Unclassified excluded from P/N/N denominator and tracked via stance_coverage_rate.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from gni.metrics.definitions import (
    CHINA_INCLUDE_LEVELS,
    METHODOLOGY_VERSION,
    TAXONOMY_V1_VERSION,
    UNCLASSIFIED_LABEL,
    V1_ANALYSIS_VERSION,
    V1_COMPATIBLE_ANALYSIS_VERSIONS,
)
from gni.metrics.taxonomy_v1 import boards_for_topics, load_taxonomy_v1, normalize_topic_ids

_TRACKING_PARAM_PREFIXES = ("utm_",)
_TRACKING_PARAM_NAMES = frozenset(
    {
        "fbclid",
        "gclid",
        "yclid",
        "mc_cid",
        "mc_eid",
        "ref",
        "referrer",
        "source",
        "src",
        "spm",
        "from",
        "ocid",
        "cmpid",
    }
)
_VALID_STANCES = frozenset({"Positive", "Neutral", "Negative"})


@dataclass
class V1ArticleInput:
    """Normalized article + V1.0 analysis fields for deterministic aggregation."""

    article_id: str
    source_id: str
    source_country: str | None
    published_at: datetime | None
    canonical_url: str | None = None
    url: str | None = None
    content_hash: str | None = None
    exclude_from_metrics: bool = False
    china_relevance_level: str | None = None
    topics_v1: list[str] = field(default_factory=list)
    stance_label: str = UNCLASSIFIED_LABEL
    stance_evidence: list[dict[str, Any]] = field(default_factory=list)
    analysis_schema_version: str | None = None


@dataclass
class StatSnapshotRow:
    """Single scope row matching V1.0 Section 9."""

    period_start: datetime
    period_end: datetime
    scope_type: str  # GLOBAL | COUNTRY | BOARD | TOPIC
    scope_id: str
    article_count: int
    positive_count: int
    neutral_count: int
    negative_count: int
    unclassified_count: int
    positive_rate: float | None
    neutral_rate: float | None
    negative_rate: float | None
    stance_coverage_rate: float | None
    generated_at: datetime
    methodology_version: str = METHODOLOGY_VERSION
    taxonomy_version: str = TAXONOMY_V1_VERSION
    analysis_version: str = V1_ANALYSIS_VERSION
    article_ids: list[str] = field(default_factory=list)
    label_zh: str | None = None
    board_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "scope_type": self.scope_type,
            "scope_id": self.scope_id,
            "article_count": self.article_count,
            "positive_count": self.positive_count,
            "neutral_count": self.neutral_count,
            "negative_count": self.negative_count,
            "unclassified_count": self.unclassified_count,
            "classified_count": self.positive_count + self.neutral_count + self.negative_count,
            "positive_rate": self.positive_rate,
            "neutral_rate": self.neutral_rate,
            "negative_rate": self.negative_rate,
            "stance_coverage_rate": self.stance_coverage_rate,
            "methodology_version": self.methodology_version,
            "taxonomy_version": self.taxonomy_version,
            "analysis_version": self.analysis_version,
            "article_ids": list(self.article_ids),
            "generated_at": self.generated_at.isoformat(),
        }
        if self.label_zh is not None:
            out["label_zh"] = self.label_zh
        if self.board_id is not None:
            out["board_id"] = self.board_id
        return out


def _as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def normalize_url_for_dedup(raw_url: str | None) -> str | None:
    """Strip tracking query parameters and normalize host/path for deduplication."""
    raw = (raw_url or "").strip()
    if not raw:
        return None
    try:
        parts = urlsplit(raw)
        scheme = (parts.scheme or "https").lower()
        netloc = parts.netloc.lower()
        path = parts.path.rstrip("/") or "/"
        kept_params = [
            (k, v)
            for k, v in parse_qsl(parts.query, keep_blank_values=False)
            if k.lower() not in _TRACKING_PARAM_NAMES
            and not any(k.lower().startswith(p) for p in _TRACKING_PARAM_PREFIXES)
        ]
        kept_params.sort()
        query = urlencode(kept_params)
        return urlunsplit((scheme, netloc, path, query, ""))
    except Exception:  # noqa: BLE001
        return raw


def _in_published_window(
    published_at: datetime | None,
    period_start: datetime,
    period_end: datetime,
) -> bool:
    """Strict V1.0 Section 8.1: ONLY published_at is used; missing published_at is excluded."""
    pub = _as_utc(published_at)
    if pub is None:
        return False
    return _as_utc(period_start) <= pub < _as_utc(period_end)  # type: ignore[operator]


def deduplicate_v1_articles(rows: Iterable[V1ArticleInput]) -> list[V1ArticleInput]:
    """Deterministic article deduplication by article_id, canonical_url, then content_hash."""
    seen_ids: set[str] = set()
    seen_urls: set[str] = set()
    seen_hashes: set[str] = set()
    kept: list[V1ArticleInput] = []

    for row in rows:
        if row.article_id in seen_ids:
            continue
        url_key = normalize_url_for_dedup(row.canonical_url or row.url)
        if url_key and url_key in seen_urls:
            continue
        ch = (row.content_hash or "").strip()
        if ch and ch in seen_hashes:
            continue
        seen_ids.add(row.article_id)
        if url_key:
            seen_urls.add(url_key)
        if ch:
            seen_hashes.add(ch)
        kept.append(row)
    return kept


def _effective_stance(row: V1ArticleInput) -> str:
    """Strict V1.0+ stance: non-V1.0/v1.1 schema or invalid label -> Unclassified."""
    if (
        row.analysis_schema_version is not None
        and row.analysis_schema_version not in V1_COMPATIBLE_ANALYSIS_VERSIONS
    ):
        return UNCLASSIFIED_LABEL
    if row.stance_label in _VALID_STANCES:
        return row.stance_label
    return UNCLASSIFIED_LABEL


def _effective_topics(row: V1ArticleInput) -> list[str]:
    if (
        row.analysis_schema_version is not None
        and row.analysis_schema_version not in V1_COMPATIBLE_ANALYSIS_VERSIONS
    ):
        return []
    return normalize_topic_ids(row.topics_v1)


def _aggregate_bucket(
    *,
    articles: list[V1ArticleInput],
    period_start: datetime,
    period_end: datetime,
    scope_type: str,
    scope_id: str,
    generated_at: datetime,
    label_zh: str | None = None,
    board_id: str | None = None,
) -> StatSnapshotRow:
    # Guarantee distinct article_id within bucket
    by_id: dict[str, V1ArticleInput] = {}
    for a in articles:
        if a.article_id not in by_id:
            by_id[a.article_id] = a

    unique_articles = list(by_id.values())
    article_count = len(unique_articles)
    pos = neu = neg = unc = 0
    for a in unique_articles:
        st = _effective_stance(a)
        if st == "Positive":
            pos += 1
        elif st == "Neutral":
            neu += 1
        elif st == "Negative":
            neg += 1
        else:
            unc += 1

    classified = pos + neu + neg
    if classified > 0:
        pos_rate: float | None = round(pos / classified, 6)
        neu_rate: float | None = round(neu / classified, 6)
        neg_rate: float | None = round(neg / classified, 6)
    else:
        pos_rate = neu_rate = neg_rate = None

    coverage: float | None = round(classified / article_count, 6) if article_count > 0 else None

    return StatSnapshotRow(
        period_start=_as_utc(period_start) or period_start,
        period_end=_as_utc(period_end) or period_end,
        scope_type=scope_type,
        scope_id=scope_id,
        article_count=article_count,
        positive_count=pos,
        neutral_count=neu,
        negative_count=neg,
        unclassified_count=unc,
        positive_rate=pos_rate,
        neutral_rate=neu_rate,
        negative_rate=neg_rate,
        stance_coverage_rate=coverage,
        generated_at=_as_utc(generated_at) or generated_at,
        article_ids=sorted(by_id.keys()),
        label_zh=label_zh,
        board_id=board_id,
    )


def compute_v1_stat_snapshots(
    rows: Iterable[V1ArticleInput],
    *,
    period_start: datetime,
    period_end: datetime,
    generated_at: datetime | None = None,
    include_zero_taxonomy: bool = True,
) -> list[StatSnapshotRow]:
    """Compute deterministic V1.0 stat snapshots across GLOBAL, COUNTRY, BOARD, and TOPIC."""
    p_start = _as_utc(period_start)
    p_end = _as_utc(period_end)
    assert p_start is not None and p_end is not None
    gen_at = _as_utc(generated_at) or datetime.now(timezone.utc)
    tax = load_taxonomy_v1()

    eligible = [
        r
        for r in rows
        if not r.exclude_from_metrics
        and r.china_relevance_level in CHINA_INCLUDE_LEVELS
        and _in_published_window(r.published_at, p_start, p_end)
    ]
    unique_rows = deduplicate_v1_articles(eligible)

    snapshots: list[StatSnapshotRow] = []

    # 1. GLOBAL
    snapshots.append(
        _aggregate_bucket(
            articles=unique_rows,
            period_start=p_start,
            period_end=p_end,
            scope_type="GLOBAL",
            scope_id="ALL",
            generated_at=gen_at,
            label_zh="全球涉华总量",
        )
    )

    # 2. COUNTRY (strictly by source_country)
    by_country: dict[str, list[V1ArticleInput]] = defaultdict(list)
    for r in unique_rows:
        cid = (r.source_country or "").strip().upper()
        if cid:
            by_country[cid].append(r)
    for cid in sorted(by_country.keys()):
        snapshots.append(
            _aggregate_bucket(
                articles=by_country[cid],
                period_start=p_start,
                period_end=p_end,
                scope_type="COUNTRY",
                scope_id=cid,
                generated_at=gen_at,
            )
        )

    # 3. BOARD & 4. TOPIC (multi-label, deduplicated per board and per topic)
    by_topic: dict[str, list[V1ArticleInput]] = defaultdict(list)
    by_board: dict[str, list[V1ArticleInput]] = defaultdict(list)
    for r in unique_rows:
        tids = _effective_topics(r)
        for tid in tids:
            by_topic[tid].append(r)
        for bid in boards_for_topics(tids):
            by_board[bid].append(r)

    for b in tax.boards:
        bucket = by_board.get(b.id, [])
        if include_zero_taxonomy or bucket:
            snapshots.append(
                _aggregate_bucket(
                    articles=bucket,
                    period_start=p_start,
                    period_end=p_end,
                    scope_type="BOARD",
                    scope_id=b.id,
                    generated_at=gen_at,
                    label_zh=b.name_zh,
                )
            )

    for t in tax.topics:
        bucket = by_topic.get(t.id, [])
        if include_zero_taxonomy or bucket:
            snapshots.append(
                _aggregate_bucket(
                    articles=bucket,
                    period_start=p_start,
                    period_end=p_end,
                    scope_type="TOPIC",
                    scope_id=t.id,
                    generated_at=gen_at,
                    label_zh=t.name_zh,
                    board_id=t.board_id,
                )
            )

    return snapshots


def group_snapshots_by_scope(rows: list[StatSnapshotRow]) -> dict[str, Any]:
    """Structure snapshot rows into {global, countries, boards, topics} for reports/APIs."""
    global_row: dict[str, Any] | None = None
    countries: list[dict[str, Any]] = []
    boards: list[dict[str, Any]] = []
    topics: list[dict[str, Any]] = []
    for r in rows:
        d = r.to_dict()
        if r.scope_type == "GLOBAL":
            global_row = d
        elif r.scope_type == "COUNTRY":
            countries.append(d)
        elif r.scope_type == "BOARD":
            boards.append(d)
        elif r.scope_type == "TOPIC":
            topics.append(d)
    countries.sort(key=lambda x: (-x["article_count"], x["scope_id"]))
    boards.sort(key=lambda x: (-x["article_count"], x["scope_id"]))
    topics.sort(key=lambda x: (-x["article_count"], x["scope_id"]))
    return {
        "global": global_row,
        "countries": countries,
        "boards": boards,
        "topics": topics,
    }

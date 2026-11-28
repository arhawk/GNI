"""Cross-source duplicate handling: ingestion marker, stats keep rule, daily count, backfill."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from gni.infrastructure.models import Article, Base, Country, Organization, Source
from gni.metrics.definitions import UNCLASSIFIED_LABEL, V1_ANALYSIS_VERSION
from gni.metrics.v1_stats import V1ArticleInput, deduplicate_v1_articles
from gni.processing.service import _find_duplicate, process_article

PUB = datetime(2026, 11, 26, 9, 0, tzinfo=timezone.utc)
SAME_BODY = "<html><body><article><p>" + ("China unveiled a major industrial policy today. " * 30) + "</p></article></body></html>"


def _v1(
    aid: str,
    *,
    content_hash: str | None = "h_same",
    url: str = "https://example.com/a",
    stance: str = UNCLASSIFIED_LABEL,
    first_seen: datetime | None = None,
    dup_of: str | None = None,
) -> V1ArticleInput:
    return V1ArticleInput(
        article_id=aid,
        source_id=f"src_{aid}",
        source_country="DE",
        published_at=PUB,
        canonical_url=url,
        url=url,
        content_hash=content_hash,
        china_relevance_level="core",
        topics_v1=["tariffs_trade_war"],
        stance_label=stance,
        analysis_schema_version=V1_ANALYSIS_VERSION if stance != UNCLASSIFIED_LABEL else None,
        first_seen_at=first_seen,
        duplicate_of_article_id=dup_of,
    )


# --- Stats layer: order-independent keep rule -------------------------------------------


def test_stats_keeps_record_with_stance_regardless_of_input_order():
    early_unclassified = _v1(
        "a_early", stance=UNCLASSIFIED_LABEL, first_seen=datetime(2026, 11, 26, 1, tzinfo=timezone.utc)
    )
    late_neutral = _v1(
        "b_late",
        stance="Neutral",
        url="https://mirror.example.com/x",
        first_seen=datetime(2026, 11, 26, 2, tzinfo=timezone.utc),
    )
    for ordering in ([early_unclassified, late_neutral], [late_neutral, early_unclassified]):
        kept = deduplicate_v1_articles(ordering)
        assert [r.article_id for r in kept] == ["b_late"]


def test_stats_prefers_unmarked_primary_over_marked_duplicate():
    marked = _v1("a", stance="Neutral", first_seen=datetime(2026, 11, 26, 1, tzinfo=timezone.utc), dup_of="b")
    primary = _v1("b", stance=UNCLASSIFIED_LABEL, first_seen=datetime(2026, 11, 26, 2, tzinfo=timezone.utc))
    kept = deduplicate_v1_articles([marked, primary])
    assert [r.article_id for r in kept] == ["b"]


def test_stats_falls_back_to_earlier_first_seen_then_article_id():
    late = _v1("z_late", stance="Positive", first_seen=datetime(2026, 11, 26, 5, tzinfo=timezone.utc))
    early = _v1("m_early", stance="Negative", first_seen=datetime(2026, 11, 26, 1, tzinfo=timezone.utc))
    assert [r.article_id for r in deduplicate_v1_articles([late, early])] == ["m_early"]

    tie_a = _v1("a", stance="Positive")
    tie_b = _v1("b", stance="Positive")
    assert [r.article_id for r in deduplicate_v1_articles([tie_b, tie_a])] == ["a"]


def test_stats_grouping_is_transitive_url_then_hash():
    # A shares URL with B; B shares content_hash with C. One duplicate group, one survivor.
    a = _v1("a", content_hash="h1", url="https://example.com/story?utm_source=x")
    b = _v1("b", content_hash="h2", url="https://example.com/story")
    c = _v1("c", content_hash="h2", url="https://other.example.com/copy")
    assert len(deduplicate_v1_articles([a, b, c])) == 1


def test_stats_distinct_articles_are_not_merged():
    a = _v1("a", content_hash="h1", url="https://example.com/one")
    b = _v1("b", content_hash="h2", url="https://example.com/two")
    assert len(deduplicate_v1_articles([a, b])) == 2


# --- Ingestion: cross-source exact content_hash ------------------------------------------


@pytest.fixture()
def session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(Country(id="DE", code="DE", name="Germany"))
        s.add(Organization(id="org_dw", country_id="DE", name="DW", organization_type="public_service"))
        for sid in ("de_dw_english", "de_dw_asia"):
            s.add(
                Source(
                    id=sid,
                    organization_id="org_dw",
                    country_id="DE",
                    name=sid,
                    source_type="public_service",
                    access_method="rss",
                    adapter_type="rss_adapter",
                    language="en",
                    active_status="active",
                    verification_status="verified",
                )
            )
        s.commit()
        yield s


def _article(aid: str, source_id: str, first_seen: datetime, url: str) -> Article:
    return Article(
        id=aid,
        source_id=source_id,
        title="China tariffs update",
        url=url,
        content_original="stub",
        quality_status="rss_stub",
        processing_status="pending",
        first_seen_at=first_seen,
        published_at=PUB,
    )


def test_process_article_marks_later_cross_source_copy_as_duplicate(session: Session):
    earlier = _article(
        "00000000-0000-0000-0000-00000000000a",
        "de_dw_english",
        datetime(2026, 11, 26, 1, tzinfo=timezone.utc),
        "https://www.dw.com/en/story?maca=en",
    )
    later = _article(
        "00000000-0000-0000-0000-00000000000b",
        "de_dw_asia",
        datetime(2026, 11, 26, 2, tzinfo=timezone.utc),
        "https://www.dw.com/en/story?maca=asia",
    )
    session.add_all([earlier, later])
    session.commit()

    detail_1 = process_article(session, earlier, offline_html=SAME_BODY)
    session.commit()
    detail_2 = process_article(session, later, offline_html=SAME_BODY)
    session.commit()

    assert detail_1["ok"] and detail_2["ok"]
    assert earlier.duplicate_of_article_id is None
    assert earlier.exclude_from_metrics is False
    assert later.duplicate_of_article_id == earlier.id
    assert later.exclude_from_metrics is True
    assert later.quality_status == "duplicate"


def test_find_duplicate_ignores_later_records_and_chained_duplicates(session: Session):
    first = _article("00000000-0000-0000-0000-00000000000a", "de_dw_english",
                     datetime(2026, 11, 26, 1, tzinfo=timezone.utc), "https://x.example/a")
    first.content_hash = "hash_x"
    newer = _article("00000000-0000-0000-0000-00000000000b", "de_dw_asia",
                     datetime(2026, 11, 26, 3, tzinfo=timezone.utc), "https://x.example/b")
    newer.content_hash = "hash_x"
    session.add_all([first, newer])
    session.commit()

    # `first` is older than `newer`, so it is the canonical match for `newer`.
    assert _find_duplicate(session, newer, content_hash="hash_x", title_norm="") is first
    # `first` must not be treated as a duplicate of the newer record.
    assert _find_duplicate(session, first, content_hash="hash_x", title_norm="") is None


# --- Daily count alignment ----------------------------------------------------------------


def test_daily_china_count_is_unique_like_v1_stats(session: Session):
    from gni.reports.daily import _china_count_in_window

    a = _article("00000000-0000-0000-0000-00000000000a", "de_dw_english",
                 datetime(2026, 11, 26, 1, tzinfo=timezone.utc), "https://www.dw.com/en/s?maca=en")
    b = _article("00000000-0000-0000-0000-00000000000b", "de_dw_asia",
                 datetime(2026, 11, 26, 2, tzinfo=timezone.utc), "https://www.dw.com/en/s?maca=asia")
    for art in (a, b):
        art.content_hash = "same_hash"
        art.china_relevance_level = "core"
    session.add_all([a, b])
    session.commit()

    start = datetime(2026, 11, 25, 16, tzinfo=timezone.utc)
    end = datetime(2026, 11, 26, 16, tzinfo=timezone.utc)
    # Both rows are still primary here (no ingestion marker yet); the count must not be 2.
    assert _china_count_in_window([a, b], start, end) == 1


# --- Backfill ----------------------------------------------------------------------------


def test_backfill_marks_cross_source_copies_and_is_idempotent(session: Session):
    import importlib.util
    from pathlib import Path

    script = Path(__file__).resolve().parents[2] / "scripts" / "backfill_duplicate_articles.py"
    spec = importlib.util.spec_from_file_location("backfill_duplicate_articles", script)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    apply_backfill, plan_backfill = mod.apply_backfill, mod.plan_backfill

    a = _article("00000000-0000-0000-0000-00000000000a", "de_dw_english",
                 datetime(2026, 11, 26, 1, tzinfo=timezone.utc), "https://www.dw.com/en/s?maca=en")
    b = _article("00000000-0000-0000-0000-00000000000b", "de_dw_asia",
                 datetime(2026, 11, 26, 2, tzinfo=timezone.utc), "https://www.dw.com/en/s?maca=asia")
    for art in (a, b):
        art.content_hash = "bf_hash"
    session.add_all([a, b])
    session.commit()

    marks, summary = plan_backfill(session)
    assert summary["articles_to_mark_duplicate"] == 1
    assert marks[0][0].id == b.id and marks[0][1].id == a.id
    apply_backfill(marks)
    session.commit()
    assert b.duplicate_of_article_id == a.id and b.exclude_from_metrics is True

    marks_2, summary_2 = plan_backfill(session)
    assert marks_2 == []
    assert summary_2["articles_to_mark_duplicate"] == 0

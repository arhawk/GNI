"""Normalize + extract unit tests (offline HTML)."""

from gni.processing.extractor import extract_from_html
from gni.processing.normalize import normalize_title_for_dedup, normalize_url
from gni.processing.service import process_article
from gni.infrastructure.models import Article, Country, Organization, Source


def test_normalize_url_strips_utm_and_www():
    u = normalize_url("https://WWW.Example.com/path/?utm_source=x&id=1")
    assert u == "https://example.com/path?id=1"


def test_normalize_title_dedup():
    assert normalize_title_for_dedup("Hello, World!") == "hello world"


def test_extract_from_simple_html():
    html = """
    <html><body>
    <article>
      <h1>China trade update</h1>
      <p>""" + ("The Chinese government announced new measures. " * 20) + """</p>
      <p>""" + ("Further details on exports and tariffs follow. " * 20) + """</p>
    </article>
    </body></html>
    """
    result = extract_from_html(html)
    assert result.quality_status == "extracted"
    assert result.content_clean
    assert "Chinese government" in result.content_clean or "China" in result.content_clean


def test_extract_insufficient():
    result = extract_from_html("<html><body><p>Hi</p></body></html>")
    assert result.quality_status == "insufficient_text"


def test_process_article_offline(tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from gni.infrastructure.models import Base

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(Country(id="US", code="US", name="United States"))
        session.add(
            Organization(
                id="org_t",
                country_id="US",
                name="Test Org",
                organization_type="test",
            )
        )
        session.add(
            Source(
                id="us_test",
                organization_id="org_t",
                country_id="US",
                name="Test",
                source_type="public_service",
                access_method="rss",
                adapter_type="rss_adapter",
                language="en",
                active_status="active",
                verification_status="verified",
            )
        )
        article = Article(
            id="00000000-0000-0000-0000-000000000001",
            source_id="us_test",
            title="China announces new EV policy",
            url="https://example.com/a1",
            content_original="short stub",
            quality_status="rss_stub",
            processing_status="pending",
        )
        session.add(article)
        session.commit()

        html = (
            "<html><body><article>"
            + "<p>"
            + ("China unveiled a major industrial policy today affecting EVs. " * 30)
            + "</p></article></body></html>"
        )
        detail = process_article(session, article, offline_html=html)
        session.commit()
        assert detail["ok"] is True
        assert detail["title_screening"] == "explicit_relevant"
        assert article.content_clean
        assert article.processing_status == "done"
        assert article.quality_status == "processed"


def test_process_article_l1_no_match_hard_gate_and_restore(tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from gni.infrastructure.models import Base

    engine = create_engine(f"sqlite:///{tmp_path / 't_gate.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(Country(id="US", code="US", name="US"))
        session.add(Organization(id="o1", country_id="US", name="Org1"))
        session.add(Source(id="s1", organization_id="o1", country_id="US", name="Src1", source_type="public_service"))
        article = Article(
            id="a_nomatch",
            source_id="s1",
            title="Local school bus schedule updated for winter",
            url="https://example.com/local-bus",
            content_original="Short local traffic notice.",
            quality_status="rss_stub",
            processing_status="pending",
        )
        session.add(article)
        session.commit()

        # Hard gate triggers before extraction; even if offline_html is given, it is skipped.
        detail = process_article(session, article, offline_html="<html><body><p>unused</p></body></html>")
        session.commit()
        assert detail["ok"] is True
        assert detail["title_screening"] == "no_match"
        assert detail["title_filtered"] is True
        assert article.exclude_from_metrics is True
        assert article.quality_status == "title_filtered"
        assert article.pipeline_state == "TITLE_SCREENED"
        assert article.processing_status == "done"
        assert article.content_clean is None

        # If title later matches L1 (e.g. reprocess after dictionary update), restore cleanly.
        article.title = "China announces new semiconductor tariff policy"
        html = (
            "<html><body><article><p>"
            + ("Beijing announced new semiconductor tariffs affecting global supply chains. " * 20)
            + "</p></article></body></html>"
        )
        detail2 = process_article(session, article, offline_html=html)
        session.commit()
        assert detail2["ok"] is True
        assert detail2["title_screening"] == "explicit_relevant"
        assert article.exclude_from_metrics is False
        assert article.quality_status == "processed"
        assert article.content_clean


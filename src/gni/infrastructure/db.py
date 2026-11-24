"""Database engine and session helpers."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from gni.core.config import get_settings

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None

# Columns added after P1-A initial articles table (P1-B / P1-C).
# Used when alembic is behind but ORM already expects these fields.
_ARTICLES_EXTRA_COLUMNS: dict[str, dict[str, str]] = {
    "sqlite": {
        "processing_status": "VARCHAR(32) DEFAULT 'pending'",
        "duplicate_of_article_id": "VARCHAR(36)",
        "exclude_from_metrics": "BOOLEAN DEFAULT 0",
        "processed_at": "DATETIME",
        "title_screening_label": "VARCHAR(32)",
        "title_screening_priority": "VARCHAR(8)",
        "analysis_status": "VARCHAR(32) DEFAULT 'pending'",
        "fulltext_screening_label": "VARCHAR(64)",
        "china_relevance_level": "VARCHAR(32)",
        "china_relevance_weight": "FLOAT",
        "analyzed_at": "DATETIME",
    },
    "postgresql": {
        "processing_status": "VARCHAR(32) DEFAULT 'pending'",
        "duplicate_of_article_id": "UUID",
        "exclude_from_metrics": "BOOLEAN DEFAULT FALSE",
        "processed_at": "TIMESTAMP WITH TIME ZONE",
        "title_screening_label": "VARCHAR(32)",
        "title_screening_priority": "VARCHAR(8)",
        "analysis_status": "VARCHAR(32) DEFAULT 'pending'",
        "fulltext_screening_label": "VARCHAR(64)",
        "china_relevance_level": "VARCHAR(32)",
        "china_relevance_weight": "DOUBLE PRECISION",
        "analyzed_at": "TIMESTAMP WITH TIME ZONE",
    },
}


def get_engine(*, echo: bool = False) -> Engine:
    global _engine, _SessionLocal
    if _engine is None:
        settings = get_settings()
        url = settings.database_url
        kwargs: dict = {"pool_pre_ping": True, "echo": echo}
        if url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False}
        _engine = create_engine(url, **kwargs)
        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    get_engine()
    assert _SessionLocal is not None
    return _SessionLocal


@contextmanager
def session_scope() -> Iterator[Session]:
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def reset_engine() -> None:
    """Test helper: dispose cached engine."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None


def ensure_schema() -> list[str]:
    """Create missing tables and ADD missing P1-B/P1-C columns on articles (SQLite + Postgres).

    Safe for partially-migrated DBs where create_all added newer tables but articles
    columns from alembic P1-B/C were never applied.
    """
    from gni.infrastructure.models import Base

    engine = get_engine()
    Base.metadata.create_all(engine)
    applied: list[str] = []

    backend = engine.url.get_backend_name()
    if backend.startswith("sqlite"):
        dialect_key = "sqlite"
    elif backend.startswith("postgres"):
        dialect_key = "postgresql"
    else:
        return applied

    insp = inspect(engine)
    if "articles" not in insp.get_table_names():
        return applied
    existing = {c["name"] for c in insp.get_columns("articles")}
    alters = _ARTICLES_EXTRA_COLUMNS[dialect_key]
    with engine.begin() as conn:
        for name, ddl in alters.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE articles ADD COLUMN {name} {ddl}"))
                applied.append(name)
        # Best-effort FK for duplicate_of on Postgres (ignore if already present)
        if dialect_key == "postgresql" and "duplicate_of_article_id" in applied:
            try:
                conn.execute(
                    text(
                        "ALTER TABLE articles ADD CONSTRAINT fk_articles_duplicate_of "
                        "FOREIGN KEY (duplicate_of_article_id) REFERENCES articles (id)"
                    )
                )
            except Exception:  # noqa: BLE001
                pass

    return applied

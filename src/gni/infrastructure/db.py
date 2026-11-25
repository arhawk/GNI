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

_EVENTS_EXTRA_COLUMNS: dict[str, dict[str, str]] = {
    "sqlite": {
        "actor_key": "VARCHAR(128)",
        "action_key": "VARCHAR(64)",
        "object_key": "VARCHAR(256)",
        "event_time": "DATETIME",
        "qualifiers": "JSON",
        "fingerprint_hash": "VARCHAR(64)",
    },
    "postgresql": {
        "actor_key": "VARCHAR(128)",
        "action_key": "VARCHAR(64)",
        "object_key": "VARCHAR(256)",
        "event_time": "TIMESTAMP WITH TIME ZONE",
        "qualifiers": "JSONB",
        "fingerprint_hash": "VARCHAR(64)",
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
    tables = set(insp.get_table_names())
    with engine.begin() as conn:
        if "articles" in tables:
            existing = {c["name"] for c in insp.get_columns("articles")}
            for name, ddl in _ARTICLES_EXTRA_COLUMNS[dialect_key].items():
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE articles ADD COLUMN {name} {ddl}"))
                    applied.append(f"articles.{name}")
            if dialect_key == "postgresql" and "articles.duplicate_of_article_id" in applied:
                try:
                    conn.execute(
                        text(
                            "ALTER TABLE articles ADD CONSTRAINT fk_articles_duplicate_of "
                            "FOREIGN KEY (duplicate_of_article_id) REFERENCES articles (id)"
                        )
                    )
                except Exception:  # noqa: BLE001
                    pass

        if "events" in tables:
            existing_ev = {c["name"] for c in insp.get_columns("events")}
            for name, ddl in _EVENTS_EXTRA_COLUMNS[dialect_key].items():
                if name not in existing_ev:
                    conn.execute(text(f"ALTER TABLE events ADD COLUMN {name} {ddl}"))
                    applied.append(f"events.{name}")

        if "sources" in tables:
            existing_src = {c["name"] for c in insp.get_columns("sources")}
            if "feed_scope" not in existing_src:
                col = "VARCHAR(64)" if dialect_key == "sqlite" else "VARCHAR(64)"
                conn.execute(text(f"ALTER TABLE sources ADD COLUMN feed_scope {col}"))
                applied.append("sources.feed_scope")

        if "event_locations" in tables:
            existing_loc = {c["name"] for c in insp.get_columns("event_locations")}
            loc_cols = {
                "geographic_precision": "VARCHAR(32)",
                "confidence": "FLOAT" if dialect_key == "sqlite" else "DOUBLE PRECISION",
                "evidence": "JSON" if dialect_key == "sqlite" else "JSONB",
            }
            for name, ddl in loc_cols.items():
                if name not in existing_loc:
                    conn.execute(text(f"ALTER TABLE event_locations ADD COLUMN {name} {ddl}"))
                    applied.append(f"event_locations.{name}")

    return applied

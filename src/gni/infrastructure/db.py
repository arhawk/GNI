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
    """Create missing tables; on SQLite also ADD missing P1-B/P1-C columns on articles."""
    from gni.infrastructure.models import Base

    engine = get_engine()
    Base.metadata.create_all(engine)
    applied: list[str] = []
    if not engine.url.get_backend_name().startswith("sqlite"):
        return applied

    insp = inspect(engine)
    if "articles" not in insp.get_table_names():
        return applied
    existing = {c["name"] for c in insp.get_columns("articles")}
    alters = [
        ("processing_status", "VARCHAR(32) DEFAULT 'pending'"),
        ("duplicate_of_article_id", "VARCHAR(36)"),
        ("exclude_from_metrics", "BOOLEAN DEFAULT 0"),
        ("processed_at", "DATETIME"),
        ("title_screening_label", "VARCHAR(32)"),
        ("title_screening_priority", "VARCHAR(8)"),
        ("analysis_status", "VARCHAR(32) DEFAULT 'pending'"),
        ("fulltext_screening_label", "VARCHAR(64)"),
        ("china_relevance_level", "VARCHAR(32)"),
        ("china_relevance_weight", "FLOAT"),
        ("analyzed_at", "DATETIME"),
    ]
    with engine.begin() as conn:
        for name, ddl in alters:
            if name not in existing:
                conn.execute(text(f"ALTER TABLE articles ADD COLUMN {name} {ddl}"))
                applied.append(name)
    return applied

"""Event fingerprint MVP: candidates, event keys, metric/attitude snapshots.

Revision ID: 20261124_0007
Revises: 20261124_0006
Create Date: 2026-11-24

Idempotent: safe when create_all already created new tables without event columns.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

revision: str = "20261124_0007"
down_revision: Union[str, None] = "20261124_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    return name in inspect(bind).get_table_names()


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    if table not in inspect(bind).get_table_names():
        return False
    return column in {c["name"] for c in inspect(bind).get_columns(table)}


def _has_index(table: str, index: str) -> bool:
    bind = op.get_bind()
    if table not in inspect(bind).get_table_names():
        return False
    return index in {i["name"] for i in inspect(bind).get_indexes(table)}


def upgrade() -> None:
    event_cols = [
        ("actor_key", sa.Column("actor_key", sa.String(128))),
        ("action_key", sa.Column("action_key", sa.String(64))),
        ("object_key", sa.Column("object_key", sa.String(256))),
        ("event_time", sa.Column("event_time", sa.DateTime(timezone=True))),
        ("qualifiers", sa.Column("qualifiers", postgresql.JSONB(astext_type=sa.Text()))),
        ("fingerprint_hash", sa.Column("fingerprint_hash", sa.String(64))),
    ]
    for name, col in event_cols:
        if not _has_column("events", name):
            op.add_column("events", col)

    for idx, cols in (
        ("ix_events_actor_key", ["actor_key"]),
        ("ix_events_action_key", ["action_key"]),
        ("ix_events_object_key", ["object_key"]),
        ("ix_events_fingerprint_hash", ["fingerprint_hash"]),
    ):
        if not _has_index("events", idx):
            op.create_index(idx, "events", cols)

    if not _has_table("article_event_candidates"):
        op.create_table(
            "article_event_candidates",
            sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
            sa.Column(
                "article_id",
                postgresql.UUID(as_uuid=False),
                sa.ForeignKey("articles.id"),
                nullable=False,
            ),
            sa.Column(
                "article_version_id",
                postgresql.UUID(as_uuid=False),
                sa.ForeignKey("article_versions.id"),
            ),
            sa.Column(
                "analysis_id",
                postgresql.UUID(as_uuid=False),
                sa.ForeignKey("article_analyses.id"),
            ),
            sa.Column("fingerprint", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text())),
            sa.Column("schema_version", sa.String(64), server_default="event_fingerprint_v0.1"),
            sa.Column("prompt_version", sa.String(64)),
            sa.Column("confidence", sa.Float()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
    if not _has_index("article_event_candidates", "ix_article_event_candidates_article_id"):
        op.create_index(
            "ix_article_event_candidates_article_id",
            "article_event_candidates",
            ["article_id"],
        )

    if not _has_table("event_metric_snapshots"):
        op.create_table(
            "event_metric_snapshots",
            sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
            sa.Column(
                "event_id",
                postgresql.UUID(as_uuid=False),
                sa.ForeignKey("events.id"),
                nullable=False,
            ),
            sa.Column("window", sa.String(32), nullable=False, server_default="all"),
            sa.Column("article_count", sa.Integer(), server_default="0"),
            sa.Column("source_count", sa.Integer(), server_default="0"),
            sa.Column("country_count", sa.Integer(), server_default="0"),
            sa.Column("sentiment_shares", postgresql.JSONB(astext_type=sa.Text())),
            sa.Column("stance_shares", postgresql.JSONB(astext_type=sa.Text())),
            sa.Column("by_country", postgresql.JSONB(astext_type=sa.Text())),
            sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint("event_id", "window", name="uq_event_metric_snapshots_event_window"),
        )
    if not _has_index("event_metric_snapshots", "ix_event_metric_snapshots_event_id"):
        op.create_index(
            "ix_event_metric_snapshots_event_id", "event_metric_snapshots", ["event_id"]
        )

    if not _has_table("country_china_attitude_snapshots"):
        op.create_table(
            "country_china_attitude_snapshots",
            sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
            sa.Column("country_id", sa.String(8), nullable=False),
            sa.Column("window", sa.String(32), nullable=False, server_default="30d"),
            sa.Column("positive_count", sa.Integer(), server_default="0"),
            sa.Column("neutral_count", sa.Integer(), server_default="0"),
            sa.Column("negative_count", sa.Integer(), server_default="0"),
            sa.Column("unknown_count", sa.Integer(), server_default="0"),
            sa.Column("dominant_label", sa.String(32)),
            sa.Column("sample_article_ids", postgresql.JSONB(astext_type=sa.Text())),
            sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint(
                "country_id", "window", name="uq_country_china_attitude_country_window"
            ),
        )
    if not _has_index(
        "country_china_attitude_snapshots", "ix_country_china_attitude_snapshots_country_id"
    ):
        op.create_index(
            "ix_country_china_attitude_snapshots_country_id",
            "country_china_attitude_snapshots",
            ["country_id"],
        )


def downgrade() -> None:
    if _has_table("country_china_attitude_snapshots"):
        op.drop_table("country_china_attitude_snapshots")
    if _has_table("event_metric_snapshots"):
        op.drop_table("event_metric_snapshots")
    if _has_table("article_event_candidates"):
        op.drop_table("article_event_candidates")
    for idx in (
        "ix_events_fingerprint_hash",
        "ix_events_object_key",
        "ix_events_action_key",
        "ix_events_actor_key",
    ):
        if _has_index("events", idx):
            op.drop_index(idx, table_name="events")
    for col in (
        "fingerprint_hash",
        "qualifiers",
        "event_time",
        "object_key",
        "action_key",
        "actor_key",
    ):
        if _has_column("events", col):
            op.drop_column("events", col)

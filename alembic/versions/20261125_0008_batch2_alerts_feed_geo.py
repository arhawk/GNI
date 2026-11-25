"""Batch2: alerts persistence, feed_scope, geo precision, event_revisions, report_snapshots.

Revision ID: 20261125_0008
Revises: 20261124_0007
Create Date: 2026-11-25
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

revision: str = "20261125_0008"
down_revision: Union[str, None] = "20261124_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    return name in inspect(op.get_bind()).get_table_names()


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    if table not in inspect(bind).get_table_names():
        return False
    return column in {c["name"] for c in inspect(bind).get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"
    json_type = postgresql.JSONB() if is_pg else sa.JSON()

    if not _has_column("sources", "feed_scope"):
        op.add_column("sources", sa.Column("feed_scope", sa.String(64), nullable=True))

    if not _has_column("event_locations", "geographic_precision"):
        op.add_column("event_locations", sa.Column("geographic_precision", sa.String(32), nullable=True))
    if not _has_column("event_locations", "confidence"):
        op.add_column("event_locations", sa.Column("confidence", sa.Float(), nullable=True))
    if not _has_column("event_locations", "evidence"):
        op.add_column("event_locations", sa.Column("evidence", json_type, nullable=True))

    if not _has_table("event_revisions"):
        op.create_table(
            "event_revisions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("event_id", sa.String(36), sa.ForeignKey("events.id"), nullable=False),
            sa.Column("action", sa.String(32), nullable=False),
            sa.Column("payload", json_type),
            sa.Column("actor", sa.String(128)),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("ix_event_revisions_event_id", "event_revisions", ["event_id"])

    if not _has_table("alert_rules"):
        op.create_table(
            "alert_rules",
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("version", sa.String(64), nullable=False, server_default="v1"),
            sa.Column("thresholds", json_type),
            sa.Column("enabled", sa.Boolean(), server_default=sa.text("1" if not is_pg else "true")),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        )

    if not _has_table("alerts"):
        op.create_table(
            "alerts",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("category", sa.String(32), nullable=False),
            sa.Column("subcategory", sa.String(64), nullable=False),
            sa.Column("severity", sa.String(16), nullable=False),
            sa.Column("status", sa.String(32), nullable=False, server_default="OPEN"),
            sa.Column("deduplication_key", sa.String(256), nullable=False),
            sa.Column("title", sa.Text(), nullable=False),
            sa.Column("summary", sa.Text()),
            sa.Column("first_triggered_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("last_triggered_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("trigger_count", sa.Integer(), server_default="1"),
            sa.Column("window_start", sa.DateTime(timezone=True)),
            sa.Column("window_end", sa.DateTime(timezone=True)),
            sa.Column("evidence_snapshot", json_type),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("deduplication_key", name="uq_alerts_dedupe_key"),
        )

    if not _has_table("alert_events"):
        op.create_table(
            "alert_events",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("alert_id", sa.String(36), sa.ForeignKey("alerts.id"), nullable=False),
            sa.Column("action", sa.String(32), nullable=False),
            sa.Column("actor", sa.String(128)),
            sa.Column("payload", json_type),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("ix_alert_events_alert_id", "alert_events", ["alert_id"])

    if not _has_table("alert_evidence"):
        op.create_table(
            "alert_evidence",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("alert_id", sa.String(36), sa.ForeignKey("alerts.id"), nullable=False),
            sa.Column("article_id", sa.String(36), sa.ForeignKey("articles.id"), nullable=True),
            sa.Column("event_id", sa.String(36), sa.ForeignKey("events.id"), nullable=True),
            sa.Column("snapshot", json_type),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("ix_alert_evidence_alert_id", "alert_evidence", ["alert_id"])

    if not _has_table("report_snapshots"):
        op.create_table(
            "report_snapshots",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("report_type", sa.String(32), nullable=False),
            sa.Column("period", sa.String(64), nullable=False),
            sa.Column("schema_version", sa.String(64)),
            sa.Column("payload", json_type, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("report_type", "period", name="uq_report_snapshots_type_period"),
        )


def downgrade() -> None:
    for t in (
        "report_snapshots",
        "alert_evidence",
        "alert_events",
        "alerts",
        "alert_rules",
        "event_revisions",
    ):
        if _has_table(t):
            op.drop_table(t)
    if _has_column("event_locations", "evidence"):
        op.drop_column("event_locations", "evidence")
    if _has_column("event_locations", "confidence"):
        op.drop_column("event_locations", "confidence")
    if _has_column("event_locations", "geographic_precision"):
        op.drop_column("event_locations", "geographic_precision")
    if _has_column("sources", "feed_scope"):
        op.drop_column("sources", "feed_scope")

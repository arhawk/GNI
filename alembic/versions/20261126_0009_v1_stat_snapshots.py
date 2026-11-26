"""V1.0 traceable stat_snapshots table (methodology_v1.0 Section 9).

Revision ID: 20261126_0009
Revises: 20261125_0008
Create Date: 2026-11-26
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

revision: str = "20261126_0009"
down_revision: Union[str, None] = "20261125_0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    return name in inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    if not _has_table("stat_snapshots"):
        op.create_table(
            "stat_snapshots",
            sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
            sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
            sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
            sa.Column("scope_type", sa.String(16), nullable=False),
            sa.Column("scope_id", sa.String(64), nullable=False),
            sa.Column("article_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("positive_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("neutral_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("negative_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("unclassified_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("positive_rate", sa.Float(), nullable=True),
            sa.Column("neutral_rate", sa.Float(), nullable=True),
            sa.Column("negative_rate", sa.Float(), nullable=True),
            sa.Column("stance_coverage_rate", sa.Float(), nullable=True),
            sa.Column("methodology_version", sa.String(32), nullable=False),
            sa.Column("taxonomy_version", sa.String(32), nullable=False),
            sa.Column("analysis_version", sa.String(64), nullable=False),
            sa.Column("article_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column(
                "generated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
        )
        op.create_index(
            "ix_stat_snapshots_period_scope",
            "stat_snapshots",
            ["period_start", "period_end", "scope_type", "scope_id"],
        )


def downgrade() -> None:
    if _has_table("stat_snapshots"):
        op.drop_index("ix_stat_snapshots_period_scope", table_name="stat_snapshots")
        op.drop_table("stat_snapshots")

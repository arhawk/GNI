"""P1-D: metric_runs table.

Revision ID: 20261124_0004
Revises: 20261124_0003
Create Date: 2026-11-24
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261124_0004"
down_revision: Union[str, None] = "20261124_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "metric_runs",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("metric_definition_version", sa.String(64), nullable=False),
        sa.Column("relevance_weight_version", sa.String(64)),
        sa.Column("deduplication_method", sa.String(64)),
        sa.Column("timezone", sa.String(64)),
        sa.Column("window_start", sa.DateTime(timezone=True)),
        sa.Column("window_end", sa.DateTime(timezone=True)),
        sa.Column("country_scope", postgresql.JSONB()),
        sa.Column("source_scope", postgresql.JSONB()),
        sa.Column("topic_scope", postgresql.JSONB()),
        sa.Column("target_scope", sa.String(64)),
        sa.Column("numerator", sa.Float()),
        sa.Column("denominator", sa.Float()),
        sa.Column("excluded_count", sa.Integer()),
        sa.Column("missing_count", sa.Integer()),
        sa.Column("results", postgresql.JSONB()),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("stats", postgresql.JSONB()),
    )


def downgrade() -> None:
    op.drop_table("metric_runs")

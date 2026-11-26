"""Report narrative LLM task cache and audit table.

Revision ID: 20261126_0010
Revises: 20261126_0009
Create Date: 2026-11-26
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

revision: str = "20261126_0010"
down_revision: Union[str, None] = "20261126_0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    return name in inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    if not _has_table("report_narrative_tasks"):
        op.create_table(
            "report_narrative_tasks",
            sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
            sa.Column("report_type", sa.String(16), nullable=False),
            sa.Column("period", sa.String(64), nullable=False),
            sa.Column("task_type", sa.String(64), nullable=False),
            sa.Column("evidence_hash", sa.String(64), nullable=False),
            sa.Column("prompt_version", sa.String(64), nullable=False),
            sa.Column("model_version", sa.String(128), nullable=True),
            sa.Column("provider", sa.String(64), nullable=True),
            sa.Column("status", sa.String(32), nullable=False, server_default="completed"),
            sa.Column("prompt_tokens", sa.Integer(), nullable=True),
            sa.Column("completion_tokens", sa.Integer(), nullable=True),
            sa.Column("total_tokens", sa.Integer(), nullable=True),
            sa.Column("latency_ms", sa.Integer(), nullable=True),
            sa.Column("estimated_cost_usd", sa.Float(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("raw_output", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("validated_output", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("validation_result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.UniqueConstraint(
                "report_type",
                "period",
                "task_type",
                "prompt_version",
                name="uq_report_narrative_task_key",
            ),
        )
        op.create_index(
            "ix_report_narrative_tasks_lookup",
            "report_narrative_tasks",
            ["report_type", "period", "task_type"],
        )


def downgrade() -> None:
    if _has_table("report_narrative_tasks"):
        op.drop_index("ix_report_narrative_tasks_lookup", table_name="report_narrative_tasks")
        op.drop_table("report_narrative_tasks")

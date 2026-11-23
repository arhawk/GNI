"""P1-A initial schema: sources, health, jobs, articles stub.

Revision ID: 20261123_0001
Revises:
Create Date: 2026-11-23
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261123_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "countries",
        sa.Column("id", sa.String(8), primary_key=True),
        sa.Column("code", sa.String(8), nullable=False, unique=True),
        sa.Column("name", sa.String(128), nullable=False),
    )
    op.create_table(
        "organizations",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("country_id", sa.String(8), sa.ForeignKey("countries.id"), nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("organization_type", sa.String(64)),
        sa.Column("ownership_type", sa.String(64)),
        sa.Column("government_control_level", sa.String(32)),
    )
    op.create_table(
        "sources",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("organization_id", sa.String(64), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("country_id", sa.String(8), sa.ForeignKey("countries.id"), nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("canonical_url", sa.Text()),
        sa.Column("source_type", sa.String(64), nullable=False),
        sa.Column("ownership_type", sa.String(64)),
        sa.Column("funding_type", sa.String(64)),
        sa.Column("government_control_level", sa.String(32)),
        sa.Column("editorial_independence", sa.String(32)),
        sa.Column("language", sa.String(32)),
        sa.Column("timezone", sa.String(64)),
        sa.Column("access_method", sa.String(32), nullable=False),
        sa.Column("adapter_type", sa.String(64), nullable=False),
        sa.Column("terms_url", sa.Text()),
        sa.Column("robots_checked_at", sa.DateTime(timezone=True)),
        sa.Column("compliance_status", sa.String(32)),
        sa.Column("evidence_url", sa.Text()),
        sa.Column("classification_confidence", sa.String(16)),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("reviewed_by", sa.String(128)),
        sa.Column("active_status", sa.String(32)),
        sa.Column("verification_status", sa.String(32)),
        sa.Column("feed_or_api_url", sa.Text()),
        sa.Column("notes", sa.Text()),
        sa.Column("config", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "source_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("source_id", sa.String(64), sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("reviewer", sa.String(128)),
        sa.Column("decision", sa.String(64)),
        sa.Column("notes", sa.Text()),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "source_attribute_history",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("source_id", sa.String(64), sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("field", sa.String(128), nullable=False),
        sa.Column("old_value", sa.Text()),
        sa.Column("new_value", sa.Text()),
        sa.Column("reason", sa.Text()),
        sa.Column("changed_by", sa.String(128)),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "source_health",
        sa.Column("source_id", sa.String(64), sa.ForeignKey("sources.id"), primary_key=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True)),
        sa.Column("last_failure_at", sa.DateTime(timezone=True)),
        sa.Column("success_count", sa.Integer(), server_default="0"),
        sa.Column("failure_count", sa.Integer(), server_default="0"),
        sa.Column("success_rate", sa.Float()),
        sa.Column("error_message", sa.Text()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "ingestion_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("source_id", sa.String(64), sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("error", sa.Text()),
        sa.Column("stats", postgresql.JSONB()),
    )
    op.create_table(
        "articles",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("source_id", sa.String(64), sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("title", sa.Text()),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("canonical_url", sa.Text()),
        sa.Column("content_original", sa.Text()),
        sa.Column("content_clean", sa.Text()),
        sa.Column("language", sa.String(32)),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("content_hash", sa.String(64)),
        sa.Column("title_hash", sa.String(64)),
        sa.Column("quality_status", sa.String(32)),
        sa.Column("source_timezone", sa.String(64)),
        sa.Column("time_precision", sa.String(32)),
        sa.UniqueConstraint("source_id", "url", name="uq_articles_source_url"),
    )
    op.create_index("ix_articles_source_id", "articles", ["source_id"])
    op.create_index("ix_ingestion_jobs_source_id", "ingestion_jobs", ["source_id"])


def downgrade() -> None:
    op.drop_index("ix_ingestion_jobs_source_id", table_name="ingestion_jobs")
    op.drop_index("ix_articles_source_id", table_name="articles")
    op.drop_table("articles")
    op.drop_table("ingestion_jobs")
    op.drop_table("source_health")
    op.drop_table("source_attribute_history")
    op.drop_table("source_reviews")
    op.drop_table("sources")
    op.drop_table("organizations")
    op.drop_table("countries")

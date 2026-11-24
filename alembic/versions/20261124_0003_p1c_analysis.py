"""P1-C: relevance assessments, china spans, analyses.

Revision ID: 20261124_0003
Revises: 20261124_0002
Create Date: 2026-11-24
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261124_0003"
down_revision: Union[str, None] = "20261124_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("articles", sa.Column("analysis_status", sa.String(32), server_default="pending"))
    op.add_column("articles", sa.Column("fulltext_screening_label", sa.String(64)))
    op.add_column("articles", sa.Column("china_relevance_level", sa.String(32)))
    op.add_column("articles", sa.Column("china_relevance_weight", sa.Float()))
    op.add_column("articles", sa.Column("analyzed_at", sa.DateTime(timezone=True)))

    op.create_table(
        "article_relevance_assessments",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("article_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("articles.id"), nullable=False),
        sa.Column(
            "article_version_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("article_versions.id"),
            nullable=True,
        ),
        sa.Column("relevance_level", sa.String(32), nullable=False),
        sa.Column("relevance_weight", sa.Float()),
        sa.Column("content_share_estimate", sa.Float()),
        sa.Column("headline_prominence", sa.String(32)),
        sa.Column("thesis_contribution", sa.String(32)),
        sa.Column("china_actor_role", sa.String(32)),
        sa.Column("analysis_depth", sa.String(32)),
        sa.Column("reasoning_summary", sa.Text()),
        sa.Column("assessment_version", sa.String(64)),
        sa.Column("review_status", sa.String(32)),
        sa.Column("features", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_article_relevance_article_id", "article_relevance_assessments", ["article_id"])

    op.create_table(
        "article_china_spans",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("article_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("articles.id"), nullable=False),
        sa.Column(
            "article_version_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("article_versions.id"),
            nullable=True,
        ),
        sa.Column("paragraph_index", sa.Integer()),
        sa.Column("char_start", sa.Integer()),
        sa.Column("char_end", sa.Integer()),
        sa.Column("text_original", sa.Text(), nullable=False),
        sa.Column("language", sa.String(32)),
        sa.Column("span_type", sa.String(64)),
        sa.Column("related_entities", postgresql.JSONB()),
        sa.Column("candidate_targets", postgresql.JSONB()),
        sa.Column("relevance_reason", sa.Text()),
        sa.Column("extraction_confidence", sa.Float()),
        sa.Column("validation_status", sa.String(32)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_article_china_spans_article_id", "article_china_spans", ["article_id"])

    op.create_table(
        "analysis_runs",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("provider", sa.String(64)),
        sa.Column("model_name", sa.String(128)),
        sa.Column("prompt_version", sa.String(64)),
        sa.Column("schema_version", sa.String(64)),
        sa.Column("taxonomy_version", sa.String(64)),
        sa.Column("relevance_weight_version", sa.String(64)),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("error", sa.Text()),
        sa.Column("token_usage", sa.Integer()),
        sa.Column("estimated_cost_usd", sa.Float()),
        sa.Column("stats", postgresql.JSONB()),
    )

    op.create_table(
        "article_analyses",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("article_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("articles.id"), nullable=False),
        sa.Column(
            "analysis_run_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("analysis_runs.id"),
            nullable=True,
        ),
        sa.Column(
            "article_version_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("article_versions.id"),
            nullable=True,
        ),
        sa.Column("provider", sa.String(64)),
        sa.Column("model_name", sa.String(128)),
        sa.Column("prompt_version", sa.String(64)),
        sa.Column("schema_version", sa.String(64)),
        sa.Column("taxonomy_version", sa.String(64)),
        sa.Column("relevance_weight_version", sa.String(64)),
        sa.Column("analysis_status", sa.String(32)),
        sa.Column("confidence", sa.Float()),
        sa.Column("token_usage", sa.Integer()),
        sa.Column("estimated_cost_usd", sa.Float()),
        sa.Column("structured_result", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_article_analyses_article_id", "article_analyses", ["article_id"])


def downgrade() -> None:
    op.drop_index("ix_article_analyses_article_id", table_name="article_analyses")
    op.drop_table("article_analyses")
    op.drop_table("analysis_runs")
    op.drop_index("ix_article_china_spans_article_id", table_name="article_china_spans")
    op.drop_table("article_china_spans")
    op.drop_index("ix_article_relevance_article_id", table_name="article_relevance_assessments")
    op.drop_table("article_relevance_assessments")
    op.drop_column("articles", "analyzed_at")
    op.drop_column("articles", "china_relevance_weight")
    op.drop_column("articles", "china_relevance_level")
    op.drop_column("articles", "fulltext_screening_label")
    op.drop_column("articles", "analysis_status")

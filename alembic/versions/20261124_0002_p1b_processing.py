"""P1-B: article_versions, article_screenings, processing fields.

Revision ID: 20261124_0002
Revises: 20261123_0001
Create Date: 2026-11-24
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261124_0002"
down_revision: Union[str, None] = "20261123_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "articles",
        sa.Column("processing_status", sa.String(32), server_default="pending"),
    )
    op.add_column(
        "articles",
        sa.Column("duplicate_of_article_id", postgresql.UUID(as_uuid=False), nullable=True),
    )
    op.add_column(
        "articles",
        sa.Column("exclude_from_metrics", sa.Boolean(), server_default=sa.false()),
    )
    op.add_column("articles", sa.Column("processed_at", sa.DateTime(timezone=True)))
    op.add_column("articles", sa.Column("title_screening_label", sa.String(32)))
    op.add_column("articles", sa.Column("title_screening_priority", sa.String(8)))
    op.create_foreign_key(
        "fk_articles_duplicate_of",
        "articles",
        "articles",
        ["duplicate_of_article_id"],
        ["id"],
    )

    op.create_table(
        "article_versions",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("article_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("articles.id"), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("extraction_method", sa.String(64)),
        sa.Column("raw_html_excerpt", sa.Text()),
        sa.Column("content_clean", sa.Text()),
        sa.Column("content_hash", sa.String(64)),
        sa.Column("language", sa.String(32)),
        sa.Column("char_count", sa.Integer()),
        sa.Column("quality_status", sa.String(32)),
        sa.Column("error_message", sa.Text()),
        sa.Column("extracted_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_article_versions_article_id", "article_versions", ["article_id"])

    op.create_table(
        "article_screenings",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("article_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("articles.id"), nullable=False),
        sa.Column(
            "article_version_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("article_versions.id"),
            nullable=True,
        ),
        sa.Column("stage", sa.String(32), nullable=False),
        sa.Column("screening_label", sa.String(64), nullable=False),
        sa.Column("reason_codes", postgresql.JSONB()),
        sa.Column("matched_entities", postgresql.JSONB()),
        sa.Column("supporting_paragraph_ids", postgresql.JSONB()),
        sa.Column("confidence", sa.Float()),
        sa.Column("requires_human_review", sa.Boolean(), server_default=sa.false()),
        sa.Column("priority", sa.String(8)),
        sa.Column("rule_version", sa.String(64)),
        sa.Column("entity_dictionary_version", sa.String(64)),
        sa.Column("schema_version", sa.String(64)),
        sa.Column("input_hash", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_article_screenings_article_id", "article_screenings", ["article_id"])
    op.create_index(
        "ix_article_screenings_label",
        "article_screenings",
        ["screening_label", "created_at"],
    )

    op.create_table(
        "processing_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("error", sa.Text()),
        sa.Column("stats", postgresql.JSONB()),
    )


def downgrade() -> None:
    op.drop_table("processing_jobs")
    op.drop_index("ix_article_screenings_label", table_name="article_screenings")
    op.drop_index("ix_article_screenings_article_id", table_name="article_screenings")
    op.drop_table("article_screenings")
    op.drop_index("ix_article_versions_article_id", table_name="article_versions")
    op.drop_table("article_versions")
    op.drop_constraint("fk_articles_duplicate_of", "articles", type_="foreignkey")
    op.drop_column("articles", "title_screening_priority")
    op.drop_column("articles", "title_screening_label")
    op.drop_column("articles", "processed_at")
    op.drop_column("articles", "exclude_from_metrics")
    op.drop_column("articles", "duplicate_of_article_id")
    op.drop_column("articles", "processing_status")

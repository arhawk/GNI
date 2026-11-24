"""Data layers core: collection_tasks, raw_documents, discovered_articles, pipeline_state.

Revision ID: 20261124_0006
Revises: 20261124_0005
Create Date: 2026-11-24
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261124_0006"
down_revision: Union[str, None] = "20261124_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "collection_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("task_type", sa.String(32), nullable=False),
        sa.Column("source_id", sa.String(64), sa.ForeignKey("sources.id")),
        sa.Column("status", sa.String(32), nullable=False, server_default="running"),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("error", sa.Text()),
        sa.Column("stats", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("code_version", sa.String(64)),
        sa.Column("config_snapshot", sa.Text()),
        sa.Column("legacy_job_id", sa.String(64)),
    )
    op.create_index("ix_collection_tasks_source_id", "collection_tasks", ["source_id"])

    op.create_table(
        "raw_documents",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("source_id", sa.String(64), sa.ForeignKey("sources.id"), nullable=False),
        sa.Column(
            "collection_task_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("collection_tasks.id"),
        ),
        sa.Column("discovered_article_id", postgresql.UUID(as_uuid=False)),
        sa.Column("url", sa.Text()),
        sa.Column("content_type", sa.String(32), server_default="rss_item"),
        sa.Column("payload_text", sa.Text()),
        sa.Column("payload_hash", sa.String(64)),
        sa.Column("object_key", sa.String(512)),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_raw_documents_source_id", "raw_documents", ["source_id"])
    op.create_index("ix_raw_documents_collection_task_id", "raw_documents", ["collection_task_id"])
    op.create_index(
        "ix_raw_documents_discovered_article_id", "raw_documents", ["discovered_article_id"]
    )

    op.add_column(
        "articles",
        sa.Column("pipeline_state", sa.String(48), server_default="DISCOVERED", nullable=False),
    )
    op.add_column(
        "articles",
        sa.Column("latest_raw_document_id", postgresql.UUID(as_uuid=False)),
    )
    op.add_column(
        "articles",
        sa.Column("latest_article_version_id", postgresql.UUID(as_uuid=False)),
    )
    op.create_index("ix_articles_pipeline_state", "articles", ["pipeline_state"])

    op.create_table(
        "discovered_articles",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("source_id", sa.String(64), sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("canonical_url", sa.Text()),
        sa.Column("title", sa.Text()),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("discovered_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "raw_document_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("raw_documents.id"),
        ),
        sa.Column(
            "article_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("articles.id"),
        ),
        sa.Column("status", sa.String(32), server_default="discovered"),
        sa.Column(
            "collection_task_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("collection_tasks.id"),
        ),
        sa.UniqueConstraint("source_id", "url", name="uq_discovered_source_url"),
    )
    op.create_index("ix_discovered_articles_source_id", "discovered_articles", ["source_id"])
    op.create_index("ix_discovered_articles_article_id", "discovered_articles", ["article_id"])

    op.create_foreign_key(
        "fk_raw_documents_discovered_article_id",
        "raw_documents",
        "discovered_articles",
        ["discovered_article_id"],
        ["id"],
    )

    # Backfill existing articles as RAW_STORED (already ingested historically).
    op.execute(
        sa.text(
            "UPDATE articles SET pipeline_state = 'RAW_STORED' "
            "WHERE processing_status = 'pending' AND pipeline_state = 'DISCOVERED'"
        )
    )
    op.execute(
        sa.text(
            "UPDATE articles SET pipeline_state = 'EXTRACTION_COMPLETED' "
            "WHERE processing_status = 'done' AND analysis_status = 'pending'"
        )
    )
    op.execute(
        sa.text(
            "UPDATE articles SET pipeline_state = 'ANALYSIS_COMPLETED' "
            "WHERE analysis_status IN ('completed', 'insufficient_evidence')"
        )
    )
    op.execute(
        sa.text(
            "UPDATE articles SET pipeline_state = 'AVAILABLE_FOR_ANALYTICS' "
            "WHERE china_relevance_level IN ('core', 'substantial', 'secondary') "
            "AND analysis_status = 'completed'"
        )
    )
    op.execute(
        sa.text(
            "UPDATE articles SET pipeline_state = 'DEDUPLICATED' "
            "WHERE exclude_from_metrics IS TRUE OR quality_status = 'duplicate'"
        )
    )


def downgrade() -> None:
    op.drop_constraint("fk_raw_documents_discovered_article_id", "raw_documents", type_="foreignkey")
    op.drop_table("discovered_articles")
    op.drop_index("ix_articles_pipeline_state", table_name="articles")
    op.drop_column("articles", "latest_article_version_id")
    op.drop_column("articles", "latest_raw_document_id")
    op.drop_column("articles", "pipeline_state")
    op.drop_table("raw_documents")
    op.drop_index("ix_collection_tasks_source_id", table_name="collection_tasks")
    op.drop_table("collection_tasks")

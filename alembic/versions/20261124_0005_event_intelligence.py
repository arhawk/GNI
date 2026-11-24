"""Event Intelligence tables (proto-Event / Phase 2 ready).

Revision ID: 20261124_0005
Revises: 20261124_0004
Create Date: 2026-11-24
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261124_0005"
down_revision: Union[str, None] = "20261124_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("parent_event_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("events.id")),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text()),
        sa.Column("event_type", sa.String(64)),
        sa.Column("status", sa.String(32), server_default="proto"),
        sa.Column("importance_score", sa.Float()),
        sa.Column("window_start", sa.DateTime(timezone=True)),
        sa.Column("window_end", sa.DateTime(timezone=True)),
        sa.Column("has_physical_location", sa.Boolean(), server_default=sa.false()),
        sa.Column("schema_version", sa.String(64), server_default="event_v0.1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "event_locations",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("event_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("location_type", sa.String(64), nullable=False),
        sa.Column("label", sa.String(256)),
        sa.Column("country_id", sa.String(8)),
        sa.Column("lat", sa.Float()),
        sa.Column("lon", sa.Float()),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_event_locations_event_id", "event_locations", ["event_id"])
    op.create_table(
        "event_participants",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("event_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("participant_id", sa.String(128), nullable=False),
        sa.Column("participant_name", sa.String(256)),
        sa.Column("role", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_event_participants_event_id", "event_participants", ["event_id"])
    op.create_table(
        "event_articles",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("event_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("article_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("articles.id"), nullable=False),
        sa.Column("relation", sa.String(32), server_default="covers"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("event_id", "article_id", name="uq_event_articles"),
    )
    op.create_index("ix_event_articles_event_id", "event_articles", ["event_id"])
    op.create_index("ix_event_articles_article_id", "event_articles", ["article_id"])
    op.create_table(
        "narrative_clusters",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("event_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("label", sa.String(256), nullable=False),
        sa.Column("frame_id", sa.String(64)),
        sa.Column("summary", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_narrative_clusters_event_id", "narrative_clusters", ["event_id"])
    op.create_table(
        "event_narrative_evidence",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "narrative_cluster_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("narrative_clusters.id"),
            nullable=False,
        ),
        sa.Column("article_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("articles.id"), nullable=False),
        sa.Column("span_id", postgresql.UUID(as_uuid=False)),
        sa.Column("quote", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_event_narrative_evidence_cluster",
        "event_narrative_evidence",
        ["narrative_cluster_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_event_narrative_evidence_cluster", table_name="event_narrative_evidence")
    op.drop_table("event_narrative_evidence")
    op.drop_index("ix_narrative_clusters_event_id", table_name="narrative_clusters")
    op.drop_table("narrative_clusters")
    op.drop_index("ix_event_articles_article_id", table_name="event_articles")
    op.drop_index("ix_event_articles_event_id", table_name="event_articles")
    op.drop_table("event_articles")
    op.drop_index("ix_event_participants_event_id", table_name="event_participants")
    op.drop_table("event_participants")
    op.drop_index("ix_event_locations_event_id", table_name="event_locations")
    op.drop_table("event_locations")
    op.drop_table("events")

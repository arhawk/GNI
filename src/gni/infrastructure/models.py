"""SQLAlchemy models for P1-A / P1-B / P1-C."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator


class PortableUUID(TypeDecorator):
    """UUID stored as str on SQLite, native UUID on PostgreSQL."""

    impl = String(36)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(UUID(as_uuid=False))
        return dialect.type_descriptor(String(36))


class PortableJSON(TypeDecorator):
    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(JSON())


class Base(DeclarativeBase):
    pass


class Country(Base):
    __tablename__ = "countries"

    id: Mapped[str] = mapped_column(String(8), primary_key=True)
    code: Mapped[str] = mapped_column(String(8), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)

    organizations: Mapped[list[Organization]] = relationship(back_populates="country")


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    country_id: Mapped[str] = mapped_column(ForeignKey("countries.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    organization_type: Mapped[str | None] = mapped_column(String(64))
    ownership_type: Mapped[str | None] = mapped_column(String(64))
    government_control_level: Mapped[str | None] = mapped_column(String(32))

    country: Mapped[Country] = relationship(back_populates="organizations")
    sources: Mapped[list[Source]] = relationship(back_populates="organization")


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    country_id: Mapped[str] = mapped_column(ForeignKey("countries.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    canonical_url: Mapped[str | None] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    ownership_type: Mapped[str | None] = mapped_column(String(64))
    funding_type: Mapped[str | None] = mapped_column(String(64))
    government_control_level: Mapped[str | None] = mapped_column(String(32))
    editorial_independence: Mapped[str | None] = mapped_column(String(32))
    language: Mapped[str | None] = mapped_column(String(32))
    timezone: Mapped[str | None] = mapped_column(String(64))
    access_method: Mapped[str] = mapped_column(String(32), nullable=False, default="rss")
    adapter_type: Mapped[str] = mapped_column(String(64), nullable=False, default="rss_adapter")
    terms_url: Mapped[str | None] = mapped_column(Text)
    robots_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    compliance_status: Mapped[str] = mapped_column(String(32), default="pending")
    evidence_url: Mapped[str | None] = mapped_column(Text)
    classification_confidence: Mapped[str | None] = mapped_column(String(16))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by: Mapped[str | None] = mapped_column(String(128))
    active_status: Mapped[str] = mapped_column(String(32), default="candidate")
    verification_status: Mapped[str] = mapped_column(String(32), default="unverified")
    feed_or_api_url: Mapped[str | None] = mapped_column(Text)
    # GENERAL_NEWS | INTERNATIONAL_NEWS | CHINA_FOCUSED | TOPIC_SPECIFIC | GOVERNMENT_RELEASES
    feed_scope: Mapped[str | None] = mapped_column(String(64))
    notes: Mapped[str | None] = mapped_column(Text)
    config: Mapped[dict[str, Any] | None] = mapped_column(PortableJSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    organization: Mapped[Organization] = relationship(back_populates="sources")
    health: Mapped[SourceHealth | None] = relationship(back_populates="source", uselist=False)


class SourceReview(Base):
    __tablename__ = "source_reviews"

    id: Mapped[str] = mapped_column(PortableUUID, primary_key=True, default=lambda: str(uuid4()))
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"), nullable=False)
    reviewer: Mapped[str | None] = mapped_column(String(128))
    decision: Mapped[str | None] = mapped_column(String(64))
    notes: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SourceAttributeHistory(Base):
    __tablename__ = "source_attribute_history"

    id: Mapped[str] = mapped_column(PortableUUID, primary_key=True, default=lambda: str(uuid4()))
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"), nullable=False)
    field: Mapped[str] = mapped_column(String(128), nullable=False)
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)
    changed_by: Mapped[str | None] = mapped_column(String(128))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SourceHealth(Base):
    __tablename__ = "source_health"

    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"), primary_key=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)
    success_rate: Mapped[float | None] = mapped_column(Float)
    error_message: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    source: Mapped[Source] = relationship(back_populates="health")


class CollectionTask(Base):
    """Cross-layer task lineage (dual-write with ingestion/processing/analysis jobs)."""

    __tablename__ = "collection_tasks"

    id: Mapped[str] = mapped_column(PortableUUID, primary_key=True, default=lambda: str(uuid4()))
    task_type: Mapped[str] = mapped_column(String(32), nullable=False)  # ingest|process|analyze|backfill
    source_id: Mapped[str | None] = mapped_column(ForeignKey("sources.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="running")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
    stats: Mapped[dict[str, Any] | None] = mapped_column(PortableJSON)
    code_version: Mapped[str | None] = mapped_column(String(64))
    config_snapshot: Mapped[str | None] = mapped_column(Text)
    legacy_job_id: Mapped[str | None] = mapped_column(String(64))  # ingestion_jobs / etc.


class RawDocument(Base):
    """Layer 1 — immutable-ish raw capture (append-only)."""

    __tablename__ = "raw_documents"

    id: Mapped[str] = mapped_column(PortableUUID, primary_key=True, default=lambda: str(uuid4()))
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"), nullable=False, index=True)
    collection_task_id: Mapped[str | None] = mapped_column(
        PortableUUID, ForeignKey("collection_tasks.id"), nullable=True, index=True
    )
    discovered_article_id: Mapped[str | None] = mapped_column(PortableUUID, nullable=True, index=True)
    url: Mapped[str | None] = mapped_column(Text)
    content_type: Mapped[str] = mapped_column(String(32), default="rss_item")  # rss_item|api_json|html
    payload_text: Mapped[str | None] = mapped_column(Text)
    payload_hash: Mapped[str | None] = mapped_column(String(64))
    object_key: Mapped[str | None] = mapped_column(String(512))  # R2 reserved
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DiscoveredArticle(Base):
    """Layer 1 — discovery record before/alongside article promotion."""

    __tablename__ = "discovered_articles"
    __table_args__ = (UniqueConstraint("source_id", "url", name="uq_discovered_source_url"),)

    id: Mapped[str] = mapped_column(PortableUUID, primary_key=True, default=lambda: str(uuid4()))
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"), nullable=False, index=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_url: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    raw_document_id: Mapped[str | None] = mapped_column(
        PortableUUID, ForeignKey("raw_documents.id"), nullable=True
    )
    article_id: Mapped[str | None] = mapped_column(
        PortableUUID, ForeignKey("articles.id"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(32), default="discovered")  # discovered|promoted|rejected
    collection_task_id: Mapped[str | None] = mapped_column(
        PortableUUID, ForeignKey("collection_tasks.id"), nullable=True
    )


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id: Mapped[str] = mapped_column(PortableUUID, primary_key=True, default=lambda: str(uuid4()))
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="running")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
    stats: Mapped[dict[str, Any] | None] = mapped_column(PortableJSON)


class Article(Base):
    __tablename__ = "articles"
    __table_args__ = (UniqueConstraint("source_id", "url", name="uq_articles_source_url"),)

    id: Mapped[str] = mapped_column(PortableUUID, primary_key=True, default=lambda: str(uuid4()))
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"), nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_url: Mapped[str | None] = mapped_column(Text)
    content_original: Mapped[str | None] = mapped_column(Text)
    content_clean: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(String(32))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    content_hash: Mapped[str | None] = mapped_column(String(64))
    title_hash: Mapped[str | None] = mapped_column(String(64))
    quality_status: Mapped[str] = mapped_column(String(32), default="rss_stub")
    source_timezone: Mapped[str | None] = mapped_column(String(64))
    time_precision: Mapped[str | None] = mapped_column(String(32))
    processing_status: Mapped[str] = mapped_column(String(32), default="pending")
    pipeline_state: Mapped[str] = mapped_column(String(48), default="DISCOVERED", index=True)
    latest_raw_document_id: Mapped[str | None] = mapped_column(PortableUUID, nullable=True)
    latest_article_version_id: Mapped[str | None] = mapped_column(PortableUUID, nullable=True)
    duplicate_of_article_id: Mapped[str | None] = mapped_column(
        PortableUUID, ForeignKey("articles.id"), nullable=True
    )
    exclude_from_metrics: Mapped[bool] = mapped_column(Boolean, default=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    title_screening_label: Mapped[str | None] = mapped_column(String(32))
    title_screening_priority: Mapped[str | None] = mapped_column(String(8))
    analysis_status: Mapped[str] = mapped_column(String(32), default="pending")
    fulltext_screening_label: Mapped[str | None] = mapped_column(String(64))
    china_relevance_level: Mapped[str | None] = mapped_column(String(32))
    china_relevance_weight: Mapped[float | None] = mapped_column(Float)
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    versions: Mapped[list["ArticleVersion"]] = relationship(
        "ArticleVersion", back_populates="article"
    )
    screenings: Mapped[list["ArticleScreening"]] = relationship(
        "ArticleScreening", back_populates="article"
    )


class ArticleVersion(Base):
    __tablename__ = "article_versions"

    id: Mapped[str] = mapped_column(PortableUUID, primary_key=True, default=lambda: str(uuid4()))
    article_id: Mapped[str] = mapped_column(ForeignKey("articles.id"), nullable=False, index=True)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    extraction_method: Mapped[str | None] = mapped_column(String(64))
    raw_html_excerpt: Mapped[str | None] = mapped_column(Text)
    content_clean: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str | None] = mapped_column(String(64))
    language: Mapped[str | None] = mapped_column(String(32))
    char_count: Mapped[int | None] = mapped_column(Integer)
    quality_status: Mapped[str] = mapped_column(String(32), default="ok")
    error_message: Mapped[str | None] = mapped_column(Text)
    extracted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    article: Mapped[Article] = relationship(back_populates="versions")


class ArticleScreening(Base):
    __tablename__ = "article_screenings"

    id: Mapped[str] = mapped_column(PortableUUID, primary_key=True, default=lambda: str(uuid4()))
    article_id: Mapped[str] = mapped_column(ForeignKey("articles.id"), nullable=False, index=True)
    article_version_id: Mapped[str | None] = mapped_column(
        PortableUUID, ForeignKey("article_versions.id"), nullable=True
    )
    stage: Mapped[str] = mapped_column(String(32), nullable=False)  # title | fulltext
    screening_label: Mapped[str] = mapped_column(String(64), nullable=False)
    reason_codes: Mapped[list[Any] | None] = mapped_column(PortableJSON)
    matched_entities: Mapped[list[Any] | dict[str, Any] | None] = mapped_column(PortableJSON)
    supporting_paragraph_ids: Mapped[list[Any] | None] = mapped_column(PortableJSON)
    confidence: Mapped[float | None] = mapped_column(Float)
    requires_human_review: Mapped[bool] = mapped_column(Boolean, default=False)
    priority: Mapped[str | None] = mapped_column(String(8))
    rule_version: Mapped[str | None] = mapped_column(String(64))
    entity_dictionary_version: Mapped[str | None] = mapped_column(String(64))
    schema_version: Mapped[str | None] = mapped_column(String(64))
    input_hash: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    article: Mapped[Article] = relationship(back_populates="screenings")


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id: Mapped[str] = mapped_column(PortableUUID, primary_key=True, default=lambda: str(uuid4()))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="running")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
    stats: Mapped[dict[str, Any] | None] = mapped_column(PortableJSON)


class ArticleRelevanceAssessment(Base):
    __tablename__ = "article_relevance_assessments"

    id: Mapped[str] = mapped_column(PortableUUID, primary_key=True, default=lambda: str(uuid4()))
    article_id: Mapped[str] = mapped_column(ForeignKey("articles.id"), nullable=False, index=True)
    article_version_id: Mapped[str | None] = mapped_column(
        PortableUUID, ForeignKey("article_versions.id"), nullable=True
    )
    relevance_level: Mapped[str] = mapped_column(String(32), nullable=False)
    relevance_weight: Mapped[float | None] = mapped_column(Float)
    content_share_estimate: Mapped[float | None] = mapped_column(Float)
    headline_prominence: Mapped[str | None] = mapped_column(String(32))
    thesis_contribution: Mapped[str | None] = mapped_column(String(32))
    china_actor_role: Mapped[str | None] = mapped_column(String(32))
    analysis_depth: Mapped[str | None] = mapped_column(String(32))
    reasoning_summary: Mapped[str | None] = mapped_column(Text)
    assessment_version: Mapped[str | None] = mapped_column(String(64))
    review_status: Mapped[str] = mapped_column(String(32), default="auto")
    features: Mapped[dict[str, Any] | None] = mapped_column(PortableJSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ArticleChinaSpan(Base):
    __tablename__ = "article_china_spans"

    id: Mapped[str] = mapped_column(PortableUUID, primary_key=True, default=lambda: str(uuid4()))
    article_id: Mapped[str] = mapped_column(ForeignKey("articles.id"), nullable=False, index=True)
    article_version_id: Mapped[str | None] = mapped_column(
        PortableUUID, ForeignKey("article_versions.id"), nullable=True
    )
    paragraph_index: Mapped[int | None] = mapped_column(Integer)
    char_start: Mapped[int | None] = mapped_column(Integer)
    char_end: Mapped[int | None] = mapped_column(Integer)
    text_original: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str | None] = mapped_column(String(32))
    span_type: Mapped[str] = mapped_column(String(64), default="direct_mention")
    related_entities: Mapped[list[Any] | None] = mapped_column(PortableJSON)
    candidate_targets: Mapped[list[Any] | None] = mapped_column(PortableJSON)
    relevance_reason: Mapped[str | None] = mapped_column(Text)
    extraction_confidence: Mapped[float | None] = mapped_column(Float)
    validation_status: Mapped[str] = mapped_column(String(32), default="valid")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    id: Mapped[str] = mapped_column(PortableUUID, primary_key=True, default=lambda: str(uuid4()))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="running")
    provider: Mapped[str | None] = mapped_column(String(64))
    model_name: Mapped[str | None] = mapped_column(String(128))
    prompt_version: Mapped[str | None] = mapped_column(String(64))
    schema_version: Mapped[str | None] = mapped_column(String(64))
    taxonomy_version: Mapped[str | None] = mapped_column(String(64))
    relevance_weight_version: Mapped[str | None] = mapped_column(String(64))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
    token_usage: Mapped[int | None] = mapped_column(Integer)
    estimated_cost_usd: Mapped[float | None] = mapped_column(Float)
    stats: Mapped[dict[str, Any] | None] = mapped_column(PortableJSON)


class ArticleAnalysis(Base):
    __tablename__ = "article_analyses"

    id: Mapped[str] = mapped_column(PortableUUID, primary_key=True, default=lambda: str(uuid4()))
    article_id: Mapped[str] = mapped_column(ForeignKey("articles.id"), nullable=False, index=True)
    analysis_run_id: Mapped[str | None] = mapped_column(
        PortableUUID, ForeignKey("analysis_runs.id"), nullable=True
    )
    article_version_id: Mapped[str | None] = mapped_column(
        PortableUUID, ForeignKey("article_versions.id"), nullable=True
    )
    provider: Mapped[str | None] = mapped_column(String(64))
    model_name: Mapped[str | None] = mapped_column(String(128))
    prompt_version: Mapped[str | None] = mapped_column(String(64))
    schema_version: Mapped[str] = mapped_column(String(64), default="article_analysis_v0.2")
    taxonomy_version: Mapped[str | None] = mapped_column(String(64))
    relevance_weight_version: Mapped[str | None] = mapped_column(String(64))
    analysis_status: Mapped[str] = mapped_column(String(32), default="completed")
    confidence: Mapped[float | None] = mapped_column(Float)
    token_usage: Mapped[int | None] = mapped_column(Integer)
    estimated_cost_usd: Mapped[float | None] = mapped_column(Float)
    structured_result: Mapped[dict[str, Any] | None] = mapped_column(PortableJSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MetricRun(Base):
    __tablename__ = "metric_runs"

    id: Mapped[str] = mapped_column(PortableUUID, primary_key=True, default=lambda: str(uuid4()))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="success")
    metric_definition_version: Mapped[str] = mapped_column(String(64), nullable=False)
    relevance_weight_version: Mapped[str | None] = mapped_column(String(64))
    deduplication_method: Mapped[str | None] = mapped_column(String(64))
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    window_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    country_scope: Mapped[list[Any] | None] = mapped_column(PortableJSON)
    source_scope: Mapped[list[Any] | None] = mapped_column(PortableJSON)
    topic_scope: Mapped[list[Any] | None] = mapped_column(PortableJSON)
    target_scope: Mapped[str | None] = mapped_column(String(64))
    numerator: Mapped[float | None] = mapped_column(Float)
    denominator: Mapped[float | None] = mapped_column(Float)
    excluded_count: Mapped[int | None] = mapped_column(Integer)
    missing_count: Mapped[int | None] = mapped_column(Integer)
    results: Mapped[dict[str, Any] | None] = mapped_column(PortableJSON)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    stats: Mapped[dict[str, Any] | None] = mapped_column(PortableJSON)


class Event(Base):
    """Unique real-world event (Phase 1: proto / fingerprint MVP; Phase 2: full clustering)."""

    __tablename__ = "events"

    id: Mapped[str] = mapped_column(PortableUUID, primary_key=True, default=lambda: str(uuid4()))
    parent_event_id: Mapped[str | None] = mapped_column(
        PortableUUID, ForeignKey("events.id"), nullable=True
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    event_type: Mapped[str | None] = mapped_column(String(64))  # taxonomy topic hint, not threat-class
    status: Mapped[str] = mapped_column(String(32), default="proto")  # proto | active | closed
    importance_score: Mapped[float | None] = mapped_column(Float)
    window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    window_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    has_physical_location: Mapped[bool] = mapped_column(Boolean, default=False)
    # Event Fingerprint canonical keys (MVP)
    actor_key: Mapped[str | None] = mapped_column(String(128), index=True)
    action_key: Mapped[str | None] = mapped_column(String(64), index=True)
    object_key: Mapped[str | None] = mapped_column(String(256), index=True)
    event_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    qualifiers: Mapped[dict[str, Any] | None] = mapped_column(PortableJSON)
    fingerprint_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    schema_version: Mapped[str] = mapped_column(String(64), default="event_v0.2")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ArticleEventCandidate(Base):
    """Per-article event candidate fingerprint (append-only)."""

    __tablename__ = "article_event_candidates"

    id: Mapped[str] = mapped_column(PortableUUID, primary_key=True, default=lambda: str(uuid4()))
    article_id: Mapped[str] = mapped_column(ForeignKey("articles.id"), nullable=False, index=True)
    article_version_id: Mapped[str | None] = mapped_column(
        PortableUUID, ForeignKey("article_versions.id"), nullable=True
    )
    analysis_id: Mapped[str | None] = mapped_column(
        PortableUUID, ForeignKey("article_analyses.id"), nullable=True
    )
    fingerprint: Mapped[dict[str, Any]] = mapped_column(PortableJSON, nullable=False)
    evidence: Mapped[dict[str, Any] | None] = mapped_column(PortableJSON)
    schema_version: Mapped[str] = mapped_column(String(64), default="event_fingerprint_v0.1")
    prompt_version: Mapped[str | None] = mapped_column(String(64))
    confidence: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EventMetricSnapshot(Base):
    """Rolled-up article metrics for an event (recomputable)."""

    __tablename__ = "event_metric_snapshots"
    __table_args__ = (
        UniqueConstraint("event_id", "window", name="uq_event_metric_snapshots_event_window"),
    )

    id: Mapped[str] = mapped_column(PortableUUID, primary_key=True, default=lambda: str(uuid4()))
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"), nullable=False, index=True)
    window: Mapped[str] = mapped_column(String(32), nullable=False, default="all")
    article_count: Mapped[int] = mapped_column(Integer, default=0)
    source_count: Mapped[int] = mapped_column(Integer, default=0)
    country_count: Mapped[int] = mapped_column(Integer, default=0)
    sentiment_shares: Mapped[dict[str, Any] | None] = mapped_column(PortableJSON)
    stance_shares: Mapped[dict[str, Any] | None] = mapped_column(PortableJSON)
    by_country: Mapped[dict[str, Any] | None] = mapped_column(PortableJSON)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CountryChinaAttitudeSnapshot(Base):
    """Country-level China-attitude rollup for attitude map (monitored media sample)."""

    __tablename__ = "country_china_attitude_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "country_id", "window", name="uq_country_china_attitude_country_window"
        ),
    )

    id: Mapped[str] = mapped_column(PortableUUID, primary_key=True, default=lambda: str(uuid4()))
    country_id: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    window: Mapped[str] = mapped_column(String(32), nullable=False, default="30d")
    positive_count: Mapped[int] = mapped_column(Integer, default=0)
    neutral_count: Mapped[int] = mapped_column(Integer, default=0)
    negative_count: Mapped[int] = mapped_column(Integer, default=0)
    unknown_count: Mapped[int] = mapped_column(Integer, default=0)
    dominant_label: Mapped[str | None] = mapped_column(String(32))  # positive|neutral|negative|none
    sample_article_ids: Mapped[list[Any] | None] = mapped_column(PortableJSON)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EventLocation(Base):
    __tablename__ = "event_locations"

    id: Mapped[str] = mapped_column(PortableUUID, primary_key=True, default=lambda: str(uuid4()))
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"), nullable=False, index=True)
    location_type: Mapped[str] = mapped_column(String(64), nullable=False)
    # EVENT_LOCATION | ANNOUNCEMENT_LOCATION | PARTICIPANT_LOCATION | AFFECTED_AREA | RELATED_LOCATION
    label: Mapped[str | None] = mapped_column(String(256))
    country_id: Mapped[str | None] = mapped_column(String(8))
    lat: Mapped[float | None] = mapped_column(Float)
    lon: Mapped[float | None] = mapped_column(Float)
    # city | region | country | maritime | unknown
    geographic_precision: Mapped[str | None] = mapped_column(String(32))
    confidence: Mapped[float | None] = mapped_column(Float)
    evidence: Mapped[dict[str, Any] | None] = mapped_column(PortableJSON)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EventParticipant(Base):
    __tablename__ = "event_participants"

    id: Mapped[str] = mapped_column(PortableUUID, primary_key=True, default=lambda: str(uuid4()))
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"), nullable=False, index=True)
    participant_id: Mapped[str] = mapped_column(String(128), nullable=False)
    participant_name: Mapped[str | None] = mapped_column(String(256))
    role: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EventArticle(Base):
    __tablename__ = "event_articles"
    __table_args__ = (UniqueConstraint("event_id", "article_id", name="uq_event_articles"),)

    id: Mapped[str] = mapped_column(PortableUUID, primary_key=True, default=lambda: str(uuid4()))
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"), nullable=False, index=True)
    article_id: Mapped[str] = mapped_column(ForeignKey("articles.id"), nullable=False, index=True)
    relation: Mapped[str] = mapped_column(String(32), default="covers")  # covers | follow_up | background
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class NarrativeCluster(Base):
    __tablename__ = "narrative_clusters"

    id: Mapped[str] = mapped_column(PortableUUID, primary_key=True, default=lambda: str(uuid4()))
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(256), nullable=False)
    frame_id: Mapped[str | None] = mapped_column(String(64))
    summary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EventNarrativeEvidence(Base):
    __tablename__ = "event_narrative_evidence"

    id: Mapped[str] = mapped_column(PortableUUID, primary_key=True, default=lambda: str(uuid4()))
    narrative_cluster_id: Mapped[str] = mapped_column(
        ForeignKey("narrative_clusters.id"), nullable=False, index=True
    )
    article_id: Mapped[str] = mapped_column(ForeignKey("articles.id"), nullable=False, index=True)
    span_id: Mapped[str | None] = mapped_column(PortableUUID, nullable=True)
    quote: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EventRevision(Base):
    """Audit log for event merge / split / correct / lock."""

    __tablename__ = "event_revisions"

    id: Mapped[str] = mapped_column(PortableUUID, primary_key=True, default=lambda: str(uuid4()))
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(32), nullable=False)  # merge|split|correct|lock
    payload: Mapped[dict[str, Any] | None] = mapped_column(PortableJSON)
    actor: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AlertRule(Base):
    __tablename__ = "alert_rules"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # rule_id
    version: Mapped[str] = mapped_column(String(64), nullable=False, default="v1")
    thresholds: Mapped[dict[str, Any] | None] = mapped_column(PortableJSON)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (UniqueConstraint("deduplication_key", name="uq_alerts_dedupe_key"),)

    id: Mapped[str] = mapped_column(PortableUUID, primary_key=True, default=lambda: str(uuid4()))
    category: Mapped[str] = mapped_column(String(32), nullable=False)  # intelligence | system
    subcategory: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="medium")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="OPEN")
    deduplication_key: Mapped[str] = mapped_column(String(256), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    first_triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    trigger_count: Mapped[int] = mapped_column(Integer, default=1)
    window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    window_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    evidence_snapshot: Mapped[dict[str, Any] | None] = mapped_column(PortableJSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AlertEvent(Base):
    __tablename__ = "alert_events"

    id: Mapped[str] = mapped_column(PortableUUID, primary_key=True, default=lambda: str(uuid4()))
    alert_id: Mapped[str] = mapped_column(ForeignKey("alerts.id"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(32), nullable=False)  # create|trigger|ack|resolve|close|reopen
    actor: Mapped[str | None] = mapped_column(String(128))
    payload: Mapped[dict[str, Any] | None] = mapped_column(PortableJSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AlertEvidence(Base):
    __tablename__ = "alert_evidence"

    id: Mapped[str] = mapped_column(PortableUUID, primary_key=True, default=lambda: str(uuid4()))
    alert_id: Mapped[str] = mapped_column(ForeignKey("alerts.id"), nullable=False, index=True)
    article_id: Mapped[str | None] = mapped_column(ForeignKey("articles.id"), nullable=True)
    event_id: Mapped[str | None] = mapped_column(ForeignKey("events.id"), nullable=True)
    snapshot: Mapped[dict[str, Any] | None] = mapped_column(PortableJSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReportSnapshot(Base):
    __tablename__ = "report_snapshots"
    __table_args__ = (
        UniqueConstraint("report_type", "period", name="uq_report_snapshots_type_period"),
    )

    id: Mapped[str] = mapped_column(PortableUUID, primary_key=True, default=lambda: str(uuid4()))
    report_type: Mapped[str] = mapped_column(String(32), nullable=False)  # daily|weekly|monthly
    period: Mapped[str] = mapped_column(String(64), nullable=False)
    schema_version: Mapped[str | None] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(PortableJSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StatSnapshot(Base):
    """V1.0 traceable statistical snapshot (methodology_v1.0 Section 9)."""

    __tablename__ = "stat_snapshots"

    id: Mapped[str] = mapped_column(PortableUUID, primary_key=True, default=lambda: str(uuid4()))
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    scope_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)  # GLOBAL|COUNTRY|BOARD|TOPIC
    scope_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    article_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    positive_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    neutral_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    negative_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unclassified_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    positive_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    neutral_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    negative_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    stance_coverage_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    methodology_version: Mapped[str] = mapped_column(String(32), nullable=False)
    taxonomy_version: Mapped[str] = mapped_column(String(32), nullable=False)
    analysis_version: Mapped[str] = mapped_column(String(64), nullable=False)
    article_ids: Mapped[list[str] | None] = mapped_column(PortableJSON)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReportNarrativeTask(Base):
    """Cached per-task LLM intelligence analysis output with audit & validation metadata."""

    __tablename__ = "report_narrative_tasks"
    __table_args__ = (
        UniqueConstraint(
            "report_type",
            "period",
            "task_type",
            "prompt_version",
            name="uq_report_narrative_task_key",
        ),
    )

    id: Mapped[str] = mapped_column(PortableUUID, primary_key=True, default=lambda: str(uuid4()))
    report_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)  # daily|weekly|monthly
    period: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    task_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    evidence_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)
    model_version: Mapped[str | None] = mapped_column(String(128))
    provider: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="completed")
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
    total_tokens: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    estimated_cost_usd: Mapped[float | None] = mapped_column(Float)
    error_message: Mapped[str | None] = mapped_column(Text)
    raw_output: Mapped[dict[str, Any] | None] = mapped_column(PortableJSON)
    validated_output: Mapped[dict[str, Any] | None] = mapped_column(PortableJSON)
    validation_result: Mapped[dict[str, Any] | None] = mapped_column(PortableJSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


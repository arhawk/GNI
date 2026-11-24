"""Load verified source seed YAML into the database."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from gni.infrastructure.models import Country, Organization, Source, SourceHealth, SourceReview

DEFAULT_SEED = Path(__file__).resolve().parents[3] / "configs" / "sources_seed.yaml"


def _source_config(row: dict[str, Any]) -> dict[str, Any]:
    """Build persisted Source.config; keep editorial_focus when declared in seed."""
    cfg: dict[str, Any] = {
        "feed_url": row.get("feed_or_api_url"),
        **(row.get("config") or {}),
    }
    focus = row.get("editorial_focus")
    if focus:
        cfg["editorial_focus"] = focus
    return cfg


def load_seed_file(path: Path | None = None) -> dict[str, Any]:
    seed_path = path or DEFAULT_SEED
    with seed_path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Invalid seed file: {seed_path}")
    return data


def seed_sources(session: Session, path: Path | None = None) -> dict[str, int]:
    data = load_seed_file(path)
    counts = {"countries": 0, "organizations": 0, "sources": 0, "reviews": 0}

    for row in data.get("countries", []):
        existing = session.get(Country, row["id"])
        if existing is None:
            session.add(Country(id=row["id"], code=row["code"], name=row["name"]))
            counts["countries"] += 1
        else:
            existing.code = row["code"]
            existing.name = row["name"]

    for row in data.get("organizations", []):
        existing = session.get(Organization, row["id"])
        if existing is None:
            session.add(
                Organization(
                    id=row["id"],
                    country_id=row["country_id"],
                    name=row["name"],
                    organization_type=row.get("organization_type"),
                    ownership_type=row.get("ownership_type"),
                    government_control_level=row.get("government_control_level"),
                )
            )
            counts["organizations"] += 1
        else:
            existing.name = row["name"]
            existing.country_id = row["country_id"]
            existing.organization_type = row.get("organization_type")
            existing.ownership_type = row.get("ownership_type")
            existing.government_control_level = row.get("government_control_level")

    session.flush()

    now = datetime.now(timezone.utc)
    for row in data.get("sources", []):
        sid = row["source_id"]
        existing = session.get(Source, sid)
        fields = dict(
            organization_id=row["organization_id"],
            country_id=row["country_id"],
            name=row["name"],
            canonical_url=row.get("canonical_url"),
            source_type=row["source_type"],
            ownership_type=row.get("ownership_type"),
            funding_type=row.get("funding_type"),
            government_control_level=row.get("government_control_level"),
            editorial_independence=row.get("editorial_independence"),
            language=row.get("language"),
            timezone=row.get("timezone"),
            access_method=row.get("access_method", "rss"),
            adapter_type=row.get("adapter_type", "rss_adapter"),
            terms_url=row.get("terms_url"),
            compliance_status=row.get("compliance_status", "pending"),
            evidence_url=row.get("evidence_url"),
            classification_confidence=row.get("classification_confidence"),
            reviewed_at=now,
            reviewed_by=row.get("reviewed_by"),
            active_status=row.get("active_status", "candidate"),
            verification_status=row.get("verification_status", "unverified"),
            feed_or_api_url=row.get("feed_or_api_url"),
            notes=row.get("notes"),
            config=_source_config(row),
        )
        if existing is None:
            session.add(Source(id=sid, **fields))
            counts["sources"] += 1
            session.flush()  # ensure FK parent exists before reviews/health (Postgres)
            session.add(
                SourceReview(
                    source_id=sid,
                    reviewer=row.get("reviewed_by"),
                    decision="activate" if row.get("active_status") == "active" else "register",
                    notes="Seeded from configs/sources_seed.yaml",
                    reviewed_at=now,
                )
            )
            counts["reviews"] += 1
        else:
            for k, v in fields.items():
                setattr(existing, k, v)
            session.flush()

        if session.get(SourceHealth, sid) is None:
            session.add(SourceHealth(source_id=sid, success_count=0, failure_count=0))
            session.flush()

    return counts


def list_sources(session: Session, *, active_only: bool = False) -> list[Source]:
    stmt = select(Source).order_by(Source.country_id, Source.id)
    if active_only:
        stmt = stmt.where(Source.active_status == "active")
    return list(session.scalars(stmt))

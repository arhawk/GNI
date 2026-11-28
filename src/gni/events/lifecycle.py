"""Event lifecycle: derive active / dormant / closed from last article activity.

Rules (spec: writing-block.md §5.5 事件生命周期):
- last_activity_at = max(published_at or first_seen_at) over linked articles.
  ``event_time`` is never used here.
- age <= dormant_days                      -> active
- dormant_days < age <= closed_days        -> dormant   (休眠，不删除)
- age > closed_days                        -> closed    (归档，不删除)
- dormant / closed event regaining activity (age <= dormant_days) -> active,
  logged as ``reactivate``.
- Manual or merge states (locked, confirmed, merged) are never changed.
- While recent, the proto / active confidence tier set by the clusterer is kept.

Every status change writes an ``EventRevision`` row so transitions are auditable.
Dormant and closed rows are never deleted.
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from gni.core.config import Settings, get_settings
from gni.infrastructure.models import Article, Event, EventArticle, EventRevision

LIFECYCLE_ACTOR = "system:lifecycle"

# Statuses owned by humans or by merge; lifecycle never rewrites them.
MANUAL_STATUSES = frozenset({"locked", "confirmed", "merged"})
# Confidence tiers assigned by clustering while an event is recent.
RECENT_TIER_STATUSES = frozenset({"proto", "active"})
# Hidden from default lists, boards and reports.
HIDDEN_STATUSES = frozenset({"closed", "merged"})


def classify_lifecycle(
    age_days: float | None,
    current_status: str,
    *,
    dormant_days: int,
    closed_days: int,
) -> str | None:
    """Return the target status, or None when the event must not change.

    ``age_days`` is days since last linked article activity (None = no linked articles).
    """
    if current_status in MANUAL_STATUSES or age_days is None:
        return None
    if age_days <= dormant_days:
        return current_status if current_status in RECENT_TIER_STATUSES else "active"
    if age_days <= closed_days:
        return "dormant"
    return "closed"


def _utc(t: datetime | None) -> datetime | None:
    if t is None:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def _transition_action(prev: str, target: str) -> str:
    if target == "active" and prev in ("dormant", "closed"):
        return "reactivate"
    if target == "closed":
        return "archive"
    return "dormant"


def last_activity_by_event(session: Session) -> dict[str, datetime]:
    """Latest ``published_at`` (fallback ``first_seen_at``) per event across linked articles."""
    rows = session.execute(
        select(EventArticle.event_id, Article.published_at, Article.first_seen_at).join(
            Article, Article.id == EventArticle.article_id
        )
    ).all()
    out: dict[str, datetime] = {}
    for event_id, published_at, first_seen_at in rows:
        t = _utc(published_at or first_seen_at)
        if t is None:
            continue
        if event_id not in out or t > out[event_id]:
            out[event_id] = t
    return out


def refresh_event_lifecycle(
    session: Session,
    *,
    now: datetime | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Recompute lifecycle status for every event. Idempotent for unchanged inputs."""
    cfg = settings or get_settings()
    dormant_days = cfg.event_dormant_days
    closed_days = cfg.event_closed_days
    now_utc = _utc(now) or datetime.now(UTC)

    last_at = last_activity_by_event(session)
    transitions: Counter[str] = Counter()
    final: Counter[str] = Counter()
    for event in session.scalars(select(Event)).all():
        last = last_at.get(event.id)
        age = None if last is None else (now_utc - last).total_seconds() / 86400.0
        target = classify_lifecycle(
            age, event.status, dormant_days=dormant_days, closed_days=closed_days
        )
        if target is None:
            final[event.status] += 1
            continue
        if target != event.status:
            prev = event.status
            action = _transition_action(prev, target)
            event.status = target
            session.add(
                EventRevision(
                    id=str(uuid4()),
                    event_id=event.id,
                    action=action,
                    payload={
                        "from": prev,
                        "to": target,
                        "last_activity_at": last.isoformat() if last else None,
                        "age_days": round(age, 2) if age is not None else None,
                        "dormant_days": dormant_days,
                        "closed_days": closed_days,
                    },
                    actor=LIFECYCLE_ACTOR,
                )
            )
            transitions[action] += 1
        final[target] += 1
    session.flush()
    return {
        "transitions": dict(transitions),
        "status_counts": dict(final),
        "dormant_days": dormant_days,
        "closed_days": closed_days,
    }

"""Seed helpers, and the context a per-domain seed section receives.

`SeedContext` exists so a section can reach what earlier sections created without
`run()` threading a dozen locals through it. Extend the dataclass rather than
widening a section's signature.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.activity.models import ActivityLog


@dataclass
class SeedContext:
    """What a seed section may rely on having already been created.

    `db` and `actor_id` are always populated. The lookup dicts are keyed by the
    row's natural key (`suppliers["SUPP-0001"]`, `customers["CUST-0001"]`) and are
    filled in by `run()` as the earlier sections create them, so a section only
    sees what genuinely precedes it.
    """

    db: Session
    actor_id: Any
    activity: Any = None
    suppliers: dict[str, Any] = field(default_factory=dict)
    customers: dict[str, Any] = field(default_factory=dict)
    products: dict[str, Any] = field(default_factory=dict)


def get_or_create(db: Session, model, *, defaults: dict | None = None, **filters):
    """Return (instance, created)."""
    stmt = select(model)
    for key, val in filters.items():
        stmt = stmt.where(getattr(model, key) == val)
    instance = db.scalar(stmt)
    if instance is not None:
        return instance, False
    params = {**filters, **(defaults or {})}
    instance = model(**params)
    db.add(instance)
    db.flush()
    return instance, True


def record_creation(
    db: Session, activity, *, entity_type: str, entity_id, summary: str, actor_id
) -> None:
    """Give a seeded record the `created` history line it would have had.

    The seed writes masters with `get_or_create` rather than through their service,
    so their change-history panel would be empty on the demo rows the founder
    actually clicks (R2.10, G14). The existence check makes it idempotent and also
    backfills a database seeded before this existed; `occurred_at` is then the
    backfill time rather than the original insert, which is the one thing a
    re-seeded demo database cannot recover.
    """
    if not db.scalar(
        select(func.count()).select_from(ActivityLog).where(ActivityLog.entity_id == entity_id)
    ):
        activity.log(
            actor_id=actor_id,
            verb="created",
            entity_type=entity_type,
            entity_id=entity_id,
            summary=summary,
        )

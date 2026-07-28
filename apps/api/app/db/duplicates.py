"""The one duplicate-prevention mechanism (R2.9).

Every master has a natural key — the thing a human would call "the same record".
Left to the database, a collision surfaces as an `IntegrityError` at flush time:
a 500, with a message naming a constraint. R2.9 asks for the opposite — a
pre-save check that names the field and reads like a sentence.

So natural keys are configuration (`NATURAL_KEYS`, keyed on `__tablename__`) and
`ensure_unique()` is the single check every service calls before it writes. Adding
duplicate protection to a master is a dict entry plus one call, which is what
"applied per entity via configuration" means and what stage 2 (R3.8) consumes.

**The check matches the constraint, not the read filter.** A soft-deleted row still
occupies a `UNIQUE` column — `product.sku_code` is unique across every row in the
table, deleted or not. A check that only looked at live rows would pass and then
hit the IntegrityError it exists to prevent, so keys marked `db_unique=True` scan
deleted rows too and say so in the message. Keys with no database constraint
(a composite business identity like name + spec + brand) only consider live rows,
because that is the whole of what they promise.
"""
from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import DuplicateError


@dataclass(frozen=True)
class NaturalKey:
    """One "same record" rule for an entity.

    `fields` are model attributes; all of them together form the key. `label` is
    what the message calls it. `field` is which form field to blame when the key
    spans several (defaults to the first). `db_unique` says a database UNIQUE
    constraint backs this key, which is what decides whether soft-deleted rows
    count as collisions.
    """

    fields: tuple[str, ...]
    label: str
    field: str | None = None
    case_insensitive: bool = True
    db_unique: bool = False

    @property
    def blame(self) -> str:
        return self.field or self.fields[0]


# Natural keys per table. Stage 1 configures the two masters the machinery is
# proven on (R2.11); stage 2 adds the rest as further entries here (R3.8) — not as
# further checks in services.
NATURAL_KEYS: dict[str, tuple[NaturalKey, ...]] = {
    "product": (
        # `sku_code` carries a UNIQUE constraint, so a deleted product still holds it.
        NaturalKey(("sku_code",), "SKU", db_unique=True),
        # The business identity: the same thing, same size, same brand is one SKU.
        NaturalKey(
            ("name", "specification", "brand_id"),
            "name, specification and brand",
            field="name",
        ),
    ),
    "customer": (
        NaturalKey(("code",), "customer code", db_unique=True),
        NaturalKey(("name", "city"), "name and city", field="name"),
    ),
}


def natural_keys_for(model: type[Any]) -> tuple[NaturalKey, ...]:
    return NATURAL_KEYS.get(str(getattr(model, "__tablename__", "")), ())


def _shown(key: NaturalKey, values: Mapping[str, Any]) -> str:
    """The key's value as a human would quote it back.

    Foreign keys are dropped: "Toilet Roll / 2 Ply" is a useful thing to read,
    "Toilet Roll / 2 Ply / 0f8c…" is not.
    """
    parts = [
        str(values[f])
        for f in key.fields
        if not f.endswith("_id") and values.get(f) not in (None, "")
    ]
    if not parts:
        parts = [str(values[f]) for f in key.fields]
    return " / ".join(parts)


def _message(model: type[Any], key: NaturalKey, values: Mapping[str, Any], *, deleted: bool) -> str:
    noun = str(getattr(model, "__tablename__", "record")).replace("_", " ")
    shown = _shown(key, values)
    if deleted:
        return (
            f"A deleted {noun} still holds this {key.label} ({shown}). "
            f"Choose a different {key.label} — the deleted record keeps its own."
        )
    return f"Another {noun} already uses this {key.label} ({shown})."


def find_duplicate(
    db: Session,
    model: type[Any],
    values: Mapping[str, Any],
    *,
    exclude_id: uuid.UUID | None = None,
) -> tuple[NaturalKey, Any] | None:
    """The first natural key `values` collides on, with the row holding it.

    A key whose value is incomplete (any field absent, `None` or blank) cannot
    collide and is skipped — a create that omits an optional part of a composite
    key is not thereby a duplicate of every other row that also omits it.
    """
    for key in natural_keys_for(model):
        if any(values.get(f) in (None, "") for f in key.fields):
            continue

        stmt = select(model)
        for name in key.fields:
            column = getattr(model, name, None)
            if column is None:
                stmt = None
                break
            value = values[name]
            if key.case_insensitive and isinstance(value, str):
                stmt = stmt.where(func.lower(column) == value.strip().lower())
            else:
                stmt = stmt.where(column == value)
        if stmt is None:
            continue  # a key naming a column this model does not have: config bug, not user input

        if not key.db_unique and hasattr(model, "deleted_at"):
            stmt = stmt.where(model.deleted_at.is_(None))
        if exclude_id is not None:
            stmt = stmt.where(model.id != exclude_id)

        found = db.scalar(stmt.limit(1))
        if found is not None:
            return key, found
    return None


def ensure_unique(
    db: Session,
    model: type[Any],
    values: Mapping[str, Any],
    *,
    exclude_id: uuid.UUID | None = None,
) -> None:
    """Raise `DuplicateError` if `values` collides on any of the model's natural keys.

    Called by a service before it writes. `exclude_id` is the row being updated,
    so a record never counts as a duplicate of itself.
    """
    hit = find_duplicate(db, model, values, exclude_id=exclude_id)
    if hit is None:
        return
    key, found = hit
    raise DuplicateError(
        _message(model, key, values, deleted=getattr(found, "deleted_at", None) is not None),
        field=key.blame,
        value=values.get(key.blame),
    )

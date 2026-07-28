"""Change history, derived from `activity_log` — no new table (R2.10).

R2.10 permits a dedicated history table only if `activity_log` provably cannot
answer "what changed on this record, when, by whom". It can, on all three counts:

| question | column |
|---|---|
| what changed | `verb` + `summary`, and field-level detail in the `data` JSON |
| when | `occurred_at` |
| by whom | `actor_id` |

`entity_type` + `entity_id` already index every row to its record, and every
state-changing verb writes exactly one row in the same transaction (G5), so the
log is complete by construction — a second table would be a second place for the
same facts to be incomplete in.

The one thing that was missing is field-level detail: services wrote `summary`
and left `data` null, so history could say "customer updated" but not "credit
limit 300000.00 → 500000.00". `field_changes()` closes that without a schema
change, because the `data` JSON column already existed for exactly this.
`ActivityService.history()` reads it back.

Reading history writes nothing (G15).
"""
from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.core.money import minor_to_text

# The `data` key field-level changes live under, so the JSON column stays open to
# other per-verb payloads without either clobbering the other.
CHANGES_KEY = "changes"


@dataclass(frozen=True)
class FieldChange:
    """One field's before/after, already formatted for reading."""

    field: str
    label: str
    before: str
    after: str


@dataclass(frozen=True)
class HistoryEntry:
    """One activity row as a history line."""

    occurred_at: datetime
    verb: str
    summary: str
    actor: str
    changes: tuple[FieldChange, ...] = ()


def _jsonable(value: Any) -> Any:
    """Make a column value safe for the `data` JSON column, losing nothing."""
    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    return str(value)


def field_changes(instance: Any, updates: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """`{field: {"from": old, "to": new}}` for the fields `updates` actually changes.

    Call it *before* applying the update — it reads the current values off
    `instance`. Fields whose value is unchanged, and names the model does not
    have, are left out, so a form that resubmits every field unedited produces an
    empty diff rather than a wall of no-ops.
    """
    changed: dict[str, dict[str, Any]] = {}
    for name, new in updates.items():
        if not hasattr(instance, name):
            continue
        old = getattr(instance, name)
        if old == new:
            continue
        changed[name] = {"from": _jsonable(old), "to": _jsonable(new)}
    return changed


def _label(name: str) -> str:
    """`payment_terms_days` -> `Payment terms days`; `credit_limit_minor` -> `Credit limit (₹)`."""
    if name.endswith("_minor"):
        name = name[: -len("_minor")]
        return name.replace("_", " ").capitalize() + " (₹)"
    return name.replace("_", " ").capitalize()


def _value_text(name: str, raw: Any) -> str:
    if raw is None or raw == "":
        return ""
    if name.endswith("_minor"):
        try:
            return minor_to_text(int(raw))
        except (TypeError, ValueError):
            return str(raw)
    return str(raw)


def changes_from_data(data: Mapping[str, Any] | None) -> tuple[FieldChange, ...]:
    """Read the field-level diff back out of an activity row's `data` JSON."""
    if not data:
        return ()
    raw = data.get(CHANGES_KEY)
    if not isinstance(raw, Mapping):
        return ()
    out = []
    for name, delta in raw.items():
        if not isinstance(delta, Mapping):
            continue
        out.append(
            FieldChange(
                field=str(name),
                label=_label(str(name)),
                before=_value_text(str(name), delta.get("from")),
                after=_value_text(str(name), delta.get("to")),
            )
        )
    return tuple(sorted(out, key=lambda c: c.label))

"""The one generic soft-delete mechanism (R1.1).

Reads already exclude `deleted_at IS NOT NULL` everywhere (G3); this module owns
the *write* side, so there is exactly one place in the codebase that deletes
anything. Services call `soft_delete(...)`; nothing else assigns `deleted_at`,
and no module carries its own delete implementation.

Three things it guarantees that a hand-rolled `instance.deleted_at = now` would
not:

* **Exactly one activity row.** One `activity_log` row per deletion, flushed
  inside the caller's transaction (G5, R1.6).
* **Append-only tables are refused with a reason.** `PROTECTED_TABLES` names
  every table whose rows are a permanent record; attempting one raises
  `ConflictError`, so the UI shows a sentence rather than a 500 (R1.3).
* **Double deletion is refused** instead of silently re-stamping `deleted_at`
  and writing a second activity row for something already gone from the lists.

Soft delete deliberately does *not* cascade and does *not* check for inbound
references. A deleted row keeps its primary key, so documents that reference it
keep rendering — an invoice for a deleted customer still shows the customer's
name (R1.7). Hard deletes would break exactly that.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import ConflictError

# Tables that must never be soft-deleted, and why (R1.3). Financial documents and
# the stock ledger are append-only by G4: a mistake is corrected with a new
# document — a credit note, a reversing movement — never by removing history.
#
# The guard is table-level and unconditional, which is stricter than the letter of
# R1.3 ("*posted* sales/purchase orders"): ApexOS exposes no delete path for an
# unposted draft either, so nothing is foreclosed. A later part that wants draft
# deletion should make the relevant entry status-aware here rather than bypass it.
PROTECTED_TABLES: dict[str, str] = {
    "invoice": (
        "Invoices are a permanent financial record. Cancel the invoice or raise a "
        "credit note instead of deleting it."
    ),
    "invoice_line": (
        "Invoice lines belong to a permanent financial record. Correct the invoice "
        "with a credit note instead."
    ),
    "bill": (
        "Bills are a permanent financial record. Cancel the bill or raise a debit "
        "note instead of deleting it."
    ),
    "bill_line": (
        "Bill lines belong to a permanent financial record. Correct the bill with a "
        "debit note instead."
    ),
    "payment": (
        "Payments are an append-only ledger. Reverse the payment with a new entry "
        "instead of deleting it."
    ),
    "payment_allocation": (
        "Payment allocations are an append-only ledger. Re-allocate with a new "
        "entry instead of deleting this one."
    ),
    "sales_order": (
        "Sales orders are a posted document with downstream fulfilments and "
        "invoices. Cancel the order instead of deleting it."
    ),
    "sales_order_line": (
        "Sales order lines belong to a posted document. Cancel or revise the order "
        "instead of deleting a line."
    ),
    "purchase_order": (
        "Purchase orders are a posted document with downstream receipts and bills. "
        "Cancel the order instead of deleting it."
    ),
    "purchase_order_line": (
        "Purchase order lines belong to a posted document. Cancel or revise the "
        "order instead of deleting a line."
    ),
    "goods_receipt": (
        "Goods receipts record stock that physically arrived and have already moved "
        "the stock ledger. Adjust the stock instead of deleting the receipt."
    ),
    "goods_receipt_line": (
        "Goods receipt lines record stock that physically arrived. Adjust the stock "
        "instead of deleting a line."
    ),
    "fulfillment": (
        "Fulfilments record stock that physically left and have already moved the "
        "stock ledger. Raise a return instead of deleting the fulfilment."
    ),
    "fulfillment_line": (
        "Fulfilment lines record stock that physically left. Raise a return instead "
        "of deleting a line."
    ),
    "stock_movement": (
        "The stock ledger is append-only — it is the only source of truth for stock "
        "on hand. Post a correcting adjustment instead of deleting a movement."
    ),
    "activity_log": (
        "The activity log is the audit trail. It records what happened and is never "
        "edited or deleted."
    ),
}

# Attributes tried, in order, for the human label in the activity summary.
_LABEL_FIELDS = ("name", "title", "company_name", "filename", "code")


def describe(instance: Any) -> str:
    """Best-effort human label for an entity row (used in the activity summary)."""
    for field in _LABEL_FIELDS:
        value = getattr(instance, field, None)
        if value:
            return str(value)
    return str(getattr(instance, "id", "row"))


def entity_type_of(instance: Any) -> str:
    """The activity-log `entity_type` for a row — its table name.

    Every model ApexOS soft-deletes names its table after the entity (`customer`,
    `supplier`, `product`, `task`, `lead`, `category`, `document`), which is also
    the `entity_type` its other activity rows already use, so deletions land on
    the same timeline as the creates and updates.
    """
    return str(instance.__tablename__)


def soft_delete(
    db: Session,
    instance: Any,
    *,
    actor_id: uuid.UUID | None,
    label: str | None = None,
) -> None:
    """Soft-delete any entity row and record it on the activity ledger.

    Raises `ConflictError` if the row's table is append-only (`PROTECTED_TABLES`)
    or if the row is already deleted. Flushes rather than commits, so the deletion
    and its activity row participate in the caller's transaction.
    """
    entity_type = entity_type_of(instance)
    protected = PROTECTED_TABLES.get(entity_type)
    if protected is not None:
        raise ConflictError(protected)

    if not hasattr(instance, "deleted_at"):
        # A model without the soft-delete column is a schema bug, not user input.
        raise TypeError(f"{type(instance).__name__} has no deleted_at column")
    if instance.deleted_at is not None:
        raise ConflictError(f"{describe(instance)} is already deleted.")

    instance.deleted_at = datetime.now(UTC)
    if hasattr(instance, "updated_by"):
        instance.updated_by = actor_id

    # Imported here rather than at module scope so app.db stays free of a runtime
    # dependency on app.modules (the codebase's existing local-import idiom).
    from app.modules.activity.service import ActivityService

    ActivityService(db).log(
        actor_id=actor_id,
        verb="deleted",
        entity_type=entity_type,
        entity_id=instance.id,
        summary=f"{label or entity_type.replace('_', ' ').title()} "
        f"{describe(instance)} deleted",
    )
    db.flush()

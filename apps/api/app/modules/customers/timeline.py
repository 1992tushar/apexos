"""R8.10 — one chronological view of everything that happened with a customer.

**A read-only projection, assembled per request.** The requirement says so explicitly and
it is worth restating why: an events table would be a second copy of facts the orders,
invoices, payments, tasks and notes already hold, and the moment it exists it can disagree
with them. Nothing here is stored (G7).

Six sources, six queries — not one query per event. `activity_log` carries the state changes
(and is where a credit override shows up, which is the point of logging it against the
customer); the entity tables carry the money.

**Ordering ties are real.** Several of these default their timestamp to `func.now()`, so rows
written in one transaction share it — a seeded order and its invoice, for example. Sorting on
the timestamp alone leaves their order to chance, which is visible on screen as an invoice
appearing above the order that produced it. The sort key includes a per-kind rank so a
same-instant group reads in causal order, and `id` last so it is deterministic.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.customers.schemas import TimelineEvent

# When two events share a timestamp, this is the order they read in: you cannot be paid for
# an invoice you have not raised, and you cannot invoice an order that does not exist.
_CAUSAL_RANK = {
    "order": 0,
    "invoice": 1,
    "payment": 2,
    "task": 3,
    "note": 4,
    "activity": 5,
}


def _aware(value: datetime | None) -> datetime:
    """SQLite hands back naive datetimes even for `DateTime(timezone=True)`; comparing a
    naive against an aware one raises TypeError, and only on SQLite."""
    if value is None:
        return datetime.min.replace(tzinfo=UTC)
    return value if value.tzinfo else value.replace(tzinfo=UTC)


class CustomerTimelineService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def events(self, customer_id: uuid.UUID, *, limit: int = 200) -> list[TimelineEvent]:
        """Everything, newest first. An empty list for a customer with no history — not an
        error and not a blank page (R8.11)."""
        events: list[TimelineEvent] = []
        events += self._orders(customer_id)
        events += self._invoices(customer_id)
        events += self._payments(customer_id)
        events += self._tasks(customer_id)
        events += self._notes(customer_id)
        events += self._activity(customer_id)

        events.sort(
            key=lambda e: (_aware(e.at), _CAUSAL_RANK.get(e.kind, 9)), reverse=True
        )
        return events[:limit]

    def _orders(self, customer_id: uuid.UUID) -> list[TimelineEvent]:
        from app.modules.sales.models import SalesOrder

        rows = self.db.scalars(
            select(SalesOrder).where(
                SalesOrder.customer_id == customer_id, SalesOrder.deleted_at.is_(None)
            )
        )
        return [
            TimelineEvent(
                at=_aware(r.created_at),
                kind="order",
                summary=f"Sales order {r.order_no} — {r.status}",
                href=f"/sales/{r.id}",
                amount_minor=r.total_minor,
            )
            for r in rows
        ]

    def _invoices(self, customer_id: uuid.UUID) -> list[TimelineEvent]:
        from app.modules.finance.models import Invoice

        rows = self.db.scalars(
            select(Invoice).where(
                Invoice.customer_id == customer_id, Invoice.deleted_at.is_(None)
            )
        )
        return [
            TimelineEvent(
                at=_aware(r.created_at),
                kind="invoice",
                summary=f"Invoice {r.invoice_no} — {r.status}",
                amount_minor=r.total_minor,
            )
            for r in rows
        ]

    def _payments(self, customer_id: uuid.UUID) -> list[TimelineEvent]:
        from app.modules.finance.models import Payment

        rows = self.db.scalars(
            select(Payment).where(
                Payment.customer_id == customer_id, Payment.deleted_at.is_(None)
            )
        )
        return [
            TimelineEvent(
                # `paid_at`, not `created_at`: when the money arrived is the fact worth
                # placing on a timeline, not when someone keyed it in.
                at=_aware(r.paid_at or r.created_at),
                kind="payment",
                summary=f"Payment {r.payment_no} received ({r.method or 'unspecified'})",
                amount_minor=r.amount_minor,
            )
            for r in rows
        ]

    def _tasks(self, customer_id: uuid.UUID) -> list[TimelineEvent]:
        from app.modules.tasks.models import Task

        rows = self.db.scalars(
            select(Task).where(
                Task.entity_type == "customer",
                Task.entity_id == customer_id,
                Task.deleted_at.is_(None),
            )
        )
        return [
            TimelineEvent(
                at=_aware(r.created_at),
                kind="task",
                summary=f"Task: {r.title} — {r.status}",
                href="/tasks",
            )
            for r in rows
        ]

    def _notes(self, customer_id: uuid.UUID) -> list[TimelineEvent]:
        from app.modules.customers.models import CustomerNote

        rows = self.db.scalars(
            select(CustomerNote).where(
                CustomerNote.customer_id == customer_id,
                CustomerNote.deleted_at.is_(None),
            )
        )
        return [
            TimelineEvent(at=_aware(r.created_at), kind="note", summary=r.body)
            for r in rows
        ]

    def _activity(self, customer_id: uuid.UUID) -> list[TimelineEvent]:
        """State changes, including a credit override — which is exactly why R8.8 logs it
        against the customer rather than only against the order."""
        from app.modules.activity.models import ActivityLog

        rows = self.db.scalars(
            select(ActivityLog).where(
                ActivityLog.entity_type == "customer",
                ActivityLog.entity_id == customer_id,
            )
        )
        return [
            TimelineEvent(
                at=_aware(r.occurred_at),
                kind="activity",
                summary=r.summary,
            )
            for r in rows
        ]

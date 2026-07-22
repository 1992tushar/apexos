"""QuickBooks Online sync — a thin, feature-flagged bridge (Phase C).

When `settings.flag_quickbooks` is off, every push is a clean no-op returning
`{"synced": False, "reason": "disabled"}`. When on, this records a `qbo.synced`
activity event and returns a stub reference; the real QBO connector call is the
only thing that would slot in here. Nothing in the core trade loop depends on it.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import NotFoundError
from app.modules.activity.service import ActivityService
from app.modules.finance.models import Bill, Invoice, Payment


class QuickBooksSyncService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.activity = ActivityService(db)

    @property
    def enabled(self) -> bool:
        return bool(settings.flag_quickbooks)

    def status(self) -> dict:
        return {"enabled": self.enabled, "provider": "quickbooks_online"}

    def _disabled(self) -> dict:
        return {"synced": False, "reason": "disabled"}

    def _record(self, entity_type: str, entity_id: uuid.UUID, ref_no: str, *, actor_id) -> dict:
        self.activity.log(
            actor_id=actor_id,
            verb="synced",
            entity_type="qbo",
            entity_id=entity_id,
            summary=f"Synced {entity_type} {ref_no} to QuickBooks Online",
            data={"entity_type": entity_type},
        )
        return {"synced": True, "entity_type": entity_type, "ref": ref_no}

    def push_invoice(self, invoice_id: uuid.UUID, *, actor_id: uuid.UUID | None) -> dict:
        if not self.enabled:
            return self._disabled()
        inv = self.db.scalar(select(Invoice).where(Invoice.id == invoice_id))
        if inv is None:
            raise NotFoundError(f"Invoice {invoice_id} not found")
        return self._record("invoice", inv.id, inv.invoice_no, actor_id=actor_id)

    def push_bill(self, bill_id: uuid.UUID, *, actor_id: uuid.UUID | None) -> dict:
        if not self.enabled:
            return self._disabled()
        bill = self.db.scalar(select(Bill).where(Bill.id == bill_id))
        if bill is None:
            raise NotFoundError(f"Bill {bill_id} not found")
        return self._record("bill", bill.id, bill.bill_no, actor_id=actor_id)

    def push_payment(self, payment_id: uuid.UUID, *, actor_id: uuid.UUID | None) -> dict:
        if not self.enabled:
            return self._disabled()
        payment = self.db.scalar(select(Payment).where(Payment.id == payment_id))
        if payment is None:
            raise NotFoundError(f"Payment {payment_id} not found")
        return self._record("payment", payment.id, payment.payment_no, actor_id=actor_id)

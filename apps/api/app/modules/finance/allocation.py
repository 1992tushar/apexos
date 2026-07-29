"""Spreading one receipt or payment across several open documents (R10.9).

The founder is handed a cheque for the month, not for an invoice. R10.9 asks for that
case: a partial payment across multiple invoices, and an over-payment on one invoice
**spilling to the next**.

Three decisions shape this module, and a later checkpoint should not quietly reverse them:

1. **Oldest due first.** The spill order is `(due date, document number)` — settle what
   has been outstanding longest, then move down. Deterministic, and it is what both
   parties would assume in the absence of an instruction.
2. **An allocation is a new row, never an edit.** Money applied to an invoice is a
   `PaymentAllocation`; the invoice itself is untouched (G4). `invoice.status` is the one
   exception and it is a documented *cache* of the derived balance, not the balance.
3. **A receipt larger than everything open is REFUSED**, naming what could be applied.
   The alternative — holding the surplus as unallocated cash — would create money the
   receivable definition cannot see, and then `outstanding_minor` and the statement would
   disagree about what the party owes. That is the exact defect R10.x exists to prevent,
   and it is worth a refusal the founder can act on. `InvoiceService.add_payment` already
   refuses an over-payment on a single invoice for the same reason.
"""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationError
from app.core.money import minor_to_text
from app.modules.activity.service import ActivityService
from app.modules.customers.repository import CustomerRepository
from app.modules.finance.ledger import open_bills, open_invoices
from app.modules.finance.models import Bill, Invoice, Payment, PaymentAllocation
from app.modules.finance.repository import FinanceRepository
from app.modules.finance.schemas import (
    AllocationCreate,
    AllocationLine,
    AllocationResult,
    OpenDocument,
)
from app.modules.suppliers.repository import SupplierRepository


class AllocationService:
    """One receipt or payment, spread across a party's open documents (R10.9)."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = FinanceRepository(db)
        self.activity = ActivityService(db)

    def allocate_receipt(
        self, customer_id: uuid.UUID, payload: AllocationCreate, *, actor_id: uuid.UUID | None
    ) -> AllocationResult:
        """Money in, spread across the customer's open invoices, oldest due first."""
        if CustomerRepository(self.db).get(customer_id) is None:
            raise NotFoundError(f"Customer {customer_id} not found")
        return self._allocate(
            side="receivable",
            party_id=customer_id,
            payload=payload,
            documents=open_invoices(self.db, customer_id=customer_id),
            actor_id=actor_id,
        )

    def allocate_payment(
        self, supplier_id: uuid.UUID, payload: AllocationCreate, *, actor_id: uuid.UUID | None
    ) -> AllocationResult:
        """Money out, spread across the vendor's open bills, oldest due first."""
        if SupplierRepository(self.db).get(supplier_id) is None:
            raise NotFoundError(f"Supplier {supplier_id} not found")
        return self._allocate(
            side="payable",
            party_id=supplier_id,
            payload=payload,
            documents=open_bills(self.db, supplier_id=supplier_id),
            actor_id=actor_id,
        )

    def _allocate(
        self,
        *,
        side: str,
        party_id: uuid.UUID,
        payload: AllocationCreate,
        documents: list[OpenDocument],
        actor_id: uuid.UUID | None,
    ) -> AllocationResult:
        receivable = side == "receivable"
        noun = "invoices" if receivable else "bills"

        # Oldest DUE first, not oldest issued — decision 1 in the module docstring.
        documents.sort(key=lambda d: (d.due_date, d.doc_no))
        total_open = sum(doc.open_minor for doc in documents)
        if total_open == 0:
            raise ValidationError(f"There are no open {noun} to apply this to")
        if payload.amount_minor > total_open:
            raise ValidationError(
                f"{minor_to_text(payload.amount_minor)} is more than the "
                f"{minor_to_text(total_open)} open across {len(documents)} {noun}. "
                f"Apply {minor_to_text(total_open)} or less."
            )

        payment = Payment(
            direction="in" if receivable else "out",
            customer_id=party_id if receivable else None,
            supplier_id=None if receivable else party_id,
            payment_no=self.repo.next_payment_no(),
            amount_minor=payload.amount_minor,
            method=payload.method,
            created_by=actor_id,
        )

        remaining = payload.amount_minor
        lines: list[AllocationLine] = []
        model = Invoice if receivable else Bill
        for doc in documents:
            if remaining == 0:
                break
            # The spill: take what this document can absorb, carry the rest to the next.
            applied = min(remaining, doc.open_minor)
            remaining -= applied
            payment.allocations.append(
                PaymentAllocation(
                    invoice_id=doc.id if receivable else None,
                    bill_id=None if receivable else doc.id,
                    amount_minor=applied,
                    created_by=actor_id,
                )
            )
            row = self.db.get(model, doc.id)
            open_after = doc.open_minor - applied
            # `status` is a cache of the derived balance (see the service docstring); the
            # ledger row above is what actually moved the money.
            row.status = "paid" if open_after == 0 else "part_paid"
            lines.append(
                AllocationLine(
                    document_id=doc.id,
                    doc_no=doc.doc_no,
                    href=doc.href,
                    applied_minor=applied,
                    open_before_minor=doc.open_minor,
                    open_after_minor=open_after,
                    status_after=row.status,
                )
            )

        self.repo.add_payment(payment)
        self.db.flush()

        settled = sum(1 for line in lines if line.open_after_minor == 0)
        self.activity.log(
            actor_id=actor_id,
            verb="payment_allocated",
            entity_type="payment",
            entity_id=payment.id,
            summary=(
                f"{payment.payment_no}: {minor_to_text(payload.amount_minor)} applied across "
                f"{len(lines)} {noun} ({settled} settled) — "
                + ", ".join(f"{ln.doc_no} {minor_to_text(ln.applied_minor)}" for ln in lines)
            ),
            data={
                "side": side,
                "amount_minor": payload.amount_minor,
                "documents": [
                    {"doc_no": ln.doc_no, "applied_minor": ln.applied_minor} for ln in lines
                ],
            },
        )
        return AllocationResult(
            payment_id=payment.id,
            payment_no=payment.payment_no,
            side=side,
            party_id=party_id,
            amount_minor=payload.amount_minor,
            allocated_minor=sum(line.applied_minor for line in lines),
            lines=lines,
        )

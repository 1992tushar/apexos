"""Supplier repository — persistence + read projections (mirrors CustomerRepository)."""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.config.models import SupplierType
from app.modules.suppliers.models import Supplier, SupplierEvaluation


class SupplierRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # --- writes ---------------------------------------------------------
    def add(self, supplier: Supplier) -> Supplier:
        self.db.add(supplier)
        self.db.flush()
        return supplier

    def add_evaluation(self, evaluation: SupplierEvaluation) -> SupplierEvaluation:
        self.db.add(evaluation)
        self.db.flush()
        return evaluation

    # --- reads ----------------------------------------------------------
    def get(self, supplier_id: uuid.UUID) -> Supplier | None:
        return self.db.scalar(
            select(Supplier).where(Supplier.id == supplier_id, Supplier.deleted_at.is_(None))
        )

    def count_all(self) -> int:
        return self.db.scalar(
            select(func.count()).select_from(Supplier).where(Supplier.deleted_at.is_(None))
        ) or 0

    # No `search()` here: paginated/filtered/sorted reads go through the one query
    # helper in `app.db.listing`, driven by `suppliers/listing.py`'s spec (R2.4).

    def supplier_type_name(self, supplier_type_id: uuid.UUID) -> str | None:
        return self.db.scalar(
            select(SupplierType.name).where(SupplierType.id == supplier_type_id)
        )

    def evaluations(self, supplier_id: uuid.UUID) -> list[SupplierEvaluation]:
        return list(
            self.db.scalars(
                select(SupplierEvaluation)
                .where(
                    SupplierEvaluation.supplier_id == supplier_id,
                    SupplierEvaluation.deleted_at.is_(None),
                )
                .order_by(SupplierEvaluation.evaluated_on.desc(), SupplierEvaluation.created_at.desc())
            )
        )

    def latest_score(self, supplier_id: uuid.UUID) -> int | None:
        return self.db.scalar(
            select(SupplierEvaluation.overall_score)
            .where(
                SupplierEvaluation.supplier_id == supplier_id,
                SupplierEvaluation.deleted_at.is_(None),
            )
            .order_by(SupplierEvaluation.evaluated_on.desc(), SupplierEvaluation.created_at.desc())
            .limit(1)
        )

    def evaluation_count(self, supplier_id: uuid.UUID) -> int:
        return self.db.scalar(
            select(func.count())
            .select_from(SupplierEvaluation)
            .where(
                SupplierEvaluation.supplier_id == supplier_id,
                SupplierEvaluation.deleted_at.is_(None),
            )
        ) or 0

    def outstanding_minor(self, supplier_id: uuid.UUID) -> int:
        """Payable = Σ bill.total − Σ allocations against those bills."""
        from app.modules.finance.models import Bill, PaymentAllocation

        billed = self.db.scalar(
            select(func.coalesce(func.sum(Bill.total_minor), 0)).where(
                Bill.supplier_id == supplier_id,
                Bill.status != "cancelled",
                Bill.deleted_at.is_(None),
            )
        ) or 0
        allocated = self.db.scalar(
            select(func.coalesce(func.sum(PaymentAllocation.amount_minor), 0))
            .select_from(PaymentAllocation)
            .join(Bill, Bill.id == PaymentAllocation.bill_id)
            .where(Bill.supplier_id == supplier_id)
        ) or 0
        return int(billed) - int(allocated)

    def outstanding_by_supplier(self) -> dict[uuid.UUID, int]:
        """`outstanding_minor` for every supplier at once — the SAME two terms.

        The payable-side mirror of `CustomerRepository.outstanding_by_customer`, and it
        exists for the same reason: Part 8's AP ageing (R10.5) needs the payable for every
        vendor, and calling the single-party method in a loop is a query fan-out. Filters
        copied from `outstanding_minor` above so the two cannot disagree; there is no
        credit-note term because credits exist only on the sell side.
        """
        from app.modules.finance.models import Bill, PaymentAllocation

        totals: dict[uuid.UUID, int] = {}

        billed = self.db.execute(
            select(Bill.supplier_id, func.coalesce(func.sum(Bill.total_minor), 0))
            .where(Bill.status != "cancelled", Bill.deleted_at.is_(None))
            .group_by(Bill.supplier_id)
        ).all()
        for supplier_id, amount in billed:
            totals[supplier_id] = totals.get(supplier_id, 0) + int(amount or 0)

        allocated = self.db.execute(
            select(Bill.supplier_id, func.coalesce(func.sum(PaymentAllocation.amount_minor), 0))
            .select_from(PaymentAllocation)
            .join(Bill, Bill.id == PaymentAllocation.bill_id)
            .group_by(Bill.supplier_id)
        ).all()
        for supplier_id, amount in allocated:
            totals[supplier_id] = totals.get(supplier_id, 0) - int(amount or 0)

        return totals

    def next_code(self) -> str:
        n = self.count_all() + 1
        return f"SUPP-{n:04d}"

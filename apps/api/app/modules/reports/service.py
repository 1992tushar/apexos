"""Report service — read-only tabular projections over the ledgers.

Owns no entities and writes no `activity_log` rows (Dashboard/Reports/Analytics
are read-only, per docs §2.10). Each report returns a `ReportResult` (columns +
rows + which columns are money in minor units) that the router renders as JSON or
CSV. Filters are an optional `from`/`to` date window on the document/movement date.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.modules.config.models import Warehouse
from app.modules.customers.models import Customer
from app.modules.finance.models import Bill, Invoice
from app.modules.inventory.models import StockMovement
from app.modules.products.models import Product
from app.modules.suppliers.models import Supplier


@dataclass
class ReportResult:
    key: str
    title: str
    columns: list[str]
    rows: list[dict[str, Any]]
    money_columns: set[str] = field(default_factory=set)


REPORTS: dict[str, str] = {
    "sales-register": "Sales Register",
    "purchase-register": "Purchase Register",
    "stock-ledger": "Stock Ledger",
    "ar-aging": "Accounts Receivable Aging",
    "ap-aging": "Accounts Payable Aging",
    "gst-summary": "GST Summary",
}


class ReportService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def catalog(self) -> list[dict[str, str]]:
        return [{"key": k, "title": v} for k, v in REPORTS.items()]

    def run(self, key: str, *, date_from: date | None, date_to: date | None) -> ReportResult:
        builder = {
            "sales-register": self._sales_register,
            "purchase-register": self._purchase_register,
            "stock-ledger": self._stock_ledger,
            "ar-aging": self._ar_aging,
            "ap-aging": self._ap_aging,
            "gst-summary": self._gst_summary,
        }.get(key)
        if builder is None:
            raise NotFoundError(f"Unknown report '{key}'")
        return builder(date_from, date_to)

    # --- reports --------------------------------------------------------
    def _sales_register(self, date_from, date_to) -> ReportResult:
        stmt = (
            select(
                Invoice.invoice_no,
                Invoice.invoice_date,
                Customer.name,
                Invoice.subtotal_minor,
                Invoice.tax_minor,
                Invoice.total_minor,
                Invoice.status,
            )
            .join(Customer, Customer.id == Invoice.customer_id)
            .where(Invoice.deleted_at.is_(None))
        )
        if date_from:
            stmt = stmt.where(Invoice.invoice_date >= date_from)
        if date_to:
            stmt = stmt.where(Invoice.invoice_date <= date_to)
        stmt = stmt.order_by(Invoice.invoice_date.desc(), Invoice.invoice_no.desc())
        rows = [
            {
                "invoice_no": r[0],
                "date": r[1].isoformat() if r[1] else "",
                "customer": r[2],
                "subtotal_minor": int(r[3]),
                "tax_minor": int(r[4]),
                "total_minor": int(r[5]),
                "status": r[6],
            }
            for r in self.db.execute(stmt).all()
        ]
        return ReportResult(
            key="sales-register",
            title="Sales Register",
            columns=["invoice_no", "date", "customer", "subtotal_minor", "tax_minor", "total_minor", "status"],
            rows=rows,
            money_columns={"subtotal_minor", "tax_minor", "total_minor"},
        )

    def _purchase_register(self, date_from, date_to) -> ReportResult:
        stmt = (
            select(
                Bill.bill_no,
                Bill.bill_date,
                Supplier.name,
                Bill.subtotal_minor,
                Bill.tax_minor,
                Bill.total_minor,
                Bill.status,
            )
            .join(Supplier, Supplier.id == Bill.supplier_id)
            .where(Bill.deleted_at.is_(None))
        )
        if date_from:
            stmt = stmt.where(Bill.bill_date >= date_from)
        if date_to:
            stmt = stmt.where(Bill.bill_date <= date_to)
        stmt = stmt.order_by(Bill.bill_date.desc(), Bill.bill_no.desc())
        rows = [
            {
                "bill_no": r[0],
                "date": r[1].isoformat() if r[1] else "",
                "supplier": r[2],
                "subtotal_minor": int(r[3]),
                "tax_minor": int(r[4]),
                "total_minor": int(r[5]),
                "status": r[6],
            }
            for r in self.db.execute(stmt).all()
        ]
        return ReportResult(
            key="purchase-register",
            title="Purchase Register",
            columns=["bill_no", "date", "supplier", "subtotal_minor", "tax_minor", "total_minor", "status"],
            rows=rows,
            money_columns={"subtotal_minor", "tax_minor", "total_minor"},
        )

    def _stock_ledger(self, date_from, date_to) -> ReportResult:
        stmt = (
            select(
                StockMovement.occurred_at,
                Product.sku_code,
                Product.name,
                Warehouse.name,
                StockMovement.qty_delta,
                StockMovement.reason,
                StockMovement.ref_type,
            )
            .join(Product, Product.id == StockMovement.product_id)
            .join(Warehouse, Warehouse.id == StockMovement.warehouse_id)
            .where(StockMovement.deleted_at.is_(None))
        )
        if date_from:
            stmt = stmt.where(func.date(StockMovement.occurred_at) >= date_from)
        if date_to:
            stmt = stmt.where(func.date(StockMovement.occurred_at) <= date_to)
        stmt = stmt.order_by(StockMovement.occurred_at.desc())
        rows = [
            {
                "date": r[0].isoformat() if r[0] else "",
                "sku_code": r[1],
                "product": r[2],
                "warehouse": r[3],
                "qty_delta": str(r[4]),
                "reason": r[5],
                "ref_type": r[6] or "",
            }
            for r in self.db.execute(stmt).all()
        ]
        return ReportResult(
            key="stock-ledger",
            title="Stock Ledger",
            columns=["date", "sku_code", "product", "warehouse", "qty_delta", "reason", "ref_type"],
            rows=rows,
        )

    # --- the two ageing reports DELEGATE (R10.5, G16) -----------------------
    #
    # These two builders each had their own arithmetic until Part 8 C1, and it was wrong.
    # Neither AGED anything despite the name — no due date, no buckets, just outstanding
    # per party — and `_ar_aging` never subtracted credit notes, so it had disagreed with
    # `CustomerRepository.outstanding_minor` from the moment Part 7 introduced them. Two
    # definitions of the receivable is precisely the defect R10.x exists to prevent, and it
    # was already in the tree. They now call `AgeingService`, the one projection the
    # /finance/ageing screen renders.
    #
    # The report's date window maps to the ageing report's AS-OF date: `to` is "age it as
    # at this date" and `from` has no meaning for a point-in-time balance, so it is ignored
    # rather than silently changing what the buckets mean.

    def _ageing_result(self, report, *, key: str, title: str, party_label: str) -> ReportResult:
        from app.modules.finance.schemas import AR_AGE_BUCKETS

        bucket_cols = [f"bucket_{bkey}" for bkey, _l, _u in AR_AGE_BUCKETS]
        columns = [
            party_label,
            "outstanding_minor",
            "not_yet_due_minor",
            "overdue_minor",
            *bucket_cols,
            "oldest_days_overdue",
        ]
        rows = []
        for row in report.rows:
            rows.append(
                {
                    party_label: row.party_name,
                    "outstanding_minor": row.outstanding_minor,
                    "not_yet_due_minor": row.due_minor,
                    "overdue_minor": row.overdue_minor,
                    **{f"bucket_{k}": row.buckets.get(k, 0) for k, _l, _u in AR_AGE_BUCKETS},
                    "oldest_days_overdue": row.oldest_days_overdue,
                }
            )
        return ReportResult(
            key=key,
            title=title,
            columns=columns,
            rows=rows,
            money_columns={
                "outstanding_minor",
                "not_yet_due_minor",
                "overdue_minor",
                *bucket_cols,
            },
        )

    def _ar_aging(self, date_from, date_to) -> ReportResult:
        from app.modules.finance.ageing import AgeingService

        report = AgeingService(self.db).ar_ageing(as_of=date_to)
        return self._ageing_result(
            report,
            key="ar-aging",
            title=f"Accounts Receivable Ageing (as at {report.as_of.isoformat()})",
            party_label="customer",
        )

    def _ap_aging(self, date_from, date_to) -> ReportResult:
        from app.modules.finance.ageing import AgeingService

        report = AgeingService(self.db).ap_ageing(as_of=date_to)
        return self._ageing_result(
            report,
            key="ap-aging",
            title=f"Accounts Payable Ageing (as at {report.as_of.isoformat()})",
            party_label="supplier",
        )

    def _gst_summary(self, date_from, date_to) -> ReportResult:
        # Output tax collected (sales) and tax paid (purchases) per invoice/bill window.
        inv_stmt = select(
            func.coalesce(func.sum(Invoice.subtotal_minor), 0),
            func.coalesce(func.sum(Invoice.tax_minor), 0),
        ).where(Invoice.status != "cancelled", Invoice.deleted_at.is_(None))
        bill_stmt = select(
            func.coalesce(func.sum(Bill.subtotal_minor), 0),
            func.coalesce(func.sum(Bill.tax_minor), 0),
        ).where(Bill.status != "cancelled", Bill.deleted_at.is_(None))
        if date_from:
            inv_stmt = inv_stmt.where(Invoice.invoice_date >= date_from)
            bill_stmt = bill_stmt.where(Bill.bill_date >= date_from)
        if date_to:
            inv_stmt = inv_stmt.where(Invoice.invoice_date <= date_to)
            bill_stmt = bill_stmt.where(Bill.bill_date <= date_to)
        inv_sub, inv_tax = self.db.execute(inv_stmt).one()
        bill_sub, bill_tax = self.db.execute(bill_stmt).one()
        rows = [
            {"kind": "Output GST (sales)", "taxable_minor": int(inv_sub), "tax_minor": int(inv_tax)},
            {"kind": "Input GST (purchases)", "taxable_minor": int(bill_sub), "tax_minor": int(bill_tax)},
            {
                "kind": "Net GST payable",
                "taxable_minor": 0,
                "tax_minor": int(inv_tax) - int(bill_tax),
            },
        ]
        return ReportResult(
            key="gst-summary",
            title="GST Summary",
            columns=["kind", "taxable_minor", "tax_minor"],
            rows=rows,
            money_columns={"taxable_minor", "tax_minor"},
        )

    # --- CSV rendering --------------------------------------------------
    @staticmethod
    def to_csv(result: ReportResult) -> str:
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(result.columns)
        for row in result.rows:
            out = []
            for col in result.columns:
                val = row.get(col, "")
                if col in result.money_columns and isinstance(val, (int, float, Decimal)):
                    out.append(f"{Decimal(val) / 100:.2f}")
                else:
                    out.append(val)
            writer.writerow(out)
        return buf.getvalue()

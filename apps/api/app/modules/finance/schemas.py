"""Finance schemas."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from app.db.explain import Explained


class InvoiceLineRead(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    product_name: str | None = None
    qty: Decimal
    unit_price_minor: int
    tax_rate_bps: int
    line_subtotal_minor: int
    line_tax_minor: int
    line_total_minor: int


class InvoiceListRow(BaseModel):
    """One invoice as a list row.

    `balance_minor` is `total − paid − credited` — the ONE open-balance definition, the
    same three terms `CustomerRepository.outstanding_minor` sums. It omitted the credit
    note until Part 8 C1, which meant this column disagreed with the customer's
    receivable from the moment Part 7 shipped returns.
    """

    id: uuid.UUID
    invoice_no: str
    customer_name: str | None = None
    total_minor: int
    paid_minor: int
    credited_minor: int = 0
    balance_minor: int
    status: str
    invoice_date: date
    due_date: date | None = None


class InvoiceDetail(BaseModel):
    id: uuid.UUID
    invoice_no: str
    customer_id: uuid.UUID
    customer_name: str | None = None
    sales_order_id: uuid.UUID | None = None
    status: str
    invoice_date: date
    due_date: date | None = None
    subtotal_minor: int
    tax_minor: int
    total_minor: int
    paid_minor: int
    credited_minor: int = 0
    balance_minor: int
    lines: list[InvoiceLineRead]


class PaymentCreate(BaseModel):
    amount_minor: int = Field(gt=0)
    method: str = "bank"


class PaymentResult(BaseModel):
    payment_id: uuid.UUID
    payment_no: str
    invoice_id: uuid.UUID
    amount_minor: int
    invoice_status: str
    balance_minor: int


# --- Bills (buy side; mirror of Invoice) ---------------------------------


class BillLineRead(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    product_name: str | None = None
    qty: Decimal
    unit_price_minor: int
    tax_rate_bps: int
    line_subtotal_minor: int
    line_tax_minor: int
    line_total_minor: int


class BillListRow(BaseModel):
    id: uuid.UUID
    bill_no: str
    supplier_name: str | None = None
    total_minor: int
    paid_minor: int
    balance_minor: int
    status: str
    bill_date: date
    due_date: date | None = None


class BillDetail(BaseModel):
    id: uuid.UUID
    bill_no: str
    supplier_id: uuid.UUID
    supplier_name: str | None = None
    purchase_order_id: uuid.UUID | None = None
    status: str
    bill_date: date
    due_date: date | None = None
    subtotal_minor: int
    tax_minor: int
    total_minor: int
    paid_minor: int
    balance_minor: int
    lines: list[BillLineRead]


class BillPaymentCreate(BaseModel):
    amount_minor: int = Field(gt=0)
    method: str = "bank"


class BillPaymentResult(BaseModel):
    payment_id: uuid.UUID
    payment_no: str
    bill_id: uuid.UUID
    amount_minor: int
    bill_status: str
    balance_minor: int


# --- Part 8 C1: ledgers, ageing, collections, allocation (R10.x) ----------
#
# Everything below is a READ-ONLY PROJECTION over the append-only invoice / bill /
# payment_allocation / credit_note ledgers (R10.10). No new table, no new column, no
# stored balance — R10.2 and G7 both say the running balance is derived, and Part 8 is
# the part where a mutable `balance_minor` column would have been most tempting.

#: Ageing buckets, by **days overdue** as of the report date (R10.5, R10.6).
#:
#: Shape and convention copied from `inventory/schemas.py:AGE_BUCKETS` — a module
#: constant of `(key, label, inclusive_upper_bound)`, printed on screen, every edge
#: pinned by a test — so the screen, the CSV, the explanation and the tests read one
#: source. `None` as the bound means "no upper bound".
#:
#: **The upper bound is INCLUSIVE** (R6.10's convention, matched rather than
#: contradicted), and the first bucket's bound of 0 is what settles R10.6's awkward
#: case: an invoice whose due date is exactly today has `days_overdue == 0`, lands in
#: `current`, and is therefore **NOT overdue**. Due today is due today, not late.
#: Anything due in the future is negative and lands in the same bucket.
AR_AGE_BUCKETS: tuple[tuple[str, str, int | None], ...] = (
    ("current", "Not yet due", 0),
    ("d1_30", "1–30 days overdue", 30),
    ("d31_60", "31–60 days overdue", 60),
    ("d61_90", "61–90 days overdue", 90),
    ("d90_plus", "Over 90 days overdue", None),
)

#: The one bucket that is not overdue. Named rather than assumed, so the due-vs-overdue
#: split (R10.5) and the collections filter (R10.7) cannot drift apart.
CURRENT_BUCKET = "current"


def bucket_for(days_overdue: int) -> str:
    """The first bucket whose inclusive upper bound covers `days_overdue` (R10.6).

    One rule for every edge: `<=` against the bound, in declaration order. A negative
    value (due in the future) and exactly 0 (due today) both land in `current`.
    """
    for key, _label, upper in AR_AGE_BUCKETS:
        if upper is None or days_overdue <= upper:
            return key
    raise AssertionError("AR_AGE_BUCKETS must end with an unbounded bucket")


class OpenDocument(BaseModel):
    """One invoice or bill with its open balance, derived (G7).

    `open_minor` is `total − Σ allocations − Σ credit notes` for an invoice, and
    `total − Σ allocations` for a bill (no credit notes exist on the buy side).
    **Clamped at zero**: an invoice credited for more than it billed is not
    "negatively open" — the excess is a credit on the party, and the ageing report
    carries it as `unaged_minor` rather than hiding it in a bucket.

    `days_overdue` is `as_of − due_date` in whole days. A NULL `due_date` is aged from
    the invoice date and `due_date_assumed` says so on screen: with no payment terms
    agreed the money is due on issue, which is exactly what `SalesOrderService.invoice`
    already writes when the customer has no credit policy (`payment_terms_days` 0). Two
    customers with the same commercial reality must not land in different buckets.
    """

    id: uuid.UUID
    doc_no: str
    href: str
    party_id: uuid.UUID
    party_name: str | None = None
    doc_date: date
    due_date: date
    due_date_assumed: bool = False
    total_minor: int
    allocated_minor: int
    credited_minor: int
    open_minor: int
    status: str
    days_overdue: int
    bucket: str

    @property
    def is_overdue(self) -> bool:
        return self.bucket != CURRENT_BUCKET


class LedgerLine(BaseModel):
    """One line of a running party statement (R10.1, R10.3, R10.4).

    All four document types R10.4 names produce a line: invoices and bills debit the
    party, credit notes and payment allocations credit them. `href` is never blank —
    R10.3 requires every line to drill through to its source document, and a line with
    nowhere to go is the defect that requirement exists to prevent.

    `balance_minor` is the running balance **computed here from the ledger** (R10.2),
    never read from a stored column.
    """

    occurred_on: date
    doc_type: str  # invoice | bill | credit_note | payment
    doc_no: str
    href: str
    detail: str | None = None
    debit_minor: int = 0
    credit_minor: int = 0
    balance_minor: int = 0


class PartyStatement(BaseModel):
    """A customer's or vendor's running statement (R10.1).

    `closing_balance_minor` is **the one receivable / payable definition** —
    `CustomerRepository.outstanding_minor` or `SupplierRepository.outstanding_minor`,
    called rather than re-derived. The lines are built from exactly the three terms
    those methods sum, so `Σ(debit − credit) == closing_balance_minor` holds by
    construction and is asserted by a test rather than hoped for.
    """

    side: str  # receivable | payable
    party_id: uuid.UUID
    party_name: str
    party_href: str
    lines: list[LedgerLine]
    opening_balance_minor: int = 0
    closing_balance_minor: int = 0
    open_documents: list[OpenDocument] = Field(default_factory=list)

    @property
    def line_total_minor(self) -> int:
        """Σ over the lines of (debit − credit) — the reconciliation figure."""
        return sum(line.debit_minor - line.credit_minor for line in self.lines)


class AgeingBucketTotal(BaseModel):
    key: str
    label: str
    total_minor: int
    count: int


class AgeingPartyRow(BaseModel):
    """One party's outstanding, split across the buckets (R10.5)."""

    party_id: uuid.UUID
    party_name: str
    href: str
    ledger_href: str
    outstanding_minor: int
    due_minor: int
    overdue_minor: int
    unaged_minor: int
    buckets: dict[str, int] = Field(default_factory=dict)
    open_count: int = 0
    oldest_days_overdue: int | None = None
    oldest_doc_no: str | None = None

    def flat(self) -> dict[str, Any]:
        """The row as a flat mapping, for the one CSV writer (R10.12).

        The bucket columns are generated from `AR_AGE_BUCKETS`, so a bucket added to
        the constant appears in the export without touching this method.
        """
        return {
            "party_name": self.party_name,
            "outstanding_minor": self.outstanding_minor,
            "due_minor": self.due_minor,
            "overdue_minor": self.overdue_minor,
            "unaged_minor": self.unaged_minor,
            "open_count": self.open_count,
            "oldest_days_overdue": self.oldest_days_overdue,
            **{f"bucket_{key}": self.buckets.get(key, 0) for key, _l, _u in AR_AGE_BUCKETS},
        }


class AgeingReport(BaseModel):
    """AR or AP outstanding with buckets and the due-vs-overdue split (R10.5).

    `unaged_minor` is the reconciling term, and it exists so that

        Σ bucket totals + unaged_minor == Σ party outstanding

    holds **unconditionally**. It is non-zero only when a credit or an allocation does
    not sit against an open invoice — a credit note larger than the invoice it credits,
    or a payment against a since-cancelled invoice. Reporting it as its own figure is
    what keeps ONE definition of the receivable: the alternative is a bucket total that
    quietly disagrees with `CustomerRepository.outstanding_minor`, which is the exact
    defect R10.x exists to prevent.
    """

    side: str  # receivable | payable
    as_of: date
    buckets: list[AgeingBucketTotal]
    rows: list[AgeingPartyRow]
    total_minor: int = 0
    due_minor: int = 0
    overdue_minor: int = 0
    unaged_minor: int = 0

    @property
    def bucket_total_minor(self) -> int:
        return sum(b.total_minor for b in self.buckets)


class CollectionsEntry(BaseModel):
    """One party to chase today, with the reason stated (R10.7).

    `reason` is R10.7's "reason per entry" in one sentence; `explained` is G11's full
    shape behind it — the inputs, the formula the ordering uses, the window, and links
    to the invoices it reasoned from. A collections list is a recommendation, so it owes
    G11 an explanation and gets the ONE implementation of it rather than a new one.
    """

    customer_id: uuid.UUID
    customer_name: str
    href: str
    ledger_href: str
    outstanding_minor: int
    overdue_minor: int
    oldest_days_overdue: int
    oldest_doc_no: str
    oldest_doc_href: str
    open_count: int
    reason: str
    explained: Explained | None = None

    def flat(self) -> dict[str, Any]:
        return {
            "customer_name": self.customer_name,
            "overdue_minor": self.overdue_minor,
            "outstanding_minor": self.outstanding_minor,
            "oldest_days_overdue": self.oldest_days_overdue,
            "oldest_doc_no": self.oldest_doc_no,
            "open_count": self.open_count,
            "reason": self.reason,
        }


class PaymentsDueEntry(BaseModel):
    """One bill to pay, oldest due first (R10.8) — the payable-side mirror."""

    bill_id: uuid.UUID
    bill_no: str
    href: str
    supplier_id: uuid.UUID
    supplier_name: str
    ledger_href: str
    due_date: date
    due_date_assumed: bool = False
    days_overdue: int
    bucket: str
    bucket_label: str
    open_minor: int

    def flat(self) -> dict[str, Any]:
        return {
            "bill_no": self.bill_no,
            "supplier_name": self.supplier_name,
            "due_date": self.due_date,
            "days_overdue": self.days_overdue,
            "bucket_label": self.bucket_label,
            "open_minor": self.open_minor,
        }


class AllocationCreate(BaseModel):
    """A receipt or payment to spread across a party's open documents (R10.9)."""

    amount_minor: int = Field(gt=0)
    method: str = "bank"


class AllocationLine(BaseModel):
    """How much of the money landed on one document, and where that left it."""

    document_id: uuid.UUID
    doc_no: str
    href: str
    applied_minor: int
    open_before_minor: int
    open_after_minor: int
    status_after: str


class AllocationResult(BaseModel):
    """The outcome of spreading one payment across several documents (R10.9).

    `allocated_minor` always equals the amount received: a receipt larger than the
    party's total open balance is REFUSED rather than partly absorbed, so there is no
    unapplied remainder for the receivable definition to disagree about.
    """

    payment_id: uuid.UUID
    payment_no: str
    side: str  # receivable | payable
    party_id: uuid.UUID
    amount_minor: int
    allocated_minor: int
    lines: list[AllocationLine]


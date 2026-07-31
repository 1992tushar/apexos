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


# --- Part 13: the GST tax-invoice print view (R16.x) ----------------------
#
# A different SHAPE from `InvoiceDetail` (which drives the dashboard view), not a
# second source of the figures: every amount below is read from the same `Invoice`/
# `InvoiceLine` rows, and the CGST/SGST/IGST split is arithmetic over `tax_rate_bps`/
# `line_tax_minor`, never a new stored column (G7).


class InvoicePrintLine(BaseModel):
    line_no: int
    product_name: str
    hsn_code: str | None = None
    qty: Decimal
    unit_price_minor: int
    taxable_minor: int
    cgst_bps: int
    sgst_bps: int
    igst_bps: int
    cgst_minor: int
    sgst_minor: int
    igst_minor: int
    line_total_minor: int


class InvoicePrintView(BaseModel):
    """Everything a printable GST tax invoice needs, assembled in one place so the
    template holds no query and no arithmetic (R16.4)."""

    id: uuid.UUID
    invoice_no: str
    invoice_date: date
    due_date: date | None = None

    company_legal_name: str
    company_address_line1: str
    company_address_line2: str | None = None
    company_city: str
    company_state: str
    company_pincode: str | None = None
    company_gstin: str | None = None
    company_pan: str | None = None
    company_phone: str | None = None
    company_email: str | None = None
    company_bank_name: str | None = None
    company_bank_account_no: str | None = None
    company_bank_ifsc: str | None = None
    company_signatory_name: str | None = None
    company_is_placeholder: bool

    customer_name: str
    customer_gstin: str | None = None
    customer_billing_address: str | None = None
    customer_city: str | None = None
    customer_state: str | None = None

    same_state: bool
    state_assumed: bool

    lines: list[InvoicePrintLine]
    subtotal_minor: int
    tax_minor: int
    cgst_total_minor: int
    sgst_total_minor: int
    igst_total_minor: int
    total_minor: int


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


# --- Part 8 C2: cash flow, working capital, the cash conversion cycle (R11.x) ---
#
# C1's projections are point-in-time and take `as_of`. These are FLOWS, so every one of
# them takes an explicit `date_from` / `date_to` — that is R11.13, and it is the contract
# Parts 9 and 10 consume rather than recompute.


class CashFlowPeriodRow(BaseModel):
    """One calendar month of actual cash movement (R11.1).

    Monthly rather than daily: a founder reads a trend off twelve rows, not off three
    hundred, and R11.14 says a figure that does not change a decision does not belong.
    """

    label: str
    date_from: date
    date_to: date
    in_minor: int
    out_minor: int
    net_minor: int
    receipts: int
    payments: int

    def flat(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "in_minor": self.in_minor,
            "out_minor": self.out_minor,
            "net_minor": self.net_minor,
            "receipts": self.receipts,
            "payments": self.payments,
        }


class CommittedCash(BaseModel):
    """Money contractually due in the window, and the pipeline behind it (R11.2).

    **R11.2 requires this to be defined on screen, naming exactly what it includes**, so
    `terms` carries those sentences and the template prints them verbatim. They are held
    here rather than in the template because the test that proves the figure matches its
    stated definition has to read the same words the founder does.

    The split is the honest one:

    * **committed** — invoices and bills that exist and have a **due date inside the
      window**. Reconstructible to the rupee from the ageing screen.
    * **pipeline** — confirmed sales orders not yet invoiced, and confirmed purchase
      orders not yet billed. Real commitments, but **no due date exists** for either: a
      due date is created when the order is invoiced or the PO is billed. Folding them
      into "committed" would mean inventing a date, so they are reported beside it and
      excluded from the total.
    """

    in_minor: int
    out_minor: int
    pipeline_in_minor: int
    pipeline_out_minor: int
    invoice_count: int
    bill_count: int
    pipeline_order_count: int
    pipeline_po_count: int
    terms: list[str] = Field(default_factory=list)

    @property
    def net_minor(self) -> int:
        return self.in_minor - self.out_minor

    @property
    def pipeline_net_minor(self) -> int:
        return self.pipeline_in_minor - self.pipeline_out_minor


class CashFlowReport(BaseModel):
    """Actual and committed cash over an explicit window (R11.1, R11.2, R11.13)."""

    date_from: date
    date_to: date
    rows: list[CashFlowPeriodRow]
    actual_in_minor: int
    actual_out_minor: int
    committed: CommittedCash

    @property
    def actual_net_minor(self) -> int:
        return self.actual_in_minor - self.actual_out_minor

    @property
    def projected_net_minor(self) -> int:
        """Actual net plus committed net. **Not** a forecast — no estimate is involved,
        only documents that already exist. The pipeline is excluded, as above."""
        return self.actual_net_minor + self.committed.net_minor


class WorkingCapitalSnapshot(BaseModel):
    """Working capital as at a date (R11.3).

    **Cash at bank is not part of this, because ApexOS does not track a bank balance.**
    Saying so is the point: a "working capital" figure that silently omits cash would be
    read as though it included it. `caveat` carries that sentence to the screen.
    """

    as_of: date
    receivables_minor: int
    inventory_minor: int
    payables_minor: int
    inventory_known: bool
    products_without_cost: int
    caveat: str

    @property
    def working_capital_minor(self) -> int:
        return self.receivables_minor + self.inventory_minor - self.payables_minor

    def flat(self) -> dict[str, Any]:
        return {
            "component": None,
            "receivables_minor": self.receivables_minor,
            "inventory_minor": self.inventory_minor,
            "payables_minor": self.payables_minor,
            "working_capital_minor": self.working_capital_minor,
        }


class CashCycleReport(BaseModel):
    """DSO, DIO, DPO and the cycle they add up to (R11.4).

    **Each component is reported individually**, which is the whole of R11.4: a single CCC
    number tells the founder nothing about which of the three to act on. Each carries its
    own `Explained` — the formula, the window, the inputs and the records — and any
    component whose denominator is zero is `Explained.unknown`, never 0 (G11).

    `ccc_days` is None whenever **any** component is unknown. A cycle built from two of
    three terms would be a smaller number that looks like good news.
    """

    date_from: date
    date_to: date
    window_days: int
    dso_days: int | None
    dio_days: int | None
    dpo_days: int | None
    ccc_days: int | None
    dso: Explained
    dio: Explained
    dpo: Explained
    ccc: Explained

    @property
    def components(self) -> list[tuple[str, int | None, Explained]]:
        return [
            ("DSO — days sales outstanding", self.dso_days, self.dso),
            ("DIO — days inventory outstanding", self.dio_days, self.dio),
            ("DPO — days payables outstanding", self.dpo_days, self.dpo),
        ]

    def flat_rows(self) -> list[dict[str, Any]]:
        rows = [
            {"component": label, "days": days, "formula": exp.formula, "window": exp.window}
            for label, days, exp in self.components
        ]
        rows.append(
            {
                "component": "CCC — cash conversion cycle",
                "days": self.ccc_days,
                "formula": self.ccc.formula,
                "window": self.ccc.window,
            }
        )
        return rows


# --- Part 8 C3: margin, leakage, GST (R11.5–R11.10) -----------------------
#
# All windowed (R11.13), all projections (R11.10/G15), and all tax-EXCLUSIVE where margin is
# concerned: GST is collected on the customer's behalf, not earned, so it has no place in a
# margin ratio. C2's `_cogs` already made that choice for DIO and this keeps to it.

#: The four dimensions R11.5 names, as `(key, label)`. A module constant so the screen, the
#: export and the tests read one source, and so `by_dimension` is ONE projection
#: parameterised by key rather than four near-copies of the same query.
MARGIN_DIMENSIONS: tuple[tuple[str, str], ...] = (
    ("product", "Product"),
    ("customer", "Customer"),
    ("category", "Category"),
    ("business_unit", "Business unit"),
)

#: A line sold more than this far below the product's current list price is discount creep.
#: **Strictly more than** — exactly 1500 bps (15%) is not yet an offender, and both sides of
#: that edge are pinned by a test, the same way `AR_AGE_BUCKETS` pins its boundaries.
DISCOUNT_CREEP_BPS = 1500


class MarginRow(BaseModel):
    """One dimension member's revenue, cost and gross profit (R11.5).

    `margin_bps` is integer basis points and is **None when it cannot be computed** — no
    revenue, or every line's cost unknown. `unknown_cost_lines` is never hidden: a product
    with no recorded purchase price would otherwise report a 100% margin, which is the
    single most misleading number this checkpoint could have produced (G11).
    """

    key: uuid.UUID | None
    label: str
    href: str | None = None
    revenue_minor: int
    cost_minor: int
    gp_minor: int
    margin_bps: int | None
    line_count: int
    unknown_cost_lines: int = 0

    @property
    def cost_is_complete(self) -> bool:
        return self.unknown_cost_lines == 0

    def flat(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "revenue_minor": self.revenue_minor,
            "cost_minor": self.cost_minor,
            "gp_minor": self.gp_minor,
            "margin_bps": self.margin_bps,
            "line_count": self.line_count,
            "unknown_cost_lines": self.unknown_cost_lines,
        }


class MarginReport(BaseModel):
    """Margin across one of the four dimensions, over an explicit window (R11.5, R11.13)."""

    dimension: str
    dimension_label: str
    date_from: date
    date_to: date
    rows: list[MarginRow]
    revenue_minor: int
    cost_minor: int
    gp_minor: int
    margin_bps: int | None
    line_count: int
    unknown_cost_lines: int
    explained: Explained


class LeakageRecord(BaseModel):
    """One specific offending line — R11.8's "something to click"."""

    doc_no: str
    href: str
    occurred_on: date
    product_name: str
    party_name: str | None = None
    qty: Decimal
    unit_price_minor: int
    reference_minor: int
    reference_label: str
    impact_minor: int
    detail: str

    def flat(self) -> dict[str, Any]:
        return {
            "doc_no": self.doc_no,
            "occurred_on": self.occurred_on,
            "product_name": self.product_name,
            "party_name": self.party_name,
            "qty": self.qty,
            "unit_price_minor": self.unit_price_minor,
            "reference_minor": self.reference_minor,
            "impact_minor": self.impact_minor,
            "detail": self.detail,
        }


class LeakageIndicator(BaseModel):
    """One indicator, with the records it fired on (R11.7, R11.8).

    `rule` is printed on screen so the founder can check the arithmetic, and `records` is
    the point of the whole thing: **R11.8 says an indicator with nothing to click must be
    removed**, so an indicator that cannot ever produce records is not built at all. One
    that simply found nothing *this window* still appears and says so — that is a clean
    result, not an empty feature.
    """

    key: str
    label: str
    rule: str
    records: list[LeakageRecord]
    impact_minor: int
    explained: Explained

    @property
    def fired(self) -> bool:
        return bool(self.records)


class LeakageReport(BaseModel):
    """The computable indicators, plus an honest note about the one that is not (R11.7).

    `not_measured` is deliberately NOT a list of empty indicators. It names what the data
    cannot support and why, which is different from an indicator reporting no offenders —
    and leaving it silent would have the founder assume freight was checked and clean.
    """

    date_from: date
    date_to: date
    indicators: list[LeakageIndicator]
    not_measured: list[dict[str, str]] = Field(default_factory=list)

    @property
    def total_impact_minor(self) -> int:
        """Σ over the indicators of what each measured.

        **Not presented as a single "total leakage" figure**, and the screen says why: the
        indicators measure different quantities — money lost against cost, money given away
        against list — and one line can appear under both. Summing them would read as a loss
        nobody made. Kept as a property because "did anything fire at all" is a useful test.
        """
        return sum(i.impact_minor for i in self.indicators)

    @property
    def flagged_line_count(self) -> int:
        """Distinct offending lines, counted once even where two indicators flag them."""
        return len(
            {
                (record.doc_no, record.product_name)
                for indicator in self.indicators
                for record in indicator.records
            }
        )

    @property
    def fired(self) -> list[LeakageIndicator]:
        return [i for i in self.indicators if i.fired]


class GstPeriodRow(BaseModel):
    """One calendar month of GST (R11.9). Output − input = the net position."""

    label: str
    period_from: date
    period_to: date
    output_taxable_minor: int
    output_tax_minor: int
    input_taxable_minor: int
    input_tax_minor: int

    @property
    def net_tax_minor(self) -> int:
        return self.output_tax_minor - self.input_tax_minor

    def flat(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "output_taxable_minor": self.output_taxable_minor,
            "output_tax_minor": self.output_tax_minor,
            "input_taxable_minor": self.input_taxable_minor,
            "input_tax_minor": self.input_tax_minor,
            "net_tax_minor": self.net_tax_minor,
        }


class GstSummary(BaseModel):
    """Output tax, input tax and the net position, BY PERIOD (R11.9).

    A report and nothing more (R11.10): no return-filing workflow, no submission, no
    reconciliation against a portal. `net_tax_minor` positive means payable, negative means
    a credit — the screen says which rather than leaving a signed number to be interpreted.
    """

    date_from: date
    date_to: date
    rows: list[GstPeriodRow]

    @property
    def output_tax_minor(self) -> int:
        return sum(r.output_tax_minor for r in self.rows)

    @property
    def input_tax_minor(self) -> int:
        return sum(r.input_tax_minor for r in self.rows)

    @property
    def net_tax_minor(self) -> int:
        return self.output_tax_minor - self.input_tax_minor

    @property
    def output_taxable_minor(self) -> int:
        return sum(r.output_taxable_minor for r in self.rows)

    @property
    def input_taxable_minor(self) -> int:
        return sum(r.input_taxable_minor for r in self.rows)


"""Part 8 C1 — AR/AP ageing, the boundaries, collections and payments due.

Covers R10.5, R10.6, R10.7, R10.8, R10.10, R10.11 and R10.12. Two of these are the ones
worth reading twice:

* `test_r10_6_the_bucket_boundaries_are_exact_at_every_edge` pins **every** edge of the
  constant, including the one R10.6 singles out — an invoice due exactly today.
* `test_r10_5_the_buckets_reconcile_to_the_one_receivable` proves the bucket split and
  `CustomerRepository.outstanding_minor` are the same money, per party and in total.
"""
from __future__ import annotations

import csv
import io
from datetime import date, timedelta

from sqlalchemy import func, select

from app.modules.activity.models import ActivityLog
from app.modules.customers.repository import CustomerRepository
from app.modules.finance.ageing import AgeingService, bucket_boundaries
from app.modules.finance.ledger import open_bills, open_invoices
from app.modules.finance.repository import FinanceRepository
from app.modules.finance.schemas import AR_AGE_BUCKETS, CURRENT_BUCKET, bucket_for
from app.modules.suppliers.repository import SupplierRepository

# --- R10.6: the boundaries, as a pure function ------------------------------


def test_r10_6_the_bucket_boundaries_are_exact_at_every_edge():
    """Every edge of `AR_AGE_BUCKETS`, including both sides of each bound.

    The upper bound is INCLUSIVE, matching R6.10's convention on stock ageing, so 30 is in
    `d1_30` and 31 has moved on. `0` is the case R10.6 names: due today is not overdue.
    """
    assert bucket_for(-365) == "current"
    assert bucket_for(-1) == "current"
    assert bucket_for(0) == "current", "an invoice due exactly today was treated as overdue"
    assert bucket_for(1) == "d1_30"
    assert bucket_for(30) == "d1_30", "30 days is the inclusive upper bound of the first bucket"
    assert bucket_for(31) == "d31_60"
    assert bucket_for(60) == "d31_60"
    assert bucket_for(61) == "d61_90"
    assert bucket_for(90) == "d61_90"
    assert bucket_for(91) == "d90_plus"
    assert bucket_for(10_000) == "d90_plus"


def test_r10_6_the_boundaries_are_printed_on_screen_not_merely_implied():
    """R10.5/R10.6: the rule is stated, so a figure can be checked by hand."""
    rows = bucket_boundaries()
    assert len(rows) == len(AR_AGE_BUCKETS)
    assert [r["key"] for r in rows] == [key for key, _l, _u in AR_AGE_BUCKETS]
    for row in rows:
        assert row["rule"], f"{row['key']} has no stated rule"
    assert "NOT overdue" in rows[0]["rule"]
    assert "30 included" in rows[1]["rule"]


def test_r10_6_the_last_bucket_is_unbounded():
    """Without an unbounded tail, an ancient invoice falls out of every bucket."""
    assert AR_AGE_BUCKETS[-1][2] is None
    bounds = [upper for _k, _l, upper in AR_AGE_BUCKETS[:-1]]
    assert bounds == sorted(bounds), "the buckets are not in ascending order"


# --- R10.5: the ageing report ------------------------------------------------


def test_r10_5_the_bulk_receivable_is_the_same_arithmetic_as_the_single_one(db):
    """`outstanding_by_customer` is a sibling of `outstanding_minor`, not a rival."""
    repo = CustomerRepository(db)
    bulk = repo.outstanding_by_customer()
    assert len(bulk) >= 3, f"only {len(bulk)} customers have finance history — too thin"
    for customer_id, amount in bulk.items():
        assert amount == repo.outstanding_minor(customer_id), str(customer_id)


def test_r10_5_the_bulk_payable_is_the_same_arithmetic_as_the_single_one(db):
    repo = SupplierRepository(db)
    bulk = repo.outstanding_by_supplier()
    assert bulk, "no supplier has a bill"
    for supplier_id, amount in bulk.items():
        assert amount == repo.outstanding_minor(supplier_id), str(supplier_id)


def test_r10_5_the_buckets_reconcile_to_the_one_receivable(db):
    """Per party and in total: Σ buckets + unaged == the one receivable definition."""
    repo = CustomerRepository(db)
    report = AgeingService(db).ar_ageing()
    assert report.rows, "the ageing report is empty — the seed cannot exercise it (G14)"

    for row in report.rows:
        aged = sum(row.buckets.values())
        assert aged + row.unaged_minor == row.outstanding_minor, row.party_name
        assert row.outstanding_minor == repo.outstanding_minor(row.party_id), row.party_name
        assert row.due_minor + row.overdue_minor == aged, row.party_name

    assert report.bucket_total_minor + report.unaged_minor == report.total_minor
    assert report.due_minor + report.overdue_minor == report.bucket_total_minor


def test_r10_5_the_payable_buckets_reconcile_to_the_one_payable(db):
    repo = SupplierRepository(db)
    report = AgeingService(db).ap_ageing()
    assert report.rows, "the AP ageing report is empty"
    for row in report.rows:
        assert sum(row.buckets.values()) + row.unaged_minor == row.outstanding_minor
        assert row.outstanding_minor == repo.outstanding_minor(row.party_id), row.party_name


def test_r10_5_the_seed_populates_more_than_one_bucket(db):
    """G14: an ageing screen showing one bucket cannot demonstrate ageing."""
    report = AgeingService(db).ar_ageing()
    filled = [b.key for b in report.buckets if b.count]
    assert len(filled) >= 4, f"only {filled} carry documents — the demo cannot show ageing"
    assert CURRENT_BUCKET in filled, "nothing is not-yet-due, so the split is untested"
    assert "d90_plus" in filled, "nothing is badly overdue, so the tail is untested"


def test_r10_5_a_settled_document_appears_on_no_ageing_screen(db):
    """A paid invoice is not outstanding, and an ageing screen is about what is owed."""
    for doc in open_invoices(db):
        assert doc.open_minor > 0, f"{doc.doc_no} has nothing open but was aged"
    for doc in open_bills(db):
        assert doc.open_minor > 0, f"{doc.doc_no} has nothing open but was aged"

    aged_ids = {doc.id for doc in open_invoices(db)}
    settled = [
        inv
        for inv, _name in FinanceRepository(db).invoices_with_party()
        if inv.id not in aged_ids
    ]
    assert settled, "every invoice is open — the exclusion is untested"


def test_r10_6_an_invoice_due_exactly_today_is_aged_as_current(db):
    """The seeded boundary document, not just the pure function."""
    stamp = date.today()
    due_today = [doc for doc in open_invoices(db, as_of=stamp) if doc.days_overdue == 0]
    assert due_today, "the seed has no invoice due exactly today — R10.6's edge is undemoed"
    for doc in due_today:
        assert doc.bucket == CURRENT_BUCKET, doc.doc_no
        assert not doc.is_overdue, f"{doc.doc_no} is due today and was called overdue"


def test_r10_6_a_missing_due_date_is_aged_from_the_invoice_date(db):
    """`due_date` is nullable; the screen says what a NULL was taken to mean."""
    assumed = [doc for doc in open_invoices(db) if doc.due_date_assumed]
    assert assumed, "the seed has no invoice without a due date — the NULL rule is undemoed"
    for doc in assumed:
        assert doc.due_date == doc.doc_date, doc.doc_no
        assert doc.days_overdue == (date.today() - doc.doc_date).days


def test_r10_6_the_as_of_date_moves_the_buckets(db):
    """Ageing is relative to a report date, so a later date ages things further.

    Without this, `as_of` could be accepted and ignored — and the report would say "as at"
    a date it had not used.
    """
    early = {d.doc_no: d.bucket for d in open_invoices(db, as_of=date.today())}
    late = {d.doc_no: d.bucket for d in open_invoices(db, as_of=date.today() + timedelta(days=95))}
    assert early and late
    moved = [no for no in early if late.get(no) != early[no]]
    assert moved, "shifting the report date 95 days moved nothing between buckets"


# --- R10.7: collections -----------------------------------------------------


def test_r10_7_every_collections_entry_carries_a_reason_and_linked_records(db):
    """R10.7's reason, plus G11's full explanation behind it."""
    entries = AgeingService(db).collections()
    assert entries, "nothing is overdue — the collections view cannot be exercised (G14)"
    for entry in entries:
        assert entry.reason.strip(), entry.customer_name
        assert "overdue" in entry.reason
        assert entry.oldest_doc_no in entry.reason
        explained = entry.explained
        assert explained is not None and explained.is_known, entry.customer_name
        assert explained.formula and explained.window
        assert explained.inputs, "an explanation with no inputs explains nothing"
        assert explained.records, "G11 wants ≥1 record the number was reasoned from"
        for record in explained.records:
            assert record.href and record.href.startswith("/invoices/")


def test_r10_7_the_collections_order_is_deterministic_and_worst_first(db):
    svc = AgeingService(db)
    first = [e.customer_id for e in svc.collections()]
    second = [e.customer_id for e in svc.collections()]
    assert first == second, "two reads produced two orders"

    entries = svc.collections()
    keys = [(-e.oldest_days_overdue, -e.overdue_minor, e.customer_name) for e in entries]
    assert keys == sorted(keys), "the chase list is not in priority order"
    assert entries[0].oldest_days_overdue >= entries[-1].oldest_days_overdue


def test_r10_7_a_customer_with_nothing_overdue_is_not_on_the_chase_list(db):
    """Money not yet due is not a collection problem, and padding the list kills it."""
    chased = {e.customer_id for e in AgeingService(db).collections()}
    report = AgeingService(db).ar_ageing()
    not_yet_due_only = [r for r in report.rows if r.overdue_minor == 0 and r.due_minor > 0]
    assert not_yet_due_only, "no customer owes only not-yet-due money — the filter is untested"
    for row in not_yet_due_only:
        assert row.party_id not in chased, f"{row.party_name} is chased with nothing overdue"


def test_r10_7_the_overdue_figure_is_the_sum_of_the_overdue_documents(db):
    by_party: dict = {}
    for doc in open_invoices(db):
        if doc.is_overdue:
            by_party[doc.party_id] = by_party.get(doc.party_id, 0) + doc.open_minor
    for entry in AgeingService(db).collections():
        assert entry.overdue_minor == by_party[entry.customer_id], entry.customer_name


# --- R10.8: payments due ----------------------------------------------------


def test_r10_8_payments_due_lists_every_open_bill_earliest_due_first(db):
    entries = AgeingService(db).payments_due()
    assert entries, "no bill is open — the payments-due view cannot be exercised (G14)"
    assert len(entries) == len(open_bills(db))
    dues = [(e.due_date, e.bill_no) for e in entries]
    assert dues == sorted(dues), "payments due is not ordered by due date"
    for entry in entries:
        assert entry.open_minor > 0
        assert entry.href.startswith("/bills/")
        assert entry.bucket_label


def test_r10_8_a_bill_due_today_is_not_reported_overdue(db):
    entries = AgeingService(db).payments_due()
    today_entries = [e for e in entries if e.days_overdue == 0]
    assert today_entries, "the seed has no bill due exactly today"
    for entry in today_entries:
        assert entry.bucket == CURRENT_BUCKET, entry.bill_no


# --- R10.10 / R10.11: projections, and no float anywhere --------------------


def test_r10_10_the_ageing_projections_write_no_activity_row(db):
    before = db.scalar(select(func.count()).select_from(ActivityLog)) or 0
    svc = AgeingService(db)
    svc.ar_ageing()
    svc.ap_ageing()
    svc.collections()
    svc.payments_due()
    assert (db.scalar(select(func.count()).select_from(ActivityLog)) or 0) == before


def test_r10_11_every_money_and_ageing_figure_is_an_integer(db):
    """G1/R10.11: no float in a total, a bucket or a day count.

    `isinstance(x, int)` also rejects a `Decimal` that slipped in, and `bool` is excluded
    because `True` is an int and would pass by accident.
    """

    def whole(value, label):
        assert isinstance(value, int) and not isinstance(value, bool), (
            f"{label} is {type(value).__name__}, not an integer"
        )

    svc = AgeingService(db)
    for side, report in (("ar", svc.ar_ageing()), ("ap", svc.ap_ageing())):
        for field in ("total_minor", "due_minor", "overdue_minor", "unaged_minor"):
            whole(getattr(report, field), f"{side}.{field}")
        for bucket in report.buckets:
            whole(bucket.total_minor, f"{side}.{bucket.key}")
            whole(bucket.count, f"{side}.{bucket.key}.count")
        for row in report.rows:
            for field in ("outstanding_minor", "due_minor", "overdue_minor", "unaged_minor"):
                whole(getattr(row, field), f"{side}.{row.party_name}.{field}")
            for key, amount in row.buckets.items():
                whole(amount, f"{side}.{row.party_name}.{key}")
            if row.oldest_days_overdue is not None:
                whole(row.oldest_days_overdue, f"{side}.{row.party_name}.days")

    for entry in AgeingService(db).collections():
        whole(entry.overdue_minor, "collections.overdue")
        whole(entry.outstanding_minor, "collections.outstanding")
        whole(entry.oldest_days_overdue, "collections.days")
    for entry in AgeingService(db).payments_due():
        whole(entry.open_minor, "payments_due.open")
        whole(entry.days_overdue, "payments_due.days")


# --- R10.12: CSV export through Part 2's one export path --------------------


def _rows(body: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(body.lstrip("﻿"))))


def test_r10_12_the_ageing_export_carries_every_row_on_screen(client, db):
    response = client.get("/finance/ageing?export=csv")
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    rows = _rows(response.text)
    assert rows[0][0] == "Party"
    assert len(rows) - 1 == len(AgeingService(db).ar_ageing().rows)
    # The bucket columns come from the constant, so the header proves the two agree.
    for _key, label, _upper in AR_AGE_BUCKETS:
        assert label in rows[0], f"the export is missing the {label!r} bucket column"


def test_r10_12_the_export_respects_the_side_on_screen(client, db):
    payable = _rows(client.get("/finance/ageing?side=payable&export=csv").text)
    assert len(payable) - 1 == len(AgeingService(db).ap_ageing().rows)
    receivable = _rows(client.get("/finance/ageing?export=csv").text)
    assert len(payable) != len(receivable) or payable[1:] != receivable[1:], (
        "the payable and receivable exports are identical — `side` is being ignored"
    )


def test_r10_12_the_collections_and_payments_due_exports_carry_their_reasons(client, db):
    collections = _rows(client.get("/finance/collections?export=csv").text)
    assert collections[0][-1] == "Reason"
    assert len(collections) - 1 == len(AgeingService(db).collections())
    assert all(row[-1].strip() for row in collections[1:]), "a chase line exported no reason"

    due = _rows(client.get("/finance/payments-due?export=csv").text)
    assert due[0][0] == "Bill"
    assert len(due) - 1 == len(AgeingService(db).payments_due())


def test_r10_12_the_ledger_export_carries_the_statement_lines(client, db):
    customer_id, _name = FinanceRepository(db).customers_with_activity()[0]
    from app.modules.finance.ledger import PartyLedgerService

    expected = PartyLedgerService(db).customer_statement(customer_id).lines
    rows = _rows(client.get(f"/finance/ledger?customer_id={customer_id}&export=csv").text)
    assert rows[0] == ["Date", "Type", "Document", "Detail", "Debit", "Credit", "Balance"]
    assert len(rows) - 1 == len(expected)
    closing = expected[-1].balance_minor
    assert rows[-1][-1] == f"{closing // 100}.{closing % 100:02d}"


def test_r10_5_an_unparseable_as_of_renders_the_screen_rather_than_an_error(client):
    """A stale bookmark degrades, the same rule the list machinery follows."""
    for path in ("/finance/ageing", "/finance/collections", "/finance/payments-due"):
        response = client.get(f"{path}?as_of=not-a-date")
        assert response.status_code == 200, path
        assert "text/html" in response.headers["content-type"]

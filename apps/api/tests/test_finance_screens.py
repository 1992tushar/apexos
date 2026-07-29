"""Part 8 C1's screens — that the figures reach the page, and say what they mean.

The route walk in `test_web_smoke.py` already asserts every plain GET renders. These tests
assert the things a 200 cannot: that the bucket rule is *printed* rather than implied
(R10.5/R10.6), that every chase line carries its reason and its explanation (R10.7, G11),
and that R10.3's drill-through has somewhere to land on the invoice itself.

Every assertion is on a phrase that does not straddle a template line break — four earlier
runs were lost to that.
"""
from __future__ import annotations

from sqlalchemy import func, select

from app.modules.activity.models import ActivityLog
from app.modules.finance.ageing import AgeingService
from app.modules.finance.models import CreditNote
from app.modules.finance.repository import FinanceRepository


def test_r10_1_the_ledger_page_with_no_party_renders_a_real_empty_state(client):
    """The route walk requests every plain GET blind, so this must be a screen."""
    r = client.get("/finance/ledger")
    assert r.status_code == 200
    assert "Pick a customer or a vendor to see their running statement." in r.text


def test_r10_1_the_ledger_page_renders_a_statement_and_its_closing_balance(client, db):
    customer_id, name = FinanceRepository(db).customers_with_activity()[0]
    r = client.get(f"/finance/ledger?customer_id={customer_id}")
    assert r.status_code == 200
    assert name in r.text
    assert "Running statement" in r.text
    assert "Closing balance" in r.text


def test_r10_1_the_vendor_side_of_the_ledger_page_renders(client, db):
    supplier_id, name = FinanceRepository(db).suppliers_with_activity()[0]
    r = client.get(f"/finance/ledger?side=payable&supplier_id={supplier_id}")
    assert r.status_code == 200
    assert name in r.text
    assert "Running statement" in r.text


def test_r10_6_the_ageing_page_prints_the_bucket_rule(client):
    """R10.6 is about the boundary being exact; stating it is how a reader can check."""
    r = client.get("/finance/ageing")
    assert r.status_code == 200
    assert "Bucket boundaries" in r.text
    assert "due today is NOT overdue" in r.text
    assert "30 days past the due date, 30 included" in r.text


def test_r10_5_the_ageing_page_shows_the_due_and_overdue_split(client):
    r = client.get("/finance/ageing")
    assert "Not yet due" in r.text
    assert "Overdue" in r.text
    assert "Total outstanding" in r.text


def test_r10_5_the_payable_side_of_the_ageing_page_renders(client):
    r = client.get("/finance/ageing?side=payable")
    assert r.status_code == 200
    assert "Payables ageing" in r.text


def test_r10_7_the_collections_page_shows_a_reason_and_an_explanation_per_entry(client, db):
    entries = AgeingService(db).collections()
    assert entries, "nothing overdue — the collections screen cannot be exercised"
    r = client.get("/finance/collections")
    assert r.status_code == 200
    assert "Priority order" in r.text
    for entry in entries[:3]:
        assert entry.customer_name in r.text
        assert entry.reason in r.text, f"{entry.customer_name}'s reason is not on screen"
        assert entry.oldest_doc_no in r.text
    # G11's panel, rendered by the ONE macro — its formula line proves it is the real thing.
    assert "An invoice due today is not overdue." in r.text


def test_r10_8_the_payments_due_page_lists_the_bills(client, db):
    entries = AgeingService(db).payments_due()
    r = client.get("/finance/payments-due")
    assert r.status_code == 200
    assert "Due list" in r.text
    for entry in entries[:3]:
        assert entry.bill_no in r.text


def test_r10_3_the_invoice_page_shows_what_was_applied_to_it(client, db):
    """The gap R10.3 had: payments have no page and credits rendered only on the customer."""
    note = db.scalar(select(CreditNote).where(CreditNote.deleted_at.is_(None)).limit(1))
    assert note is not None, "no credit note to drill through to"
    r = client.get(f"/invoices/{note.invoice_id}")
    assert r.status_code == 200
    assert "Applied to this invoice" in r.text
    assert note.credit_note_no in r.text
    assert "Open balance" in r.text


def test_r10_3_the_bill_page_shows_what_was_applied_to_it(client, db):
    repo = FinanceRepository(db)
    paid = next(
        (
            bill
            for bill, _name in repo.bills_with_party()
            if repo.allocations_for_bill(bill.id)
        ),
        None,
    )
    assert paid is not None, "no bill has a payment against it"
    r = client.get(f"/bills/{paid.id}")
    assert r.status_code == 200
    assert "Applied to this bill" in r.text


def test_the_finance_index_links_to_all_four_new_screens(client):
    r = client.get("/finance")
    for href in (
        "/finance/collections",
        "/finance/payments-due",
        "/finance/ageing",
        "/finance/ledger",
    ):
        assert f'href="{href}"' in r.text, f"{href} is not reachable from /finance"


def test_r10_10_loading_the_finance_screens_writes_no_activity_row(client, db):
    """G15 — reads own nothing, over HTTP as well as at the service layer."""
    before = db.scalar(select(func.count()).select_from(ActivityLog)) or 0
    for path in (
        "/finance",
        "/finance/ageing",
        "/finance/ageing?side=payable",
        "/finance/collections",
        "/finance/payments-due",
        "/finance/ledger",
    ):
        assert client.get(path).status_code == 200
    db.expire_all()
    assert (db.scalar(select(func.count()).select_from(ActivityLog)) or 0) == before


def test_the_ar_ageing_report_now_delegates_to_the_one_ageing_definition(client, db):
    """`ReportService._ar_aging` had its own arithmetic and it disagreed (G16, R10.5).

    It never subtracted credit notes and aged nothing at all. The report catalogue entry
    still exists — it now renders the same buckets the /finance/ageing screen does.
    """
    from app.modules.reports.service import ReportService

    result = ReportService(db).run("ar-aging", date_from=None, date_to=None)
    report = AgeingService(db).ar_ageing()
    assert len(result.rows) == len(report.rows)
    assert "bucket_d90_plus" in result.columns, "the report is still not ageing anything"
    assert "invoiced_minor" not in result.columns, "the old, credit-note-blind columns survive"
    for row, expected in zip(result.rows, report.rows, strict=True):
        assert row["customer"] == expected.party_name
        assert row["outstanding_minor"] == expected.outstanding_minor

    r = client.get("/reports?report=ar-aging")
    assert r.status_code == 200
    assert "Accounts Receivable Ageing" in r.text


def test_the_ap_ageing_report_delegates_too(db):
    from app.modules.reports.service import ReportService

    result = ReportService(db).run("ap-aging", date_from=None, date_to=None)
    report = AgeingService(db).ap_ageing()
    assert len(result.rows) == len(report.rows)
    assert "bucket_d90_plus" in result.columns
    for row, expected in zip(result.rows, report.rows, strict=True):
        assert row["supplier"] == expected.party_name
        assert row["outstanding_minor"] == expected.outstanding_minor

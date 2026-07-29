# Part 8 — Finance · the part record

> Archived progressively, one checkpoint at a time, so `PROGRESS.md` stays at its cap.
> **A session does not read this file.** It exists for audit.

Part 8 is three checkpoints: **C1** ledgers + AR/AP ageing + collections + allocation ·
**C2** cash flow + working capital + CCC · **C3** margin by four dimensions + leakage + GST.
Not tagged — the user waived tagging for this run, so the SHA table in `PROGRESS.md` is the record.

---

## C1 — customer/vendor ledgers, AR/AP ageing, collections, allocation

**Commit `ec8a573`** · from `3aede6e` · **688 passed** (was 623) · **ruff exactly 37** — zero new
findings, eight parts running.

### Requirements passed

| R | What proves it |
|---|---|
| R10.1 | `test_r10_1_the_customer_statement_lists_every_document_with_a_running_balance`, `…_the_ledger_page_renders_a_statement_and_its_closing_balance`, `…_the_ledger_picker_offers_only_parties_with_documents` |
| R10.2 | `test_r10_2_the_statement_closes_on_the_one_receivable_definition`, `…_the_vendor_statement_closes_on_the_one_payable_definition`, `…_the_running_balance_tracks_a_new_payment`, `…_a_cancelled_invoice_is_excluded_from_both_definitions` |
| R10.3 | `test_r10_3_every_ledger_line_drills_through_to_a_live_document`, `…_the_vendor_statement_drills_through_to_its_bills`, `…_the_invoice_page_shows_what_was_applied_to_it`, `…_the_bill_page_…` |
| R10.4 | `test_r10_4_the_statement_incorporates_invoices_payments_and_credit_notes`, `…_a_credit_note_reduces_the_receivable_without_mutating_its_invoice` |
| R10.5 | `test_r10_5_the_bulk_receivable_is_the_same_arithmetic_as_the_single_one` (+ payable twin), `…_the_buckets_reconcile_to_the_one_receivable` (+ payable twin), `…_the_seed_populates_more_than_one_bucket`, `…_a_settled_document_appears_on_no_ageing_screen` |
| R10.6 | `test_r10_6_the_bucket_boundaries_are_exact_at_every_edge`, `…_an_invoice_due_exactly_today_is_aged_as_current`, `…_a_missing_due_date_is_aged_from_the_invoice_date`, `…_the_as_of_date_moves_the_buckets`, `…_the_boundaries_are_printed_on_screen_not_merely_implied`, `…_the_ageing_page_prints_the_bucket_rule`, `…_the_last_bucket_is_unbounded` |
| R10.7 | `test_r10_7_every_collections_entry_carries_a_reason_and_linked_records`, `…_the_collections_order_is_deterministic_and_worst_first`, `…_a_customer_with_nothing_overdue_is_not_on_the_chase_list`, `…_the_overdue_figure_is_the_sum_of_the_overdue_documents`, `…_the_collections_page_shows_a_reason_and_an_explanation_per_entry` |
| R10.8 | `test_r10_8_payments_due_lists_every_open_bill_earliest_due_first`, `…_a_bill_due_today_is_not_reported_overdue`, `…_the_payments_due_page_lists_the_bills` |
| R10.9 | `test_r10_9_a_partial_payment_spreads_across_multiple_invoices`, `…_an_over_payment_spills_to_the_next_invoice`, `…_the_spill_order_is_oldest_due_first`, `…_more_than_the_total_open_is_refused_with_the_figure`, `…_a_party_with_nothing_open_is_refused`, `…_an_unknown_party_is_a_not_found`, `…_allocation_appends_rows_and_never_edits_the_invoice`, `…_allocation_writes_exactly_one_activity_row`, `…_the_receivable_drops_by_exactly_the_amount_applied`, `…_the_buy_side_allocates_the_same_way` |
| R10.10 | `test_r10_10_reading_a_statement_writes_no_activity_row`, `…_the_ageing_projections_write_no_activity_row`, `…_loading_the_finance_screens_writes_no_activity_row`. **No new model, no new column** — nothing owed to `references.py` |
| R10.11 | `test_r10_11_every_money_and_ageing_figure_is_an_integer` — walks every figure on both reports, both work lists, and rejects `Decimal` and `bool` as well as `float` |
| R10.12 | `test_r10_12_the_ageing_export_carries_every_row_on_screen`, `…_the_export_respects_the_side_on_screen`, `…_the_collections_and_payments_due_exports_carry_their_reasons`, `…_the_ledger_export_carries_the_statement_lines` |
| R10.13 | The whole table above. Its six named cases: running balance across all four document types, ageing boundaries, multi-invoice allocation, over-payment spillover, credit note reducing the receivable without mutating the invoice, collections ordering + reasons |
| R10.14 | Nothing built. No QuickBooks bridge, not even a stub (D-D) |

`pytest -q -k r10_` is the evidence: **58 tests**.

### Two disagreements that were already in the tree

Both are the same mistake in different places, and both are why R10.x exists:

1. **`ReportService._ar_aging` / `_ap_aging`** each had their own arithmetic. Neither *aged* anything
   despite the name — no due date, no buckets, just outstanding per party — and `_ar_aging` never
   subtracted credit notes, so it had disagreed with `CustomerRepository.outstanding_minor` from the
   moment Part 7 shipped returns. Both now delegate to `AgeingService`; the catalogue keys survive,
   the columns are the buckets, and `PaymentAllocation` is no longer imported there.
2. **`InvoiceService`'s `balance_minor` was `total − paid`.** An invoice reduced by a return therefore
   showed a balance the customer did not owe, and `add_payment` validated against that figure — so it
   would have accepted a payment for money already credited. It is now `total − paid − credited`, in
   `list()`, `_to_detail()`, `add_payment()`'s guard and the status cache. `list()` also stopped doing
   two queries per row: it reads the same grouped dicts the projections use.

### Decisions a later checkpoint must not reverse

1. **`outstanding_by_customer()` / `outstanding_by_supplier()` are SIBLINGS, not rivals.** Same terms
   and the same filters as the single-party methods, copied deliberately including the ones that look
   like oversights (the allocation term joins `Invoice` with no status or `deleted_at` filter, so a
   payment against a cancelled invoice is subtracted by both). They exist so the ageing screen does
   not fan out three queries per party. A test asserts they agree for every seeded party.
2. **`unaged_minor` is a deliberate residual.** `Σ buckets + unaged == the party's outstanding` holds
   *unconditionally* because unaged is defined as the difference. It is non-zero only for a credit
   larger than the invoice it credits, or money applied to a since-cancelled invoice. **Do not "fix"
   it by dropping it** — the alternative is a bucket total that quietly disagrees with the receivable.
3. **Due today is NOT overdue.** `AR_AGE_BUCKETS[0]` has an inclusive upper bound of `0`.
4. **A NULL `due_date` is aged from the invoice date**, and the screen says "(assumed)". Zero-day
   terms already produce exactly that due date, so identical commercial reality must not land in two
   different buckets.
5. **A per-document open balance is clamped at zero.** An over-credited invoice is not "negatively
   open"; the excess is a credit on the party and shows up in `unaged_minor`.
6. **Allocation spills oldest DUE first** — `(due_date, doc_no)`, not oldest issued.
7. **A receipt larger than everything open is REFUSED**, naming the figure that would fit. Holding the
   surplus on account would create money `outstanding_minor` cannot see, and then the statement and
   the receivable would disagree — the exact defect this part is about. `InvoiceService.add_payment`
   already refuses a single-invoice over-payment for the same reason.
8. **The statement's money-received term is ALLOCATIONS, not payments.** That is what makes the
   closing balance equal `outstanding_minor` by construction. A payment line shows the amount that
   landed on the named document.
9. **`csv_rows_response` was extracted from `csv_response`**, not written beside it. `csv_text` only
   ever needed the spec for its columns, so a projection exports through Part 2's one path.
   `ReportService.to_csv` is already a second CSV writer; a third would be indefensible.

### Mutation check — four mutations, four caught

| Mutation | Caught by |
|---|---|
| `AR_AGE_BUCKETS[0]` bound `0 → -1` (due today becomes overdue) | 5 tests, all of them R10.6/R10.8 boundary tests |
| Allocation spill suppressed (`remaining = 0`) | 6 of the 10 R10.9 tests |
| `status != "cancelled"` dropped from `invoices_with_party` | exactly `test_r10_2_a_cancelled_invoice_is_excluded_from_both_definitions` |
| `Explained.records` emptied (an alert with nothing to click) | exactly `test_r10_7_every_collections_entry_carries_a_reason_and_linked_records` |

**A PowerShell `Set-Content -Encoding utf8` round-trip corrupted the file it mutated** — `Get-Content`
read UTF-8 as cp1252 and every em dash became mojibake. Reversed by re-encoding
(`text.encode('cp1252')`) and confirmed with `git diff --stat` showing insertions only. **Mutate with
the edit tools, never with `Set-Content`.**

### Verified live, not just in tests

Seeded a scratch DB (port 8032, `DATABASE_URL` — not `APEXOS_DATABASE_URL`), then over real HTTP:
all six screens, all three CSV exports, the `ar-aging` report, the statement → invoice drill-through,
and the allocation POST in both directions. The success flash read
`PAY-00006: applied across 1 document(s), 0 settled`; the refusal read
`99999999.00 is more than the 5950.60 open across 2 invoices. Apply 5950.60 or less.` Ageing headline
figures reconciled on screen: **₹24,712.15 = ₹10,221.75 not yet due + ₹14,490.40 overdue.**

One real defect found this way rather than by a test: `CollectionsEntry.ledger_href` was built and
never rendered. The screen now carries a Statement column, so the field is not dead data.

### Seed

`app/seed/finance.py` — eight invoices and three bills, placed by **offset from the report date** so
every bucket is populated: 120 / 75 (part paid) / 45 / 10 days overdue, **due exactly today**, due in
20 days, **no due date at all**, and one **settled in full** so the exclusion is visible. Bills: 50
days overdue, due today, due in 15 days (part paid). Invoices are written **directly** —
`sales_order_id` is nullable — because the sell loop needs stock and reservations and would leave OPEN
sales orders on customers other tests assert are quiet. Subjects come from `_CUSTOMER_OFFSET = 5` in
code order for the same reason.

### What C1 did not do

- **No cash flow, working capital or CCC** — that is C2 (R11.1–R11.4).
- **No margin, leakage or GST** — C3 (R11.5–R11.14).
- **R11.13's period parameters**: C1's projections take `as_of` (a point-in-time balance is the right
  shape for ageing). **C2 owes Parts 9 and 10 explicit period parameters** on the flow projections,
  and owes the resume block their signatures copied from source.

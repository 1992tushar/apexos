# Part 8 — Finance · the part record

> Archived progressively, one checkpoint at a time, so `PROGRESS.md` stays at its cap.
> **A session does not read this file.** It exists for audit.

Part 8 is three checkpoints: **C1** ledgers + AR/AP ageing + collections + allocation ·
**C2** cash flow + working capital + CCC · **C3** margin by four dimensions + leakage + GST.
Not tagged — the user waived tagging for this run, so the SHA table in `PROGRESS.md` is the record.

---

## C2 — cash flow, working capital, the cash conversion cycle

**Commit `30b3cc1`** · from `ec8a573` · **721 passed** (was 688) · **ruff exactly 37**.
`pytest -q -k r11_` is **29 tests**.

### Requirements passed

| R | What proves it |
|---|---|
| R11.1 | `test_r11_1_actual_cash_is_payments_and_nothing_accrued`, `…_the_monthly_rows_sum_to_the_window_total`, `…_a_window_with_no_payments_is_zero_not_an_error`, `…_projected_net_is_actual_plus_committed_and_excludes_pipeline`, `…_the_cash_screens_state_what_they_are` |
| R11.2 | `test_r11_2_committed_in_is_exactly_the_open_invoices_due_in_the_window`, `…_committed_out_is_exactly_the_open_bills_…`, `…_committed_excludes_a_document_due_outside_the_window`, `…_the_pipeline_is_reported_but_not_inside_committed`, `…_the_stated_definition_names_every_term_of_the_figure` |
| R11.3 | `test_r11_3_working_capital_reads_the_one_receivable_and_payable`, `…_inventory_comes_from_part_5s_valuation`, `…_the_snapshot_says_that_cash_at_bank_is_not_in_it` |
| R11.4 | `test_r11_4_each_cycle_component_is_hand_verified`, `…_the_cycle_is_dso_plus_dio_minus_dpo`, `…_every_component_is_reported_individually`, `…_each_component_explains_itself_with_inputs_and_records`, `…_a_component_with_no_denominator_says_unknown_not_zero`, `…_a_day_count_longer_than_its_own_window_says_it_is_a_direction`, `…_the_caveat_reaches_the_screen_not_only_the_object` |
| R11.11 | `test_r11_11_cogs_is_marginservice_and_not_a_second_cost_derivation`, plus R11.3's two delegation tests |
| R11.12 | `test_r11_12_the_one_division_rounds_once_and_returns_none_on_a_zero_rate`, `…_every_cash_figure_is_an_integer` |
| R11.13 | `test_r11_13_the_window_bounds_are_respected_at_both_ends`, `…_the_default_window_is_the_stated_length`, `…_a_bad_or_reversed_window_renders_the_screen` |
| R11.14 (part) | `test_r11_14_the_cash_flow_export_carries_the_months_on_screen`, `…_the_cash_cycle_export_carries_all_four_components`. **No charts** — both screens are tables. C3 owes the rest of R11.14 for its own views |
| G15 | `test_r11_3_the_cash_projections_write_no_activity_row` |

### Decisions a later checkpoint must not reverse

1. **"Actual" is payments, not accruals.** There is no bank ledger, so cash in/out is what
   was received and paid. A test asserts cash in is *smaller* than everything invoiced, which
   fails if anything starts accruing.
2. **Committed = documents that exist with a due date INSIDE the window.** Pipeline (confirmed
   uninvoiced orders, confirmed unbilled POs) is reported beside it and excluded, because no
   due date exists for either. `COMMITTED_TERMS` is the definition and lives in `cash.py`
   next to the arithmetic — **do not move it into the template**, the test reads it.
3. **`working_capital` takes `as_of`, not a window.** A balance has no window and a parameter
   that looks rigorous while meaning nothing is worse than none.
4. **Cash at bank is excluded and the screen says so.** Do not silently start including a
   cash figure; there is nothing to include it from.
5. **`_days()` is the only division in the module** and returns None on a zero rate. Day
   counts deliberately do NOT go through `round_minor` — that is the one *money* rounding step
   and a day count is not money.
6. **CCC is None when any component is unknown.** Two of three terms would be a smaller
   number that reads as good news.
7. **A component longer than its own window carries a caveat**, and the cycle inherits it. The
   figure is still shown.
8. **COGS is `subtotal − MarginService.gp`**, so one cost definition exists. `gp` uses the
   product's *current* buy price rather than the price at the time of sale — that is the
   existing behaviour R11.6 says to reuse, and DIO's panel states it rather than hiding it.

### The defect the baseline surfaced — `CreditPolicyService.history`

The full suite went red **once**, on `test_r8_3_a_version_carries_forward_what_the_caller_did_not_name`,
and passed on re-run. Not a flake: `history()` ordered by `(valid_from DESC, id DESC)` with a
docstring asserting "keys are UUID v7 and time-ordered, so `id` breaks it by real write order".
**`uuid7()` is not monotonic within a millisecond** — the low bits are `os.urandom` — so two
versions written in one tick came back in a random order and `history()[0]` was sometimes the
superseded row. Every caller of `history()[0]` wanted the current policy.

Fixed by sorting the open row (`valid_to IS NULL`, unique by construction) to the head, so the
tie cannot decide anything.

**The test for it is the interesting part.** A first version forced only the timestamp tie and
**passed under the old ordering** — with three rows, `id DESC` picks the right head about two
times in three. It now also re-keys the open row to `UUID(int=1)` (nothing references a policy
version; `references.py` declares it empty), which the old ordering fails deterministically —
verified by reverting the fix and watching it go red. *A test that forces one half of a race
and trusts luck for the other half is a test that passes without testing anything.*

### Mutation check — three mutations

| Mutation | Caught by |
|---|---|
| `_days` returns 0 instead of None on a zero rate | `test_r11_4_a_component_with_no_denominator_says_unknown_not_zero`, `test_r11_12_the_one_division_…` |
| `committed` drops its due-date window filter | **first pass: only 1 test.** `…_committed_in_is_exactly_the_open_invoices_due_in_the_window` used a 425-day window in which *every* open invoice sat, so the filter was a no-op and the equality held either way. Narrowed to 30 days with an assertion that at least one open invoice falls **outside** it; now 2 tests catch it |
| DSO's numerator and denominator swapped | `…_each_cycle_component_is_hand_verified`, `…_a_component_with_no_denominator_…` |

The middle row is the lesson worth carrying: **an equality assertion between two code paths
only tests what the current data distinguishes** — the trap already recorded twice in this
build, and it caught the session that had just written the warning into the handoff.

### Verified live

Fresh scratch DB on port 8034 (`DATABASE_URL`). Working capital reconciled on screen —
**₹24,712.15 receivables + ₹13,52,085.53 inventory − ₹15,983.93 payables = ₹13,60,813.75** —
with receivables equal to C1's ageing total, which is the R11.11 delegation visible rather than
merely asserted. Cash flow over the default 90-day window: **₹4,849.80 in, ₹6,703.81 out, net
−₹1,854.01**, committed net **₹4,655.69**. DSO 111 days, DPO 63, DIO 10,221, CCC 10,269 — the
three over 90 days each carrying the caveat, DPO correctly without one.

### What C2 did not do

- **No margin, no leakage, no GST** — all C3's (R11.5–R11.10).
- **R11.14 is only half met**: C2's two screens export and carry no charts, but C3 owes the
  same for its own views.
- **`MarginService.gp` calls `latest_purchase_minor` per line**, so COGS costs one query per
  invoice line in the window. Small on the seed and left alone deliberately: Part 11 C1 is
  measurement-only and optimising without a baseline is what R14.7/R14.8 forbid.

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

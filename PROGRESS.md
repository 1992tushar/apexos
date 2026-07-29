# ApexOS — Build Progress

> The source of truth for status. **This file is capped at ~350 lines and does not grow.**
> Closed parts live in `docs/parts/`. A new part's handoff **replaces** the previous one here — never appends.

_Last updated: 2026-07-29_

### What belongs in this file

Exactly one `▶ NEXT SESSION PROMPT` and exactly one `▶ Handoff`, both rewritten — never appended to —
by the session that closes a checkpoint. Anything else belongs in `docs/parts/`.

**This is a hard cap, not a preference.** At Part 3 close this file was **1,212 lines / 90KB ≈ 22k
tokens, re-read at the start of every remaining session**, growing ~300 lines per part — the single
largest avoidable cost in the build. What keeps it down is **archiving progressively**: each finished
checkpoint's record moves to `docs/parts/part-0N.md` as it closes, and the signature block carries
what the NEXT checkpoint needs rather than everything ever built.

Where everything else lives is in `CLAUDE.md`.

---

# ▶ CURRENT WORK — read this first

**Parts 1–7 are COMPLETE and the cross-part E2E gate is CLEAN** (44 checks; record in
`docs/parts/e2e-gate.md`). **Part 8 C1 is DONE.** The build continues at **Part 8 C2 — cash flow,
working capital, cash conversion cycle**.

**All work is on `main`** — no feature branches, no PRs. **Nothing in this run is tagged** (the user
waived it), so this SHA table is what `part-0N-done` would otherwise be.

| Checkpoint | From | Commit | Tests | Ruff |
|---|---|---|---|---|
| **P8-C1** ledgers · AR/AP ageing · collections · allocation | `3aede6e` | **`ec8a573`** | 623 → **688** | 37 → **37** |
| **P8-C2** cash flow · working capital · CCC | `ec8a573` | — | — | — |
| **P8-C3** margin ×4 · leakage · GST — closes Part 8 | — | — | — | — |

**C1's full record is in `docs/parts/part-08.md`. Do not read it** — everything C2 needs is below.

### ▶ How to start the next session

Type **`Start next part of development`** in a fresh session. `CLAUDE.md` binds that phrase to "read
the **▶ NEXT SESSION PROMPT** below and follow it". **The session that closes a checkpoint owns that
prompt** — one still naming last checkpoint's baseline counts is worse than none, because the next
session will trust it.

#### ▶ NEXT SESSION PROMPT — Part 8, C2 (Finance: cash flow, working capital, CCC)

```
Continue the ApexOS build. Do this in order:

1. git checkout main && git pull origin main. Then git status — one writer per working tree;
   if it is dirty, STOP and report. Nothing in this run is tagged (the user waived it), so do
   not expect part-05-done..part-08-done to exist. The SHA table in the CURRENT WORK block is
   the record instead, and keeping it accurate is the deliverable that replaces the tag.

2. Read the "▶ CURRENT WORK" block below. PARTS 1–7 ARE COMPLETE, the E2E gate is clean, and
   PART 8 C1 IS DONE. That block carries C1's decisions, the invariants C2 must not break, and
   verified signatures to CALL without opening the source. Its "Do NOT read" list is binding.

3. Read docs/REQUIREMENTS.md §1 (G1–G17) and §12 (R11.x). §11 (R10.x) is C1's and is CLOSED —
   do not re-read it; what C2 needs from it is inlined below. Then docs/prompts/part-08.md and
   docs/STANDING-RULES.md (binding). Do NOT open docs/ROADMAP.md — planning only, ~17k tokens.
   C2 owns R11.1–R11.4 and R11.13. R11.5–R11.12 and R11.14 are C3's.

4. `git show --stat ec8a573` for C1's shape in one command. Not a tree walk —
   docs/CODEBASE-MAP.md is current and now has a "Finance" section plus four routing-table rows.

5. Verify the baseline before writing code (from apps/api, venv activated):
     python -m pytest -q                  # expect 688 passed
     python -m ruff check app/ tests/     # expect EXACTLY 37 — 38 is a regression
   If either is off, STOP and report. All 37 are pre-existing (E501/F841/B007 in modules this
   run never touched); tests/ contributes zero. EIGHT PARTS HAVE ADDED ZERO NEW FINDINGS.

6. C2 is cash: a cash-flow view (in vs out, ACTUAL and COMMITTED), a working-capital snapshot,
   and the cash conversion cycle. Four things decide whether this checkpoint is any good:

   **"COMMITTED" MUST BE DEFINED ON SCREEN (R11.2), naming exactly what it includes.** Pick the
   set — confirmed POs not yet received, confirmed sales orders not yet invoiced, invoices due
   inside the window — say so in prose on the page, and write a test that the figure matches
   the stated definition. A "committed" number nobody can reconstruct is worse than none.

   **CCC SHOWS DSO, DIO AND DPO EACH INDIVIDUALLY (R11.4), not just the total.** Each component
   hand-verified in a test. DSO reads C1's receivable, DPO C1's payable, DIO Part 5's valuation
   — all three through the existing services (R11.11/G16).

   **DIVISION IS THE ONLY PLACE A RATIO APPEARS (R11.12).** Money stays integer minor units; a
   ratio rounds through ONE explicit step, states where it rounded, and a float NEVER
   round-trips back into a displayed money value. Days are integers.

   **R11.13 IS THE CONTRACT PARTS 9 AND 10 DEPEND ON.** Expose every projection as a clean
   service method with EXPLICIT PERIOD PARAMETERS (date_from/date_to), so the Command Center
   and the intelligence layer CONSUME rather than recompute. C1's projections take `as_of`
   because a balance is point-in-time; a FLOW needs a window. If Part 9 later needs a number
   C2 did not expose, that is a gap in THIS checkpoint. **Copy those signatures into the resume
   block from source** — an inlined contract that is wrong is worse than none.

7. Constraints that bind:
     - G4: invoices, bills, payments, allocations, credit notes are APPEND-ONLY.
     - G7: every balance and every ratio is DERIVED. No stored cash position, no cached DSO.
     - G1: money is integer minor units through `app.core.money.round_minor` only.
     - G5: exactly one activity_log row per state change. C2 should write NONE — it is all
       projections (G15), and a test should assert loading the screens writes no rows.
     - G11: DSO/DIO/DPO and the committed figure are computed numbers, so each explains itself
       through `Explained` + the `explain_panel` macro. Insufficient history is
       `Explained.unknown(...)` — NEVER a default like 0 or 30 days.
     - G12: no ML, no runtime LLM call. G17: no chart of accounts, no journals, no
       double-entry, no QuickBooks bridge (R10.14, cut by D-D).
     - R11.14: no decorative charts. If a chart does not change a decision, make it a table.
     - Any new model owes app/db/references.py an entry, even an empty tuple (R3.7). C1 added
       NO new model and owed nothing; C2 should aim for the same.
     - A new column on an EXISTING table needs an `_ADDITIVE_COLUMNS` entry in app/main.py.

8. Work on main. No branches, no PRs, NO TAGS. Commit at the END OF C2 and push. Personal
   credentials only (github.com/1992tushar/apexos).

9. NAME EVERY NEW TEST AFTER THE REQUIREMENT IT PROVES — `pytest -q -k r11_` becomes the
   evidence. MUTATION-CHECK the new suite once: break the implementation and confirm the tests
   go red. C1 did this four ways and each mutation was caught by exactly the test that names
   it. Good mutations here: drop one term from "committed", swap DSO's numerator and
   denominator, return a default where history is insufficient.

   Lessons already paid for, each worth carrying:
     - A test that reads a CONVENIENCE FIELD rather than the source of truth can be
       confidently wrong. C1 found `InvoiceService.balance_minor` was exactly this.
     - An equality assertion between two code paths only tests what the CURRENT DATA
       distinguishes — assert the structure too, and add the case the seed cannot produce.
     - A source-walk test cannot tell a call from a comment. Count queries with a SQLAlchemy
       `before_cursor_execute` listener; `tests/test_fast_entry.py` has a working example.
     - MUTATE WITH THE EDIT TOOLS, NEVER PowerShell `Set-Content` — it round-trips UTF-8
       through cp1252 and turns every em dash in the file into mojibake.

10. BEFORE you run low, update the "▶ CURRENT WORK" block: the SHA table, R-numbers passed and
    outstanding, gotchas, decisions a later checkpoint must not reverse, and the four delta
    lines — Changed since / Read for the next checkpoint / Call, don't read (copy signatures
    FROM SOURCE) / Do NOT read. Then rewrite this prompt for C3 with MEASURED baselines.
    Archive C2's record to docs/parts/part-08.md (C1's is already there — append a section,
    and do not read C1's). Amend docs/CODEBASE-MAP.md if the SHAPE changed. Commit and push.
    PROGRESS.md IS CAPPED AT ~350 LINES — replace, never append.

Use pytest -q, never verbose. Don't re-read files you just edited.
```

**If a session has drifted** and you want a hard reset on scope, paste the whole ```-fenced PROMPT
from `docs/prompts/part-08.md` instead. More deterministic, more typing.

#### ▶ What C1 settled — decisions C2 must not reverse, and the traps it hit

**Baseline measured at `ec8a573`: 688 passed, ruff exactly 37.** Tree clean. `-k r10_` is 58 tests.

1. **ONE receivable, ONE payable, and now a bulk sibling of each.**
   `CustomerRepository.outstanding_by_customer()` and `SupplierRepository.outstanding_by_supplier()`
   return `{party_id: minor}` using the *same terms and the same filters* as the single-party
   `outstanding_minor`. They exist so a screen covering every party does not fan out three queries
   per party. **DSO must read one of these, not a fourth derivation.**
2. **`unaged_minor` on the ageing report is a deliberate residual**, not a bug: it makes
   `Σ buckets + unaged == the party's outstanding` hold *unconditionally*. Do not remove it.
3. **Due today is NOT overdue** — `AR_AGE_BUCKETS[0]` has an inclusive upper bound of `0`. A NULL
   `due_date` is aged from the invoice date and the screen says "(assumed)".
4. **Allocation spills oldest DUE first, and a receipt larger than everything open is REFUSED**
   naming the figure that fits. There is deliberately no unallocated cash, because it would be money
   `outstanding_minor` cannot see. **C2's cash-flow view must not invent an "on account" bucket.**
5. **`InvoiceService.balance_minor` is now `total − paid − credited`** in `list()`, `_to_detail()`,
   `add_payment()`'s guard and the status cache. It was `total − paid` and had disagreed with the
   receivable since Part 7 shipped returns. **Do not reintroduce the two-term version.**
6. **Both ageing reports in `ReportService` now DELEGATE** to `AgeingService`; their columns are the
   buckets. `ReportService.to_csv` remains a second CSV writer — **do not add a third.** Part 2's
   path now covers projections too: `csv_rows_response(spec, rows)` in `app/web/listing.py`.
7. **The seed's finance section is `app/seed/finance.py`** — 8 invoices, 3 bills, placed by offset
   from the report date so every bucket is populated (incl. due-today, no-due-date, settled-in-full).
   Invoices are written DIRECTLY (`sales_order_id` is nullable) because the sell loop needs stock and
   reservations and would leave OPEN sales orders on customers other tests assert are quiet.
   Subjects come from `_CUSTOMER_OFFSET = 5` in code order, for the same reason.
8. **A new plain GET route is picked up automatically by `test_web_smoke.py`'s route walk and must
   200 with NO query parameters** — so any new screen needs a real empty state. `/finance/ledger`
   with no party is the worked example. A bad `?as_of=` degrades to today rather than raising.
9. **Build the figure and RENDER it in the same pass.** C1 shipped `CollectionsEntry.ledger_href`
   and forgot to put it on the page; only driving the real app found it. A field nothing renders is
   dead weight the tests will happily pass.

---

## ▶ Handoff — Parts 5, 6 and 7 are COMPLETE · the E2E gate is CLEAN

**Not tagged** — waived for this run, so these SHAs are the record. Full records in
`docs/parts/part-05.md`, `part-06.md`, `part-07.md` and `e2e-gate.md`. **Do not read them.**

**The E2E gate passed 44 checks** — 28 on the cross-part trail (recommendation → requisition → PO →
receipt into a bin → cost and ageing move → quotation → convert at the quoted price → confirm reserves
→ fulfil consumes → invoice → partial return drops the receivable) and 16 driving the real POST forms.
Driven over **HTTP, not clicked in a browser**, so layout and whether the screens *feel* fast are not
covered: **R9.12's manual walkthrough remains a human task.** Its one failure was a miswritten
assertion reading a convenience field instead of the ledger — recorded, not erased.

Part 5 `437a185` `b442322` `eaee67b` `4667a5e` (inventory: locations, four derived states, the
reservation ledger, weighted-average cost, ageing, operations, health) · Part 6 `a8c9bde` (customer
depth: contacts, branches, versioned credit terms, the gate at confirm, the timeline) · Part 7
`eeae971` `27d1c49` `761e9aa` `2b98c4a` (quotation, returns + credit notes, health score, fast entry;
**R9.13 measured a 5-line repeat order at ~100 keystrokes → 5**, and a *manual* one at ~100 → ~55).

### Five invariants still load-bearing for C2 and C3

C1's own decisions are in the section above; these are the older ones Part 8 must keep true.

1. **`InventoryService.record_movement` is the ONLY writer of `stock_movement`** (G8), enforced by a
   source walk that fails if anything else constructs one. DIO reads valuation, never the raw table.
2. **`ReservationService.reserve/release/consume` is the only reservation mechanism** (R6.5/R6.6).
   No flag; a test asserts no boolean `reserv*` column exists anywhere.
3. **G11 has exactly one implementation**: `Explained` + the `explain_panel` macro. C2's DSO/DIO/DPO
   and C3's margin are new *outputs*, not new shapes, and "unknown" is `Explained.unknown` — never a
   default number. **R13.1 had this unification scheduled for Part 10; it is already done.**
4. **Two versioning idioms exist and that is the limit** — Part 3/7's append-only revision rows
   (`revision_no`, no `superseded_at`) and Part 6's period rows (`valid_from`/`valid_to`). Pick one
   and say which; do not invent a third.
5. **`uuid7()` is NOT monotonic within a millisecond** — its low bits come from `os.urandom`, so
   `ORDER BY (timestamp, id)` cannot break a same-millisecond tie. Select by a discriminating column,
   or stamp an explicit `datetime.now(UTC)` (microsecond resolution) as credit policies and notes do.

### Read for C2 — these and nothing else

- `docs/REQUIREMENTS.md` §1 (invariants) + **§12 (R11.x)**. §11 is C1's and is closed.
- `docs/prompts/part-08.md` · `docs/STANDING-RULES.md` (binding) · `docs/08-module-breakdown.md`
  § Finance · `docs/CODEBASE-MAP.md`'s new **Finance** section (~20 lines) if you want C1's shape.
- **The likely edit set for C2:** a new `app/modules/finance/cash.py` (cash flow + working capital +
  CCC — C1's precedent is one module per question asked) · `app/modules/finance/schemas.py` ·
  `app/web/pages/finance.py` + a template or two · `tests/test_finance_cash.py`.
- **Do not rebuild what C1 built.** `finance/{ledger,ageing,allocation}.py` are finished; their
  signatures are below. `finance/models.py` needs no new model for C2.

### Call, don't read — verified signatures, copied from source at P8-C1 close

```python
# app/core/money.py — G1. Integer minor units end to end.
round_minor(value: Decimal) -> int      # THE one rounding step. No second one.
qty_text(value: Decimal) -> str         # "40", not "40.0000". Service messages only.
minor_to_text(minor: int | None) -> str # 123456 -> "1234.56"

# app/db/explain.py — the ONE shape for every explained number (G11)
Explained(what, value: str | None, formula, window, inputs=(), records=(),
          unknown_reason=None, caveat=None)   # .is_known · .display -> value or "unknown"
Explained.unknown(*, what, formula, reason, window="no data", inputs=(), records=())
Input(label, value, weight=None, missing_reason=None)   # .is_missing
SourceRecord(label, href=None)
# Rendered by ONE macro:  {{ ui.explain_panel(explained, "Optional title") }}

# app/modules/finance/ — Part 8 C1. Projections; they write NOTHING (G15).
#   ledger.py
open_invoices(db, *, customer_id=None, as_of: date | None = None) -> list[OpenDocument]
open_bills(db, *, supplier_id=None, as_of: date | None = None) -> list[OpenDocument]
#   OpenDocument: .open_minor .total_minor .allocated_minor .credited_minor .due_date
#                 .due_date_assumed .days_overdue .bucket .is_overdue .doc_no .href .party_id
today() -> date                       # the report date, in one place
PartyLedgerService(db).customer_statement(customer_id, *, as_of=None) -> PartyStatement
PartyLedgerService(db).vendor_statement(supplier_id, *, as_of=None) -> PartyStatement
PartyLedgerService(db).statement_note(statement) -> str | None   # None unless figures diverge
#   PartyStatement: .lines[LedgerLine] .closing_balance_minor .open_documents .line_total_minor
#   closing_balance_minor IS outstanding_minor — called, not recomputed.

#   ageing.py
AgeingService(db).ar_ageing(*, as_of=None) -> AgeingReport
AgeingService(db).ap_ageing(*, as_of=None) -> AgeingReport
AgeingService(db).collections(*, as_of=None) -> list[CollectionsEntry]   # each has .explained
AgeingService(db).payments_due(*, as_of=None) -> list[PaymentsDueEntry]
bucket_boundaries() -> list[dict]     # what the screen prints; BUCKET_LABELS is the key->label map
#   AgeingReport: .rows[AgeingPartyRow] .buckets[AgeingBucketTotal] .total_minor .due_minor
#                 .overdue_minor .unaged_minor .bucket_total_minor
#   Σ buckets + unaged == total, unconditionally. AgeingPartyRow.flat() for CSV.

#   allocation.py — oldest DUE first; more than the total open RAISES ValidationError
AllocationService(db).allocate_receipt(customer_id, AllocationCreate, *, actor_id)
AllocationService(db).allocate_payment(supplier_id, AllocationCreate, *, actor_id)
#   -> AllocationResult(.payment_no .allocated_minor .lines[AllocationLine])

#   schemas.py — the ageing constant and its ONE rule
AR_AGE_BUCKETS: tuple[tuple[str, str, int | None], ...]   # (key, label, INCLUSIVE upper bound)
CURRENT_BUCKET = "current"            # the one bucket that is not overdue
bucket_for(days_overdue: int) -> str  # first bucket whose bound covers it; 0 -> "current"

#   repository.py — grouped, so a whole screen is a handful of queries
FinanceRepository(db).allocated_by_invoice() / .credited_by_invoice() / .allocated_by_bill()
FinanceRepository(db).invoices_with_party(*, customer_id=None) / .bills_with_party(...)
FinanceRepository(db).allocations_for_invoice(id) / .allocations_for_bill(id)
FinanceRepository(db).credit_notes_for_customer(id) / .credit_notes_for_invoice(id)
FinanceRepository(db).customers_with_activity() / .suppliers_with_activity()
FinanceRepository(db).credited_minor(invoice_id) -> int

# app/web/listing.py — Part 2's ONE export path, now covering projections too
csv_rows_response(spec: ListSpec, rows: Sequence[Any]) -> Response   # rows already in hand

# app/modules/pricing/service.py — R11.6's cost basis, for C3
MarginService(db).gp(line) -> int     # selling − the LATEST PURCHASE price × qty, minor units
#   Takes anything exposing product_id, qty, unit_price_minor. NOT a valuation layer (D-A).

# app/modules/customers/ — Part 6/7, extended by Part 8 C1
CustomerRepository(db).outstanding_minor(customer_id) -> int   # THE receivable. Call it.
CustomerRepository(db).outstanding_by_customer() -> dict[uuid.UUID, int]   # the bulk SIBLING
SupplierRepository(db).outstanding_minor(supplier_id) -> int               # THE payable
SupplierRepository(db).outstanding_by_supplier() -> dict[uuid.UUID, int]   # its bulk SIBLING
CustomerHealthService(db).score(customer_id, *, as_of=None) -> Explained
#   Four inputs renormalising over what exists; "never invoiced" is MISSING, not full marks.
#   Also on CreditPolicyService: .check/.enforce/.set_policy/.current/.history/.explain, and
#   CustomerTimelineService(db).events(customer_id, *, limit=200). C2 needs none of them.

# app/modules/inventory/ — Part 5. DIO's input; do NOT read the raw ledger for it (G8).
ValuationService(db).cost_basis(product_id) -> Explained   # weighted average, or unknown
ValuationService(db).stock_value() · .ageing()             # on-hand VALUE — DIO reads this
InventoryService(db).on_hand/available/states/bin_stock/location_rollup
InventoryService(db).record_movement(...)   # THE only writer of stock_movement (G8)
#   Also: ReservationService.reserve/release/consume · InventoryHealthService.abc/dead_stock/
#   movement_rates/low_stock/reorder_suggestions · RecommendationService(db).recommend(...)
#   (R5.9's ONE entry point — a source walk FAILS if a second `def recommend` appears).
#   Sales, Part 7: SalesOrderService.confirm/fulfill/cancel · QuotationService ·
#   SalesReturnService · FastEntryService. C2 and C3 should need none of these.

# app/modules/config/service.py
default_business_unit(db) -> uuid.UUID
allocate_document_number(db, *, doc_type, business_unit_id, on_date) -> "INV-202607-00001"
#   In use: PO GRN BILL REQ RFQ QUO SO INV TRF CNT FUL SQT RET CRN.
```

Part 2's machinery still holds: `ListSpec` + `view_from_request`, `ensure_unreferenced` /
`soft_delete` / `ensure_unique`, `ActivityService.history`, and the `page_header` / `stat` / `badge` /
`list_*` / `history_panel` / `explain_panel` macros.

### Gotchas that will bite C2 and C3

- **`create_all` builds new TABLES but never ALTERs an existing one.** A new column needs an
  `_ADDITIVE_COLUMNS` entry in `app/main.py` (~line 45) or it is silently missing on every DB seeded
  earlier. Get the DDL from what `create_all` emits (`CreateTable(...).compile(sqlite)`); don't guess.
- **`client.post` COMMITS; `db`-fixture writes roll back.** A test that POSTs leaves rows behind, and
  three checkpoints broke the same two Part 1/3 tests by leaving an OPEN document (draft *or*
  confirmed counts) on the first customer. **A POSTing test needs a subject no other test asserts
  about** — `test_fast_entry.py`'s `spare_customer` and C1's `quiet_customer` are the two patterns.
- **A source-walk test cannot tell a call from a comment** — one failed on its own docstring. Count
  queries with a SQLAlchemy `before_cursor_execute` listener instead.
- **A test can pass without testing anything.** Assert a **floor** on anything you enumerate, and
  mutation-check once. `assert x > 0` on an always-positive value asserts nothing.
- **Assert on HTML phrases that do NOT straddle a template line break** — cost four runs so far.
- **A `select()` per row in a projector is the thing to avoid**; `db.get(Model, id)` in a loop is free
  (identity map). C1's grouped `*_by_invoice()` dicts are the pattern for a whole-table figure.
- **The env var is `DATABASE_URL`, not `APEXOS_DATABASE_URL`.** The wrong name silently writes the
  real `apexos.db`. Stop uvicorn before deleting a scratch `.db`
  (`Get-CimInstance Win32_Process | Where CommandLine -like '*<port>*' | Stop-Process -Force`;
  `pkill` does not exist here). Ports 8015–8032 have been used; pick above that.
- **PowerShell has no heredocs and `$pid` is read-only** — a multi-line commit message needs the Bash
  tool (`git commit -F - <<'EOF'`). Shell variables do not persist between tool calls. And **never
  edit a source file with `Set-Content`**: it round-trips UTF-8 through cp1252 and mojibakes every
  em dash. C1 hit this mutation-testing and had to re-encode the file to recover.
- **A script that reads the DB without booting the app skips `_ensure_new_columns`** and crashes on
  any additively-added column. Use a `TestClient(app)` context if the shim must have run.
- **A self-referencing Pydantic model needs `Model.model_rebuild()`** after its class body.

### Do NOT read

`app/seed/core.py` (740 lines — read `app/seed/__init__.py`'s docstring, and `app/seed/finance.py` as
the pattern for a new section) · `app/modules/finance/{ledger,ageing,allocation}.py` (C1 finished
them; signatures above) · `app/modules/procurement/preorder.py` · `app/modules/suppliers/vendor.py` ·
`app/modules/inventory/{valuation,health}.py` · `app/modules/customers/{credit,timeline,health}.py` ·
`app/modules/sales/{quotation,returns,fast_entry}.py` · `tests/test_finance_*.py`,
`test_inventory_*.py`, `test_customer_*.py`, `test_quotations.py`,
`test_returns_and_reservations.py`, `test_fast_entry.py`, `test_preorder.py`, `test_po_revisions.py`,
`test_vendor_*.py`, `test_procurement_planning.py` (they pass; read one only if you change what it
covers) · anything in `docs/parts/` · `docs/ROADMAP.md` (~17k tokens, planning only) · the older
`docs/` design files, `docs/DELETION-POLICY.md` and `docs/MIGRATION-STRATEGY.md`.

Note `docs/REQUIREMENTS.md` is at v1.2: the stock writer is `InventoryService.record_movement`, and
any older doc naming `post_movement` is wrong.

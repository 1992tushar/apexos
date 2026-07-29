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
`docs/parts/e2e-gate.md`). **Part 8 C1 and C2 are DONE.** The build continues at **Part 8 C3 —
margin by four dimensions, leakage indicators, GST — which CLOSES Part 8**.

**All work is on `main`** — no feature branches, no PRs. **Nothing in this run is tagged** (the user
waived it), so this SHA table is what `part-0N-done` would otherwise be.

| Checkpoint | From | Commit | Tests | Ruff |
|---|---|---|---|---|
| **P8-C1** ledgers · AR/AP ageing · collections · allocation | `3aede6e` | **`ec8a573`** | 623 → **688** | 37 → **37** |
| **P8-C2** cash flow · working capital · CCC | `ec8a573` | **`30b3cc1`** | 688 → **721** | 37 → **37** |
| **P8-C3** margin ×4 · leakage · GST — closes Part 8 | `30b3cc1` | — | — | — |

**C1's and C2's full records are in `docs/parts/part-08.md`. Do not read them** — everything C3
needs is below.

### ▶ How to start the next session

Type **`Start next part of development`** in a fresh session; `CLAUDE.md` binds that phrase to the
prompt below. **The session that closes a checkpoint owns it** — one still naming the previous
baseline is worse than none, because the next session will trust it.

#### ▶ NEXT SESSION PROMPT — Part 8, C3 (margin ×4, leakage, GST) · CLOSES PART 8

```
Continue the ApexOS build. Do this in order:

1. git checkout main && git pull origin main, then git status — one writer per working tree;
   if it is dirty, STOP and report. Nothing in this run is tagged (waived), so the SHA table
   in the CURRENT WORK block is the record and keeping it accurate replaces the tag.

2. Read the "▶ CURRENT WORK" block below — PARTS 1–7 COMPLETE, E2E gate clean, PART 8 C1 AND
   C2 DONE. It carries their decisions, the invariants C3 must not break, and verified
   signatures to CALL without opening the source. Its "Do NOT read" list is binding.

3. Read docs/REQUIREMENTS.md §1 (G1–G17) + §12 (R11.x) — §11 is C1's and is CLOSED. Then
   docs/prompts/part-08.md, docs/STANDING-RULES.md (binding), docs/08-module-breakdown.md
   § Finance. Do NOT open docs/ROADMAP.md (planning only, ~17k tokens). C3 owns R11.5–R11.10
   and R11.14 and inherits R11.11–R11.13's rules; C1+C2 passed R11.1–R11.4, R11.11–R11.13 and
   half of R11.14. `git show --stat 30b3cc1` for C2's shape — not a tree walk.

4. Verify the baseline before writing code (from apps/api, venv activated):
     python -m pytest -q                  # expect 721 passed
     python -m ruff check app/ tests/     # expect EXACTLY 37 — 38 is a regression
   If either is off, STOP and report. All 37 are pre-existing (E501/F841/B007 in modules this
   run never touched); tests/ contributes zero. EIGHT PARTS HAVE ADDED ZERO NEW FINDINGS.
   NOTE: if a single unrelated test fails and passes on re-run, do not shrug — C2 found a real
   uuid7 ordering defect exactly that way. Diagnose it, then continue or stop.

5. C3 closes Part 8: margin by four dimensions, leakage indicators, and a GST summary.
   Four things decide whether this checkpoint is any good:

   **MARGIN IS `MarginService.gp` AND NOTHING ELSE (R11.6).** `MarginService(db).gp(line)` is
   selling − the purchase price, × qty, in minor units — NOT an inventory valuation layer.
   D-A removed FIFO and margin never needed it. Part 5 left a source walk asserting
   `pricing/service.py` does not read the cost basis; keep it true in the other direction.
   C2 already consumes `gp` for COGS (`cash.py:_cogs` is `subtotal − gp`), so a second cost
   derivation would now disagree with DIO as well as with margin.
   NOTE the honest wart: `gp` uses the product's CURRENT buy price, not the price at the time
   of sale. R11.6 says reuse it, so reuse it — and SAY SO on screen as C2's DIO panel does.

   **MARGIN ACROSS FOUR DIMENSIONS (R11.5): product, customer, category, business unit.**
   One projection parameterised by dimension, not four near-copies. A test per dimension.

   **EVERY LEAKAGE INDICATOR LISTS ITS OFFENDING RECORDS (R11.8).** An indicator with nothing
   to click MUST be REMOVED, not shipped empty — that is the requirement, not a suggestion.
   Each needs a test that it FIRES on a seeded offender and stays SILENT otherwise, so the
   seed owes one deliberate offender per indicator (G14). **This session checked what R11.7's
   three indicators can actually be computed from; two can, one cannot:**
     - Sold below purchase price — YES. `MarginService.gp(line) < 0` on an invoice line.
     - Discount creep — YES, but it must be DERIVED: there is **no discount column anywhere**.
       The baseline is the list price, i.e. the `selling_price` row with `customer_id IS NULL
       AND customer_type_id IS NULL` (`PricingService.resolve_selling_minor` resolves
       customer → segment → list). Creep = line `unit_price_minor` below that list price.
       A product with NO list-price row has an UNKNOWN discount, not a 0% one.
     - Freight not recovered — **NO. There is no freight, shipping, carriage or delivery-charge
       field in the schema at all** (grepped `app/` for all four). Nothing can be computed, so
       per R11.8 do NOT ship it empty and do NOT invent a column for it — adding a freight
       charge to the document model is a product decision, not a C3 task (G17). Record the gap
       in PROGRESS.md, note R11.7 as partially met with the reason, and ASK THE USER whether
       they want freight captured before Part 8 is called closed.

   **GST IS A REPORT, NOT A FILING ENGINE (R11.9/R11.10).** Output tax, input tax, net
   position, BY PERIOD. `ReportService._gst_summary` already exists and already windows by
   date — read it before writing anything, and prefer extending/delegating over a second one
   (the same trap C1 found in `_ar_aging`, which had its own arithmetic and was wrong).
   NO return-filing workflow. Nothing that submits anything anywhere.

6. Constraints that bind:
     - G1/R11.12: money is integer minor units through `app.core.money.round_minor` only.
       A MARGIN PERCENTAGE IS A RATIO — round it once, state where, and never let a float
       round-trip back into a money figure. C2's `cash.py:_days` is the worked example of
       one explicit rounding step with its reasoning written down.
     - G7: derived, never stored. No cached margin column.
     - G11: margin percentages and leakage indicators are computed numbers, so each explains
       itself through `Explained` + the `explain_panel` macro. Insufficient data is
       `Explained.unknown(...)` — never 0%. A product with no purchase price recorded has
       UNKNOWN margin, not 100%: that is the single most likely wrong number in this
       checkpoint, and `ValuationService` already had to handle the same case.
     - G15: these are projections and must write NO activity_log rows; assert it.
     - G12: no ML, no runtime LLM call. G17: no chart of accounts, no journals, no
       double-entry, no QuickBooks bridge (R10.14, cut by D-D).
     - R11.14: part 2's macros, CSV export on every view, and NO DECORATIVE CHARTS — if a
       chart does not change a decision, make it a table. Export via
       `csv_rows_response(spec, rows)` (C1 extracted it for exactly this).
     - Any new model owes app/db/references.py an entry, even an empty tuple (R3.7). C1 and
       C2 each added NO new model and owed nothing; C3 should aim for the same.
     - A new column on an EXISTING table needs an `_ADDITIVE_COLUMNS` entry in app/main.py.

7. Work on main. No branches, no PRs, NO TAGS. Commit at the END OF C3 and push. Personal
   credentials only (github.com/1992tushar/apexos).

8. NAME EVERY NEW TEST AFTER THE REQUIREMENT IT PROVES — `pytest -q -k r11_` is the evidence
   for Part 8 group B (29 tests today). MUTATION-CHECK the new suite once. Good mutations
   here: make a leakage indicator fire with an empty record list, return 0% where the
   purchase price is unknown, and swap one dimension's group-by key for another's.

   The one lesson to re-read before writing an assertion — it has now cost three sessions,
   most recently C2: AN EQUALITY ASSERTION BETWEEN TWO CODE PATHS ONLY TESTS WHAT THE CURRENT
   DATA DISTINGUISHES. C2 compared committed cash against a recomputation over a window wide
   enough to contain every document, so the due-date filter was a no-op and the mutation
   passed. Choose data that can tell the two apart, and ASSERT that it does. The rest are in
   "Gotchas" below. Also: DRIVE THE REAL APP before calling it done — C1 and C2 each found a
   defect that way which the tests were happy to miss.

9. BEFORE you run low, update the "▶ CURRENT WORK" block: the SHA table, R-numbers passed
    and outstanding, gotchas, decisions a later checkpoint must not reverse, and the four
    delta lines — Changed since / Read for the next checkpoint / Call, don't read (copy
    signatures FROM SOURCE) / Do NOT read. C3 CLOSES PART 8, so also write the Part 9
    handoff: replace the "▶ Handoff — Parts 5, 6 and 7" section with Part 8's, and rewrite
    this prompt for P9-C1 (tiles, alerts, activity, quick actions — R12.1–R12.11) with
    MEASURED baselines. Archive C3's record to docs/parts/part-08.md (C1's and C2's are
    already there — add a section; do not read theirs). Amend docs/CODEBASE-MAP.md if the
    SHAPE changed. Commit and push.
    PROGRESS.md IS CAPPED AT ~350 LINES — replace, never append.

Use pytest -q, never verbose. Don't re-read files you just edited.
```

**If a session has drifted** and you want a hard reset on scope, paste the whole ```-fenced PROMPT
from `docs/prompts/part-08.md` instead. More deterministic, more typing.

#### ▶ What C1 and C2 settled — decisions C3 must not reverse, and the traps they hit

**Baseline measured at `30b3cc1`: 721 passed, ruff exactly 37.** Tree clean. `-k r10_` is 58 tests,
`-k r11_` is 29.

1. **ONE receivable, ONE payable, and a bulk sibling of each** —
   `CustomerRepository.outstanding_by_customer()` / `SupplierRepository.outstanding_by_supplier()`,
   same terms and same filters as the single-party `outstanding_minor`. C2's DSO/DPO read these.
   **Margin must not derive a fifth version of anything already defined.** (C1 also fixed
   `InvoiceService.balance_minor` to `total − paid − credited`; do not reintroduce the two-term form.)
2. **COGS is already defined, once: `cash.py:_cogs` is `Σ line_subtotal − Σ MarginService.gp`.**
   C3's margin must agree with it, and the way to guarantee that is to use the same `gp`. A second
   cost basis would now put margin *and* DIO out of step.
3. **Delegate rather than duplicate — this part has already caught one instance.** Both ageing
   reports in `ReportService` now call `AgeingService` because they had their own, wrong, arithmetic.
   **`_gst_summary` is still the old hand-rolled kind**, so C3 should extend or delegate rather than
   sit a second GST report beside it. `ReportService.to_csv` is already a second CSV writer — **do
   not add a third**; `csv_rows_response(spec, rows)` covers projections.
4. **Flows take `date_from`/`date_to`; balances take `as_of`** (R11.13). Keep that split — a window
   on a balance looks rigorous and means nothing.
5. **A ratio with a thin denominator says so.** DIO is ~10,000 days on the seed: correct, and useless
   as a precise figure, so `_thin_window_caveat` marks any component longer than its own window and
   the cycle inherits it. **A margin percentage computed off one sale has the same problem — treat it
   the same way rather than shipping a confident number.**
6. **`Explained.unknown` is the answer for a missing input, never 0.** A product with no recorded
   purchase price has UNKNOWN margin, not 100% — the single most likely wrong number in C3.
   `StockValueRow.value_minor` is None in exactly that case, and C2's snapshot counts and reports
   those products rather than skipping them.
7. **The seed's finance section is `app/seed/finance.py`** — 8 invoices, 3 bills, placed by offset
   from the report date. Invoices are written DIRECTLY (`sales_order_id` is nullable) because the
   sell loop needs stock and reservations and would leave OPEN sales orders on customers other tests
   assert are quiet; subjects come from `_CUSTOMER_OFFSET = 5` in code order for the same reason.
   **C3's leakage offenders belong in that module, on that kind of subject.**
8. **A new plain GET route is picked up automatically by `test_web_smoke.py`'s route walk and must
   200 with NO query parameters** — so every new screen needs a real empty state. A bad
   `?as_of=`/`?date_from=` degrades to a default rather than raising, and a reversed window is
   repaired rather than rendered empty.
9. **Build the figure and RENDER it in the same pass.** C1 shipped `CollectionsEntry.ledger_href` and
   never put it on the page; only driving the real app found it. A field nothing renders is dead
   weight the tests will happily pass.

---

## ▶ Handoff — Parts 5, 6 and 7 are COMPLETE · the E2E gate is CLEAN

**Not tagged** — waived for this run. Full records in `docs/parts/part-05.md`, `part-06.md`,
`part-07.md` and `e2e-gate.md`; **do not read them.** Part 5 `437a185` `b442322` `eaee67b` `4667a5e`
(inventory) · Part 6 `a8c9bde` (customer depth) · Part 7 `eeae971` `27d1c49` `761e9aa` `2b98c4a`
(quotation, returns, health score, fast entry).

**The E2E gate passed 44 checks**, but over **HTTP, not clicked in a browser** — so layout and whether
the screens *feel* fast are not covered, and **R9.12's manual walkthrough remains a human task.**

### Three older invariants still load-bearing for C3

1. **`InventoryService.record_movement` is the ONLY writer of `stock_movement`** (G8), enforced by a
   source walk that fails if anything else constructs one. Read valuation, never the raw table.
2. **G11 has exactly one implementation**: `Explained` + the `explain_panel` macro. Margin and the
   leakage indicators are new *outputs*, not new shapes. **R13.1 had this unification scheduled for
   Part 10; it is already done, and P10-C1 should record that rather than rebuild it.**
3. **Two versioning idioms exist and that is the limit** — Part 3/7's append-only revision rows
   (`revision_no`) and Part 6's period rows (`valid_from`/`valid_to`). Do not invent a third.

### Read for C3 — these and nothing else

- `docs/REQUIREMENTS.md` §1 (invariants) + **§12 (R11.x)**. §11 is C1's and is closed.
- `docs/prompts/part-08.md` · `docs/STANDING-RULES.md` (binding) · `docs/08-module-breakdown.md`
  § Finance · `docs/CODEBASE-MAP.md`'s **Finance** section (~30 lines) for C1/C2's shape.
- **The likely edit set for C3:** a new `app/modules/finance/margin.py` (margin ×4 + leakage — the
  precedent is one module per question asked) · `app/modules/finance/schemas.py` ·
  `app/modules/reports/service.py` (`_gst_summary`) · `app/web/pages/finance.py` + templates ·
  `app/seed/finance.py` (the leakage offenders) · `tests/test_finance_margin.py`.
- **Read `app/modules/pricing/service.py` in full** — it is ~150 lines and holds both
  `PricingService` and `MarginService`, and R11.6 turns entirely on what `gp` actually does.
- **Do not rebuild what C1 and C2 built.** `finance/{ledger,ageing,allocation,cash}.py` are
  finished; their signatures are below. `finance/models.py` needs no new model for C3.

### Call, don't read — verified signatures, copied from source at P8-C2 close

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

# app/modules/finance/ — Part 8 C1 + C2. Projections; they write NOTHING (G15).
# Field-by-field shapes are in the source; C3 calls few of these, so only the entry points
# are listed. FLOWS take a window (R11.13); a BALANCE takes as_of.
#   ledger.py — the per-document open balance and the running statement
open_invoices(db, *, customer_id=None, as_of=None) -> list[OpenDocument]   # .open_minor
open_bills(db, *, supplier_id=None, as_of=None) -> list[OpenDocument]      # .days_overdue etc
today() -> date                       # the report date, in one place
PartyLedgerService(db).customer_statement/.vendor_statement(party_id, *, as_of=None)
PartyLedgerService(db).statement_note(statement) -> str | None
#   PartyStatement.closing_balance_minor IS outstanding_minor — called, not recomputed.

#   ageing.py — buckets, the chase list, payments due
AgeingService(db).ar_ageing/.ap_ageing(*, as_of=None) -> AgeingReport
AgeingService(db).collections(*, as_of=None) -> list[CollectionsEntry]   # each has .explained
AgeingService(db).payments_due(*, as_of=None) -> list[PaymentsDueEntry]
bucket_boundaries() -> list[dict]     # what the screen prints; BUCKET_LABELS maps key->label
#   AgeingReport: .rows .buckets .total_minor .due_minor .overdue_minor .unaged_minor
#   Σ buckets + unaged == total, unconditionally. Row/entry `.flat()` feeds the CSV.

#   allocation.py — oldest DUE first; more than the total open RAISES ValidationError
AllocationService(db).allocate_receipt/.allocate_payment(party_id, AllocationCreate, *, actor_id)

#   cash.py — Part 8 C2
CashFlowService(db).cash_flow(*, date_from: date, date_to: date) -> CashFlowReport
CashFlowService(db).committed(*, date_from: date, date_to: date) -> CommittedCash
CashFlowService(db).working_capital(*, as_of: date | None = None) -> WorkingCapitalSnapshot
#   .receivables_minor .inventory_minor .payables_minor .working_capital_minor
#   .inventory_known .products_without_cost .caveat
CashFlowService(db).cash_conversion_cycle(*, date_from, date_to) -> CashCycleReport
#   .dso/.dio/.dpo/.ccc are Explained · .*_days are int|None (None => unknown) · .window_days
default_window(*, as_of=None) -> tuple[date, date]     # DEFAULT_WINDOW_DAYS = 90, ending today
COMMITTED_TERMS: tuple[str, ...]      # R11.2's definition; the screen prints it verbatim

#   schemas.py — the ageing constant and its ONE rule
AR_AGE_BUCKETS: tuple[tuple[str, str, int | None], ...]   # (key, label, INCLUSIVE upper bound)
CURRENT_BUCKET = "current" · bucket_for(days_overdue) -> str    # 0 -> "current"

#   repository.py — grouped, so a whole screen is a handful of queries
FinanceRepository(db).allocated_by_invoice() / .credited_by_invoice() / .allocated_by_bill()
FinanceRepository(db).invoices_with_party(*, customer_id=None) / .bills_with_party(...)
FinanceRepository(db).invoice_lines_between(date_from, date_to)   # C3's margin input
FinanceRepository(db).invoiced_between(f, t) / .billed_between(f, t) -> (subtotal, total)
FinanceRepository(db).payments_between(f, t) / .sales_pipeline() / .purchase_pipeline()
FinanceRepository(db).credited_minor(invoice_id) · .credit_notes_for_invoice(id)
FinanceRepository(db).customers_with_activity() / .suppliers_with_activity()

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
#   Also CreditPolicyService.check/.enforce/.set_policy/.current/.history/.explain and
#   CustomerTimelineService.events(...). history()[0] is ALWAYS the current policy (C2 fix).

# app/modules/inventory/ — Part 5. Read valuation, never the raw ledger (G8).
ValuationService(db).cost_basis(product_id) -> Explained   # weighted average, or unknown
ValuationService(db).stock_value() · .ageing()             # StockValueRow.value_minor is
#   None where no purchase cost exists — C3 must treat that as UNKNOWN margin, not 100%.
InventoryService(db).on_hand/available/states/bin_stock/location_rollup · .record_movement(...)
#   Also: ReservationService · InventoryHealthService.abc/dead_stock/movement_rates/low_stock/
#   reorder_suggestions · RecommendationService(db).recommend(...) (R5.9's ONE entry point — a
#   source walk FAILS if a second `def recommend` appears) · Part 7's SalesOrderService /
#   QuotationService / SalesReturnService / FastEntryService. C3 should need none of these.

# app/modules/config/service.py
default_business_unit(db) -> uuid.UUID
allocate_document_number(db, *, doc_type, business_unit_id, on_date) -> "INV-202607-00001"
#   In use: PO GRN BILL REQ RFQ QUO SO INV TRF CNT FUL SQT RET CRN.
```

Part 2's machinery still holds: `ListSpec` + `view_from_request`, `ensure_unreferenced` /
`soft_delete` / `ensure_unique`, `ActivityService.history`, and the `page_header` / `stat` / `badge` /
`list_*` / `history_panel` / `explain_panel` macros.

### Gotchas that will bite C3

- **`create_all` builds new TABLES but never ALTERs an existing one.** A new column needs an
  `_ADDITIVE_COLUMNS` entry in `app/main.py` (~line 45) or it is silently missing on every DB seeded
  earlier. Get the DDL from `CreateTable(...).compile(sqlite)`; don't guess.
- **`client.post` COMMITS; `db`-fixture writes roll back.** A POSTing test leaves rows behind, and
  three checkpoints broke the same two Part 1/3 tests by leaving an OPEN document (draft *or*
  confirmed counts) on the first customer. **It needs a subject no other test asserts about** —
  `test_fast_entry.py`'s `spare_customer` and C1's `quiet_customer` are the two patterns.
- **A source-walk test cannot tell a call from a comment** — one failed on its own docstring. Count
  queries with a SQLAlchemy `before_cursor_execute` listener instead.
- **A test can pass without testing anything.** Assert a **floor** on anything you enumerate, and
  mutation-check once. `assert x > 0` on an always-positive value asserts nothing. A test that reads
  a **convenience field** instead of the source of truth can be confidently wrong (C1 found
  `InvoiceService.balance_minor` was), and one that forces half a race and trusts luck for the other
  half proves nothing (C2's first ordering test passed ~2 times in 3 against broken code).
- **Never order by `uuid7()` as a tiebreak** — its low bits are `os.urandom`, so it is not monotonic
  within a millisecond. Sort on a column that cannot tie: `CreditPolicyService.history` now leads with
  `valid_to IS NULL`, which exactly one row has.
- **Assert on HTML phrases that do NOT straddle a template line break** — cost four runs so far.
- **A `select()` per row in a projector is the thing to avoid**; `db.get(Model, id)` in a loop is free
  (identity map). C1's grouped `*_by_invoice()` dicts are the pattern for a whole-table figure. Note
  `MarginService.gp` costs one query per line — fine at seed scale, and Part 11 C1 owns optimising it.
- **The env var is `DATABASE_URL`, not `APEXOS_DATABASE_URL`.** The wrong name silently writes the
  real `apexos.db`. Stop uvicorn before deleting a scratch `.db`
  (`Get-CimInstance Win32_Process | Where CommandLine -like '*<port>*' | Stop-Process -Force`;
  `pkill` does not exist here). Ports 8015–8034 have been used; pick above that.
- **PowerShell has no heredocs and `$pid` is read-only** — a multi-line commit message needs the Bash
  tool (`git commit -F - <<'EOF'`). Shell variables do not persist between tool calls. And **never
  edit a source file with `Set-Content`**: it round-trips UTF-8 through cp1252 and mojibakes every
  em dash. C1 hit this mutation-testing and had to re-encode the file to recover.
- **A script that reads the DB without booting the app skips `_ensure_new_columns`** and crashes on
  any additively-added column. Use a `TestClient(app)` context if the shim must have run.
- **A self-referencing Pydantic model needs `Model.model_rebuild()`** after its class body.

### Do NOT read

`app/seed/core.py` (740 lines — read `app/seed/__init__.py`'s docstring, and `app/seed/finance.py` as
the pattern for a new section) · `app/modules/finance/{ledger,ageing,allocation,cash}.py` (C1 and C2
finished them; signatures above) · `app/modules/procurement/preorder.py` ·
`app/modules/suppliers/vendor.py` · `app/modules/inventory/{valuation,health}.py` ·
`app/modules/customers/{credit,timeline,health}.py` · `app/modules/sales/{quotation,returns,
fast_entry}.py` · `tests/test_finance_*.py`, `test_inventory_*.py`, `test_customer_*.py`,
`test_quotations.py`, `test_returns_and_reservations.py`, `test_fast_entry.py`, `test_preorder.py`,
`test_po_revisions.py`, `test_vendor_*.py`, `test_procurement_planning.py` (they pass; read one only
if you change what it covers) · anything in `docs/parts/` · `docs/ROADMAP.md` (~17k tokens, planning
only) · the older `docs/` design files, `docs/DELETION-POLICY.md`, `docs/MIGRATION-STRATEGY.md`.

Note `docs/REQUIREMENTS.md` is at v1.2: the stock writer is `InventoryService.record_movement`, and
any older doc naming `post_movement` is wrong.

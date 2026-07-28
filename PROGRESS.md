# ApexOS — Build Progress

> The source of truth for status. **This file is capped at ~350 lines and does not grow.**
> Closed parts live in `docs/parts/`. A new part's handoff **replaces** the previous one here — never appends.

_Last updated: 2026-07-28_

### What belongs in this file

| Section | Rule |
|---|---|
| `▶ NEXT SESSION PROMPT` | Exactly one. The session that closes a checkpoint rewrites it. |
| `▶ Handoff` | Exactly one — the part just closed, pointing at what comes next. |
| Anything else | Does not belong here. |

**Closing a part archives it.** Move its record to `docs/parts/part-0N.md`, then delete it from this
file. This is not tidiness. At Part 3 close this file was **1,212 lines / 90KB — about 22k tokens,
re-read at the start of every remaining session**, growing ~300 lines per part. It was the single
largest avoidable cost in the build. Parts 5–7 kept it near cap by **archiving progressively** —
each finished checkpoint's record moved to `docs/parts/` rather than waiting for the close.

Where everything else lives is in `CLAUDE.md` — setup in `RUNNING.md`, closed parts in `docs/parts/`,
per-part prompts in `docs/prompts/part-NN.md`, the binding rules in `docs/STANDING-RULES.md`, the
layout in `docs/CODEBASE-MAP.md`, and `docs/ROADMAP.md` which a session does not read.

---

# ▶ CURRENT WORK — read this first

**Parts 1–7 are COMPLETE.** What remains of this run is **one cross-part E2E gate**, then the build
continues at Part 8 (Finance).

**All work is on `main`** — no feature branches, no PRs. **Parts 5–7 were NOT tagged** (the user
waived it), so the checkpoint SHA table below is what `part-0N-done` would otherwise be.

### ▶ How to start the next session

Type **`Start next part of development`** in a fresh session. `CLAUDE.md` binds that phrase to "read
the **▶ NEXT SESSION PROMPT** below and follow it". **The session that closes a checkpoint owns that
prompt** — one still naming last checkpoint's baseline counts is worse than none, because the next
session will trust it.

#### ▶ NEXT SESSION PROMPT — the cross-part E2E gate · closes the Parts 5–7 run

```
Continue the ApexOS build. This is the E2E GATE — the last item of the Parts 5–7 run. It is
mostly VERIFICATION, not new code. Do this in order:

1. git checkout main && git pull origin main. Then git status — if it is dirty, stop and
   report. No tags this run; do not expect part-0N-done to exist.

2. Read the "▶ CURRENT WORK" block below. Parts 1–7 are COMPLETE: every R1–R9 requirement
   passes. Do NOT re-read the part records in docs/parts/ — everything needed is below.

3. Verify the baseline (from apps/api, venv activated):
     python -m pytest -q                  # expect 623 passed
     python -m ruff check app/ tests/     # expect EXACTLY 37 — 38 is a regression
   If either is off, stop and report. 37 is pre-existing (32 E501, 4 F841, 1 B007, all in
   modules this run never touched). Parts 1–7 added ZERO new findings; that is the record to
   preserve.

4. THE GATE. Use a FRESH database. The env var is DATABASE_URL, NOT APEXOS_DATABASE_URL —
   the wrong name silently writes the real apexos.db and you will "verify" against stale
   data:
     export DATABASE_URL="sqlite:///./e2e.db"
     python -m app.seed
     python -m uvicorn app.main:app --port 8025      # 8000 may be busy; 8015–8024 were used
   Then walk ONE trail through the SCREENS — not through pytest, which has already passed:

   BUY SIDE: /procurement shows a recommendation from R5.9's engine → raise a requisition →
   convert to a PO → confirm → receive INTO A BIN → /inventory shows the bin total rolling
   up to its rack and warehouse, the weighted-average cost moving, an ageing bucket
   appearing, and the vendor score updating on /suppliers.

   OPERATIONS: open a cycle count on /warehouse, enter a variance, close it → exactly one
   adjustment posts. Close a second count with no variance → NOTHING posts. Dispatch a
   transfer → /inventory shows it IN TRANSIT with total on-hand unchanged → receive it.

   SELL SIDE: raise a quotation on /quotations → send → revise → convert → the order carries
   the QUOTED price → confirm (the credit check fires; /inventory's reserved rises and
   available falls while ON-HAND DOES NOT) → fulfil (the reservation is consumed and the
   stock leaves) → invoice → record a payment → raise a PARTIAL return → a credit note
   appears, the INVOICE IS UNCHANGED, and the customer's outstanding falls by the credit.

   CUSTOMER: /customers/{id} shows contacts, ship-to branches, the versioned credit terms
   with their reasons, notes, the timeline, and the health score with its four inputs and
   weighting. Try an order that breaches the limit → the block STATES THE NUMBERS → override
   with a reason → the override appears on the timeline.

   Every nav page 200s. A bad id (/customers/<random-uuid>) renders error.html at 404.

5. WRITE DOWN WHICH STEPS YOU WALKED IN A BROWSER VERSUS ASSERTED ONLY IN A TEST. Report
   failures with their output. **Do not describe a step you skipped as passing** — the value
   of this gate is that it is the one check no test performed, so an inflated report destroys
   the only thing it was for.

6. Stop uvicorn BEFORE deleting the scratch .db (Windows holds the file; pkill does not exist
   here):
     Get-CimInstance Win32_Process | Where CommandLine -like '*8025*' | Stop-Process -Force

7. If the gate finds defects: fix them, add a test named after the requirement each one
   breaks, and re-run the loop. If it finds none, say so plainly — a clean gate after seven
   parts is a real result, not a non-event.

8. Then write docs/parts/e2e-gate.md with what was walked and what was found, update this
   block, and rewrite the NEXT SESSION PROMPT for PART 8 C1 (Finance: customer/vendor
   ledgers + AR/AP ageing + collections + allocation; docs/REQUIREMENTS.md §11's R10.x,
   docs/prompts/part-08.md, THREE checkpoints). Commit and push.
   PROGRESS.md IS CAPPED AT ~350 LINES — replace, never append.

Use pytest -q, never verbose. Don't re-read files you just edited.
```

**If a session has drifted** and you want a hard reset on scope, paste the whole ```-fenced PROMPT
from `docs/prompts/part-08.md` instead. More deterministic, more typing.

---

## ▶ Handoff — Parts 5, 6 and 7 are COMPLETE

**Not tagged** — waived for this run, so these SHAs are the record. Full records in
`docs/parts/part-05.md`, `part-06.md` and `part-07.md`. **Do not read them.**

| Part | Commits | What landed |
|---|---|---|
| 5 | `437a185` `b442322` `eaee67b` `4667a5e` | Inventory: locations, four derived states, the reservation ledger, weighted-average cost, ageing, count sheets, in-transit transfers, ABC / dead stock / fast-slow / low-stock |
| 6 | `a8c9bde` | Customer depth: contacts, ship-to branches, VERSIONED credit terms, the credit gate at confirm, the logged override, the unified timeline |
| 7 | `eeae971` `27d1c49` `761e9aa` + this | Quotation, reservation wiring, returns + credit notes, the health score, fast order entry |

**Verified at Part 7 close:** **623 tests passing**, ruff **exactly 37** — **zero new findings across
all nine checkpoints of this run.** Evidence: `-k r6_` (53) `-k r7_` (47, inventory) `-k r8_` (35)
`-k r9_` (78).

**R9.13's measurement, as measured:** a 5-line **repeat** order went from **~100 keystrokes to 5**.
Two things account for nearly all of it — `autofocus` (the caret used to start outside the form,
behind 19 sidebar links) and replacing a 268-option `<select>` with Part 3's `<datalist>`. **The
honest caveat:** a *manual* 5-line order is ~100 → ~55. The large win is not re-typing an order the
customer has placed before, not faster typing.

### Eight things Part 8 inherits and must not break

1. **`CustomerRepository.outstanding_minor` is THE receivable** — `Σ invoice − Σ allocations −
   Σ credit_notes`. Part 8's AR ageing and collections must CALL it, not re-derive it. A second
   derivation is how two screens start disagreeing about what a customer owes.
2. **Invoices, bills, payments, credit notes and `stock_movement` are APPEND-ONLY** (G4). A return
   does not edit an invoice; a credit note is subtracted from the receivable instead. R10.x's
   allocation must follow the same rule.
3. **`InventoryService.record_movement` is the ONLY writer of `stock_movement`** (G8), enforced by a
   source walk that fails if anything else constructs one.
4. **`ReservationService.reserve/release/consume` is the only reservation mechanism** (R6.5/R6.6).
   No flag, and a test asserts no boolean `reserv*` column exists anywhere.
5. **G11 has exactly one implementation**: `Explained` + the `explain_panel` macro. Part 8's margin
   and ageing figures are new *outputs*, not new shapes, and "unknown" is `Explained.unknown` —
   never a default number.
6. **Two versioning idioms exist and that is the limit** — Part 3/7's append-only revision rows
   (`revision_no`, no `superseded_at`) and Part 6's period rows (`valid_from`/`valid_to`). Pick one
   and say which; do not invent a third.
7. **`uuid7()` is NOT monotonic within a millisecond** — it fills its low bits from `os.urandom`, so
   `ORDER BY (timestamp, id)` cannot break a same-millisecond tie. Select by a discriminating column
   rather than by "newest", or stamp an explicit `datetime.now(UTC)` (microsecond resolution) the way
   credit policies and notes do.
8. **Money is integer minor units end to end** (G1), rounded through the ONE step,
   `app.core.money.round_minor`. No float goes near a money path. Margin is selling − the purchase
   price snapshotted on the line (R11.6) — **never** through valuation.

### Read for Part 8 — these and nothing else

- `docs/REQUIREMENTS.md` §11 (R10.x) and §12 (R11.x) — Part 8's two groups. §1 for the invariants.
- `docs/prompts/part-08.md` — self-contained, THREE checkpoints. Binding: `docs/STANDING-RULES.md`.
- `docs/08-module-breakdown.md` § Finance.
- **The edit set for C1:** `app/modules/finance/{models,repository,service,schemas}.py` ·
  `app/web/pages/finance.py` + templates · `app/db/references.py` · `app/seed/` · `tests/`.
- **`app/modules/finance/models.py` already holds** `Invoice`, `InvoiceLine`, `Bill`, `BillLine`,
  `Payment`, `PaymentAllocation` and `CreditNote`. Extend; do not rebuild (G16).

### Call, don't read — verified signatures, copied from source at Part 7 close

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

# app/modules/customers/ — Part 6/7
CustomerRepository(db).outstanding_minor(customer_id) -> int   # THE receivable. Call it.
CreditPolicyService(db).check(customer_id, total) -> CreditDecision   # integer boundary
CreditPolicyService(db).enforce(customer_id, total, *, override_reason=None, actor_id=None,
                               ref_label="")   # raises with the numbers, or logs the override
CreditPolicyService(db).set_policy(customer_id, CreditPolicySet, *, actor_id)   # APPENDS
CreditPolicyService(db).current/history/explain/refusal_message
CustomerTimelineService(db).events(customer_id, *, limit=200)   # projection, NO events table
CustomerHealthService(db).score(customer_id, *, as_of=None) -> Explained
#   Four inputs renormalising over what exists; "never invoiced" is MISSING, not full marks.

# app/modules/sales/ — Part 7
SalesOrderService(db).confirm(order_id, *, actor_id, credit_override_reason=None)
#   Credit gate FIRST, then reserves every line. A refusal leaves the order DRAFT.
SalesOrderService(db).fulfill(...)   # consumes the reservation, THEN posts stock OUT
SalesOrderService(db).cancel(order_id, *, reason, actor_id)   # releases; refuses fulfilled
QuotationService(db).create/send/revise/expire/convert   # DOC_TYPE = "SQT"
SalesReturnService(db).returnable(invoice_id) · .create(SalesReturnCreate, *, actor_id)
SalesReturnService.returnable_qty(invoiced, already) -> Decimal   # STATICMETHOD, clamped
SalesReturnService(db).credit_notes(customer_id) -> list[CreditNoteRead]
FastEntryService(db).picker_hints(products) · .last_order_lines(customer_id)
#   .available_by_product() · .list_price_by_product() · .customers_with_history()

# app/modules/inventory/ — Part 5
InventoryService(db).record_movement(*, product_id, warehouse_id, qty_delta, reason,
    ref_type=None, ref_id=None, unit_cost_minor=None, bin_id=None, occurred_at=None,
    actor_id=None)   # THE only writer (G8). Reasons: PURCHASE SALE TRANSFER ADJUSTMENT
                     # COUNT PUTAWAY RETURN
InventoryService(db).on_hand/available/states/bin_stock/location_rollup
ReservationService(db).reserve/release/consume(ReservationCreate, *, actor_id)
ValuationService(db).cost_basis(product_id) -> Explained · .stock_value() · .ageing()
InventoryHealthService(db).abc/dead_stock/movement_rates/low_stock
InventoryHealthService(db).reorder_suggestions(...)   # DELEGATES to R5.9's engine

# app/modules/procurement/recommend.py — R5.9's ONE entry point
RecommendationService(db).recommend(*, product_id=None, limit=None)
#   A source walk FAILS if a second `def recommend|recommendations|suggest_reorder` appears.

# app/modules/config/service.py
default_business_unit(db) -> uuid.UUID
allocate_document_number(db, *, doc_type, business_unit_id, on_date) -> "INV-202607-00001"
#   In use: PO GRN BILL REQ RFQ QUO SO INV TRF CNT FUL SQT RET CRN.
```

Part 2's machinery still holds: `ListSpec` + `view_from_request`, `ensure_unreferenced` /
`soft_delete` / `ensure_unique`, `ActivityService.history`, and the `page_header` / `stat` / `badge` /
`list_*` / `history_panel` / `explain_panel` macros.

### Gotchas that will bite Part 8

- **`create_all` builds new TABLES but never ALTERs an existing one.** A new column on `invoice`,
  `payment` … needs an `_ADDITIVE_COLUMNS` entry in `app/main.py` (~line 45) or it is silently
  missing on every DB seeded earlier, including the dev `apexos.db` carried since Part 1. Get the
  DDL from what `create_all` emits (`CreateTable(...).compile(sqlite)`); don't guess.
- **`client.post` COMMITS; `db`-fixture writes roll back.** A test that POSTs leaves rows behind.
  Three checkpoints broke the same two Part 1/3 tests by leaving an OPEN document (draft *or*
  confirmed counts as open) on the first customer. **Tests that POST need a subject no other test
  asserts about** — see `test_fast_entry.py`'s `spare_customer` fixture.
- **A source-walk test cannot tell a call from a comment.** One asserted a symbol was absent and
  failed on its own docstring. Count queries with a SQLAlchemy event listener instead.
- **A test can pass without testing anything.** Assert a **floor** on anything you enumerate, and
  mutation-check once. `assert x > 0` on a value that is always positive asserts nothing.
- **Assert on HTML phrases that do NOT straddle a template line break** — cost four runs so far.
- **A `select()` per row in a projector is the thing to avoid**; `db.get(Model, id)` in a loop is
  free (identity map). An AR ageing screen over hundreds of invoices should be a handful of queries.
- **The env var is `DATABASE_URL`, not `APEXOS_DATABASE_URL`.** The wrong name silently writes the
  real `apexos.db`. A scratch `.db` cannot be deleted while uvicorn holds it — stop it first
  (`Get-CimInstance Win32_Process | Where CommandLine -like '*<port>*' | Stop-Process -Force`;
  `pkill` does not exist here). 8000 may be busy; this run used 8015–8024.
- **PowerShell has no heredocs and `$pid` is read-only** — a multi-line commit message needs the
  Bash tool (`git commit -F - <<'EOF'`). Shell variables do not persist between tool calls.
- **A script that reads the DB without booting the app skips `_ensure_new_columns`** and crashes on
  any additively-added column. Use a `TestClient(app)` context if the shim must have run.
- **A self-referencing Pydantic model needs `Model.model_rebuild()`** after its class body.

### Do NOT read

`app/seed/core.py` (740 lines — read `app/seed/__init__.py`'s docstring, and `app/seed/quotations.py`
as the pattern for a new section) · `app/modules/procurement/preorder.py` ·
`app/modules/suppliers/vendor.py` · `app/modules/inventory/{valuation,health}.py` ·
`app/modules/customers/{credit,timeline,health}.py` · `app/modules/sales/{quotation,returns,
fast_entry}.py` (Parts 5–7 finished them; their signatures are above) · `tests/test_inventory_*.py`,
`test_customer_*.py`, `test_quotations.py`, `test_returns_and_reservations.py`, `test_fast_entry.py`,
`test_preorder.py`, `test_po_revisions.py`, `test_vendor_*.py`, `test_procurement_planning.py` (they
pass; read one only if you change what it covers) · anything in `docs/parts/` · `docs/ROADMAP.md`
(~17k tokens, planning only) · the older `docs/` design files, `docs/DELETION-POLICY.md` and
`docs/MIGRATION-STRATEGY.md` — Part 1 resolved those.

Note `docs/REQUIREMENTS.md` is at v1.2: the stock writer is `InventoryService.record_movement`, and
any older doc naming `post_movement` is wrong.

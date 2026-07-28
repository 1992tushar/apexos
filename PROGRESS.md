# ApexOS — Build Progress

> The source of truth for status. **This file is capped at ~350 lines and does not grow.**
> Closed parts live in `docs/parts/`. A new part's handoff **replaces** the previous one here — never appends.

_Last updated: 2026-07-28_

### What belongs in this file

| Section | Rule |
|---|---|
| `▶ NEXT SESSION PROMPT` | Exactly one. The session that closes a checkpoint rewrites it. |
| `▶ Handoff` | Exactly one — the part just closed, pointing at the part about to start. |
| Anything else | Does not belong here. |

**Closing a part archives it.** Move its record to `docs/parts/part-0N.md`, then delete it from this
file, keeping only the `Read for the next part` and `Call, don't read` blocks the next session needs.
This is not tidiness. At Part 3 close this file was **1,212 lines / 90KB — about 22k tokens, re-read at
the start of every remaining session**, and it was growing ~300 lines per part. It was the single
largest avoidable cost in the build. Part 5 kept it near cap by **archiving progressively** — each
finished checkpoint's record moved to `docs/parts/part-05.md` rather than waiting for the close.

Where everything else lives is in `CLAUDE.md` — setup in `RUNNING.md`, closed parts in `docs/parts/`,
per-part prompts in `docs/prompts/part-NN.md`, the binding rules in `docs/STANDING-RULES.md`, the
layout in `docs/CODEBASE-MAP.md`, and `docs/ROADMAP.md` which a session does not read.

---

# ▶ CURRENT WORK — read this first

A **session** is a token budget; a **part** is a group of sessions. The checkpoint list per part is in
`docs/STANDING-RULES.md` → *Session protocol*.

**All work is on `main`** — no feature branches, no PRs. A part is "done" when every P0/P1 requirement
passes, the verify loop is green, and this file is updated. **Parts 5–7 are NOT being tagged** (the user
waived it), so the checkpoint SHA table below is what `part-0N-done` would otherwise be — the record of
where each part began and ended.

**Every session ends by updating the block below, before it runs out of room.** A session that dies
with an accurate resume block costs nothing; one that dies without it costs a re-derivation.

### ▶ How to start the next session

Type **`Start next part of development`** in a fresh session. `CLAUDE.md` binds that phrase to "read the
**▶ NEXT SESSION PROMPT** below and follow it", so the state lives here rather than in what you remember
to type. **The session that closes a checkpoint owns that prompt** — one still naming last checkpoint's
baseline counts is worse than none, because the next session will trust it.

#### ▶ NEXT SESSION PROMPT — Part 7, C2b (health score + speed) · CLOSES PART 7

```
Continue the ApexOS build. Do this in order:

1. git checkout main && git pull origin main. Then git status — one writer per working
   tree; if it is dirty, stop and report. This run does NOT tag parts (the user waived
   tags for Parts 5–7), so do not expect part-05-done or part-06-done to exist.

2. Read the "▶ CURRENT WORK" block below, especially "▶ Handoff". PARTS 5 AND 6 ARE
   COMPLETE; PART 7 C1 (quotation) and C2a (reservation wiring + returns) ARE DONE. That
   block names the edit set, carries verified signatures to call WITHOUT opening the source,
   and its "Do NOT read" list is binding. **What remains is the health score and the speed
   work, and finishing them CLOSES PART 7.**

3. Read docs/REQUIREMENTS.md §1 (global invariants G1–G17) and §10 (R9.x). NOT optional:
   the invariants you must not break — integer minor units, exactly one activity_log row
   per state change, derived-never-stored, APPEND-ONLY LEDGERS — are not in the files you
   are editing, and **R9.5 is a direct test of the last one**.
   Then docs/prompts/part-07.md (self-contained) and docs/STANDING-RULES.md (binding).
   Do NOT open docs/ROADMAP.md — planning only, ~17k tokens.

4. `git show --stat 27d1c49` for what C2a changed. Not a tree walk.

5. Verify the baseline before writing code (from apps/api, venv activated):
     python -m pytest -q                  # expect 591 passed
     python -m ruff check app/ tests/     # expect EXACTLY 37 — 38 is a regression
   If either is off, stop and report. 37 is pre-existing (32 E501, 4 F841, 1 B007, all in
   untouched modules). Parts 1–7 C2a added zero new findings; hold that line.

6. THREE things remain. The health score is service work; the speed work has the most
   value per line in the whole part.

   a. R9.10/R9.11 — CUSTOMER HEALTH SCORE: order frequency, profitability (the EXISTING
      margin logic — `MarginService.gp`, do NOT add a second), outstanding + ageing, and
      recency. Inputs AND weighting ON SCREEN through `Explained` + the `explain_panel`
      macro (G11, one shape). Insufficient history yields **`Explained.unknown`**, never a
      default number, and R9.11 needs its own test.
      **Part 4's `VendorIntelService.score` is the worked example** — read it: it weights
      60/40, RENORMALISES over whichever inputs exist, and says so in a caveat rather than
      inventing a zero. A four-input score should do the same, and "unknown" is only for
      when NO input is available.
      Everything it needs already exists: `CustomerRepository.outstanding_minor` (now net of
      credit notes), `CustomerTimelineService.events` for recency and frequency, and
      `MarginService.gp` for profitability. Reuse, do not rebuild (G16).

   b. R9.12–R9.14 — SPEED. **The highest-value item in the part.** D-B makes the founder the
      only operator, so every order is entered personally: keyboard-first entry, product
      search-as-you-type showing price AND **available stock** inline (that is
      `InventoryService.available`, not on-hand — committed stock cannot be sold twice),
      reorder-from-last-order, defaults from customer history, bulk line entry.
      REUSE Part 3's `<datalist>` picker: `_preorder.html`'s `line_grid(products, rows,
      autofocus, title, with_price)` and `app/web/pages/preorder.py`'s `_lines` resolver,
      which NAMES an unknown SKU back to the user instead of dropping the row. A `<select>`
      of 311 products cannot be typed into.
      **R9.13: MEASURE the keystrokes for a 5-line repeat order BEFORE and AFTER, and put
      BOTH numbers in PROGRESS.md.** Measure FIRST. A session that measures and optimises in
      one pass loses the baseline — Part 11's C1 is measurement-only for exactly this reason.

   c. R9.15's remainder: a confirmed order HOLDING a reservation (the seed already produces
      one via Part 6's override order — verify rather than duplicate) and a PARTIAL RETURN
      with its credit note. Extend `app/seed/quotations.py` or add a new module.

7. Constraints that bind:
     - G4: `stock_movement`, `payment`, invoices, bills and credit notes are APPEND-ONLY.
     - G8: `record_movement` is the ONLY writer of `stock_movement`; a source walk enforces it.
     - G5: exactly one activity_log row per state change.
     - G7: the health score is DERIVED — no stored score column, and no cached rating.
     - G10: every new POST carries the R1.4 authz guard; the authz walk enforces it.
     - G11 on the health score; G12 arithmetic only, no ML and no runtime LLM call.
     - Any new model owes app/db/references.py an entry (R3.7) — **the health score should
       need none.** If you are adding a table for a score, re-read G7.
     - status_class needs a bucket for any new status, or the badge renders grey.

8. Work on main. No branches, no PRs, no tags. Commit at the end and push. **C2 CLOSES
   PART 7:** write docs/parts/part-07.md, delete the Part 7 block from PROGRESS.md, and
   rewrite the NEXT SESSION PROMPT for **the E2E gate** (ledger item 7 in
   docs/prompts/parts-05-07-loop.md) with measured baselines.

9. NAME EVERY NEW TEST AFTER THE REQUIREMENT IT PROVES. Evidence is a test node id, not a
   paragraph.

   MUTATION-CHECK the new suite once. Three lessons worth carrying, each learned the hard
   way: **an equality assertion between two code paths only tests what the current data
   distinguishes** (Part 5); **when a change relocates a fact, move the assertion rather
   than deleting it** (Part 6); and **`uuid7()` is NOT monotonic within a millisecond** — it
   fills its low bits from os.urandom, so `ORDER BY (timestamp, id)` cannot break a
   same-millisecond tie. Select by a discriminating column instead of by "newest".
   Good mutations here: mutate the invoice on return (must fail R9.5), skip the release on
   cancel, and return a default score instead of "unknown".

   If the checkpoint changed the SHAPE of anything, amend docs/CODEBASE-MAP.md in the same
   session. A stale map is worse than none.

Use pytest -q, never verbose. Don't re-read files you just edited.
```

**If a session has drifted** and you want a hard reset on scope, ignore the above and paste the whole
```-fenced PROMPT from `docs/prompts/part-07.md` instead. More deterministic, more typing.

**Rules of thumb.** One checkpoint per session — don't push a session past its checkpoint to "just
finish the part". Start each session fresh (`/clear` or a new window) rather than continuing a long
one. And if a session ends messy, the recovery is `git log --oneline -5` plus this block, not
re-reading the design docs.

---

## ▶ Handoff — Part 7 C1 done · C2 closes the part

Parts 5 and 6 are **COMPLETE**; Part 7's quotation half is done. **Not tagged** — waived for Parts
5–7, so these SHAs are the record. Full records in `docs/parts/part-05.md` and `part-06.md`.
**Do not read them.**

| Part | Commit(s) | What landed |
|---|---|---|
| 5 | `437a185` `b442322` `eaee67b` `4667a5e` | Inventory: locations, four states, reservation ledger, weighted-average cost, ageing, count sheets, in-transit transfers, ABC / dead stock / fast-slow / low-stock |
| 6 | `a8c9bde` | Customer depth: contacts, branches, VERSIONED credit terms, the credit gate at confirm, the override, the timeline |
| 7 C1 | `eeae971` | Quotation: create / send / revise / expire / convert, append-only revisions |
| **7 C2a** | **`27d1c49`** | **Reservation wiring (confirm/fulfil/cancel) + returns with credit notes** |

**Verified at C2a:** **591 tests passing**, ruff **exactly 37** — zero new findings across eight
checkpoints. Evidence: `-k r6_` (53) `-k r7_` (47, inventory) `-k r8_` (35) `-k r9_` (47).

| R | State |
|---|---|
| R9.1 R9.2 R9.3 | ✅ quotation, append-only revisions, conversion carrying the quoted price |
| R9.4 R9.5 R9.6 R9.7 | ✅ return posts stock IN, credit note raised, invoice UNTOUCHED, receivable net of credits |
| R9.8 R9.9 | ✅ confirm reserves (after the credit gate), fulfil consumes, cancel releases |
| R9.15 | ⚠️ quotations + a reservation-holding order exist; **the partial return is still owed** |
| **R9.10 R9.11 R9.12 R9.13 R9.14** | ❌ **health score + speed — all that remains of Part 7** |

### Four decisions C1 made that C2 must not reverse

1. **Quotation revisions mirror Part 3's append-only shape** (`revision_no`, no `superseded_at`),
   not Part 6's `valid_from`/`valid_to`. A period versus a sequence of offers — a test asserts
   neither `superseded_at` nor `valid_to` is on the table. **Two idioms is enough; C2 must not add
   a third for credit notes.**
2. **`revision_no` 1 is written by `send`, not `create`**, and `revise` requires a *sent*
   quotation. A draft nobody has seen has no agreement to preserve (R4.7's reasoning).
3. **Conversion passes the quoted `unit_price_minor` explicitly** and calls
   `SalesOrderService.create`. A source walk asserts it does not build order lines itself.
4. **The quotation document type is `SQT`, not `QUO`** — `QUO` is Part 3's *supplier* quotation.
   Doc types now in use: PO GRN BILL REQ RFQ QUO SO INV TRF CNT FUL **SQT**.

### Four decisions C2a made that C2b must not reverse

1. **Reserve runs AFTER the credit gate**, and a refused confirm leaves NO reservation — there is
   a test. On fulfilment, consume and the outbound movement happen in one pass with the
   reservation FIRST: consuming after would briefly show the units as both reserved and gone,
   and `available` (on-hand − reserved) would double-count them.
2. **Cancel refuses a fulfilled order** and says to record a return instead. Stock that has
   shipped is undone by R9.4, not by a status change. A reason is required.
3. **The invoice is never mutated by a return** (G4/R9.5). The receivable falls because
   `CustomerRepository.outstanding_minor` now subtracts credit notes:
   `Σ invoice − Σ allocations − Σ credit_notes`. **Anything computing a receivable must use that
   method, not re-derive it** — including the health score's "outstanding" input.
4. **A credit note carries no lines**; the `sales_return` holds them. A second copy of the same
   figures is a second thing that can disagree.

### Two things C2b inherits and must not break

1. **`uuid7()` is not monotonic within a millisecond** — it fills its low bits from `os.urandom`,
   so `ORDER BY (timestamp, id)` cannot break a same-millisecond tie. Select by a discriminating
   column rather than by "newest". Product code is fine today; do not assume otherwise.
2. **Returns do not reduce measured demand.** `InventoryRepository.CONSUMPTION_REASONS` is
   `("SALE",)`, so a returned unit still counts as sold for ABC, dead stock and fast/slow.
   That is a **known limitation, not an oversight** — netting returns off demand would change
   Part 5's semantics, and it was left alone deliberately. Say so if a health-score input needs
   net revenue.

### Read for C2b — these and nothing else

- `docs/REQUIREMENTS.md` §10 — **R9.10–R9.14 remain.** §1 for the invariants.
- `docs/prompts/part-07.md` — self-contained. Binding rules: `docs/STANDING-RULES.md`.
- **`app/modules/suppliers/vendor.py`'s `score`** — the worked example for R9.10: weighted,
  renormalising over available inputs, with a caveat instead of an invented zero. This is the one
  file worth reading in full; it is otherwise on the do-not-read list.
- **The edit set:** a health module (`app/modules/customers/health.py`, beside `credit.py` and
  `timeline.py`) · `app/web/pages/{customers,sales}.py` + templates for the score and the fast
  entry path · `app/seed/` for R9.15's partial return · `tests/test_customer_health.py`,
  `tests/test_fast_entry.py`.

### Call, don't read — verified signatures, copied from source at Part 6 close

```python
# app/modules/inventory/service.py — the ONLY writer of stock_movement (G8), enforced by a
# source-walk test that fails if anything else constructs one.
InventoryService(db).record_movement(*, product_id, warehouse_id, qty_delta, reason,
    ref_type=None, ref_id=None, unit_cost_minor=None, bin_id=None, occurred_at=None,
    actor_id=None) -> StockMovement
#   Reasons in use: PURCHASE · SALE · TRANSFER · ADJUSTMENT · COUNT · PUTAWAY.
#   `occurred_at` is how the seed fabricates history at INSERT time — never by UPDATE (G4).
InventoryService(db).on_hand(product_id, warehouse_id=None) -> Decimal
InventoryService(db).available(product_id, warehouse_id=None) -> Decimal
#   sellable on-hand − outstanding reservations. NOT clamped at 0.
InventoryService(db).states(warehouse_id=None) -> list[StockStateRow]
#   (.on_hand .reserved .in_transit .quarantined .available) — all derived (G7).

# THE VERB R9.8/R9.9 CALLS. Reserve at confirm (AFTER the credit gate), consume at
# fulfilment, release at cancellation. No flag, no second mechanism.
ReservationService(db).reserve(ReservationCreate, *, actor_id)  -> ReservationResult
ReservationService(db).release(ReservationCreate, *, actor_id)  -> ReservationResult
ReservationService(db).consume(ReservationCreate, *, actor_id)  -> ReservationResult
#   reserve at SO confirm · consume at fulfilment · release at cancellation. Each appends
#   ONE signed ledger row and writes ONE activity_log row (G5). Never edits a row.
ReservationCreate(product_id, warehouse_id, qty>0, bin_id=None, ref_type=None, ref_id=None,
                  note=None)

# app/modules/inventory/{valuation,health}.py — reads only, write nothing (G15)
ValuationService(db).cost_basis(product_id) -> Explained · .stock_value() · .ageing()
InventoryHealthService(db).abc() · .dead_stock() · .movement_rates() · .low_stock()
InventoryHealthService(db).reorder_suggestions(*, product_id=None, limit=None)
#   A BARE DELEGATION to RecommendationService.recommend — never reimplement it (R7.11).

# app/modules/procurement/recommend.py — R5.9's ONE entry point
RecommendationService(db).recommend(*, product_id=None, limit=None) -> list[Recommendation]
#   .sentence is the plain-language line. Worst shortfall first. [] means nothing to buy.
#   A source walk FAILS if a second `def recommend|recommendations|suggest_reorder` appears
#   anywhere in app/.

# app/db/explain.py — the ONE shape for every explained number (G11)
Explained(what, value: str | None, formula, window, inputs=(), records=(),
          unknown_reason=None, caveat=None)   # .is_known · .display -> value or "unknown"
Explained.unknown(*, what, formula, reason, window="no data", inputs=(), records=())
Input(label, value, weight=None, missing_reason=None)   # .is_missing
SourceRecord(label, href=None)
# Rendered by ONE macro:  {{ ui.explain_panel(explained, "Optional title") }}

# app/core/money.py — money and quantity as text. G1: integer minor units end to end.
qty_text(value: Decimal) -> str      # "40", not "40.0000". Service messages only.
round_minor(value: Decimal) -> int   # THE one money rounding step. No second one.
minor_to_text(minor: int | None) -> str        # 123456 -> "1234.56"

# app/modules/config/service.py
default_business_unit(db) -> uuid.UUID
allocate_document_number(db, *, doc_type, business_unit_id, on_date) -> "SO-202607-00001"
#   Row-locked per (BU, doc_type, period). In use: PO GRN BILL REQ RFQ QUO SO INV TRF CNT FUL.
#   QUO is Part 3's SUPPLIER quotation — a customer quotation needs a different type.

# app/modules/customers/credit.py — Part 6. R9.8's confirm path already calls `enforce`.
CreditPolicyService(db).check(customer_id, order_total_minor) -> CreditDecision
#   CreditDecision(.allowed .limit_minor .outstanding_minor .order_total_minor .unlimited
#                  .overridden .override_reason) · .exposure_minor · .shortfall_minor
#   Integer arithmetic (G1): AT the limit is allowed, one minor unit over is not. A limit of
#   ZERO means none recorded — allowed, `.unlimited` True — not "refuse everything".
CreditPolicyService(db).enforce(customer_id, total, *, override_reason=None, actor_id=None,
                               ref_label="") -> CreditDecision
#   Passes, or raises ConflictError with all four numbers, or records the override as ONE
#   activity row against the CUSTOMER (G5). A passing check logs nothing.
CreditPolicyService(db).set_policy(customer_id, CreditPolicySet, *, actor_id)
#   APPENDS a version and stamps valid_to on the previous one (R8.3). Reason mandatory.
CreditPolicyService(db).current(customer_id) · .history(customer_id) · .explain(decision)
CreditPolicyService(db).refusal_message(decision) -> str   # R8.7's sentence

# app/modules/customers/{service,timeline}.py
CustomerService(db).contacts/branches/notes/documents(customer_id)
CustomerService(db).add_contact/add_branch/add_note(customer_id, payload, *, actor_id)
CustomerService(db).delete_contact(contact_id, *, actor_id) · .delete_branch(branch_id, ...)
CustomerRepository(db).outstanding_minor(customer_id) -> int   # receivable, derived
CustomerTimelineService(db).events(customer_id, *, limit=200) -> list[TimelineEvent]
#   Six sources, six queries, NO events table. TimelineEvent(.at .kind .summary .href
#   .amount_minor); kinds: order invoice payment task note activity.

# app/modules/sales/service.py — the order spine, now reservation-aware
SalesOrderService(db).confirm(order_id, *, actor_id, credit_override_reason=None)
#   Credit gate FIRST, then reserves every line (R9.8). A refusal leaves it DRAFT.
SalesOrderService(db).fulfill(order_id, *, actor_id)   # consumes, then posts stock OUT
SalesOrderService(db).cancel(order_id, *, reason, actor_id)   # releases; refuses fulfilled
SalesOrderService(db).create/invoice(...)

# app/modules/sales/returns.py — Part 7 C2a
SalesReturnService(db).returnable(invoice_id) -> list[ReturnableLine]
#   (.invoiced_qty .returned_qty .returnable_qty .unit_price_minor) · .fully_returned
SalesReturnService.returnable_qty(invoiced, already) -> Decimal   # STATICMETHOD, clamped
#   THE definition (R9.6) — the shape open_qty gave back orders. Do not inline a second.
SalesReturnService(db).create(SalesReturnCreate, *, actor_id) -> SalesReturnDetail
#   Validates the WHOLE payload first, then posts stock IN (reason "RETURN") and raises a
#   CreditNote. NEVER touches the invoice (G4/R9.5). Priced AS INVOICED.
SalesReturnService(db).get(id) · .for_invoice(invoice_id) · .credit_notes(customer_id)
DOC_TYPE_RETURN = "RET" · DOC_TYPE_CREDIT = "CRN"

# app/modules/customers/repository.py — the receivable, now net of credits (R9.7)
CustomerRepository(db).outstanding_minor(customer_id) -> int
#   Σ invoice.total − Σ allocations − Σ credit_notes. USE THIS; do not re-derive it.

# app/modules/sales/quotation.py — Part 7 C1
QuotationService(db).create(QuotationCreate, *, actor_id)  -> QuotationDetail
QuotationService(db).send(id, *, actor_id)      # -> sent, writes revision 1 verbatim
QuotationService(db).revise(id, QuotationRevise, *, actor_id)   # requires SENT; appends
QuotationService(db).expire(id, *, actor_id)    # from draft|sent only
QuotationService(db).convert(id, *, actor_id)   -> SalesOrderDetail
#   Calls SalesOrderService.create with each QUOTED unit_price_minor. Never re-resolves.
QuotationService(db).get(id) · .list(status=None, limit=100)
#   QuotationDetail(.quotation_no .status .lines .revisions .sales_order_no .past_validity)
#   · .revision_count · .is_open (draft|sent)
DOC_TYPE = "SQT" · OPEN_STATUSES = ("draft", "sent")

# app/web/templates/_preorder.html — the typed SKU picker
pre.line_grid(products, rows, autofocus=false, title="Lines", with_price=false)
#   `rows` is an ITERABLE (pass range(4)), not a count. `with_price` (added in C1) emits a
#   third column named `unit_price_rupees`. Resolver: app/web/pages/preorder.py `_lines`,
#   which NAMES an unknown SKU back to the user rather than dropping the row.
```

Part 2's machinery still holds unchanged: `ListSpec` + `view_from_request` (list pages),
`ensure_unreferenced` / `soft_delete` / `ensure_unique`, `ActivityService.history`, and the
`page_header` / `stat` / `badge` / `list_*` / `history_panel` / `explain_panel` macros.

### Gotchas that will bite Part 7

- **`create_all` builds new TABLES but never ALTERs an existing one.** A new column on `sales_order`,
  `invoice` … needs an `_ADDITIVE_COLUMNS` entry in `app/main.py` (~line 45) or it is silently
  missing on every DB seeded earlier, including the dev `apexos.db` carried since Part 1. Get the DDL
  from what `create_all` emits (`CreateTable(...).compile(sqlite)`), don't guess:
  `DateTime(timezone=True)` → `DATETIME`, `Uuid()` → `CHAR(32)`, `Numeric(18,4)` → `NUMERIC(18, 4)`.
  Part 5 verified this path against a pre-Part-5 copy of the dev database; the shim works.
- **A column default of `func.now()` TIES.** Rows written in one transaction share a timestamp, so
  ordering on it alone is non-deterministic and a test reading "the newest row" fails intermittently.
  Add `id` as the tiebreaker — UUID v7 keys are time-ordered. **Quotation revisions will hit this.**
  (`InventoryRepository.movements()` still has this latent tie — pre-existing, left alone.)
- **A test can pass without testing anything.** Assert a **floor** on anything you enumerate
  (`assert len(found) > 40`), and mutation-check once.
- **Adding a row to a shared seed can break unrelated tests.** Part 6's breaching order left a
  *confirmed* order on the first customer, which made it undeletable and broke two Part 1/3 tests
  that encode "that customer's work is closed". **Before seeding a document in an open status, ask
  which existing tests treat that party as quiet.**
- **Assert on HTML phrases that do NOT straddle a template line break** — cost three runs so far.
- **A page with an entry form has TWO `<tbody>`s**, so `html.count("<tbody>") == 1` is wrong there.
  Assert markers the shared macros emit; read totals from the paginator, not by counting `<tr>`.
- **A `select()` per row in a projector is the thing to avoid**; `db.get(Model, id)` in a loop is free
  (identity map). A timeline over six source types should be a handful of queries, not one per event.
- **The env var is `DATABASE_URL`, not `APEXOS_DATABASE_URL`.** The wrong name silently writes the real
  `apexos.db` and you "verify" against stale data. A scratch `.db` cannot be deleted while uvicorn holds
  it — stop it first (`Get-CimInstance Win32_Process | Where CommandLine -like '*<port>*' |
  Stop-Process -Force`; `pkill` does not exist here). 8000 may be busy; Part 5 used 8015–8018.
- **PowerShell has no heredocs and `$pid` is read-only** — a multi-line commit message needs the Bash
  tool (`git commit -F - <<'EOF'`). Shell variables do **not** persist between tool calls.
- **A script that reads the DB without booting the app skips `_ensure_new_columns`** and will crash on
  any additively-added column. Use a `TestClient(app)` context if you need the shim to have run.
- **A self-referencing Pydantic model needs `Model.model_rebuild()`** after its class body.

### Do NOT read

`app/seed/core.py` (720 lines — read `app/seed/__init__.py`'s docstring, and `app/seed/customers.py`
as the pattern for a new section) · `app/modules/procurement/preorder.py` (814 lines) ·
`app/modules/suppliers/vendor.py` · `app/modules/inventory/{valuation,health}.py` and
`app/modules/customers/{credit,timeline}.py` (Parts 5 and 6 finished them; their signatures are
above) · **`app/modules/procurement/service.py`'s revision code IS worth reading** for R9.2's shape —
that is the exception to this list · `tests/test_customer_depth.py`, `test_inventory_*.py`,
`tests/test_preorder.py`, `test_po_revisions.py`,
`test_vendor_intel.py`, `test_vendor_screens.py`, `test_procurement_planning.py`,
`tests/test_inventory_*.py` (they pass; read one only if you change what it covers) · anything in
`docs/parts/` · `docs/ROADMAP.md` (~17k tokens, planning only) · the older `docs/` design files,
`docs/DELETION-POLICY.md` and `docs/MIGRATION-STRATEGY.md` — Part 1 resolved those.

Note `docs/REQUIREMENTS.md` is at v1.2: the stock writer is `InventoryService.record_movement`, and any
older doc naming `post_movement` is wrong.

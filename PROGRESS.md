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

#### ▶ NEXT SESSION PROMPT — Part 7, C1 (quotation) · Part 7 has TWO checkpoints

```
Continue the ApexOS build. Do this in order:

1. git checkout main && git pull origin main. Then git status — one writer per working
   tree; if it is dirty, stop and report. This run does NOT tag parts (the user waived
   tags for Parts 5–7), so do not expect part-05-done or part-06-done to exist.

2. Read the "▶ CURRENT WORK" block below, especially "▶ Handoff — Part 6 closed".
   PARTS 5 AND 6 ARE COMPLETE: every R6.x, R7.x and R8.x passes. That block names the edit
   set, carries verified signatures to call WITHOUT opening the source, and its "Do NOT
   read" list is binding.

3. Read docs/REQUIREMENTS.md §1 (global invariants G1–G17) and §10 (R9.x — Part 7's whole
   acceptance contract). NOT optional: the invariants you must not break — integer minor
   units, exactly one activity_log row per state change, derived-never-stored, APPEND-ONLY
   LEDGERS — are not in the files you are editing, and R9.5 is a direct test of the last one.
   Then docs/prompts/part-07.md (self-contained) and docs/STANDING-RULES.md (binding:
   decisions D-A..D-D, session protocol, reading diet, verify loop). Do NOT open
   docs/ROADMAP.md — planning only, ~17k tokens.
   Also docs/08-module-breakdown.md §2.4 and §2.7.

4. `git show --stat a8c9bde` for what Part 6 changed. Not a tree walk —
   docs/CODEBASE-MAP.md is the orientation document and is current.

5. Verify the baseline before writing code (from apps/api, venv activated):
     python -m pytest -q                  # expect 541 passed
     python -m ruff check app/ tests/     # expect EXACTLY 37 — 38 is a regression
   If either is off, stop and report. 37 is pre-existing (32 E501, 4 F841, 1 B007, all in
   untouched modules). Parts 1–6 added zero new findings; hold that line.

6. GOAL: close the two gaps at the ENDS of the sales workflow. The middle —
   order → fulfilment → invoice → payment — already works and is E2E-verified. Do not
   touch it beyond what R9.8/R9.9 require (G16).

   C1 IS QUOTATION ONLY. Do not start returns; that is C2, and cramming both is how the
   append-only invoice rule gets rushed.

   a. R9.1 — quotation: create, revise, send, expire. A quotation is a new document with
      its own number (allocate_document_number, doc_type "QUO" is ALREADY in use by Part 3's
      supplier quotations — use a DIFFERENT type such as "SQT" for a customer quotation, or
      you will interleave two unrelated sequences).
   b. R9.2 — revisions are VERSIONED and APPEND-ONLY, prior versions readable VERBATIM.
      Part 3 built exactly this shape for purchase orders: PurchaseOrderRevision +
      PurchaseOrderRevisionLine, append-only, current = max(revision_no), NO superseded_at.
      Read that and mirror it rather than inventing a second versioning idiom.
      Part 6 built a second one for credit terms (valid_from/valid_to). Pick whichever fits
      and say WHY in the resume block — do not invent a third.
   c. R9.3 — quotation → sales order is ONE action carrying the QUOTED prices forward, with
      a test asserting the prices match. Part 3's decision 2 is the pattern: a conversion
      CALLS the target's service (SalesOrderService.create) rather than rebuilding it, and
      passes the quoted unit price explicitly — which is the entire point of having quoted.
   d. NOTE R8.12's fence is now yours to cross: quotations ARE Part 7's work.

7. Constraints that bind:
     - G4: append-only. A revision is a new row; nothing is edited in place.
     - G5: exactly one activity_log row per state change (create, revise, send, expire,
       convert — one each).
     - G7: totals derive from lines. Do not store a status that can be computed.
     - G10: every new POST carries the R1.4 authz guard. tests/test_web_authz.py walks the
       whole POST surface and fails on an unguarded route.
     - Every new model owes app/db/references.py an entry, even an empty tuple (R3.7), and
       EXERCISE it with blocking_references(db, row) in a test. An OPEN quotation should
       block retiring a product it names — that is the R4.1/R4.3 precedent.
     - status_class in web/core.py picks badge colour from a status STRING. draft / sent /
       expired / converted each need a bucket, or every quotation badge renders grey.
     - A new column on an EXISTING table needs an _ADDITIVE_COLUMNS entry in app/main.py.
   Seed (G14/R9.15): a quotation, a revised quotation, and one converted to an order. C2
   adds the reservation-holding order and the partial return. Extend a NEW
   app/seed/<domain>.py plus one call in run() — never by appending logic into run().

8. Work on main. No branches, no PRs, no tags. Commit at the end of C1 and push. Part 7's
   checkpoints: C1 quotation · C2 returns + credit note + reservation wiring + health score
   + the speed work. Do not push into C2.

9. NAME EVERY NEW TEST AFTER THE REQUIREMENT IT PROVES —
   `def test_r9_3_conversion_carries_the_quoted_price(...)`. A requirement's evidence is a
   test node id, NOT a paragraph. No per-requirement prose tables.

   MUTATION-CHECK the new suite once — break the implementation and confirm the tests go
   red. Every checkpoint in Parts 4–6 did this and it paid every time. Two lessons worth
   carrying: **an equality assertion between two code paths only tests what the current data
   distinguishes** (Part 5 — a no-op filter passed an "identical output" test), and **when a
   change relocates a fact, move the assertion rather than deleting it** (Part 6 — versioning
   moved where a field-diff lived and a Part 2 test had to follow it, not be weakened).
   Good mutations here: let a revision overwrite the previous one, and drop the quoted price
   on conversion so it re-resolves from the price list.

   If the checkpoint changed the SHAPE of anything, amend docs/CODEBASE-MAP.md in the same
   session. A stale map is worse than none.

10. BEFORE you run low, update the "▶ CURRENT WORK" block: the checkpoint SHA table,
    R-numbers passed and outstanding, gotchas, decisions a later checkpoint must not
    reverse, and the four delta lines — Changed since / Read for the next checkpoint /
    Call, don't read (copy signatures FROM SOURCE) / Do NOT read. Then rewrite the NEXT
    SESSION PROMPT for C2 with measured baselines. PROGRESS.md IS CAPPED AT ~350 LINES —
    replace, never append. Part 5 kept it there by archiving each finished checkpoint to
    docs/parts/ progressively rather than waiting for the close; do the same.

Use pytest -q, never verbose. Don't re-read files you just edited.
```

**If a session has drifted** and you want a hard reset on scope, ignore the above and paste the whole
```-fenced PROMPT from `docs/prompts/part-07.md` instead. More deterministic, more typing.

**Rules of thumb.** One checkpoint per session — don't push a session past its checkpoint to "just
finish the part". Start each session fresh (`/clear` or a new window) rather than continuing a long
one. And if a session ends messy, the recovery is `git log --oneline -5` plus this block, not
re-reading the design docs.

---

## ▶ Handoff — Part 6 closed · Part 7 starts here

Parts 5 and 6 are **COMPLETE** on `main`. **Not tagged** — waived for Parts 5–7, so these SHAs are
the record. Full records in `docs/parts/part-05.md` and `part-06.md`. **Do not read them.**

| Part | Commit(s) | What landed |
|---|---|---|
| 5 | `437a185` `b442322` `eaee67b` `4667a5e` | Inventory: locations, four states, reservation ledger, weighted-average cost, ageing, count sheets, in-transit transfers, ABC / dead stock / fast-slow / low-stock |
| 6 | `a8c9bde` | Customer depth: contacts, ship-to branches, VERSIONED credit terms, the credit gate at confirm, the override, the unified timeline |

**Verified at Part 6 close:** **541 tests passing**, `ruff check app/ tests/` **exactly 37** — zero
new findings across six parts. Evidence: `-k r6_` (53) `-k r7_` (47) `-k r8_` (35). Fresh seed +
uvicorn: every nav page 200s, the customer depth page renders every section, a bad id renders
`error.html` at 404.

### Four things Part 7 inherits and must not break

1. **R9.8 must reserve AFTER the credit check passes.** `SalesOrderService.confirm` now runs
   `CreditPolicyService.enforce` first and raises on a breach with no override reason, leaving the
   order in **draft**. Reserving before that check would leave a reservation holding stock for an
   order that never confirmed. The verb to call is `ReservationService.reserve` — **no flag, no
   second mechanism** (R6.5/R6.6).
2. **Two versioning idioms already exist. Do not invent a third.** Part 3 used append-only revision
   rows (`PurchaseOrderRevision`, current = `max(revision_no)`, no `superseded_at`); Part 6 used
   `valid_from`/`valid_to` on credit policy. R9.2's quotation revisions should mirror the Part 3
   shape — pick one and **say which and why** in the resume block.
3. **G11 has exactly one implementation.** `Explained` + the `explain_panel` macro. R9.10's health
   score is a new *output*, not a new shape, and R9.11's "unknown" is `Explained.unknown`.
4. **`_qty_text`, `round_minor` and `default_business_unit` have all moved** to escape circular
   imports (`app/core/money.py`, `app/modules/config/service.py`). **A fourth such move is a sign the
   layering needs a proper look rather than another move.**

### Read for Part 7 — these and nothing else

- `docs/REQUIREMENTS.md` §10 (R9.x) — the whole contract. §1 for the invariants.
- `docs/prompts/part-07.md` — self-contained. Binding rules: `docs/STANDING-RULES.md`.
- `docs/08-module-breakdown.md` §2.4 and §2.7.
- **The edit set for C1 (quotation):** a new `app/modules/sales/quotation.py` (or a `quotations`
  module — the sales module already holds the order spine) · `app/modules/sales/models.py` for the
  quotation + revision tables · `app/db/references.py` · `app/main.py`'s `_ADDITIVE_COLUMNS` if a
  column lands on an existing table · `app/web/pages/sales.py` + templates · a NEW
  `app/seed/<domain>.py` plus one call in `run()` · `tests/test_quotations.py`.
- **`allocate_document_number` doc types already in use:** PO GRN BILL REQ RFQ QUO SO INV TRF CNT
  FUL. **`QUO` is Part 3's SUPPLIER quotation** — a customer quotation needs its own type.

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

# app/modules/sales/service.py — the confirm path Part 7 hooks
SalesOrderService(db).confirm(order_id, *, actor_id, credit_override_reason=None)
#   Runs the credit gate FIRST. On a breach with no reason it raises and the order stays
#   DRAFT. R9.8 must reserve stock AFTER this passes.
SalesOrderService(db).create/fulfill/invoice(...)
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

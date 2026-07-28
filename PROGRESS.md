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

#### ▶ NEXT SESSION PROMPT — Part 6, C1 (customer depth) · the WHOLE part is one checkpoint

```
Continue the ApexOS build. Do this in order:

1. git checkout main && git pull origin main. Then git status — one writer per working
   tree; if it is dirty, stop and report. This run does NOT tag parts (the user waived
   tags for Parts 5–7), so do not expect part-05-done or part-06-done to exist.

2. Read the "▶ CURRENT WORK" block below, especially "▶ Handoff — Part 5 closed".
   PART 5 IS COMPLETE: every R6.x and R7.x passes. That block names the edit set, carries
   verified signatures to call WITHOUT opening the source, and its "Do NOT read" list is
   binding. Part 6 is ONE checkpoint — the whole part is one session's work.

3. Read docs/REQUIREMENTS.md §1 (global invariants G1–G17) and §9 (R8.x — Part 6's whole
   acceptance contract). NOT optional: the invariants you must not break — integer minor
   units, exactly one activity_log row per state change, derived-never-stored, append-only
   ledgers — are not in the files you are editing.
   Then docs/prompts/part-06.md (self-contained) and docs/STANDING-RULES.md (binding:
   decisions D-A..D-D, session protocol, reading diet, verify loop). Do NOT open
   docs/ROADMAP.md — planning only, ~17k tokens.
   Also docs/08-module-breakdown.md §2.4 (Customers/CRM) and §2.7 (Sales).

4. `git diff 64ae50f..HEAD --stat` for everything Part 5 changed (that is Part 4's close).
   Not a tree walk — docs/CODEBASE-MAP.md is the orientation document and is current.

5. Verify the baseline before writing code (from apps/api, venv activated):
     python -m pytest -q                  # expect 505 passed
     python -m ruff check app/ tests/     # expect EXACTLY 37 — 38 is a regression
   If either is off, stop and report. 37 is pre-existing (32 E501, 4 F841, 1 B007, all in
   untouched modules). Parts 1–5 added zero new findings; hold that line.

6. GOAL: everything you need to know about a customer, on one page, without looking
   anywhere else. EXTEND the proven spine — app/modules/{customers,crm,sales} and
   /customers, /leads, /sales all exist and work. Do NOT rebuild them (G16).

   a. R8.1–R8.5 — profile depth: multiple contacts, multiple branches / ship-to addresses,
      credit limit + payment terms + delivery preferences that are VERSIONED so prior
      versions stay readable, documents through the EXISTING document module (R8.4 — there
      must be no second upload path), and notes. Contact/branch/document lists use Part 2's
      macros and Part 1's soft delete (R8.13).

   b. R8.6–R8.9 — credit limit enforced at sales-order confirm via CreditPolicyService.check.
      THE BLOCK MUST STATE THE NUMBERS: limit, current outstanding, this order's value, and
      the shortfall. A refusal the founder cannot act on is a bug, not a guard.
      The boundary is EXACT and needs its own test: AT the limit is allowed, ONE MINOR UNIT
      over is not. Money is integer minor units (G1), so this is an integer comparison —
      no float anywhere near it.

   c. R8.8 — an override is possible, REQUIRES a reason, is rejected without one, and writes
      EXACTLY ONE activity_log row recording who, when and by how much. Part 5's R7.4 did
      the same thing for stock adjustments; follow that shape — the schema requires a
      non-empty string AND the service refuses whitespace, because "   " passes a length
      check and tells a later reader nothing.

   d. R8.10/R8.11 — a unified customer timeline: orders, invoices, payments, tasks, notes
      and activity in ONE chronological view, assembled from activity_log + entity events as
      a READ-ONLY PROJECTION. **Do NOT add an events table to make this easier** — that is
      called out in the requirement itself. A customer with no history renders an empty
      timeline without erroring, and that needs a test.
      NOTE a hard-won detail from Part 5: a column defaulting to func.now() TIES for rows
      written in one transaction, so a timeline ordered on timestamp alone is
      non-deterministic. Add id as the tiebreaker — keys are UUID v7 and time-ordered.

   e. R8.12 SCOPE FENCE: health score, quotations and returns are PART 7's. If you find
      yourself designing the quotation screen, you have drifted — stop (G17).

7. Constraints that bind:
     - G5: exactly one activity_log row per state change, in the same transaction.
     - G7: derived, never stored. Outstanding balance and the timeline are projections.
     - G4: ledgers are append-only. A credit policy VERSION is a new row, never an edit.
     - G10: every new POST carries the R1.4 authz guard. tests/test_web_authz.py walks the
       whole POST surface and fails on an unguarded route, so this is enforced, not trusted.
     - Any new model owes app/db/references.py an entry, even an empty tuple (R3.7), and
       EXERCISE it with blocking_references(db, row) in a test. A Reference names its column
       by STRING, so a wrong one raises AttributeError at check time, not import time.
     - A new column on an EXISTING table needs an _ADDITIVE_COLUMNS entry in app/main.py
       (~line 45), or it is silently missing on every DB seeded earlier. Part 6 adds credit
       fields to `customer`, so this WILL apply.
     - status_class in web/core.py picks badge colour from a status STRING; one not in its
       positive/warning/negative sets renders GREY, silently. A new status needs a bucket.
   Seed (G14/R8.14): a customer with multiple contacts and ship-to branches, a credit limit,
   enough order/invoice/payment history for the timeline to be worth reading, ONE order that
   breaches the limit, and ONE recorded override. Add a NEW app/seed/<domain>.py plus one
   call in run() — never by appending logic into run() itself.

8. Work on main. No branches, no PRs, no tags. Commit at the end and push. Part 6 is ONE
   checkpoint: if you run low before it is done, commit what is GREEN, write the resume
   block, and stop rather than pushing on.

9. NAME EVERY NEW TEST AFTER THE REQUIREMENT IT PROVES —
   `def test_r8_9_one_minor_unit_over_the_credit_limit_is_blocked(...)`. A requirement's
   evidence is a test node id (`pytest -q -k r8_9`), NOT a paragraph. No per-requirement
   prose tables.

   MUTATION-CHECK the new suite once — break the implementation and confirm the tests go
   red. Every checkpoint in Parts 4 and 5 did this and it paid every time. Part 5 C3b's
   fourth mutation found something worth remembering: **an equality assertion between two
   code paths only tests what the current data distinguishes.** A no-op filter inserted into
   a delegation passed an "outputs are identical" test because the seeded data could not
   tell the difference. If a test compares two paths, ask what data would make them differ —
   and if none does, assert the structure instead. Good mutations here: shift the credit
   boundary by one minor unit, accept a blank override reason, and drop a source type from
   the timeline.

   If the checkpoint changed the SHAPE of anything, amend docs/CODEBASE-MAP.md in the same
   session. A stale map is worse than none.

10. CLOSING PART 6: write docs/parts/part-06.md, delete the Part 6 block from PROGRESS.md,
    and rewrite the NEXT SESSION PROMPT for PART 7 C1 (quotation — create/revise/send/
    expire/convert; §10's R9.x) with measured baseline counts. PROGRESS.md IS CAPPED AT
    ~350 LINES AND DOES NOT GROW — replace, never append.

Use pytest -q, never verbose. Don't re-read files you just edited.
```

**If a session has drifted** and you want a hard reset on scope, ignore the above and paste the whole
```-fenced PROMPT from `docs/prompts/part-06.md` instead. More deterministic, more typing.

**Rules of thumb.** One checkpoint per session — don't push a session past its checkpoint to "just
finish the part". Start each session fresh (`/clear` or a new window) rather than continuing a long
one. And if a session ends messy, the recovery is `git log --oneline -5` plus this block, not
re-reading the design docs.

---

## ▶ Handoff — Part 5 closed · Part 6 starts here

Part 5 (Inventory: locations, states, valuation, operations, health) is **COMPLETE** on `main`.
**Not tagged** — the user waived tags for Parts 5–7, so these SHAs are the record.

| Checkpoint | Commit | What landed |
|---|---|---|
| C1 | `437a185` | Locations (warehouse→rack→bin), four derived states, the reservation ledger |
| C2 | `b442322` | Weighted-average cost, stock ageing |
| C3a | `eaee67b` | Count sheets, mandatory reasons, two-step in-transit transfers |
| C3b | `4667a5e` | ABC, dead stock, fast/slow, low-stock alerts, reorder reading R5.9 |

**Verified at close:** **505 tests passing**, `ruff check app/ tests/` **exactly 37** — zero new
findings across the whole part. Fresh seed + uvicorn: every nav page 200s, all four health sections
render with their thresholds stated, the count sheet walks open → record → close over HTTP, a bad id
renders `error.html` at 404.

**Every R6.x and R7.x passes.** The requirement-by-requirement evidence, the seventeen decisions the
part made, and the four mutation rounds are in **`docs/parts/part-05.md`**. **Do not read it.**
Everything Part 6 needs is below.

### Three things Part 6 inherits and must not break

1. **The reservation verb is Part 7's, and it already exists.** `ReservationService.reserve /
   release / consume` (R6.6). Part 7's R9.8 calls it at sales-order confirm — **Part 6 must not add
   a stock flag or a second mechanism** while working on that same confirm path, and should leave the
   method easy for Part 7 to hook.
2. **G11 has exactly one implementation.** Build an `Explained` (`app/db/explain.py`) and render it
   with the `explain_panel` macro. Part 7's health score is a new *output*, not a new shape. If Part 6
   shows a computed number (an outstanding total, a credit position), it renders through that panel.
3. **An equality test between two code paths only tests what the data distinguishes.** Part 5 C3b
   proved it: a no-op filter inserted into a delegation passed an "identical output" assertion.
   Where two paths must agree, ask what data would separate them — and if nothing would, assert the
   structure.

### Read for Part 6 — these and nothing else

- `docs/REQUIREMENTS.md` §9 (R8.x) — the whole acceptance contract. §1 for the invariants.
- `docs/prompts/part-06.md` — the brief, self-contained. Binding rules: `docs/STANDING-RULES.md`.
- `docs/08-module-breakdown.md` §2.4 (Customers/CRM) and §2.7 (Sales).
- **The edit set:** `app/modules/customers/{models,repository,service,schemas}.py` · a credit policy
  service (`CreditPolicyService.check` is what R8.6 names) · `app/modules/sales/service.py` for the
  confirm-time check · `app/web/pages/customers.py` + its templates · `app/main.py`'s
  `_ADDITIVE_COLUMNS` for the new `customer` columns · `app/db/references.py` for every new model ·
  a NEW `app/seed/customers.py` plus one call in `run()` · `tests/` — a new file per flow, following
  `tests/test_inventory_operations.py`.
- **Documents attach through the existing module** (R8.4). There is one upload path already; find it
  before writing anything that stores a file.

### Call, don't read — verified signatures, copied from source at Part 5 close

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

# THE VERB PART 7's R9.8/R9.9 CALLS. Part 6 must not add a second mechanism.
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
#   Row-locked per (BU, doc_type, period). In use: PO GRN BILL REQ RFQ QUO SO INV TRF CNT.
```

Part 2's machinery still holds unchanged: `ListSpec` + `view_from_request` (list pages),
`ensure_unreferenced` / `soft_delete` / `ensure_unique`, `ActivityService.history`, and the
`page_header` / `stat` / `badge` / `list_*` / `history_panel` / `explain_panel` macros.

### Gotchas that will bite Part 6

- **`create_all` builds new TABLES but never ALTERs an existing one.** A new column on `customer`,
  `sales_order` … needs an `_ADDITIVE_COLUMNS` entry in `app/main.py` (~line 45) or it is silently
  missing on every DB seeded earlier, including the dev `apexos.db` carried since Part 1. Get the DDL
  from what `create_all` emits (`CreateTable(...).compile(sqlite)`), don't guess:
  `DateTime(timezone=True)` → `DATETIME`, `Uuid()` → `CHAR(32)`, `Numeric(18,4)` → `NUMERIC(18, 4)`.
  Part 5 verified this path against a pre-Part-5 copy of the dev database; the shim works.
- **A column default of `func.now()` TIES.** Rows written in one transaction share a timestamp, so
  `ORDER BY occurred_at` alone is non-deterministic and a test reading "the newest row" fails
  intermittently. Add `id` as the tiebreaker — UUID v7 keys are time-ordered. **This matters directly
  for R8.10's chronological timeline.** (`InventoryRepository.movements()` still has this latent tie —
  pre-existing, left alone.)
- **A test can pass without testing anything.** Assert a **floor** on anything you enumerate
  (`assert len(found) > 40`), and mutation-check once. See "Three things Part 6 inherits" #3.
- **Assert on HTML phrases that do NOT straddle a template line break** — cost two runs in Part 5.
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

`app/seed/core.py` (720 lines — read `app/seed/__init__.py`'s docstring, and `app/seed/inventory.py`
as the pattern for a new section) · `app/modules/procurement/preorder.py` (814 lines) ·
`app/modules/suppliers/vendor.py` · `app/modules/inventory/{valuation,health}.py` (Part 5 finished
them; their signatures are above) · `tests/test_preorder.py`, `test_po_revisions.py`,
`test_vendor_intel.py`, `test_vendor_screens.py`, `test_procurement_planning.py`,
`tests/test_inventory_*.py` (they pass; read one only if you change what it covers) · anything in
`docs/parts/` · `docs/ROADMAP.md` (~17k tokens, planning only) · the older `docs/` design files,
`docs/DELETION-POLICY.md` and `docs/MIGRATION-STRATEGY.md` — Part 1 resolved those.

Note `docs/REQUIREMENTS.md` is at v1.2: the stock writer is `InventoryService.record_movement`, and any
older doc naming `post_movement` is wrong.

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
largest avoidable cost in the build.

Where things live now:

- **Setup / how to run** → `RUNNING.md`. Do not restate it here.
- **Closed part records** → `docs/parts/`. Never read during a session; they exist for audit.
- **Resume-block template** → `docs/parts/_resume-block-template.md`.
- **Per-part prompt** → `docs/prompts/part-NN.md` (one file, self-contained).
- **Standing rules, session protocol, checkpoint table, reading diet, verify loop** → `docs/STANDING-RULES.md`.
- **Sequence, dependencies, prompt index** → `docs/ROADMAP.md`. Planning only — a session does not read it.
- **What exists and where** → `docs/CODEBASE-MAP.md`.

---

# ▶ CURRENT WORK — read this first

A **session** is a token budget; a **part** is a group of sessions. The checkpoint list per part is in
`docs/STANDING-RULES.md` → *Session protocol*.

**All work is on `main`** — no feature branches, no PRs. A part is "done" when every P0/P1 requirement
passes, the verify loop is green, this file is updated, and the part is tagged `part-0N-done`. Those
tags are the rollback points.

**Every session ends by updating the block below, before it runs out of room.** A session that dies
with an accurate resume block costs nothing; one that dies without it costs a re-derivation.

### ▶ How to start the next session

Open a fresh Claude Code session in your clone of the repo and type:

```
Start next part of development
```

That's the whole thing. `CLAUDE.md` at the repo root binds that phrase to "read the **▶ NEXT SESSION
PROMPT** below and follow it," so the state lives here in one maintained place rather than in whatever
you remember to type. Nothing to look up, nothing to keep in your head.

**The session that closes a checkpoint owns this prompt.** Updating it is part of the same duty as
updating the resume block — a starter that still names last part's baseline counts and edit set is worse
than none, because the next session will trust it. Keep it short: the binding lists live in the handoff
block, and the prompt's job is to point at them and name the numbers.

#### ▶ NEXT SESSION PROMPT — Part 5, checkpoint C1 (locations + stock states + reservation)

```
Continue the ApexOS build. Do this in order:

1. git checkout main && git pull origin main && git fetch origin --tags
   (tags don't come down with a plain pull, and the delta command below needs part-04-done)
   Then git status — one writer per working tree. If it is dirty, stop and report.

2. Read the "▶ CURRENT WORK" block at the top of PROGRESS.md, and in particular the
   "▶ Part 5 starts here" section. Part 4 is CLOSED and tagged part-04-done; nothing
   from it is outstanding. That section is your brief: it names the edit set, carries
   verified signatures for the services you will call without opening, and its
   "Do NOT read" list is binding.

3. Read docs/REQUIREMENTS.md §1 (global invariants G1–G17) and §7 + §8 (R6.x and R7.x —
   Part 5's acceptance contract; §8 is group B of the same part). NOT optional: the
   invariants you must not break — integer minor units, exactly one activity_log row per
   state change, derived-never-stored, append-only ledgers, and
   InventoryService.record_movement as the ONLY writer of stock_movement — are not in the
   files you are editing.
   Then docs/prompts/part-05.md (the full part brief, ~80 lines, self-contained) and
   docs/STANDING-RULES.md (binding: decisions D-A..D-D, session protocol, reading diet,
   verify loop). Do NOT open docs/ROADMAP.md — it is planning only and costs ~17k tokens.

4. `git diff part-04-done..HEAD --stat` for anything since the tag (should be nothing),
   and `git show --stat part-04-done` for what Part 4 changed. Not a tree walk —
   docs/CODEBASE-MAP.md is the orientation document and it was updated at Part 4 close.

5. Verify the baseline before writing code (from apps/api, venv activated):
     python -m pytest -q                  # expect 402 passed
     python -m ruff check app/ tests/     # expect EXACTLY 37 findings — 38 is a regression
   If either is off, stop and report. 37 is the pre-existing count (32 E501, 4 F841,
   1 B007, all in modules the current work has not touched). Parts 1–4 added zero.

6. READ DECISION D-A BEFORE DESIGNING ANYTHING. It cuts about a third of this part:
   NO batch/lot tracking, NO expiry, NO FIFO layers. Cost basis is a simple WEIGHTED
   AVERAGE from movement history (R6.16), needed only for the on-hand VALUE figure.
   R6.7/R6.8/R6.9 are struck. Building any of them means the session has drifted (G17).

7. C1 IS THE CHECKPOINT THAT MATTERS. Part 7 calls the reservation verb at sales-order
   confirm, so a wrong model here forces rework there. Do not rush C1 to reach C2. In
   order:

   a. R6.1/R6.2/R6.11 — locations: warehouse → rack → bin, stock addressed to a bin,
      the location carried on stock_movement, and bin totals rolling up to rack and
      warehouse. New columns on an EXISTING table need an `_ADDITIVE_COLUMNS` entry in
      app/main.py (~line 45) — `create_all` builds new tables but never ALTERs one, so
      without it the column is silently missing on every DB seeded earlier.

   b. R6.3 — existing movements have no location. DECIDE: backfill to a default bin per
      warehouse, or nullable with a documented meaning. Either is acceptable; leaving it
      undecided is not, and R6.3 requires the choice to be written into this file.

   c. R6.5/R6.6 — RESERVATION IS A LEDGER CONCEPT, NOT A FLAG. An append-only entry that
      reduces available without reducing on-hand, released or consumed by a later entry.
      There must be NO boolean "reserved" column, and a test must assert that. Expose it
      as one clear service verb for Part 7 to call (R9.8 calls it) — same discipline as
      R5.9's single recommendation entry point.

   d. R6.4/R6.12 — the four states reported distinctly (available / reserved / in transit
      / damaged-quarantined) on /inventory and /warehouse, through Part 2's macros.

8. Constraints that still bind:
     - G8: InventoryService.record_movement stays the ONLY writer of stock_movement. A
       reservation entry that bypasses it breaks the one invariant Part 5 is built on.
     - G7: balances stay DERIVED. No stored mutable quantity, including "available".
     - Every new model owes app/db/references.py an entry, even an empty tuple (R3.7),
       and EXERCISE it with `blocking_references(db, row)` in a test. A Reference names
       its column by STRING, so a wrong one raises AttributeError at check time, not
       import time — that bug hid in the warehouse entry for five checkpoints.
     - G11 is P0 on every number C3's health views show. Part 4 built the one shape for
       that: build an `Explained` (app/db/explain.py) and render it with the
       `explain_panel` macro. Do NOT write per-screen explanation markup.
     - R6.10's ageing is APPROXIMATE without lots — say so on screen, do not imply
       precision.
   Seed (G14/R6.14): add app/seed/inventory.py (or extend nothing — never append to
   core.py's run()). Two warehouses with racks and bins, a reservation against a
   confirmed sales order, an in-transit transfer awaiting receipt, and enough movement
   history for weighted-average cost to be non-trivial. NO batches, NO expiry dates.

9. Work on main. No branches, no PRs. Commit at the END OF C1 — one checkpoint per
   session, and do not push into C2 to "finish the part". Part 5 has THREE checkpoints:
     C1 locations + stock states + reservation as a ledger concept
     C2 weighted-average cost + stock ageing
     C3 operations (count/adjust/transfer) + health (ABC, dead stock, reorder reading R5.9)
   Only C3 tags the part.

10. BEFORE you run low on context, update the "▶ CURRENT WORK" block: checkpoints with
    commit SHAs, requirement IDs passed and outstanding, gotchas, mid-part decisions
    (R6.3's location choice belongs there), and the four delta lines — Changed since /
    Read for the next checkpoint / Call, don't read (copy signatures from source, never
    from memory) / Do NOT read. Then rewrite the "▶ NEXT SESSION PROMPT" above for C2,
    with its baseline counts. Then commit and push. If the checkpoint changed the SHAPE
    of anything, amend docs/CODEBASE-MAP.md in the same session. A stale map is worse
    than none.

    PROGRESS.md IS CAPPED AT ~350 LINES AND DOES NOT GROW. Replace the block; never
    append a new one below the old.

    NAME EVERY NEW TEST AFTER THE REQUIREMENT IT PROVES —
    `def test_r6_5_a_reservation_reduces_available_without_reducing_on_hand(...)`. Then a
    requirement's evidence is `pytest -q -k r6_5`, a test node id, NOT a paragraph. Do
    not write per-requirement prose tables. See the naming rule in docs/STANDING-RULES.md.

    A suite that passes first try is not evidence. MUTATION-CHECK the new one once:
    break the implementation deliberately and confirm the tests go red. Part 4 C2 did
    this — dropping the open-order subtraction failed 5 of 27, counting drafts failed 1.
    If breaking the code doesn't break a test, the test is decoration.

Use pytest -q, never verbose. Don't re-read files you just edited.
```

**If a session has drifted** and you want a hard reset on scope, ignore the above and paste the whole
```-fenced PROMPT from `docs/prompts/part-05.md` instead. More deterministic, more typing.

**Rules of thumb.** One checkpoint per session — don't push a session past its checkpoint to "just
finish the part". Start each session fresh (`/clear` or a new window) rather than continuing a long
one. And if a session ends messy, the recovery is `git log --oneline -5` plus this block, not
re-reading the design docs.

---

## ▶ Handoff — Part 4 closed · Part 5 starts here

Part 4 (Procurement: vendor intelligence + planning) is **COMPLETE**, on `main`, tagged `part-04-done`.

| Checkpoint | Commit | What landed |
|---|---|---|
| C1 engine | `cf552e3` | Mapping + MOQ, measured lead time, on-time rate, 60/40 score, price history, `app/db/explain.py` |
| C1 screens | `c98548a` | The `explain_panel` macro, R5.12's pages, the mapping POST verbs, score + MOQ in R4.5's grid |
| C2 | `6381ecd` | `procurement/recommend.py` — R5.9's entry point, R5.8's recommendations, R5.7's calendar |

**Verified at close:** **402 tests passing**, `ruff check app/ tests/` **exactly 37** — zero new findings
across the whole part. Fresh `python -m app.seed` + uvicorn: every nav page 200s, a bad id renders
`error.html`, and `/procurement` shows both seeded reorder cases with their arithmetic.

**Every R5.x passes.** The requirement-by-requirement evidence (a `-k` expression per R-number), the
eleven decisions the part made, and the gotchas it hit are in **`docs/parts/part-04.md`**. **Do not read
it.** Everything Part 5 needs is below.

### Three things Part 5 inherits and must not break

1. **R7.11 + R7.13 are a live contract.** C3's reorder suggestions **call**
   `RecommendationService(db).recommend(...)` — they do not reimplement it — and R7.13 requires a test
   proving both return identical output for the same product. Part 4 left a source walk
   (`test_r5_9_no_second_implementation_of_what_to_buy_exists_in_the_app`) that greps `app/` and **fails
   if a second `def recommend` appears**, including one Part 5 adds. If the two genuinely differ,
   parameterise the one engine and record the unification here.
2. **G11 has exactly one implementation, and it already exists.** Build an `Explained`
   (`app/db/explain.py`) and render it with the `explain_panel` macro. R13.1 had scheduled this
   unification for Part 10; it is done. Inventory health, ABC, dead stock and low-stock alerts are new
   *outputs*, not new shapes.
3. **G8 and G7.** `InventoryService.record_movement` stays the only writer of `stock_movement`, and
   "available" is derived from the ledger — a reservation is an append-only entry, never a column.

### Read for the next checkpoint (Part 5 C1) — these and nothing else

- `docs/REQUIREMENTS.md` §7 (R6.x) and §8 (R7.x) — the acceptance contract. §1 for the invariants.
- `docs/prompts/part-05.md` — the whole brief, self-contained. Binding rules: `docs/STANDING-RULES.md`.
- `docs/08-module-breakdown.md` § Inventory/Warehouse.
- **The edit set for C1:** `app/modules/inventory/{models,repository,service,schemas}.py` ·
  `app/modules/config/models.py` (`Warehouse` lives here — rack/bin go beside it or in the inventory
  module; decide and say which) · `app/main.py`'s `_ADDITIVE_COLUMNS` for the new
  `stock_movement` column · `app/db/references.py` for every new model · `app/web/pages/{inventory,warehouse}.py`
  + their templates · a NEW `app/seed/inventory.py` plus one call in `run()` · `tests/` — a new file per
  flow, following `tests/test_procurement_planning.py`.

### Call, don't read — verified signatures, copied from source at Part 4 close

```python
# app/modules/inventory/service.py — the ONLY writer of stock_movement (G8)
InventoryService(db).record_movement(*, product_id, warehouse_id, qty_delta: Decimal, reason: str,
    ref_type=None, ref_id=None, unit_cost_minor=None, actor_id=None) -> StockMovement
#   All keyword-only. NOT `post_movement` — that name never existed.
InventoryService(db).on_hand(product_id, warehouse_id=None) -> Decimal   # summed from the ledger
InventoryService(db).stock() -> list[StockRow] · .warehouse_stock(warehouse_id=None)
InventoryService(db).low_stock() · .low_stock_count() · .movements(product_id=None)
StockTransferService(db).transfer(payload, *, actor_id) -> StockTransferResult
StockAdjustmentService(db).adjust(payload, *, actor_id) -> StockAdjustmentResult
StockAdjustmentService(db).count(payload, *, actor_id) -> StockAdjustmentResult
#   These three EXIST and each writes one activity row. R7.1–R7.5 EXTEND them (in-transit state,
#   mandatory reason, count sheet → variance) — they do not replace them.
InventoryRepository(db).balances() -> list[(product_id, warehouse_id, qty)]   # grouped, one query
InventoryRepository(db).stock_rows() -> list[tuple]   # + sku/name/warehouse/reorder_level

# app/modules/procurement/recommend.py — R5.9's ONE entry point. R7.11 CALLS this.
RecommendationService(db).recommend(*, product_id=None, limit=None) -> list[Recommendation]
#   Recommendation(.product_id .sku_code .product_name .qty .on_hand .reorder_level .on_order
#                  .shortfall .supplier_id .supplier_name .moq .lead_time .explained)
#   .sentence -> R5.8's plain-language line. Worst shortfall first. [] means nothing to buy.
#   qty = reorder_level − on_hand − on_order, raised to the preferred supplier's MOQ if one is agreed.
ProcurementCalendarService(db).calendar(*, limit=25) -> ProcurementCalendar
#   .as_of .arrivals .recommendations .recommendation_total · .arrivals_in(bucket)
#   Arrival(.po_no .purchase_order_id .supplier_name .status .expected_date .open_qty)
#     .bucket -> overdue|today|this_week|later|unpromised   .days_away -> int | None
OPEN_PO_STATUSES = ("confirmed", "partially_received")   # NOT references.open_po — that includes draft
ARRIVAL_BUCKETS   # ((key, label), …) in reading order

# app/db/explain.py — the ONE shape for every explained number (G11)
Explained(what, value: str | None, formula, window, inputs=(), records=(),
          unknown_reason=None, caveat=None)
#   .is_known -> value is not None      .display -> value or "unknown"
Explained.unknown(*, what, formula, reason, window="no data", inputs=(), records=())
Input(label, value, weight=None, missing_reason=None)   # .is_missing
SourceRecord(label, href=None)
# Rendered by ONE macro:  {{ ui.explain_panel(explained, "Optional title") }}

# app/modules/suppliers/vendor.py — reads only, writes nothing (G15)
VendorIntelService(db).lead_time(supplier_id) / .on_time_rate(...) / .score(...) -> Explained
VendorIntelService(db).price_history(product_id) -> list[PriceHistoryRow]   # oldest first
VendorIntelService(db).receipts(supplier_id) -> list[Receipt]               # newest first

# app/modules/suppliers/service.py — the product↔supplier mapping
ProductSupplierService(db).preferred_supplier_id(product_id) -> uuid.UUID | None
ProductSupplierService(db).moq(product_id, supplier_id) -> Decimal | None
ProductSupplierService(db).list_for_product(product_id) -> list[ProductSupplierRead]
#   preferred first. Each row's .score/.lead_time/.on_time_rate are RENDERED strings that may
#   literally read "unknown" — print them, never format them as numbers.

# app/modules/procurement/service.py
PurchaseOrderService.open_qty(line) -> Decimal   # STATICMETHOD. THE definition of open (R4.9/G7).
PurchaseOrderService(db).create/confirm/revise/bill · GoodsReceiptService(db).receive(...)
default_business_unit(db) · tax_bps_for(db, product) · _round_minor(value) · _qty_text(value)
#   _qty_text gives "40", not "40.0000" — for SERVICE messages. Screens use the `number` filter.

# app/modules/config/service.py
allocate_document_number(db, *, doc_type, business_unit_id, on_date) -> "GRN-202607-00001"
#   Row-locked per (BU, doc_type, period). Types in use: PO, GRN, BILL, REQ, RFQ, QUO, SO, INV.
```

Part 2's machinery still holds unchanged: `ListSpec` + `view_from_request` (list pages),
`ensure_unreferenced` / `soft_delete` / `ensure_unique`, `ActivityService.history`, and the
`page_header` / `stat` / `badge` / `list_*` / `history_panel` / `explain_panel` macros.

### Gotchas that will bite Part 5

- **`create_all` builds new TABLES but never ALTERs an existing one.** A new column on
  `stock_movement`, `warehouse`, `product` … needs an `_ADDITIVE_COLUMNS` entry in `app/main.py`
  (~line 45) or it is silently missing on every DB seeded earlier, including the dev `apexos.db`
  carried since Part 1. Get the DDL from what `create_all` emits
  (`CreateTable(...).compile(sqlite)`), don't guess: `DateTime(timezone=True)` → `DATETIME`,
  `Uuid()` → `CHAR(32)`, `Numeric(18,4)` → `NUMERIC(18, 4)`.
- **`Decimal` from `Numeric(18, 4)` reads back at full scale.** `40.0000` is right for arithmetic and
  wrong in a sentence. Screens have the `number` filter; a service message uses `_qty_text`. Plain
  `.normalize()` is a trap — it turns 40 into `4E+1`.
- **A test can pass without testing anything.** Assert a **floor** on anything you enumerate
  (`assert len(found) > 40`) and mutation-check a new suite once.
- **`db.get(Product, id)` in a loop is fine; a `select()` per row is not.** SQLAlchemy's identity map
  makes repeat gets free within a session. A projector that runs a *query* per row is the thing to
  avoid — Part 4's engine covers all 311 products in two queries for exactly this reason.
- **`status_class` in `web/core.py` decides badge colour from a status *string*.** A status not in its
  positive/warning/negative sets renders grey, silently. **A new stock state needs a bucket**, or the
  screen stops telling the founder anything.
- **A list page with a bulk-entry form has TWO `<tbody>`s**, so `html.count("<tbody>") == 1` is wrong
  on those pages. Assert markers only the shared macros emit, and read the row total from the
  paginator (`Showing 1–25 of N`), not by counting `<tr>`.
- **`APEXOS_DATABASE_URL` is NOT the env var.** It is `DATABASE_URL`. Seeding with the wrong name
  silently writes to the real `apexos.db` and you will "verify" against stale data. Point the seed and
  uvicorn at the same fresh file: `$env:DATABASE_URL="sqlite:///./fresh.db"`.
- **A scratch `.db` cannot be deleted while uvicorn holds it** (Windows: *device or resource busy*).
  Stop the process first — `pkill` does not exist here; use `Get-CimInstance Win32_Process | Where
  CommandLine -like '*<port>*' | Stop-Process -Force`. Port 8000 may be occupied; Part 4 used 8016.
- **`$pid` is a read-only PowerShell automatic variable** — a scratch script that assigns it dies.
- **`uuid.UUID` in a Pydantic response model serialises to a string**, so an API test comparing an id
  from JSON must compare against `str(row.id)`.
- **A frozen dataclass inside a Pydantic model works** (Pydantic v2 validates stdlib dataclasses), but
  its `@property` values do **not** appear in the JSON. `Explained.display` is a property; the API
  exposes `value` and `unknown_reason`.

### Do NOT read

`app/seed/core.py` (707 lines — read `app/seed/__init__.py`'s docstring, and `app/seed/vendor.py` as
the pattern for a new section) · `app/modules/procurement/preorder.py` (814 lines — Part 3 and 4
finished it; the two functions Part 5 might want are in "Call, don't read") ·
`app/modules/suppliers/vendor.py` (465 lines — same) · `tests/test_preorder.py`,
`tests/test_po_revisions.py`, `tests/test_vendor_intel.py`, `tests/test_vendor_screens.py`,
`tests/test_procurement_planning.py` (they pass; read one only if you change what it covers) ·
anything in `docs/parts/` · `docs/ROADMAP.md` (~17k tokens, planning only) · the older `docs/` design
files, `docs/DELETION-POLICY.md` and `docs/MIGRATION-STRATEGY.md` — Part 1 resolved those.

Note `docs/REQUIREMENTS.md` is at v1.2: the stock writer is `InventoryService.record_movement`, and any
older doc naming `post_movement` is wrong.

---

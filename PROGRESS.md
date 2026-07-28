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

Where everything else lives is in `CLAUDE.md` — setup in `RUNNING.md`, closed parts in `docs/parts/`,
per-part prompts in `docs/prompts/part-NN.md`, the binding rules in `docs/STANDING-RULES.md`, the
layout in `docs/CODEBASE-MAP.md`, and `docs/ROADMAP.md` which a session does not read.

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

#### ▶ NEXT SESSION PROMPT — Part 5, checkpoint C2 (weighted-average cost + stock ageing)

```
Continue the ApexOS build. Do this in order:

1. git checkout main && git pull origin main
   Then git status — one writer per working tree. If it is dirty, stop and report.
   NOTE: this run is NOT tagging parts (the user waived tags for Parts 5–7). The
   checkpoint SHA table in the "▶ Part 5 — IN FLIGHT" block below is the only record
   of where each part began, so keep it accurate. Do not expect part-05-done to exist.

2. Read the "▶ CURRENT WORK" block at the top of PROGRESS.md, and in particular the
   "▶ Part 5 — IN FLIGHT" section. C1 IS DONE AND GREEN (437a185). That section is
   your brief: it names what C1 decided (do not reverse those), carries verified
   signatures for the services you will call without opening, and its "Do NOT read"
   list is binding.

3. Read docs/REQUIREMENTS.md §1 (global invariants G1–G17) and §7 + §8 (R6.x and R7.x —
   Part 5's acceptance contract). NOT optional: the invariants you must not break —
   integer minor units, exactly one activity_log row per state change,
   derived-never-stored, append-only ledgers, and InventoryService.record_movement as
   the ONLY writer of stock_movement — are not in the files you are editing.
   Then docs/prompts/part-05.md (the full part brief, ~80 lines, self-contained) and
   docs/STANDING-RULES.md (binding: decisions D-A..D-D, session protocol, reading diet,
   verify loop). Do NOT open docs/ROADMAP.md — it is planning only and costs ~17k tokens.

4. `git show --stat 437a185` for what C1 changed. Not a tree walk.

5. Verify the baseline before writing code (from apps/api, venv activated):
     python -m pytest -q                  # expect 435 passed
     python -m ruff check app/ tests/     # expect EXACTLY 37 findings — 38 is a regression
   If either is off, stop and report. 37 is the pre-existing count (32 E501, 4 F841,
   1 B007, all in modules the current work has not touched). Parts 1–5 C1 added zero.

6. READ DECISION D-A BEFORE DESIGNING ANYTHING — it is the whole shape of C2:
   NO batch/lot tracking, NO expiry, NO FIFO layers. R6.7/R6.8/R6.9 are STRUCK.
   Cost basis is a simple WEIGHTED AVERAGE from movement history (R6.16), and it is
   needed ONLY for the on-hand VALUE figure. MARGIN MUST NOT DEPEND ON IT — MarginService
   is selling − the purchase price snapshotted onto the line (R11.6). Building a FIFO
   layer, or routing margin through valuation, means the session has drifted (G17).

7. C2 is two things. In order:

   a. R6.16 — weighted-average cost from movement history, feeding an on-hand VALUE
      figure. Money is integer minor units (G1); stock_movement.unit_cost_minor is
      already populated by every inbound path, so the input exists — read it, do not
      add a cost column. Test against HAND-COMPUTED values, not against whatever the
      code returns. Round with the one money rounding step, not a second one.

   b. R6.10 — stock age buckets derived from receipt dates on the ledger, with a
      BOUNDARY test. Without lots this is APPROXIMATE: an item's age is inferred from
      inbound movements, and a partially consumed balance cannot be attributed to a
      specific receipt. SAY SO ON SCREEN rather than implying precision — that
      statement is part of R6.10's acceptance, not a nicety. It survives D-A only
      because R7.8's dead-stock radar consumes it, so shape it for that consumer.

   c. R6.12 — /inventory and /warehouse gain the ageing view, using the Part 2 macros.
      C1 already added the stock-by-location view there; extend those pages, do not
      add new ones.

8. Constraints that still bind:
     - G7: nothing is stored. Cost, value and age are all DERIVED per read.
     - G8: InventoryService.record_movement stays the ONLY writer of stock_movement.
       There is a source-walk test that fails if anything else constructs one.
     - G1: money is integer minor units end to end. No float touches a money path.
     - Every new model owes app/db/references.py an entry, even an empty tuple (R3.7),
       and EXERCISE it with `blocking_references(db, row)` in a test. C2 may well add
       no model at all — if so, that is the correct outcome, not a gap.
     - A new column on an EXISTING table needs an `_ADDITIVE_COLUMNS` entry in
       app/main.py (~line 45) or it is silently missing on every DB seeded earlier.
   Seed (G14): app/seed/inventory.py exists and is C1's. If C2 needs more movement
   history for the weighted average to be non-trivial, add it THERE — never by
   appending logic into core.py's run().

9. Work on main. No branches, no PRs. Commit at the END OF C2 and push. Do not push on
   into C3 to "finish the part". Part 5's remaining checkpoints:
     C2 weighted-average cost + stock ageing            <- YOU ARE HERE
     C3 operations (count/adjust/transfer) + health (ABC, dead stock, reorder reading R5.9)
   No tags this run.

10. BEFORE you run low on context, update the "▶ CURRENT WORK" block: the checkpoint
    SHA table, requirement IDs passed and outstanding, gotchas, mid-part decisions, and
    the four delta lines — Changed since / Read for the next checkpoint / Call, don't
    read (copy signatures FROM SOURCE, never from memory) / Do NOT read. Then rewrite
    the "▶ NEXT SESSION PROMPT" above for C3, with its measured baseline counts. Then
    commit and push. If the checkpoint changed the SHAPE of anything, amend
    docs/CODEBASE-MAP.md in the same session. A stale map is worse than none.

    PROGRESS.md IS CAPPED AT ~350 LINES AND DOES NOT GROW. Replace the block; never
    append a new one below the old.

    NAME EVERY NEW TEST AFTER THE REQUIREMENT IT PROVES —
    `def test_r6_16_weighted_average_cost_matches_a_hand_computed_figure(...)`. Then a
    requirement's evidence is `pytest -q -k r6_16`, a test node id, NOT a paragraph. Do
    not write per-requirement prose tables. See the naming rule in docs/STANDING-RULES.md.

    A suite that passes first try is not evidence. MUTATION-CHECK the new one once:
    break the implementation deliberately and confirm the tests go red. C1 did this and
    learned its release test could not catch a broken `available` — one mutation, one
    real gap found and closed. If breaking the code doesn't break a test, the test is
    decoration.

Use pytest -q, never verbose. Don't re-read files you just edited.
```

**If a session has drifted** and you want a hard reset on scope, ignore the above and paste the whole
```-fenced PROMPT from `docs/prompts/part-05.md` instead. More deterministic, more typing.

**Rules of thumb.** One checkpoint per session — don't push a session past its checkpoint to "just
finish the part". Start each session fresh (`/clear` or a new window) rather than continuing a long
one. And if a session ends messy, the recovery is `git log --oneline -5` plus this block, not
re-reading the design docs.

---

## ▶ Part 5 — IN FLIGHT · C1 done, C2 and C3 outstanding

Part 4 is closed; its record is in **`docs/parts/part-04.md`** — **do not read it.** Everything Part 5
needs is below.

**This run does not create tags** (the user waived them for Parts 5–7). The table below is therefore
the only record of where each checkpoint landed — the thing `part-0N-done` would normally be.

| Checkpoint | Commit | What landed |
|---|---|---|
| Part 4 C1 engine | `cf552e3` | Vendor score, measured lead time, on-time rate, price history, `explain.py` |
| Part 4 C1 screens | `c98548a` | The `explain_panel` macro, R5.12's pages, score + MOQ in R4.5's grid |
| Part 4 C2 | `6381ecd` | `procurement/recommend.py` — R5.9's entry point, R5.8, R5.7's calendar |
| Part 4 close | `64ae50f` | Archived to `docs/parts/part-04.md`; tagged `part-04-done` |
| **Part 5 C1** | **`437a185`** | **Locations, four derived states, the reservation ledger** |

**Verified at C1:** **435 tests passing** (402 + 33 new), `ruff check app/ tests/` **exactly 37** —
zero new findings. Fresh `python -m app.seed` + uvicorn on 8015: `/inventory` renders all four states,
the location rollup and the unaddressed-stock note; `/warehouse` renders the full rack/bin tree
including the empty transit and quarantine bins, plus both maintenance forms; every nav page 200s; a
bad id renders `error.html` at 404.

| R | State | Where |
|---|---|---|
| R6.1 | ✅ warehouse → rack → bin, codes unique within parent, kinds validated | `StorageRack` / `StorageBin`, `LocationService` |
| R6.2 | ✅ `stock_movement.bin_id` | `record_movement(bin_id=…)` |
| R6.3 | ✅ **nullable, not backfilled** — decision below | `_ADDITIVE_COLUMNS["stock_movement"]` |
| R6.4 | ✅ four states, all derived | `InventoryService.states()` |
| R6.5 R6.6 | ✅ append-only ledger + one verb trio | `StockReservation`, `ReservationService` |
| R6.11 | ✅ bin → rack → warehouse | `InventoryService.location_rollup()` |
| R6.12 | ⚠️ stock-by-location done; **ageing view is C2's** | `/inventory`, `/warehouse` |
| R6.14 | ⚠️ racks/bins/putaway/reservation done; **in-transit transfer + counts are C3's, cost history C2's** | `app/seed/inventory.py` |
| R6.15 R3.7 | ✅ incl. the G8 source walk and exercised references | `tests/test_inventory_locations.py` |
| **R6.10 R6.16** | ❌ **not started — all of C2** | — |
| **R7.1–R7.14** | ❌ **not started — all of C3** | — |

Evidence is `pytest -q -k r6_` (33 tests). Two new files: `tests/test_inventory_locations.py` (25) and
`tests/test_inventory_screens.py` (8).

### Five decisions C1 made that a later checkpoint must not reverse

1. **`stock_movement.bin_id` is NULLABLE and NULL means "at this warehouse, bin not recorded"
   (R6.3).** This is not a preference — backfilling a bin onto the ~400 movements that predate Part 5
   would **UPDATE an append-only ledger, which G4 forbids**, and would invent a physical fact nobody
   recorded. Both screens show the unaddressed balance rather than hiding it. A test pins the
   nullability so it cannot be quietly reversed.
2. **Rack and bin live in `app/modules/inventory/models.py`, not `config/models.py`.** `Warehouse`
   stays a config master that `/warehouse` maintains; racks and bins exist solely to address stock and
   the inventory module is their only reader and writer.
3. **R6.4's four states are derived from two ledgers plus `StorageBin.kind`** (`stock` / `transit` /
   `quarantine`). No state column exists, and a test asserts none appears. **This is the mechanism C3's
   R7.5 two-step transfer should use:** OUT of a stock bin, IN to a transit bin, then transit → the
   destination's stock bin. Do not add an in-transit flag; the bin kind already carries it.
4. **`/warehouse` shows the whole location tree; `/inventory` shows only where stock IS.** An empty
   quarantine bin appears on `/warehouse` (you must see it to use it) and not in `/inventory`'s
   rollup (it has nothing to roll up). Deliberate, not an oversight.
5. **The seed's putaway is a NET-ZERO PAIR of movements**, out of the unaddressed pool and into a bin.
   It changes an address, never a quantity, and a test asserts `SUM(qty_delta) WHERE reason='PUTAWAY'`
   is exactly 0. A later section that "fixes" it by writing only the inbound half inflates on-hand
   across the whole catalogue.

### Two things C1 changed outside the inventory module

- **`_qty_text` moved to `app.core.money.qty_text`.** Inventory needs it for its refusal messages and
  **cannot import procurement** — procurement imports `InventoryService`, so it would be circular. A
  second copy would be a second implementation of one rule (G16). `procurement/service.py` re-exports
  it under the old name, so its ~15 call sites and `recommend.py`'s import are unchanged.
- **`reservation_entries` orders by `(occurred_at, id)`.** `occurred_at` defaults to `func.now()`, so
  every entry written inside one transaction ties and `ORDER BY occurred_at` alone left the order to
  the planner. Keys are UUID v7 and therefore time-ordered, so `id` is a real tiebreaker. **The same
  latent tie exists in `InventoryRepository.movements()`** (pre-existing, ordered by `occurred_at`
  alone) — left alone deliberately rather than changing Part 1–4 behaviour mid-part, but worth fixing
  if C2 or C3 touches that method.

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

### Read for the next checkpoint (Part 5 C2) — these and nothing else

- `docs/REQUIREMENTS.md` §7 (R6.x — **R6.10 and R6.16 are C2's**) and §8 (R7.x, C3's). §1 for the
  invariants.
- `docs/prompts/part-05.md` — the whole brief, self-contained. Binding rules: `docs/STANDING-RULES.md`.
- `docs/08-module-breakdown.md` § Inventory/Warehouse, if you have not already read it.
- **The edit set for C2:** `app/modules/inventory/{repository,service,schemas}.py` (the valuation and
  ageing reads — `models.py` should need nothing, since cost and age are derived) ·
  `app/modules/pricing/service.py` (`latest_purchase_minor` already exists there — see whether the
  weighted average belongs beside it or in inventory, and say which you chose) ·
  `app/web/pages/{inventory,warehouse}.py` + their templates (extend C1's sections, do not add pages) ·
  `app/seed/inventory.py` if the weighted average needs more history to be non-trivial ·
  `tests/` — a new file, following `tests/test_inventory_locations.py`.
- **`stock_movement.unit_cost_minor` is already populated by every inbound path**, so R6.16's input
  exists. Read it; do not add a cost column.

### Call, don't read — verified signatures, copied from source (Part 4 close + Part 5 C1)

```python
# app/modules/inventory/service.py — Part 5 C1's additions
InventoryService(db).record_movement(*, product_id, warehouse_id, qty_delta, reason,
    ref_type=None, ref_id=None, unit_cost_minor=None, bin_id=None, actor_id=None)
#   `bin_id` is the C1 addition and is OPTIONAL (R6.3). Still the only writer (G8).
InventoryService(db).reserved(product_id, warehouse_id=None)  -> Decimal
InventoryService(db).available(product_id, warehouse_id=None) -> Decimal
#   sellable on-hand (stock-kind bins only) − outstanding reservations. NOT clamped at 0:
#   an over-reserved product is a real condition and is shown, not floored.
InventoryService(db).states(warehouse_id=None)   -> list[StockStateRow]
#   StockStateRow(.product_id .sku_code .product_name .warehouse_id .warehouse_name
#                 .on_hand .reserved .in_transit .quarantined .available)
#   Two grouped queries for the whole page + one for names. No per-row query.
InventoryService(db).bin_stock(warehouse_id=None) -> list[BinStockRow]
#   BinStockRow(... .rack_id .rack_code .bin_id .bin_code .bin_kind .qty_on_hand)
#   .location -> "A / A-01", or "no bin recorded" when bin_id is None (R6.3).
#   INCLUDES the bin_id IS NULL row — dropping it makes the view disagree with on-hand.
InventoryService(db).location_rollup(warehouse_id=None) -> list[LocationRollupRow]
#   LocationRollupRow(.level "warehouse"|"rack"|"bin" .id .code .name .kind
#                     .qty_on_hand .children). Each level IS the sum of its children.

LocationService(db).racks(warehouse_id=None) -> list[StorageRack]
LocationService(db).bins(rack_id=None)       -> list[StorageBin]
LocationService(db).create_rack(RackCreate, *, actor_id) -> StorageRack
LocationService(db).create_bin(BinCreate, *, actor_id)   -> StorageBin
LocationService(db).require_rack(id) / .require_bin(id)  # raise NotFoundError
BIN_KINDS = ("stock", "transit", "quarantine")   # app/modules/inventory/models.py

# THE VERB PART 7's R9.8/R9.9 CALLS — do not add a second mechanism
ReservationService(db).reserve(ReservationCreate, *, actor_id)  -> ReservationResult
ReservationService(db).release(ReservationCreate, *, actor_id)  -> ReservationResult
ReservationService(db).consume(ReservationCreate, *, actor_id)  -> ReservationResult
#   reserve at SO confirm · consume at fulfilment · release at cancellation.
#   Each appends ONE signed row and writes ONE activity_log row (G5). Never edits.
#   reserve refuses over-committing and NAMES the numbers; release/consume refuse
#   unwinding more than is outstanding.
ReservationService(db).reserved(...) / .available(...) / .entries(product_id=None)
ReservationCreate(product_id, warehouse_id, qty>0, bin_id=None, ref_type=None,
                  ref_id=None, note=None)
ReservationResult(product_id, warehouse_id, qty_delta, reason, on_hand, reserved, available)
#   reason is "RESERVE" | "RELEASE" | "CONSUME"

InventoryRepository(db).qty_by_bin_kind(warehouse_id=None) -> [(pid, wid, kind, qty)]
InventoryRepository(db).reserved_totals(warehouse_id=None) -> [(pid, wid, qty)]
InventoryRepository(db).bin_rows(warehouse_id=None)        # the outer-joined page query
#   Unaddressed stock counts as `stock` kind — no bin recorded is not a fourth state.

# app/core/money.py — moved here in C1 so inventory can use it (was procurement-private)
qty_text(value: Decimal) -> str    # "40", not "40.0000". Service messages only.
minor_to_text(minor: int | None) -> str

# app/modules/inventory/service.py — what existed before C1 (record_movement is ABOVE,
# with its new bin_id; the signature without it is stale, do not use it)
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
OPEN_PO_STATUSES = ("confirmed", "partially_received")   # NOT references.open_po — that includes draft
#   ProcurementCalendarService also lives here (Part 4 C2's /procurement calendar); Part 5
#   does not call it. Signature is in docs/parts/part-04.md if C3 ever needs it.

# app/db/explain.py — the ONE shape for every explained number (G11)
Explained(what, value: str | None, formula, window, inputs=(), records=(),
          unknown_reason=None, caveat=None)
#   .is_known -> value is not None      .display -> value or "unknown"
Explained.unknown(*, what, formula, reason, window="no data", inputs=(), records=())
Input(label, value, weight=None, missing_reason=None)   # .is_missing
SourceRecord(label, href=None)
# Rendered by ONE macro:  {{ ui.explain_panel(explained, "Optional title") }}

# app/modules/procurement/service.py — Part 5 needs only these
PurchaseOrderService.open_qty(line) -> Decimal   # STATICMETHOD. THE definition of open (R4.9/G7).
default_business_unit(db) · tax_bps_for(db, product) · _round_minor(value)
#   _round_minor is the ONE money rounding step (G1) — do not add a second.
#   VendorIntelService and ProductSupplierService (suppliers module) are NOT called by
#   Part 5 — RecommendationService already reads them internally. Signatures for those,
#   and for the full PO chain, are in docs/parts/part-04.md if C3 turns out to need them.

# app/modules/config/service.py
allocate_document_number(db, *, doc_type, business_unit_id, on_date) -> "GRN-202607-00001"
#   Row-locked per (BU, doc_type, period). C3's count sheets may want a new doc type.
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
  wrong in a sentence. Screens have the `number` filter; a service message uses
  **`app.core.money.qty_text`** (moved there in C1). Plain `.normalize()` is a trap — it turns 40
  into `4E+1`.
- **A column default of `func.now()` ties.** Rows written in one transaction share a timestamp, so
  `ORDER BY occurred_at` alone is not deterministic and a test that reads "the newest entry" fails
  intermittently. Add `id` as the tiebreaker — keys are UUID v7 and therefore time-ordered. This cost
  C1 two intermittently-failing tests before the cause was found.
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
- **`$pid` is read-only in PowerShell**, and PowerShell has **no heredocs** — a multi-line commit
  message needs the Bash tool (`git commit -F - <<'EOF'`), not `powershell`.
- **A self-referencing Pydantic model needs `Model.model_rebuild()`** after its class body
  (`LocationRollupRow.children` is a `list[LocationRollupRow]`).

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

# ApexOS — Build Progress

> The source of truth for status. **This file is capped at ~350 lines and does not grow.**
> Closed parts live in `docs/parts/`. A new part's handoff **replaces** the previous one here — never appends.
>
> **It is ~385 today, and that overage is scheduled to clear.** Part 5 is mid-flight, so this file is
> carrying the decisions of *two* checkpoints (C1 and C2) at once. C3 closes the part, and its own
> starter prompt instructs it to move the whole Part 5 record to `docs/parts/part-05.md` and delete it
> from here. If you are the C3 session: that archive step is not optional, and it is what brings this
> file back under the cap. Do not add a Part 6 block on top of the Part 5 one.

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

#### ▶ NEXT SESSION PROMPT — Part 5, checkpoint C3 (operations + inventory health) · CLOSES PART 5

```
Continue the ApexOS build. Do this in order:

1. git checkout main && git pull origin main. Then git status — one writer per working
   tree; if it is dirty, stop and report. This run does NOT tag parts (the user waived
   tags for Parts 5–7), so the checkpoint SHA table below is the only record of where
   each part began. Do not expect part-05-done to exist.

2. Read the "▶ CURRENT WORK" block below, especially "▶ Part 5 — IN FLIGHT". C1
   (437a185) and C2 (b442322) ARE DONE AND GREEN; EVERY R6.x PASSES. That block is your
   brief — it lists the nine decisions C1 and C2 made that you must not reverse, carries
   verified signatures to call without opening the source, and its "Do NOT read" list is
   binding. C3 is the LAST checkpoint of Part 5.

3. Read docs/REQUIREMENTS.md §1 (G1–G17) and §8 (R7.x — all of C3). §7 is done; read it
   only if you need context on what ageing gives you. The invariants you must not break
   are NOT in the files you are editing: one activity_log row per state change,
   derived-never-stored, append-only ledgers, record_movement as the only stock writer.
   Then docs/prompts/part-05.md and docs/STANDING-RULES.md (binding). Do NOT open
   docs/ROADMAP.md — planning only, ~17k tokens.

4. `git show --stat b442322` for what C2 changed. Not a tree walk.

5. Verify the baseline before writing code (from apps/api, venv activated):
     python -m pytest -q                  # expect 457 passed
     python -m ruff check app/ tests/     # expect EXACTLY 37 — 38 is a regression
   If either is off, stop and report. 37 is pre-existing (32 E501, 4 F841, 1 B007, all
   in untouched modules). Parts 1–5 C2 added zero.

6. C3 is operations then health. EXTEND WHAT EXISTS — StockTransferService.transfer and
   StockAdjustmentService.adjust/count are already there and each already writes one
   activity row. Rebuilding them is the G16 failure.

   a. R7.1–R7.4 — cycle count: sheet → variance → adjustment. A count with NO variance
      writes NO adjustment movement (R7.2); a variance writes EXACTLY ONE movement and
      ONE activity_log row (R7.3). Adjustment requires a reason and refuses a blank one
      (R7.4). NOTE `count` today raises ConflictError when the count matches — decide
      whether "nothing to reconcile" is an error or a normal no-variance outcome, and
      say which in the resume block. R7.2 reads more like the latter.

   b. R7.5 — transfer becomes TWO steps with in-transit between them. THE MECHANISM IS
      ALREADY BUILT: C1 made StorageBin.kind ("stock"|"transit"|"quarantine") exactly
      this, so it is OUT of the source's stock bin → IN to a transit bin, then transit →
      the destination's stock bin. DO NOT ADD AN IN-TRANSIT FLAG. Today transfer posts
      both movements at once, so nothing is ever in transit; splitting it is the work.
      /inventory already reports the in-transit state, so it lights up for free.

   c. R7.7–R7.10 — health, every output through Explained + the explain_panel macro
      (G11, one shape, already built): ABC analysis STATING its class boundaries, a
      dead-stock radar STATING its window, fast/slow movers showing the window and the
      numbers, low-stock alerts stating trigger + threshold + affected records AND
      LINKING to them. Boundary tests on ABC and on the dead-stock window.
      The inputs exist: ValuationService.ageing() rows carry .stale_qty/.oldest_days and
      InventoryRepository.last_movement_at(product_id) is there. "No movement in a
      window" and "old stock" are DIFFERENT measures — say which the radar uses.

   d. R7.11/R7.13 — THE TRAP. Reorder suggestions CALL
      RecommendationService(db).recommend(...). Part 4 left
      test_r5_9_no_second_implementation_of_what_to_buy_exists_in_the_app, a source walk
      that FAILS if a second `def recommend` appears anywhere in app/ — including one you
      add. R7.13 requires a test proving both return IDENTICAL output for the same
      product. If they genuinely must differ, parameterise the ONE engine and record the
      unification. Part 10's R13.1 audits exactly this.

7. Constraints that still bind:
     - G8: record_movement is the ONLY writer of stock_movement — a source-walk test
       enforces it. Every operation goes through it.
     - G7: derived, never stored. ABC class, dead-stock status and movement rates are
       computed per read, not columns.
     - G5: exactly one activity_log row per state change.
     - Any new model owes app/db/references.py an entry, even an empty tuple (R3.7), and
       EXERCISE it with blocking_references(db, row) in a test. A count SHEET may be a
       real new entity; a class or a rate is not.
     - A new column on an EXISTING table needs an _ADDITIVE_COLUMNS entry in
       app/main.py (~line 45), or it is silently missing on every DB seeded earlier.
     - G12: arithmetic only. No ML, no runtime LLM call.
   Seed (G14/R7.14): extend app/seed/inventory.py — a variance count and its
   adjustment, a zero-variance count, an in-transit transfer AWAITING receipt, dead
   stock, a fast mover, and enough history for non-trivial ABC classes. C2's backdated
   purchases already give you aged stock to build dead stock from. Never append logic
   into core.py's run().

8. Work on main. No branches, no PRs, no tags. Commit at the end of C3 and push.
   C3 CLOSES PART 5: when every P0/P1 in §7 and §8 passes, MOVE Part 5's record from
   PROGRESS.md to docs/parts/part-05.md and DELETE it from PROGRESS.md, keeping only the
   "Read for the next part" + "Call, don't read" blocks Part 6 needs. Then rewrite the
   NEXT SESSION PROMPT above for PART 6 C1 (customer depth — contacts, branches, credit
   limit + override, timeline; §9's R8.x) with its measured baseline counts.
   PROGRESS.md IS CAPPED AT ~350 LINES AND DOES NOT GROW — replace, never append.

9. NAME EVERY NEW TEST AFTER THE REQUIREMENT IT PROVES —
   `def test_r7_2_a_count_with_no_variance_writes_no_adjustment(...)`. A requirement's
   evidence is a test node id (`pytest -q -k r7_2`), NOT a paragraph. No per-requirement
   prose tables.

   MUTATION-CHECK the new suite once — break the implementation and confirm the tests go
   red. C1 found its release test could not catch a broken `available`; C2 ran three
   mutations and each was caught by exactly the test written for it. A suite that passes
   first try is not yet evidence.

   If the checkpoint changed the SHAPE of anything, amend docs/CODEBASE-MAP.md in the
   same session. A stale map is worse than none.

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
| Part 5 C1 | `437a185` | Locations, four derived states, the reservation ledger |
| **Part 5 C2** | **`b442322`** | **Weighted-average cost, stock ageing, `inventory/valuation.py`** |

**Verified at C2:** **457 tests passing** (402 at Part 4 close + 55 across C1 and C2),
`ruff check app/ tests/` **exactly 37** — zero new findings across both checkpoints. Fresh
`python -m app.seed` + uvicorn on 8016: `/inventory` renders the four states, the location rollup, the
unaddressed-stock note, the value table and the age buckets; `/warehouse` renders the rack/bin tree,
both maintenance forms and per-warehouse ageing; the product page renders the cost-basis panel; every
nav page 200s; a bad id renders `error.html` at 404.

**Also verified once, by hand, and worth not repeating:** the `_ADDITIVE_COLUMNS` shim upgrades a
database that predates Part 5. A copy of the dev `apexos.db` carried since Part 1 **crashed on the
missing `bin_id`** when read without the app lifespan, and served `/inventory` and `/warehouse`
after booting through it. `test_r6_2_every_additive_column_exists_on_its_model` now guards the
entries; the upgrade path itself is not unit-testable and does not need re-checking unless a new
column lands on an existing table.

| R | State | Where |
|---|---|---|
| R6.1 | ✅ warehouse → rack → bin, codes unique within parent, kinds validated | `StorageRack` / `StorageBin`, `LocationService` |
| R6.2 | ✅ `stock_movement.bin_id` | `record_movement(bin_id=…)` |
| R6.3 | ✅ **nullable, not backfilled** — decision below | `_ADDITIVE_COLUMNS["stock_movement"]` |
| R6.4 | ✅ four states, all derived | `InventoryService.states()` |
| R6.5 R6.6 | ✅ append-only ledger + one verb trio | `StockReservation`, `ReservationService` |
| R6.11 | ✅ bin → rack → warehouse | `InventoryService.location_rollup()` |
| R6.10 | ✅ inclusive-bound buckets, newest-first attribution, approximation on screen | `ValuationService.ageing` |
| R6.16 | ✅ weighted average over purchases only, `Explained`; unknown never zero | `ValuationService.cost_basis` |
| R6.12 | ✅ stock-by-location **and** ageing on both pages | `/inventory`, `/warehouse` |
| R6.14 | ⚠️ racks/bins/putaway/reservation/aged purchases done; **in-transit transfer + counts are C3's** | `app/seed/inventory.py` |
| R6.15 R3.7 | ✅ incl. the G8 source walk and exercised references | `tests/test_inventory_locations.py` |
| **R7.1–R7.14** | ❌ **not started — all of C3** | — |

**Every R6.x now passes.** Evidence is `pytest -q -k r6_` (55 tests) across
`tests/test_inventory_locations.py` (26), `test_inventory_screens.py` (12) and
`test_inventory_valuation.py` (17).

### Four decisions C2 made that a later checkpoint must not reverse

1. **Only a `PURCHASE` sets a cost basis** (`InventoryRepository.ACQUISITION_REASONS`). Transfers move
   the same units and both halves carry a cost hint, so counting them weights one purchase twice;
   putaway is net-zero; an adjustment or count corrects quantity without buying at a price. A test
   posts all four at a wildly different cost and asserts the basis does not budge.
2. **Ageing attributes the balance to arrivals newest-first**, i.e. older stock is assumed to leave
   first, and `PUTAWAY` is excluded from arrivals or every put-away product would look like it landed
   today. **This is not a FIFO layer** — nothing is stored, nothing is consumed from a layer, and
   valuation does not read it. A source-walk test asserts `pricing/service.py` never reads the cost
   basis, because margin depending on valuation is the D-A/R11.6 drift.
3. **Age bucket upper bounds are INCLUSIVE** (`AGE_BUCKETS`): 30 days is "0–30", 90 is "61–90". Every
   edge is asserted, and the last bucket must stay open-ended or old-enough stock falls out entirely.
4. **`record_movement` gained `occurred_at`**, for the same reason Part 3 gave
   `confirm(confirmed_at=…)`: stock received Saturday and keyed Monday arrived Saturday, and it is the
   only way the seed can fabricate aged history **at insert time** without UPDATE-ing a ledger (G4).
   `round_minor` moved to `app.core.money` beside `qty_text`, same circular-import reason, re-exported.

### Five decisions C1 made that a later checkpoint must not reverse

1. **`stock_movement.bin_id` is NULLABLE; NULL means "at this warehouse, bin not recorded" (R6.3).**
   Backfilling would **UPDATE an append-only ledger, which G4 forbids**, and invent a physical fact
   nobody recorded. Both screens show the unaddressed balance. A test pins the nullability.
2. **Rack and bin live in `inventory/models.py`, not `config/models.py`** — `Warehouse` stays a config
   master; racks and bins exist only to address stock, and inventory is their only reader/writer.
3. **R6.4's four states derive from the two ledgers plus `StorageBin.kind`** (`stock`/`transit`/
   `quarantine`); no state column exists and a test asserts none appears. **This is the mechanism C3's
   R7.5 transfer must use** — do not add an in-transit flag, the bin kind already carries it.
4. **`/warehouse` shows the whole location tree; `/inventory` shows only where stock IS.** An empty
   quarantine bin appears on the former, not in the latter's rollup. Deliberate.
5. **The seed's putaway is a NET-ZERO PAIR** — out of the unaddressed pool, into a bin. It changes an
   address, never a quantity; a test asserts `SUM(qty_delta) WHERE reason='PUTAWAY'` is 0. Writing only
   the inbound half would inflate on-hand across the whole catalogue.

**One pre-existing bug C1 found and deliberately left alone:** `InventoryRepository.movements()` orders
by `occurred_at` alone, which ties for rows written in one transaction (the trap that cost C1 two
tests). `reservation_entries` and `arrivals` both add `id` as the tiebreaker; `movements()` was not
changed, to avoid altering Part 1–4 behaviour mid-part. **Fix it if C3 touches that method.**

R7.11, G11's single `Explained`+`explain_panel` shape, and G8/G7 are covered in the starter prompt
above (steps 6c, 6d, 7) — not repeated here.

### Read for the next checkpoint (Part 5 C3) — these and nothing else

- `docs/REQUIREMENTS.md` §8 (R7.x — **all of C3**) and §1 for the invariants. §7 is done.
- `docs/prompts/part-05.md` — the whole brief, self-contained. Binding rules: `docs/STANDING-RULES.md`.
- **The edit set for C3:** `app/modules/inventory/service.py` — `StockTransferService.transfer` and
  `StockAdjustmentService.adjust/count` **already exist and each writes one activity row; EXTEND
  them, do not replace them** (R7.1–R7.5) · a health module for ABC / dead stock / fast-slow
  (`valuation.py` already holds the derived reads, and `arrivals` / `last_movement_at` are there for
  it) · `app/web/pages/{inventory,warehouse}.py` + templates · `app/seed/inventory.py` for R7.14 ·
  `tests/` — a new file, following `tests/test_inventory_valuation.py`.

The four things that will actually bite C3 — R7.5's mechanism, the R7.11 source-walk trap, R7.8's two
different measures, and G11 on every health output — are spelled out in the starter prompt's step 6.
Not repeated here; a second copy is a second thing to keep in step.

### Call, don't read — verified signatures, copied from source (Part 4 close + Part 5 C1/C2)

```python
# app/modules/inventory/valuation.py — Part 5 C2. Reads only, writes nothing (G15).
ValuationService(db).cost_basis(product_id)        -> Explained   # R6.16, "110.00"
ValuationService(db).cost_basis_minor(product_id)  -> int | None  # None = never bought
ValuationService(db).stock_value()                 -> list[StockValueRow]
#   StockValueRow(.product_id .sku_code .product_name .qty_on_hand .cost_basis_minor
#                 .value_minor) · .is_known. Sorted by value, highest first.
ValuationService(db).total_value_minor(rows=None) · .unknown_basis_count(rows=None)
#   PASS `rows` if you already have them, or the page recomputes stock_value() per call.
ValuationService(db).ageing(warehouse_id=None, *, as_of=None) -> list[AgeingRow]
#   AgeingRow(.product_id .sku_code .product_name .qty_on_hand .buckets .oldest_days
#             .unattributed) · .stale_qty = the over-90 bucket, R7.8's input.
#   `as_of` is injectable so a boundary test can sit exactly on a bucket edge.
ValuationService(db).ageing_note()            # the one approximation sentence, for screens
ValuationService(db).ageing_explained(row)    -> Explained   # same sentence as .caveat
bucket_for(days) -> (key, label)              # UPPER BOUNDS INCLUSIVE
AGE_BUCKETS  # (("fresh","0–30 days",30), ("thirty",…,60), ("sixty",…,90), ("stale",…,None))

InventoryRepository(db).acquisition_totals(product_id=None)
#   -> [(product_id, qty, cost_total_minor, purchases, first_at, last_at)] grouped
InventoryRepository(db).acquisitions_without_cost(product_id) -> Decimal
InventoryRepository(db).arrivals(product_id, warehouse_id=None) -> [StockMovement]
#   inbound, NEWEST FIRST, PUTAWAY excluded (it is re-addressing, not an arrival)
InventoryRepository(db).last_movement_at(product_id) -> datetime | None   # R7.8 reads this
InventoryRepository.ACQUISITION_REASONS = ("PURCHASE",)   # ONLY a purchase sets cost

# app/modules/inventory/service.py — Part 5 C1/C2's additions
InventoryService(db).record_movement(*, product_id, warehouse_id, qty_delta, reason,
    ref_type=None, ref_id=None, unit_cost_minor=None, bin_id=None, occurred_at=None,
    actor_id=None)
#   `bin_id` (C1, R6.3) and `occurred_at` (C2) are both OPTIONAL. Still the only writer
#   (G8). `occurred_at` is how the seed fabricates history at INSERT time — never UPDATE.
#   Reasons in use: PURCHASE · SALE · TRANSFER · ADJUSTMENT · COUNT · PUTAWAY.
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

# app/core/money.py — moved here in C1/C2 so inventory can use them (were
# procurement-private, and inventory cannot import procurement — it would be circular)
qty_text(value: Decimal) -> str    # "40", not "40.0000". Service messages only.
round_minor(value: Decimal) -> int # THE one money rounding step (G1). No second one.
minor_to_text(minor: int | None) -> str   # 123456 -> "1234.56"

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
- **A `select()` per row in a projector is the thing to avoid**; `db.get(Product, id)` in a loop is
  free (identity map). Part 4's engine covers all 311 products in two queries.
- **`status_class` in `web/core.py` picks badge colour from a status *string*** — one not in its
  positive/warning/negative sets renders grey, silently. A new status needs a bucket.
- **A page with an entry form has TWO `<tbody>`s**, so `html.count("<tbody>") == 1` is wrong there.
  Assert markers the shared macros emit, and read totals from the paginator, not by counting `<tr>`.
  Also assert on phrases that do **not** straddle a template line break — C2 lost a run to that.
- **The env var is `DATABASE_URL`, not `APEXOS_DATABASE_URL`.** The wrong name silently writes the real
  `apexos.db` and you "verify" against stale data. A scratch `.db` cannot be deleted while uvicorn holds
  it — stop it first (`Get-CimInstance Win32_Process | Where CommandLine -like '*<port>*' |
  Stop-Process -Force`; `pkill` does not exist here). 8000 may be occupied; C1 used 8015, C2 8016.
- **PowerShell has no heredocs and `$pid` is read-only** — a multi-line commit message needs the Bash
  tool (`git commit -F - <<'EOF'`). Shell variables do **not** persist between tool calls, so a script
  that needs `DATABASE_URL` must set it in the same invocation.
- **A self-referencing Pydantic model needs `Model.model_rebuild()`** after its class body.
- **A script that reads the DB without booting the app skips `_ensure_new_columns`** and will crash on
  any additively-added column. Use a `TestClient(app)` context if you need the shim to have run.

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

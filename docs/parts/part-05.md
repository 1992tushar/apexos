# Part 5 — Inventory: locations, states, valuation, operations, health (Phase 3)

**Status: IN FLIGHT.** C1, C2 and C3's operations half are complete; C3's health half
(R7.7–R7.13) remains. This file is the archive of what is finished — it exists so
`PROGRESS.md` can stay under its cap while the part is still open. **The session closing
Part 5 appends its own record here and deletes the Part 5 block from `PROGRESS.md`.**

Not to be read during a session. `PROGRESS.md`'s `▶ CURRENT WORK` block carries everything
a checkpoint needs.

| Checkpoint | Commit | What landed |
|---|---|---|
| C1 | `437a185` | Locations (warehouse→rack→bin), four derived stock states, the reservation ledger |
| C2 | `b442322` | Weighted-average cost, stock ageing, `inventory/valuation.py` |
| C3a | `eaee67b` | Count sheets, mandatory adjustment reasons, two-step in-transit transfers |
| C3b | — | **outstanding:** ABC, dead stock, fast/slow, low-stock alerts, reorder reading R5.9 |

**No tags.** The user waived `part-0N-done` for Parts 5–7, so the SHA table above is the
record of where each checkpoint landed.

**Verified at C3a:** 482 tests passing (402 at Part 4 close + 80 across C1/C2/C3a),
`ruff check app/ tests/` exactly 37 — **zero new findings across all three checkpoints.**

Requirement evidence is test node ids, not prose: `pytest -q -k r6_` (55 tests) and
`pytest -q -k r7_` (25), across `test_inventory_locations.py`, `test_inventory_screens.py`,
`test_inventory_valuation.py` and `test_inventory_operations.py`.

---

## C1 — locations, states, reservation (`437a185`)

R6.1 warehouse → rack → bin with codes unique within their parent · R6.2
`stock_movement.bin_id` · R6.3 nullable, not backfilled · R6.4 four derived states · R6.5/R6.6
the reservation ledger and its verb · R6.11 bin → rack → warehouse rollup · R6.15/R3.7.

**Five decisions a later part must not reverse:**

1. **`stock_movement.bin_id` is NULLABLE; NULL means "at this warehouse, bin not recorded".**
   Backfilling would **UPDATE an append-only ledger, which G4 forbids**, and would invent a
   physical fact nobody recorded. Both screens show the unaddressed balance rather than
   hiding it. A test pins the nullability.
2. **Rack and bin live in `inventory/models.py`, not `config/models.py`.** `Warehouse` stays
   a config master that `/warehouse` maintains; racks and bins exist only to address stock,
   and the inventory module is their only reader and writer.
3. **R6.4's four states derive from the two ledgers plus `StorageBin.kind`**
   (`stock`/`transit`/`quarantine`). No state column exists and a test asserts none appears.
   C3a's two-step transfer uses exactly this — there is no in-transit flag.
4. **`/warehouse` shows the whole location tree; `/inventory` shows only where stock IS.**
   An empty quarantine bin appears on the former, not in the latter's rollup.
5. **The seed's putaway is a NET-ZERO PAIR** — out of the unaddressed pool, into a bin. It
   changes an address, never a quantity; a test asserts `SUM(qty_delta) WHERE
   reason='PUTAWAY'` is 0. Writing only the inbound half would inflate on-hand catalogue-wide.

**Cost:** two intermittently-failing tests before the cause was found — `occurred_at`
defaults to `func.now()`, so rows written in one transaction tie and `ORDER BY occurred_at`
alone left ordering to the query planner. `reservation_entries` and `arrivals` add `id` (UUID
v7, time-ordered) as the tiebreaker. **`InventoryRepository.movements()` still has the same
latent tie** — left alone deliberately rather than changing Part 1–4 behaviour mid-part.

**Mutation check:** breaking `available()` failed only 1 of 22 tests, which exposed that the
release test compared before-and-after with the same broken function. Strengthened to assert
the dip as well as the recovery.

---

## C2 — valuation and ageing (`b442322`)

R6.16 weighted-average cost · R6.10 age buckets · R6.12 both views on both pages.

**Four decisions a later part must not reverse:**

1. **Only a `PURCHASE` sets a cost basis** (`InventoryRepository.ACQUISITION_REASONS`).
   Transfers move the same units and both halves carry a cost hint, so counting them weights
   one purchase twice; putaway is net-zero; an adjustment or count corrects quantity without
   buying at a price. A test posts all four at a wildly different cost and asserts the basis
   does not budge. An uncosted purchase is excluded from **both** sides and disclosed as a
   missing `Input` — counting it at zero would drag a 100.00 basis to 10.00.
2. **Ageing attributes the balance to arrivals newest-first** (older stock assumed to leave
   first), and `PUTAWAY` is excluded from arrivals or every put-away product would look like
   it landed today. **This is not a FIFO layer** — nothing is stored, nothing is consumed from
   a layer, and valuation does not read it. A source-walk test asserts `pricing/service.py`
   never reads the cost basis, because margin depending on valuation is the D-A/R11.6 drift.
3. **Age bucket upper bounds are INCLUSIVE** (`AGE_BUCKETS`): 30 days is "0–30", 90 is
   "61–90". Every edge is asserted, and the last bucket stays open-ended or old-enough stock
   falls out entirely. **This is the pattern ABC's class boundaries should copy.**
4. **`record_movement` gained `occurred_at`**, for the same reason Part 3 gave
   `confirm(confirmed_at=…)`: the seed can fabricate aged history **at insert time** without
   UPDATE-ing a ledger (G4).

**Verified once by hand, and not worth repeating:** the `_ADDITIVE_COLUMNS` shim upgrades a
database that predates Part 5. A copy of the dev `apexos.db` carried since Part 1 **crashed on
the missing `bin_id`** when read without the app lifespan, and served `/inventory` and
`/warehouse` after booting through it. `test_r6_2_every_additive_column_exists_on_its_model`
now guards the entries.

**Mutation check:** three mutations, each caught by the test written for it — exclusive bucket
bounds, counting non-purchases as acquisitions, and reversing the attribution order.

---

## C3a — operations (`eaee67b`)

R7.1 count sheet → variance → adjustment · R7.2 no variance writes nothing · R7.3 one
variance writes exactly one movement and one activity row · R7.4 mandatory reasons · R7.5
two-step in-transit transfer · R7.6 everything through `record_movement`.

**Four decisions the health half must not reverse:**

1. **A matching count posts NOTHING and is not an error.** `StockAdjustmentService.count` used
   to raise `ConflictError` — "nothing to reconcile" — which made the ordinary, desirable
   outcome of a stock count look like a failure and would have shown the founder a red flash
   for doing everything right.
2. **An uncounted line is NULL, and NULL is uncounted — not zero.** Treating it as zero would
   wipe the stock of every line the founder did not reach.
3. **A transfer dispatches into the DESTINATION's `transit` bin**, and `dispatch` refuses when
   there isn't one rather than silently posting unaddressed stock, which would make the
   in-transit state unreportable. `transfer()` is literally `dispatch()` then `receive()`, so
   the movement arithmetic has one implementation. The invariant a test pins: **a dispatch
   leaves total on-hand unchanged** — stock changes state, it does not vanish.
4. **`default_business_unit` moved to `config/service.py`** beside
   `allocate_document_number`. Inventory needs document numbers and cannot import procurement
   (procurement imports `InventoryService`). Re-exported, no caller churned. **Three helpers
   have now moved for this reason — `qty_text` (C1), `round_minor` (C2),
   `default_business_unit` (C3a). A fourth is a sign the layering needs a proper look rather
   than another move.**

**Ordering the seed forced:** `seed_locations` had to move earlier in `run()`, before the
transfer that now requires a transit bin. You build the warehouse before you move stock
through it — and that point is also the only one where the balances putaway needs already
exist.

**Mutation check:** three mutations, all caught — posting on zero variance, treating uncounted
as zero, and dispatching straight to the shelf instead of into transit.

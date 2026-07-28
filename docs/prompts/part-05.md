<!-- Extracted from docs/ROADMAP.md on 2026-07-28 (Move 0). This file is the prompt for Part 5. -->
<!-- Binding rules live in docs/STANDING-RULES.md. Do NOT read docs/ROADMAP.md mid-part. -->

## PROMPT — Part 5: Inventory — locations, states, operations, health (Phase 3)

```
You are starting Part 5 of 12 (Phase 3 — Inventory) of ApexOS at your clone of the repo.
Parts 1–4 are complete and merged. Read docs/STANDING-RULES.md first (binding: decisions D-A..D-D + the standing rules). Then read docs/REQUIREMENTS.md §7 and §8 (R6.x and R7.x — your acceptance
contract). Also read PROGRESS.md, docs/08-module-breakdown.md (§2.8 Inventory/Warehouse),
Work on main — no branch, no PR: git checkout main && git pull origin main.

SESSION PROTOCOL — 3 checkpoints, ONE PER SESSION, each ending in a commit:
  C1 locations (warehouse→rack→bin) + stock states + RESERVATION AS A LEDGER CONCEPT (R6.5/R6.6)
  C2 weighted-average cost + stock ageing
  C3 operations (count / adjust / transfer) + health (ABC, dead stock, reorder reading R5.9)
C1 is the checkpoint that matters — part 7 calls the reservation verb, so a wrong model here forces
rework there. Do not rush it to reach C2. Before you run low on room, update the CURRENT WORK resume
block in PROGRESS.md (checkpoints + SHAs, requirement IDs passed/outstanding, gotchas, mid-part
decisions — R6.3's location-nullability choice belongs there — and where to start next). Read only
REQUIREMENTS.md §7–§8, the PROGRESS.md resume block, and the module-breakdown § above. pytest -q.

GOAL: inventory must answer three questions — What do we have? Where is it? What is it worth?

READ DECISION D-A FIRST, IT CUTS A THIRD OF THE ORIGINAL SCOPE: there is NO batch/lot tracking, NO
expiry, and NO FIFO. Do not build them. Cost basis is simple WEIGHTED AVERAGE from movement history,
and it is needed only for the on-hand VALUE figure. Margin does not depend on it — MarginService.gp()
is selling − buying off the purchase price snapshotted onto the line. Requirements R6.7, R6.8 and R6.9
are struck; R6.16 (weighted average) replaces them.

WHAT EXISTS: app/modules/inventory (stock_movement ledger, record_movement as the single writer,
derived balances), multi-warehouse + transfer/adjust/count from an earlier phase. Web pages:
/inventory, /warehouse. Extend; do not rebuild. Balances stay DERIVED from the ledger — never a
stored mutable quantity.

BUILD:
1. Location depth: warehouse → rack location → bin, with stock addressed to a bin and the location
   carried on stock ledger entries. Existing movements without a location must keep working —
   backfill to a default bin per warehouse, or make location nullable with a documented meaning.
   Decide and say which in PROGRESS.md. Bin-level stock must roll up correctly to rack and warehouse.
2. Stock states, distinctly reported: available, reserved (committed to sales orders), in transit
   (between warehouses), damaged/quarantined. RESERVATION MUST BE A LEDGER CONCEPT, NOT A FLAG — an
   append-only entry that reduces available without reducing on-hand, released or consumed by a later
   entry. There must be no boolean "reserved" column.
   *** PART 7 CALLS THIS AT SALES-ORDER CONFIRM. Expose it as a clear service verb (R6.6). Getting
   this model wrong is the one mistake in this part that forces rework later. ***
3. Valuation: weighted-average cost from movement history, feeding the on-hand value figure.
4. Stock age buckets, derived from receipt dates on the ledger. Without lots this is APPROXIMATE —
   state the approximation on screen rather than implying precision. It feeds the dead-stock radar,
   which is why it survives D-A.
5. Operations: cycle count (count sheet → variance → adjustment), stock adjustment with a mandatory
   reason, warehouse transfer (two movements with in-transit between them, so stock is never
   invisible mid-flight). A count that matches produces NO adjustment movement; a variance produces
   exactly ONE. All operations write through InventoryService.record_movement — the single writer.
6. Inventory health, all explainable: ABC analysis (state the class boundaries), dead stock radar
   (state the window), fast/slow moving, reorder suggestions, low-stock alerts. Each must show the
   numbers it reasoned from and link to the affected records.

CONSOLIDATE, DO NOT DUPLICATE (requirement R7.11): part 4 already built purchase recommendations from
reorder level + open POs + measured lead time. The reorder suggestions here MUST READ that service
(R5.9), not reimplement it. If the two genuinely differ, unify them into one parameterised engine both
screens read, and say in PROGRESS.md what you unified. A test (R7.13) must prove both return identical
output for the same product. Part 10 will audit exactly this.

UI: extend /inventory and /warehouse — stock-by-location, ageing, health views, plus the count and
adjustment flows. Reuse the part 2 macros. Note decision D-B: the founder is the only user, so
"understandable without training" and printable count sheets are SHOULD, not MUST — but plain labels
and no jargon are still the house style.

Seed: two warehouses with racks and bins, a reservation against a confirmed sales order, an in-transit
transfer awaiting receipt, a completed cycle count with a variance plus one with none, dead stock, a
fast mover, and enough movement history for ABC classes and weighted-average cost to be non-trivial.
Do NOT seed batches or expiry dates — they no longer exist.

Add tests: reservation reduces available but not on-hand, release restores available, weighted-average
cost against hand-computed values, ageing bucket boundaries, bin→rack→warehouse rollup, record_movement
is still the only stock writer, variance produces exactly one adjustment, zero-variance produces none,
adjustment requires a reason, transfer sits in-transit then lands, ABC boundaries, dead-stock window
boundary, and R7.13 (reorder suggestion identical to part 4's engine).

Follow the verify loop in docs/STANDING-RULES.md, update PROGRESS.md, and commit directly to main — no branch, no PR
(see "Git: one branch" in docs/STANDING-RULES.md). When every P0/P1 requirement for the part passes, tag it
(git tag part-0N-done && git push origin part-0N-done). Update memory.
```

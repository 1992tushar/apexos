<!-- Extracted from docs/ROADMAP.md on 2026-07-28 (Move 0). This file is the prompt for Part 3. -->
<!-- Binding rules live in docs/STANDING-RULES.md. Do NOT read docs/ROADMAP.md mid-part. -->

## PROMPT — Part 3: Procurement — pre-order → PO depth (Phase 2, first half)

```
You are starting Part 3 of 12 (Phase 2 — Procurement core) of ApexOS at
your clone of the repo. Parts 1–2 are complete and merged. Read docs/STANDING-RULES.md first —
it is binding: decisions D-A..D-D plus the standing rules. Then read docs/REQUIREMENTS.md §5 (R4.x — your
acceptance contract). Also read PROGRESS.md, docs/08-module-breakdown.md (§2.5 Suppliers/Procurement,
§2.6 Pricing). Work on main — no branch, no PR: git checkout main && git pull origin main.

SESSION PROTOCOL — 2 checkpoints, ONE PER SESSION, each ending in a commit:
  C1 requisition (request → approve → convert) + RFQ + quote capture + comparison
  C2 PO revisions + partial receipt + back orders + receipt-against-revision
Before you run low on room, update the CURRENT WORK resume block in PROGRESS.md (checkpoints + SHAs,
requirement IDs passed/outstanding, gotchas, mid-part decisions, where to start next). Read only
REQUIREMENTS.md §5, the PROGRESS.md resume block, and the module-breakdown §§ above. pytest -q.

GOAL: procurement is the heart of ApexOS. Make the buy-side workflow deep and extremely efficient —
the fewest clicks and keystrokes to get from "we need this" to "it's ordered and received".

WHAT EXISTS: app/modules/procurement (purchase_order, purchase_order_line, goods_receipt +
confirm/receive), app/modules/suppliers (supplier, contacts, evaluation), app/modules/pricing
(purchase_price). Web pages: /purchase-orders, /procurement, /suppliers. Extend these; do not rebuild.

BUILD:
1. Pre-order flow: purchase requisition (request → approve → convert to PO or RFQ), RFQ to multiple
   suppliers, quotation capture, side-by-side vendor comparison (price / lead time / MOQ / score),
   quotation history per product+supplier. Approval is a state change with an actor and a reason —
   one activity_log row each.
2. PO depth: PO revisions (versioned, append-only — never mutate a confirmed PO in place; each
   revision is a new version with a reason and an activity_log row), partial receipt, back orders
   (open quantity DERIVED as ordered − received, never a stored counter), receipt against a specific
   revision — and receipt against a superseded revision handled explicitly, not silently accepted.

UI: extend /purchase-orders and /procurement; add requisition, RFQ and comparison screens. Optimise
for speed — keyboard-first entry, product search-as-you-type, sensible defaults from history, bulk
line entry. Reuse the part 2 table/filter/pagination macros; do not hand-roll list markup.

Ledger discipline: goods receipt posts stock IN through the existing InventoryService.record_movement
(the ONLY stock writer). Receipts and revisions are append-only.

HANDOFF TO PART 4 (this is a requirement, R4.11): persist the timestamps part 4 needs — PO confirm
and each receipt — so lead time can be MEASURED there rather than typed in. Do NOT build vendor
scoring here; part 4 owns it.

Seed a requisition awaiting approval, an approved requisition converted to a PO, an RFQ with 2
supplier quotes, a revised PO, and a partial receipt with an outstanding back order.

Add tests: requisition→PO conversion, approval writes exactly one activity_log row, RFQ→quote
comparison pick, PO revision preserves the prior version verbatim, partial receipt leaves the correct
back-order quantity, receipt against a superseded revision is handled explicitly.

Follow the verify loop in docs/STANDING-RULES.md, update PROGRESS.md, and commit directly to main — no branch, no PR
(see "Git: one branch" in docs/STANDING-RULES.md). When every P0/P1 requirement for the part passes, tag it
(git tag part-0N-done && git push origin part-0N-done). Update memory.
```

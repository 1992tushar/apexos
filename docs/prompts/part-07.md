<!-- Extracted from docs/ROADMAP.md on 2026-07-28 (Move 0). This file is the prompt for Part 7. -->
<!-- Binding rules live in docs/STANDING-RULES.md. Do NOT read docs/ROADMAP.md mid-part. -->

## PROMPT — Part 7: Sales — workflow completion + speed (Phase 4, second half)

```
You are starting Part 7 of 12 (Phase 4 — Sales workflow & speed) of ApexOS at
your clone of the repo. Parts 1–6 are complete and merged. Read docs/STANDING-RULES.md first —
it is binding: decisions D-A..D-D plus the standing rules. Then read docs/REQUIREMENTS.md §10 (R9.x — your
acceptance contract). Also read PROGRESS.md, docs/08-module-breakdown.md (§2.4, §2.7),
Work on main — no branch, no PR: git checkout main && git pull origin main.

SESSION PROTOCOL — 2 checkpoints, ONE PER SESSION, each ending in a commit:
  C1 quotation — create / revise / send / expire / convert-to-order
  C2 returns + credit note + reservation wiring + health score + the speed work
Before you run low on room, update the CURRENT WORK resume block in PROGRESS.md (checkpoints + SHAs,
requirement IDs passed/outstanding, gotchas, mid-part decisions, where to start next). Read only
REQUIREMENTS.md §10, the PROGRESS.md resume block, and the module-breakdown §§ above. pytest -q.

GOAL: close the two gaps at the ends of the sales workflow, wire in reservation, and make order entry
genuinely fast.

WHAT EXISTS: lead → sales_order → fulfillment → invoice → payment works and is E2E-verified. The
gaps are at the two ends: QUOTATION (before the order) and RETURNS / CREDIT NOTE (after the invoice).

BUILD:
1. Quotation: create, revise (versioned, append-only — prior versions readable verbatim), send,
   expire, and convert to a sales order in ONE action carrying the quoted prices forward.
2. Returns and credit notes: a return posts stock IN through InventoryService.record_movement and
   raises a credit note against the invoice. APPEND-ONLY — never edit the original invoice; a test
   must assert the invoice is unchanged after a return. Partial returns allowed, leaving a correct
   DERIVED returnable quantity. The credit note reduces the receivable through the ledger, not by
   mutation.
3. Reservation: confirming a sales order reserves stock by calling PART 5's RESERVATION SERVICE VERB
   (R6.6) — do NOT add a flag or a second mechanism. Fulfilment consumes the reservation;
   cancellation releases it.
4. Customer health score, fully explainable: order frequency, profitability (using the existing
   margin logic), outstanding + ageing, recency of activity. Show the inputs AND the weighting ON
   SCREEN. Where there is not enough history, say "unknown" — never a misleading default.
5. Speed — THIS IS THE HIGHEST-VALUE ITEM IN THE PART. Decision D-B makes the founder the only
   operator, so every order is entered personally: keyboard-first entry, product search-as-you-type
   showing price AND available stock inline, reorder-from-last-order, defaults from customer history,
   bulk line entry. MEASURE the keystrokes for a 5-line repeat order before and after, and report
   both numbers in PROGRESS.md.

UI: extend /sales and /customers; add quotation and return screens. Reuse the part 2 macros.

Seed: a quotation, a revised quotation, one converted to an order, a confirmed order holding a
reservation, and a partial return with its credit note.

Add tests: quotation→order conversion carries quoted prices, revision preserves the prior version,
return posts stock IN and creates a credit note WITHOUT mutating the invoice, partial return leaves
the correct returnable quantity, confirming an order creates a reservation and cancelling releases it,
health score arithmetic against known seed data, insufficient-history returns "unknown".

Follow the verify loop in docs/STANDING-RULES.md, update PROGRESS.md, and commit directly to main — no branch, no PR
(see "Git: one branch" in docs/STANDING-RULES.md). When every P0/P1 requirement for the part passes, tag it
(git tag part-0N-done && git push origin part-0N-done). Update memory.
```

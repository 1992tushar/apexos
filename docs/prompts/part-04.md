<!-- Extracted from docs/ROADMAP.md on 2026-07-28 (Move 0). This file is the prompt for Part 4. -->
<!-- Binding rules live in docs/STANDING-RULES.md. Do NOT read docs/ROADMAP.md mid-part. -->

## PROMPT — Part 4: Procurement — vendor intelligence + planning (Phase 2, second half)

```
You are starting Part 4 of 12 (Phase 2 — Vendor intelligence & planning) of ApexOS at
your clone of the repo. Parts 1–3 are complete and merged, so requisitions, RFQs, quotes, PO
revisions and partial receipts all exist with real history. Read docs/STANDING-RULES.md first (binding: decisions D-A..D-D + the standing rules). Then read docs/REQUIREMENTS.md §6 (R5.x — your acceptance
contract). Also read PROGRESS.md, docs/08-module-breakdown.md (§2.5, §2.6).
Work on main — no branch, no PR: git checkout main && git pull origin main.

SESSION PROTOCOL — 2 checkpoints, ONE PER SESSION, each ending in a commit:
  C1 product↔supplier mapping + vendor score + measured lead time + MOQ + price history
  C2 procurement calendar + recommendations behind R5.9's single service entry point
Before you run low on room, update the CURRENT WORK resume block in PROGRESS.md (checkpoints + SHAs,
requirement IDs passed/outstanding, gotchas, mid-part decisions, where to start next). Read only
REQUIREMENTS.md §6, the PROGRESS.md resume block, and the module-breakdown §§ above. pytest -q.

GOAL: make the buy side smart using the data part 3 now produces. Data and arithmetic, NOT ML.

BUILD:
1. Vendor intelligence: product↔supplier mapping with preferred + alternate vendors; vendor score
   built from the existing supplier_evaluation plus on-time receipt history; lead time MEASURED from
   PO-confirm → receipt (never typed in — there must be no editable lead-time field); MOQ; price
   history per product+supplier.
2. Planning: a procurement calendar (what is due to arrive, what is due to order) and purchase
   recommendations derived from reorder level + open POs + measured lead time.

EXPLAINABILITY IS THE FEATURE, not a nicety. Every score and every recommendation must state on
screen: what it means, the formula, the data window it used, and links to the records it reasoned
from ("reorder 40 units of X — stock 12, reorder level 50, 0 on open PO, supplier lead time 9 days
measured over 6 receipts"). Where there is not enough history to compute something, say so
explicitly — never emit a misleading default like 0 or 50.

Define boundaries explicitly: received exactly on the promised date counts as ON TIME.

Prefer transparent arithmetic (weighted ratios, trailing averages) over anything a founder cannot
audit by hand. Do NOT add an ML dependency. Do NOT call an LLM at runtime.

Keep this a projection layer: it should own few or no new mutable entities (the product↔supplier
mapping and MOQ are legitimately new master data; scores and lead times are derived, not stored —
unless you measure a real performance problem, and then say so in PROGRESS.md).

HANDOFF TO PARTS 5 AND 10 (requirement R5.9): the recommendation engine must have ONE service entry
point with a clear signature. Part 5's reorder suggestions CALL it; part 10 consolidates all
recommendation logic and will check for duplicates. Two implementations of "what should I buy" is the
specific failure this is designed to prevent.

UI: extend /procurement with the calendar and the recommendations list; add vendor comparison and
price history to the supplier and product detail pages. Reuse the part 2 macros.

Seed enough receipt history across at least two suppliers for lead time and on-time rate to be
non-trivial, plus one product below reorder level with an open PO and one without.

Add tests: lead time computed from confirm→receipt timestamps matches a hand-computed value, on-time
boundary (exactly on the promised date is on time), recommendation quantity arithmetic against known
seed data, a recommendation always carries a non-empty explanation and at least one linked record,
insufficient-history path returns "unknown" rather than a number.

Follow the verify loop in docs/STANDING-RULES.md, update PROGRESS.md, and commit directly to main — no branch, no PR
(see "Git: one branch" in docs/STANDING-RULES.md). When every P0/P1 requirement for the part passes, tag it
(git tag part-0N-done && git push origin part-0N-done). Update memory.
```

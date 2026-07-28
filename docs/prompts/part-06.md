<!-- Extracted from docs/ROADMAP.md on 2026-07-28 (Move 0). This file is the prompt for Part 6. -->
<!-- Binding rules live in docs/STANDING-RULES.md. Do NOT read docs/ROADMAP.md mid-part. -->

## PROMPT — Part 6: Sales — customer depth (Phase 4, first half)

```
You are starting Part 6 of 12 (Phase 4 — Customer depth) of ApexOS at your clone of the repo.
Parts 1–5 are complete and merged. Read docs/STANDING-RULES.md first (binding: decisions D-A..D-D + the standing rules). Then read docs/REQUIREMENTS.md §9 (R8.x — your acceptance contract). Also read
PROGRESS.md, docs/08-module-breakdown.md (§2.4 Customers/CRM, §2.7 Sales), docs/12-coding-standards.md.
Work on main — no branch, no PR: git checkout main && git pull origin main.

SESSION PROTOCOL — 1 checkpoint: this part is one session's work. If you find yourself running low
before it is done, commit what is green and write the CURRENT WORK resume block in PROGRESS.md
(requirement IDs passed/outstanding, gotchas, where to start next) rather than pushing on. Read only
REQUIREMENTS.md §9, the PROGRESS.md resume block, and the module-breakdown §§ above. pytest -q.

GOAL: everything you need to know about a customer, on one page, without looking anywhere else.

WHAT EXISTS: app/modules/customers, app/modules/crm (lead, opportunity, pipeline_stage,
convert/advance), app/modules/sales (the proven sales_order → fulfillment → invoice → payment spine).
Web pages: /customers, /leads, /sales. Extend; do not rebuild the proven spine.

BUILD:
1. Customer profile depth: multiple contacts, multiple branches / ship-to addresses, credit limit,
   payment terms, delivery preferences, documents, notes. Credit policy is versioned — prior versions
   stay readable.
2. Credit limit enforcement at sales-order confirm (CreditPolicyService.check), with an explicit
   override that is LOGGED (who, when, by how much, and why — a reason is mandatory). The block must
   state the numbers: limit, current outstanding, this order's value, the shortfall. The boundary is
   exact: at the limit is allowed, one minor unit over is not.
3. A unified customer timeline: orders, invoices, payments, tasks, notes and activity in ONE
   chronological view, assembled from activity_log plus entity events. This is a READ-ONLY
   projection — do NOT add a new events table to make it easy. A customer with no history must render
   an empty timeline without errors.

Reuse the part 2 macros for the contact/branch/document lists and the part 1 soft-delete mechanism.
Documents reuse the existing DocKeeper/document module — do not build a second upload path.

Do NOT build the health score, quotations or returns here — part 7 owns them. If you find yourself
designing the quotation screen, stop.

Seed: a customer with multiple contacts and ship-to branches, a credit limit, enough
order/invoice/payment history for the timeline to be worth reading, one order that breaches the
credit limit, and one recorded override.

Add tests: credit-limit boundary (exactly at the limit allowed, one minor unit over blocked), override
requires a reason and writes exactly one activity_log row, timeline ordering is strictly chronological
and includes every source type, empty timeline renders.

Follow the verify loop in docs/STANDING-RULES.md, update PROGRESS.md, and commit directly to main — no branch, no PR
(see "Git: one branch" in docs/STANDING-RULES.md). When every P0/P1 requirement for the part passes, tag it
(git tag part-0N-done && git push origin part-0N-done). Update memory.
```

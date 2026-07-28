<!-- Extracted from docs/ROADMAP.md on 2026-07-28 (Move 0). This file is the prompt for Part 8. -->
<!-- Binding rules live in docs/STANDING-RULES.md. Do NOT read docs/ROADMAP.md mid-part. -->

## PROMPT — Part 8: Finance — ledgers, AR/AP, cash, margin, GST (Phase 5)

```
You are starting Part 8 of 12 (Phase 5 — Finance) of ApexOS at your clone of the repo.
Parts 1–7 are complete and merged, so sales, purchases, receipts, returns and credit notes all
produce real financial history. Read docs/STANDING-RULES.md first (binding: decisions D-A..D-D + the standing rules). Then read docs/REQUIREMENTS.md §11 and §12 (R10.x and R11.x — your acceptance contract).
Also read PROGRESS.md, docs/08-module-breakdown.md (§2.9 Finance), docs/12-coding-standards.md.
Work on main — no branch, no PR: git checkout main && git pull origin main.

SESSION PROTOCOL — 3 checkpoints, ONE PER SESSION, each ending in a commit:
  C1 customer + vendor ledgers, AR/AP ageing, collections view, payment allocation
  C2 cash flow (actual + committed) + working capital + cash conversion cycle
  C3 margin across the four dimensions + leakage indicators + GST summary
Before you run low on room, update the CURRENT WORK resume block in PROGRESS.md (checkpoints + SHAs,
requirement IDs passed/outstanding, gotchas, mid-part decisions, where to start next). Read only
REQUIREMENTS.md §11–§12, the PROGRESS.md resume block, and the module-breakdown § above. pytest -q.

GOAL: OPERATIONAL finance, not accounting software. No chart of accounts, no journals, no
double-entry ledger. The questions are "who owes what, when, who do I chase today" and "are we going
to be short of cash" — never "is the trial balance balanced".

WHAT EXISTS: app/modules/finance (invoice, bill, payment with direction, payment_allocation,
receivable/payable projections). Web page: /finance. Extend; do not rebuild.

NOTE decision D-D: the QuickBooks Online bridge is CUT, not deferred. Feature 11.14 in
docs/06-feature-list.md no longer applies. Do not build it, do not stub it.

BUILD:
1. Ledgers: customer ledger and vendor ledger — running statements per party, every line drillable to
   its source document, derived from append-only invoices / bills / payments / CREDIT NOTES (all
   four). The running balance is computed from the ledger, never stored.
2. Receivables and payables: outstanding with ageing buckets, due vs overdue split, a collections view
   (who to chase today, in priority order, WITH the reason stated per entry, deterministic ordering)
   and a payments-due view. Ageing boundaries are exact, including exactly-on-due-date.
3. Payment allocation: partial payment across multiple invoices, including an over-payment that
   spills to the next invoice, and a credit note applied against an invoice.
4. Cash: cash-flow (in vs out, actual + committed), working-capital snapshot, and the cash conversion
   cycle (DSO + DIO − DPO) with EACH COMPONENT SHOWN, not just the total. "Committed" must be DEFINED
   ON SCREEN, naming exactly what it includes (confirmed POs, confirmed orders, due invoices — say
   which).
5. Margin and profitability by product / customer / category / business unit. Cost comes from the
   PURCHASE PRICE SNAPSHOTTED ONTO THE LINE (MarginService.gp), NOT from an inventory valuation layer
   — decision D-A removed FIFO, and margin never needed it. Requirement R11.6 says exactly this.
6. Margin leakage indicators: sold below purchase price, discount creep, freight not recovered. Each
   must LIST THE SPECIFIC OFFENDING RECORDS — an indicator with nothing to click is noise, remove it.
7. GST summary: output tax, input tax, net position, by period. A REPORT, not a filing engine. Do not
   build return-filing workflows.

Everything read-only-derived where possible: these are projections over existing ledgers, so they own
few or no new entities and write NO activity_log rows for reads. Money stays integer minor units
throughout — verify no float arithmetic creeps into any total, percentage, ageing or ratio. Division
appears only in ratios: round explicitly, say where, and never let a float round-trip back into a
stored or displayed money value.

HANDOFF TO PARTS 9 AND 10 (requirement R11.13): expose every projection as a clean service method
with explicit period parameters, so the cockpit and the intelligence layer CONSUME rather than
recompute. If they later need a number you did not expose, that is a gap in THIS part.

UI: extend /finance with ledger, ageing, collections, cash-flow, working-capital, margin and GST
views + CSV export on each (part 2's export path, respecting on-screen filters). Reuse the part 2
macros. No decorative charts — if a chart does not change a decision, make it a table.

Add tests: running balance across all four document types, ageing boundaries including
exactly-on-due-date, partial allocation across multiple invoices, over-payment spillover, credit note
reduces the receivable without mutating the invoice, collections ordering deterministic with a reason
per entry, cash conversion cycle components each hand-verified, committed cash matches its stated
definition, margin across all four dimensions, each leakage indicator fires on a seeded offender and
stays silent otherwise, GST net position by period, and no float in any money path.

Follow the verify loop in docs/STANDING-RULES.md, update PROGRESS.md, and commit directly to main — no branch, no PR
(see "Git: one branch" in docs/STANDING-RULES.md). When every P0/P1 requirement for the part passes, tag it
(git tag part-0N-done && git push origin part-0N-done). Update memory.
```

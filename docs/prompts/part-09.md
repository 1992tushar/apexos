<!-- Extracted from docs/ROADMAP.md on 2026-07-28 (Move 0). This file is the prompt for Part 9. -->
<!-- Binding rules live in docs/STANDING-RULES.md. Do NOT read docs/ROADMAP.md mid-part. -->

## PROMPT — Part 9: Founder Command Center (Phase 6)

```
You are starting Part 9 of 12 (Phase 6 — Founder Command Center) of ApexOS at
your clone of the repo. Parts 1–8 are complete and merged, so real operational data now exists
across procurement, inventory, sales and finance. Read docs/STANDING-RULES.md first (binding: decisions D-A..D-D + the standing rules). Then read docs/REQUIREMENTS.md §13 (R12.x — your acceptance
contract). Also read the PROGRESS.md resume block and docs/17-design-system.md.
Work on main — no branch, no PR: git checkout main && git pull origin main.

SESSION PROTOCOL — 2 checkpoints, ONE PER SESSION, each ending in a commit:
  C1 tiles + alerts + recent activity + quick actions
  C2 query-count and render-time measurement, empty state, delete the placeholder dashboard
Before you run low on room, update the CURRENT WORK resume block in PROGRESS.md (checkpoints + SHAs,
requirement IDs passed/outstanding, gotchas, mid-part decisions, where to start next). Read only
REQUIREMENTS.md §13, the PROGRESS.md resume block, and the design system. pytest -q.

GOAL: build the homepage a founder actually wants to open. This is NOT a dashboard — it is an
operating cockpit. It replaces the current /dashboard page (app/web/pages/dashboard.py +
app/modules/dashboard), which was a placeholder built before the data existed.

The screen must answer exactly three questions, in this order:
  1. What happened?    2. What needs attention?    3. What should I do now?

Show only information that requires a decision. Every number must be drillable to the rows behind it.
NO decorative charts — no donuts, no gradient hero tiles, no vanity metrics. Numbers, deltas, and
lists of things to act on. If a tile does not change a decision, delete it.

CONTENT:
  What happened — today's revenue, today's gross margin, collections today.
  What needs attention — outstanding receivables, outstanding payables, inventory value, purchase
    orders pending, sales orders pending, deliveries due, customer alerts, vendor alerts, low-stock
    alerts, margin alerts.
  Position — cash-flow snapshot, working-capital snapshot.
  Then — recent activity (from activity_log) and quick actions (new order, new PO, record payment,
    receive stock — the four things done most often).

Alerts must be honest: each states the trigger, the threshold, and the affected records, and links
straight to them. An alert with nothing to click is noise — remove it.

Implementation: this is a READ-ONLY PROJECTION LAYER. Reuse part 8's finance projections (R11.13
exposed them with explicit period parameters), part 5's inventory health, and part 4's vendor
intelligence rather than recomputing anything. If a number is not already exposed by those parts, add
it THERE and read it here — do not compute it in the page.

MEASURE: query count for one page load must not fan out into dozens of queries. State the number in
PROGRESS.md and add a test asserting it, so the fan-out cannot silently regress. Report render time on
the seeded dataset.

Delete the placeholder dashboard code you replace — do not leave two dashboards behind.

Add tests: each tile's arithmetic against known seed data, every alert's trigger boundary (fires at
the threshold, silent below it), empty-state (a fresh DB renders without errors and without fake
zeros-as-alerts), and the query-count assertion.

Follow the verify loop in docs/STANDING-RULES.md, update PROGRESS.md, and commit directly to main — no branch, no PR
(see "Git: one branch" in docs/STANDING-RULES.md). When every P0/P1 requirement for the part passes, tag it
(git tag part-0N-done && git push origin part-0N-done). Update memory.
```

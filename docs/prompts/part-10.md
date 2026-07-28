<!-- Extracted from docs/ROADMAP.md on 2026-07-28 (Move 0). This file is the prompt for Part 10. -->
<!-- Binding rules live in docs/STANDING-RULES.md. Do NOT read docs/ROADMAP.md mid-part. -->

## PROMPT — Part 10: Intelligence Layer (Phase 7)

```
You are starting Part 10 of 12 (Phase 7 — Apex Intelligence) of ApexOS at
your clone of the repo. Parts 1–9 are complete and merged. Read docs/STANDING-RULES.md first —
it is binding: decisions D-A..D-D plus the standing rules. Then read docs/REQUIREMENTS.md §14 (R13.x — your
acceptance contract). Also read PROGRESS.md and docs/16-future-roadmap.md.
Work on main — no branch, no PR: git checkout main && git pull origin main.

SESSION PROTOCOL — 2 checkpoints, ONE PER SESSION, each ending in a commit:
  C1 the R13.1 audit + the unifications it finds — THIS IS THE REAL WORK OF THE PART
  C2 radars + cockpits + forecasts + the Founder Morning Brief
Do not skip past C1 to build the visible screens. The audit is what stops this part becoming a fourth
copy of logic that already exists three times. Before you run low on room, update the CURRENT WORK
resume block in PROGRESS.md — the audit list itself belongs there, since it is a deliverable a later
session must not redo. Read only REQUIREMENTS.md §14 and the PROGRESS.md resume block. pytest -q.

GOAL: turn accumulated operational data into recommendations a founder can trust. Much of this exists
in partial form from parts 4, 5, 7 and 8 — THIS PART CONSOLIDATES, IT DOES NOT DUPLICATE.

NON-NEGOTIABLE: no black-box AI. Every score, forecast and recommendation must explain WHY it exists
in plain language, showing the inputs, the weights, and the records it reasoned from — rendered on
screen, not buried in a docstring. Prefer transparent arithmetic (weighted ratios, trailing averages,
simple linear projections) over anything a founder cannot audit by hand. Do NOT add an ML dependency.
Do NOT call an LLM at runtime for these numbers.

START WITH AN AUDIT (requirement R13.1 — this is a deliverable, not scaffolding): list every score,
radar, suggestion and alert that parts 4–9 already produce, and where each lives. Anything computed in
two places gets unified into ONE engine that both screens read. Write that list and the unifications
into PROGRESS.md. For each unification, add a test proving both screens return identical output for
the same input (R13.13).

THEN BUILD / CONSOLIDATE:
  Scores:      customer health (part 7), vendor reliability (part 4), inventory health (part 5) —
               consolidated, not rebuilt.
  Radars:      dead stock, margin leakage, customer churn risk.
  Cockpits:    working capital, category performance, business-unit performance.
  Engines:     procurement recommendations — ONE engine, unifying part 4's purchase recommendations
               and part 5's reorder suggestions.
  Forecasts:   purchase, sales, cash requirement — trailing-window based, with the window STATED and
               the confidence/limitation said out loud.
  Brief:       Founder Morning Brief — a short ranked list of "here is what changed and what to do
               today", assembled from the above. It is a VIEW over the other outputs, NOT new logic.

Each output needs: a stated definition, the formula, the data window, and a link to the underlying
records. Where a score cannot be computed (not enough history), say so explicitly — never emit a
misleading default like 0 or 50.

Add tests: each score against hand-computed seed values, each forecast against a known series,
insufficient-data path returns "unknown" not a number, every recommendation carries a non-empty
explanation and at least one linked record, plus the per-unification identical-output tests.

Follow the verify loop in docs/STANDING-RULES.md, update PROGRESS.md, and commit directly to main — no branch, no PR
(see "Git: one branch" in docs/STANDING-RULES.md). When every P0/P1 requirement for the part passes, tag it
(git tag part-0N-done && git push origin part-0N-done). Update memory.
```

# Parts 5 → 6 → 7 — the unattended checkpoint loop

You are executing **exactly ONE checkpoint**, then stopping. Do not begin a second in the same
turn: one checkpoint per firing is what keeps each firing's context small enough to do the work
properly, and the state lives on disk (PROGRESS.md) rather than in the conversation.

**No tags this run.** The user waived `part-0N-done` for Parts 5–7. The checkpoint SHA table in
PROGRESS.md's `▶ CURRENT WORK` block is therefore the only record of where each part began and
ended — writing it is the deliverable that replaces the tag, not optional bookkeeping.

---

## Step 1 — Orient (every firing)

```
git -C d:\apexos status --short
git -C d:\apexos log --oneline -6
```

Then read the `▶ CURRENT WORK` block at the top of `PROGRESS.md`. **That block, not this file,
tells you which checkpoint is next and what it needs** — it carries the R-number state table,
the prior checkpoint's decisions, and verified signatures to call without opening the source.
This file only carries the loop's own rules and the ledger below.

Read `docs/REQUIREMENTS.md` §1 (G1–G17) plus **only** the § for the part you are in — §7+§8 for
Part 5, §9 for Part 6, §10 for Part 7 — then `docs/STANDING-RULES.md` and
`docs/prompts/part-0N.md` for that part. `docs/CODEBASE-MAP.md` instead of exploring the tree.

**Do NOT read:** `docs/ROADMAP.md` (~17k tokens, planning only), anything under `docs/parts/`,
the older `docs/` design files, `docs/DELETION-POLICY.md`, `docs/MIGRATION-STRATEGY.md`,
`app/seed/core.py` in full, or any test file whose coverage you are not changing.

## Step 2 — Four hard stops. Any one of them ends the loop.

An unattended loop on a broken tree iterates on the wreckage. On any of these: write what you
found into the resume block, commit nothing else, and **stop the loop**.

1. **Dirty tree you did not write.** Another session may be working here — one writer per tree.
   Never commit work you did not produce.
2. **Red baseline.** From `apps/api` with the venv active: `python -m pytest -q` must be fully
   green and `python -m ruff check app/ tests/` must not exceed the count in the resume block.
   Do not build a checkpoint's worth of code on top of a failure.
3. **A missing upstream contract.** Part 5 C3 and Part 7 both call things earlier checkpoints
   built. Confirm the callee exists before depending on it (e.g.
   `grep -rn "class RecommendationService" apps/api/app/modules/procurement/`) and stop if it
   does not.
4. **Scope drift.** Batch/lot tracking, expiry, FIFO layers, a roles/permissions UI, a
   QuickBooks bridge, notifications, saved views, CSV import — all cut by D-A..D-D. Building one
   means the session has drifted (G17). Stop and say so.

## Step 3 — The ledger

| # | Checkpoint | Status |
|---|---|---|
| 1 | **P5-C1** locations + four states + reservation ledger | ✅ done — `437a185` |
| 2 | **P5-C2** weighted-average cost + stock ageing | ✅ done — `b442322` |
| 3a | **P5-C3** operations — count sheet, mandatory reasons, in-transit transfer | ✅ done — `eaee67b` |
| 3b | **P5-C3** health — ABC, dead stock, fast/slow, low-stock, reorder reading R5.9 | ✅ done — `4667a5e` · **Part 5 CLOSED** |
| 4 | **P6-C1** customer depth — contacts, branches, credit limit + override, timeline | ✅ done — `a8c9bde` · **Part 6 CLOSED** |
| 5 | **P7-C1** quotation — create / revise / send / expire / convert | ✅ done — `eeae971` |
| 6a | **P7-C2** reservation wiring + returns + credit notes | ✅ done — `27d1c49` |
| 6b | **P7-C2** customer health score + the speed work (R9.12's keystroke measurements) | next — **closes Part 7** |
| 7 | **E2E** the cross-part walkthrough + final PROGRESS.md and CODEBASE-MAP.md | |

After #7, stop the loop — that is the terminal state. The per-checkpoint requirement detail is
in `docs/REQUIREMENTS.md` and the resume block; the three things worth repeating here because
they cross checkpoints are:

- **#3 must CALL Part 4's `RecommendationService`, never reimplement it** (R7.11). R7.13 wants a
  test proving both return identical output for the same product, and Part 4 left a source walk
  that fails if a second `def recommend` appears anywhere in `app/`.
- **#6 must call #1's `ReservationService.reserve/consume/release`** (R9.8/R9.9) — no flag, no
  second mechanism. Note #4 also edits the sales-order confirm path, so read that method as it
  then stands rather than as #1 left it.
- **#5 and #6 reuse the `explain_panel` macro and `Explained`** for the health score (G11). One
  shape, already built. Do not write per-screen explanation markup.

## Step 4 — Close the firing (mandatory)

1. `python -m pytest -q` (never verbose) — fully green.
2. `python -m ruff check app/ tests/` — **zero new findings** versus the recorded baseline. Not
   "about the same"; Parts 1–5 C1 added zero.
3. **Mutation-check the new suite once**: break the implementation deliberately and confirm the
   tests go red. A suite that passes first try is not evidence. If breaking the code does not
   break a test, the test is decoration.
4. Commit on `main` and push. No branches, no PRs, **no tags**. Personal credentials only
   (`github.com/1992tushar/apexos`).
5. Update PROGRESS.md's `▶ CURRENT WORK` block: the checkpoint SHA table, R-numbers passed and
   outstanding, gotchas, decisions a later checkpoint must not reverse, and the four delta lines
   — Changed since / Read for the next checkpoint / Call, don't read (copy signatures **from
   source**, never from memory) / Do NOT read. Then rewrite the `▶ NEXT SESSION PROMPT` for the
   next ledger item with its **measured** baseline counts.
6. **PROGRESS.md is capped at ~350 lines and does not grow.** Adding a block means trimming
   another. Finishing a part means *moving* its record to `docs/parts/part-0N.md` and deleting
   it here — replace, never append below the previous part.
7. If the checkpoint changed the **shape** of anything, amend `docs/CODEBASE-MAP.md` in the same
   firing. A stale map is worse than none.
8. Commit and push the documentation too, then **stop**. Do not start the next checkpoint.

## When to stop the loop entirely

- Ledger item #7 is complete.
- Any hard stop in Step 2 fires.
- You need a decision only the user can make. Write the question into the resume block, commit
  it, and stop — do not guess and then build on the guess.

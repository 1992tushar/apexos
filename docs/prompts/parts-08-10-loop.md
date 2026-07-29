# Parts 8 → 9 → 10 — the unattended checkpoint loop

You are executing **exactly ONE checkpoint**, then stopping. Do not begin a second in the same
turn: one checkpoint per firing is what keeps each firing's context small enough to do the work
properly, and the state lives on disk (`PROGRESS.md`) rather than in the conversation.

**No tags this run**, carrying forward the convention from Parts 5–7. The checkpoint SHA table in
`PROGRESS.md`'s `▶ CURRENT WORK` block is therefore the only record of where each part began and
ended — writing it is the deliverable that replaces the tag, not optional bookkeeping.

---

## Step 1 — Orient (every firing)

```
git -C d:\apexos status --short
git -C d:\apexos log --oneline -6
```

Then read the `▶ CURRENT WORK` block at the top of `PROGRESS.md`. **That block, not this file,
tells you which checkpoint is next and what it needs** — it carries the R-number state table, the
prior checkpoint's decisions, and verified signatures to call without opening the source. This file
carries the loop's own rules, the ledger, and the contracts that cross parts.

Read `docs/REQUIREMENTS.md` §1 (G1–G17) plus **only** the § for the part you are in — §11+§12 for
Part 8, §13 for Part 9, §14 for Part 10 — then `docs/STANDING-RULES.md` and
`docs/prompts/part-NN.md` for that part. `docs/CODEBASE-MAP.md` instead of exploring the tree.

**Do NOT read:** `docs/ROADMAP.md` (~17k tokens, planning only), anything under `docs/parts/`, the
older `docs/` design files, `docs/DELETION-POLICY.md`, `docs/MIGRATION-STRATEGY.md`,
`app/seed/core.py` in full, or any test file whose coverage you are not changing.

## Step 2 — Four hard stops. Any one of them ends the loop.

An unattended loop on a broken tree iterates on the wreckage. On any of these: write what you found
into the resume block, commit nothing else, and **stop the loop**.

1. **Dirty tree you did not write.** One writer per tree. Never commit work you did not produce.
2. **Red baseline.** From `apps/api` with the venv active: `python -m pytest -q` fully green and
   `python -m ruff check app/ tests/` **exactly 37** — the pre-existing count, unchanged through
   seven parts. **38 is a regression**, not a rounding error.
3. **A missing upstream contract.** Each part here reads the one before it. Confirm the callee
   exists before depending on it, and stop if it does not.
4. **Scope drift.** No chart of accounts, no journals, no double-entry (Part 8's own goal says so),
   no QuickBooks bridge (R10.14, cut by D-D), no ML dependency and no runtime LLM call (G12), no
   decorative charts (R11.14/R12.9). Building one means the session has drifted (G17). Stop and say so.

## Step 3 — The ledger

| # | Checkpoint | Status |
|---|---|---|
| 1 | **P8-C1** customer/vendor ledgers · AR/AP ageing · collections · allocation (R10.x) | **done `ec8a573`** |
| 2 | **P8-C2** cash flow · working capital · cash conversion cycle (R11.1–R11.4) | **done `30b3cc1`** |
| 3 | **P8-C3** margin by four dimensions · leakage · GST (R11.5–R11.14) | **done `0ce6931`** — but **Part 8 is NOT closed**: R11.7 left open by the user's decision on 2026-07-29. Do not tag Part 8, and do not resolve R11.7 inside a later part |
| 4 | **P9-C1** tiles · alerts · activity · quick actions (R12.1–R12.11) | next |
| 5 | **P9-C2** query count + render time measured, empty state, **delete the placeholder** — **closes Part 9** | |
| 6 | **P10-C1** the R13.1 audit + the unifications (this is the real work) | |
| 7 | **P10-C2** radars · cockpits · forecasts · Morning Brief — **closes Part 10** | |
| 8 | **E2E** the cross-part gate + final `PROGRESS.md` and `CODEBASE-MAP.md` | |

After #8, stop the loop — that is the terminal state.

---

## The contracts that cross these three parts

**This is the spine of the whole run.** Parts 8, 9 and 10 are, between them, one long argument that
a number should be computed once and read everywhere. Three requirements say it explicitly —
**R11.11**, **R12.10**, **R13.2** — and Part 10 exists largely to audit whether the earlier parts
kept to it.

1. **R11.13 is the contract Parts 9 and 10 depend on.** Part 8 must expose its projections as clean
   service methods with **explicit period parameters**, so later parts consume rather than
   recompute. This is the same shape R5.9's single recommendation entry point took, and it failed
   the same way when ignored. **Whoever builds P8-C2 owes those signatures to the resume block,
   copied from source.**
2. **`CustomerRepository.outstanding_minor` is THE receivable** — `Σ invoice − Σ allocations −
   Σ credit_notes`. AR ageing, collections, the cash-flow view and the Command Center's receivables
   tile must all CALL it. If a per-invoice breakdown is needed, extend that method or add a sibling
   beside it; **do not re-derive the arithmetic**. This is the most likely mistake in the run.
3. **R11.6: margin is `MarginService.gp`** — selling minus the purchase price snapshotted on the
   line, never an inventory valuation layer. D-A removed FIFO and margin never needed it. A source
   walk in Part 5's tests already asserts `pricing/service.py` does not read the cost basis; keep it
   true in the other direction too.
4. **R13.6 is largely already done.** Part 5's `InventoryHealthService.reorder_suggestions` is a
   bare delegation to Part 4's `RecommendationService.recommend`, and
   `test_r7_13_the_reorder_suggestion_is_identical_to_part_4s_engine` already proves identical
   output. Part 4 also left a source walk that **fails if a second `def recommend` appears anywhere
   in `app/`**. P10-C1 should verify and record this rather than rebuild it — and R13.13's
   "identical output" test for it already exists.
5. **G11 already has exactly one implementation.** `Explained` + the `explain_panel` macro, built in
   Part 4 and used by Parts 5, 6 and 7. R13.1's audit had this unification scheduled for Part 10;
   **it is done.** The audit should say so and move on to whatever genuinely is duplicated.
6. **R12.11: delete the placeholder.** `app/web/pages/dashboard.py` and `app/modules/dashboard/`
   exist today. Part 9 replaces them, and **two dashboards must not remain.** Deleting code is part
   of the checkpoint, not a follow-up.

## Measurement discipline — Parts 9 and 10 both turn on it

**R12.12/R12.13/R12.14 ask for numbers, not adjectives.** Measure the query count for one Command
Center page load and the render time on the seeded dataset, write BOTH into `PROGRESS.md`, and
**assert the query count in a test** so the fan-out cannot silently regress. Part 7's R9.13 is the
worked example: count against the running application, report the figure honestly even when it is
unflattering, and say plainly what the measurement does *not* cover.

**Measure before optimising.** A session that does both in one pass has no baseline left to compare
against — that is why Part 11's C1 is measurement-only, and the same discipline applies here.

**A test that counts queries beats a source walk that greps for a symbol.** Use a SQLAlchemy
`before_cursor_execute` listener; `tests/test_fast_entry.py` has a working example. A text match
cannot tell a call from a comment, and one such test in this build failed on its own docstring.

## Step 4 — Close the firing (mandatory)

1. `python -m pytest -q` (never verbose) — fully green.
2. `python -m ruff check app/ tests/` — **zero new findings**. Seven parts have added none.
3. **Mutation-check the new suite once**: break the implementation deliberately and confirm the
   tests go red. Over the Parts 5–7 run this found two real defects, not merely passing tests.
   Good mutations here: shift an ageing boundary off exactly-on-due-date, let an over-payment
   vanish instead of spilling to the next invoice, make an alert fire with nothing to click, and
   return a default score where history is insufficient.
4. Commit on `main` and push. No branches, no PRs, **no tags**. Personal credentials only
   (`github.com/1992tushar/apexos`).
5. Update `PROGRESS.md`'s `▶ CURRENT WORK` block: the checkpoint SHA table, R-numbers passed and
   outstanding, gotchas, decisions a later checkpoint must not reverse, and the four delta lines —
   *Changed since* / *Read for the next checkpoint* / *Call, don't read* (copy signatures **from
   source**, never from memory) / *Do NOT read*. Then rewrite the `▶ NEXT SESSION PROMPT` for the
   next ledger item with its **measured** baseline counts.
6. **`PROGRESS.md` is capped at ~350 lines and does not grow.** Archive each finished checkpoint to
   `docs/parts/part-0N.md` **progressively** rather than waiting for the close — that is what kept
   it at 228 lines through the previous nine-checkpoint run. Finishing a part means the record is
   already there; replace, never append.
7. If the checkpoint changed the **shape** of anything, amend `docs/CODEBASE-MAP.md` in the same
   firing. A stale map is worse than none.
8. Commit and push the documentation too, then **stop**. Do not start the next checkpoint.

## Traps this codebase has already paid for

Carried forward because each one cost a run:

- **`client.post` COMMITS; `db`-fixture writes roll back.** A test that POSTs leaves rows behind.
  Three checkpoints broke the same two Part 1/3 tests by leaving an OPEN document (draft *or*
  confirmed counts as open) on the first customer. Tests that POST need a subject no other test
  asserts about — see `test_fast_entry.py`'s `spare_customer` fixture.
- **`uuid7()` is NOT monotonic within a millisecond** — its low bits come from `os.urandom`, so
  `ORDER BY (timestamp, id)` cannot break a same-millisecond tie. Select by a discriminating column,
  or stamp an explicit `datetime.now(UTC)` (microsecond resolution) as credit policies and notes do.
- **A test reading a CONVENIENCE FIELD rather than the source of truth can be confidently wrong.**
  The Parts 5–7 E2E gate's one failure was exactly this.
- **An equality assertion between two code paths only tests what the current data distinguishes.**
  A no-op filter once passed an "identical output" test because the seed could not tell the
  difference. **R13.13 asks for exactly this kind of test — so assert the structure too.**
- **`create_all` never ALTERs an existing table.** A new column needs an `_ADDITIVE_COLUMNS` entry
  in `app/main.py` or it is silently missing on every DB seeded earlier.
- **Assert on HTML phrases that do not straddle a template line break** — cost four runs so far.
- **`DATABASE_URL`, not `APEXOS_DATABASE_URL`.** The wrong name silently writes the real
  `apexos.db`. Stop uvicorn before deleting a scratch `.db` (`pkill` does not exist here). Ports
  8015–8025 have been used; pick above that.
- **PowerShell has no heredocs** — a multi-line commit message needs the Bash tool
  (`git commit -F - <<'EOF'`). Shell variables do not persist between tool calls.

## When to stop the loop entirely

- Ledger item #8 is complete.
- Any hard stop in Step 2 fires.
- You need a decision only the user can make. Write the question into the resume block, commit it,
  and stop — do not guess and then build on the guess.

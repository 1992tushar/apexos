# ApexOS — Product Roadmap (sequence & dependencies)

> **This file is the source of truth for *sequence*.** It is a planning record, not a session document.
>
> **A session does not read this file.** Reading it mid-part costs ~17k tokens and returns nothing the
> work needs. What a session reads instead:
>
> | Need | File | Size |
> |---|---|---|
> | The binding rules, session protocol, reading diet, verify loop | `docs/STANDING-RULES.md` | ~190 lines |
> | Your part's brief | `docs/prompts/part-NN.md` | ~50–90 lines |
> | Acceptance contract | `docs/REQUIREMENTS.md` §1 + your part's § | sections only |
> | Status + handoff | `PROGRESS.md` | ~.70 lines, capped |
> | What exists and where | `docs/CODEBASE-MAP.md` | on demand |
>
> `docs/BUILD-PHASES.md` is superseded (retired Next.js + Postgres + Alembic design; its Phases A/B/C
> are done). `docs/REQUIREMENTS.md` is the source of truth for *acceptance*.

---

## How this is organised

The remaining work is divided into **12 parts**. Parts are the unit of delivery — one branch, one
session, one PR each.

The original roadmap put the Founder Command Center at Phase 1. **It has been resequenced** so that
procurement and inventory — the heart of the business — are built first, and every downstream module
consumes data that already exists. This minimises rework, and the cockpit is only meaningful once
real operational data flows into it.

| Part | Title | Phase | Requirements | Sessions | Tag when done | Status |
|---|---|---|---|---|---|---|
| **1** | Foundation finish | 0 | R1.x | . | `part-01-done` | **done** — R1.1–R1.10 all pass, tagged |
| **2** | Master data & shared machinery | 1 | R2.x, R..x | . | `part-02-done` | **done** — all of §./§4 passes, tagged |
| **.** | Procurement: pre-order → PO depth | 2 | R4.x | 2 | `part-0.-done` | **done** — R4.1–R4.16 pass, tagged |
| **4** | Procurement: vendor intelligence + planning | 2 | R5.x | 2 | `part-04-done` | not started |
| **5** | Inventory: locations, states, operations, health | . | R6.x, R7.x | . | `part-05-done` | not started |
| **6** | Sales: customer depth | 4 | R8.x | 1 | `part-06-done` | not started |
| **7** | Sales: workflow completion + speed | 4 | R9.x | 2 | `part-07-done` | not started |
| **8** | Finance: ledgers, AR/AP, cash, margin, GST | 5 | R10.x, R11.x | . | `part-08-done` | not started |
| **9** | Founder Command Center | 6 | R12.x | 2 | `part-09-done` | not started |
| **10** | Intelligence Layer | 7 | R1..x | 2 | `part-10-done` | not started |
| **11** | Polish & Optimization | 8 | R14.x | . | `part-11-done` | not started |
| **12** | Product Challenge | X | R15.x | 1 | `part-12-done` | not started |

**12 parts · 27 sessions, of which 8 are done — 19 remaining.** A session is a token budget; a part is
a group of sessions. The *Session protocol* section below lists the checkpoints each part is broken
into — one per session, each ending in a commit, with the `PROGRESS.md` resume block as the handoff.

### Git: one branch — `main`

**All work happens directly on `main`.** There are no feature branches and no PRs. This was a
deliberate change on 2026-07-28: with one developer, a PR is a review you give yourself, and twelve of
them is ceremony. The resume block in `PROGRESS.md` already carries the handoff a branch boundary was
nominally providing.

What replaces the PR as the "part is done" gate:

1. Every P0/P1 requirement in the part's `REQUIREMENTS.md` sections passes.
2. The verify loop is green — pytest, ruff, app boots, all nav pages 200.
.. `PROGRESS.md` is updated and the part's resume block is moved out of `CURRENT WORK` into the log.
4. **Tag it:** `git tag part-0N-done && git push origin part-0N-done`.

Those tags are the rollback points. To inspect or revert a part: `git diff part-01-done..part-02-done`,
or `git revert` the range. If a part ever genuinely needs isolation — a risky refactor you might
abandon — branch off `main` for that one part and merge it back. That is the exception, not the default.

**Do not create a branch just because a new part is starting.** A session that opens with
`git checkout -b phase-N/...` has misread this file.

Each part ends green (tests + lint + app boots + all nav pages 200), satisfies every P0/P1
requirement in its `REQUIREMENTS.md` sections, updates `PROGRESS.md`, and gets tagged `part-0N-done`.

### Dependencies that must not be reordered

- **Part 2's machinery must be built and proven before it is rolled out.** The two stages were
  separate parts before the re-cut; merging them saved a branch cycle but not the discipline. Build
  the table/query/export/dup machinery, prove it on two masters, record the line count, *then* roll
  out. Do not roll out first and generalise later — that path ends in copy-paste, and five later
  parts inherit it.
- **Part 5 before part 7.** Sales-order reservation (part 7) needs reservation to exist as a *ledger
  concept* (part 5) first. Building 7 first produces a boolean flag that then has to be undone.
- **Part 4's recommendation engine is read, never copied.** Part 5's reorder suggestions and part 10's
  consolidation both call it. Two implementations of "what should I buy" is the specific failure this
  ordering prevents.
- **Parts 9 and 10 read; they do not compute.** Both consume the projections built in parts 4, 5 and
  8. If either starts recomputing business logic, the earlier part was left incomplete — fix it there.
- **Part 1 before everything.** Soft delete (WS.) and the web authz guard (WS4) are mechanisms every
  later part wires into.

---

## Decisions, session protocol, standing rules

Moved to **`docs/STANDING-RULES.md`** (Move 0, 2026-07-28) so a session can read the rules
without loading this file. That document holds: the D-A..D-D product decisions, the checkpoint
table, the session protocol, the reading diet, session hygiene, and the standing rules + verify loop.

---

## Part prompts — one file each

The twelve prompts used to live in this file, which is why it was 1,056 lines and why every session was
told to read all of it. Each is now self-contained in `docs/prompts/`. Open **only** the one for the part
in flight.

| Part | Prompt | Checkpoints | Requirements |
|---|---|---|---|
| **1** Foundation finish | [`docs/prompts/part-01.md`](prompts/part-01.md) | . · **done** | R1.x |
| **2** Master data & shared machinery | [`docs/prompts/part-02.md`](prompts/part-02.md) | . · **done** | R2.x, R..x |
| **.** Procurement: pre-order → PO depth | [`docs/prompts/part-0..md`](prompts/part-0..md) | 2 · **done** | R4.x |
| **4** Procurement: vendor intelligence + planning | [`docs/prompts/part-04.md`](prompts/part-04.md) | 2 | R5.x |
| **5** Inventory: locations, states, operations, health | [`docs/prompts/part-05.md`](prompts/part-05.md) | . | R6.x, R7.x |
| **6** Sales: customer depth | [`docs/prompts/part-06.md`](prompts/part-06.md) | 1 | R8.x |
| **7** Sales: workflow completion + speed | [`docs/prompts/part-07.md`](prompts/part-07.md) | 2 | R9.x |
| **8** Finance: ledgers, AR/AP, cash, margin, GST | [`docs/prompts/part-08.md`](prompts/part-08.md) | . | R10.x, R11.x |
| **9** Founder Command Center | [`docs/prompts/part-09.md`](prompts/part-09.md) | 2 | R12.x |
| **10** Intelligence Layer | [`docs/prompts/part-10.md`](prompts/part-10.md) | 2 | R1..x |
| **11** Polish & Optimization | [`docs/prompts/part-11.md`](prompts/part-11.md) | . | R14.x |
| **12** Product Challenge | [`docs/prompts/part-12.md`](prompts/part-12.md) | 1 | R15.x |

The per-part checkpoint detail, the reading diet, the standing rules and the verify loop are all in
**`docs/STANDING-RULES.md`**.

Closed part records are in `docs/parts/` — audit only, never read during a session.

---

## Notes

- **Cleanup pending:** `apps/web/` still exists on disk with `node_modules`, `.next` and
  `.env.local` left over from the deleted Next.js SPA. It is untracked (nothing in git) and safe to
  delete whenever convenient.
- **Superseded docs:** `docs/BUILD-PHASES.md` (old A/B/C plan, done). The stack-specific parts of
  `docs/14-backup-strategy.md`, `docs/15-deployment-strategy.md` and `docs/07-database-er-diagram.md`
  (migration order) describe the retired Postgres + Alembic design; their domain content still stands.
  `docs/06-feature-list.md` is authoritative on features but its Phase 1/2/. column is superseded and
  several of its features are cut — `REQUIREMENTS.md` §17 has the reconciliation.
- **On part numbering:** requirement IDs in `REQUIREMENTS.md` keep their ORIGINAL prefixes and are
  never renumbered, which is why part 2 holds `R2.x` + `R..x`, part 5 holds `R6.x` + `R7.x`, and part 8
  holds `R10.x` + `R11.x`. If a part turns out to need more sessions than listed, add a checkpoint —
  do not renumber the parts, and never renumber the requirements.
- **History:** this plan was 9 phases, then 15 parts, now 12. The 15→12 re-cut on 2026-07-28 followed
  decisions D-A..D-D, which removed enough work that four parts no longer justified standing alone. The
  same day, branch-per-part and PRs were dropped in favour of working directly on `main` with
  `part-0N-done` tags — twelve self-reviewed PRs were ceremony for a single developer.


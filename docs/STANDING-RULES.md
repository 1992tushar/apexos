# ApexOS - Standing rules (binding, every part)

> **This is the one rules document a session reads.** It replaces reading `docs/ROADMAP.md` mid-part.
> ROADMAP is the planning record (sequence, dependencies, notes) and is NOT needed once a part is under way.
> Extracted 2026-07-28 (Move 0) from ROADMAP's *Product decisions*, *Session protocol* and *Standing rules* sections.

Order of authority: this file and `docs/REQUIREMENTS.md` (§1 global invariants G1-G17) are binding.
`PROGRESS.md` is status. `docs/prompts/part-NN.md` is your part's brief.

---

## Product decisions that shape this plan

Settled with the user on **2026-07-28**. These are the constraints; earlier docs that assume
otherwise are wrong, not aspirational. Every cut below traces to one of these.

| # | Decision | Consequence |
|---|---|---|
| **D-A** | **No batch/lot tracking, no expiry, no FIFO.** Simple weighted-average cost. | Inventory shrinks by roughly a third. Margin is unaffected — `MarginService.gp(line)` is `selling − buying` off the purchase price snapshotted onto the line, so it never needed a valuation layer. A cost basis is needed only for the on-hand **value** figure. Stock ageing survives (it feeds the dead-stock radar) but is derived from receipt dates and is approximate — say so on screen. |
| **D-B** | **Single user — the founder.** No salespeople, no warehouse staff, no separate finance person. | Per-role permission UI is premature. The web authz guard is still worth building once as a mechanism, but exhaustively auditing and testing every route is ceremony. "Understandable without training" and printable floor documents relax to SHOULD. Accessibility narrows to labels and contrast. **Keyboard-first order entry gets *more* important, not less** — a solo operator does every order personally. |
| **D-C** | **Starting fresh — no data migration.** | CSV import drops from P0 to P2 across the board. Export stays P1 (data out for Excel is a standing need). This removed a large slice of the original shared-machinery part. |
| **D-D** | **Drop all five previously-deferred items:** QuickBooks bridge, notifications/inbox, saved views, decisions log (ADRs), SOP index. | No part owns them. `06-feature-list.md` features 11.14, 14.5, 16.15, 16.16 and X.3 are **cut, not deferred**. Reintroducing any of them is a new decision, not a backlog item. |

**Why 12 parts and not 15.** The plan was split into 15 parts before these decisions. D-A, D-B and D-C
between them removed enough work that four parts no longer justified standing alone, so the plan was
re-cut. Requirement IDs in `REQUIREMENTS.md` deliberately kept their original prefixes — a new part
number does not renumber a requirement, so today's Part 2 contains both `R2.x` and `R3.x`.

---

## Session protocol — running a part without exhausting a session

**A session is a token budget. A part is a group of sessions. They are not the same size.** Six of the
twelve parts are more than one session's work, so they are delivered over several sessions with a
**checkpoint commit** between each. 27 sessions in total, all on `main`.

### Checkpoints per part

Each `C<n>` is one session's target and ends in a commit on `main`. Only the last checkpoint of a part
tags it done.

| Part | Checkpoints |
|---|---|
| **1** Foundation finish | **C1** WS1 tests ✔ · **C2** WS2 web errors ✔ · **C3** WS3 soft delete + WS4 authz + WS5 migration decision + E501 ✔ |
| **2** Master data & shared machinery | **C1** macros + query helper + dup prevention + change history · **C2** prove on products + customers, record the R2.14 line count · **C3** roll out to the remaining 8 masters + their special cases |
| **3** Procurement core | **C1** requisition (request→approve→convert) + RFQ + quote capture + comparison · **C2** PO revisions + partial receipt + back orders + receipt-against-revision |
| **4** Vendor intelligence | **C1** mapping + vendor score + measured lead time + MOQ + price history · **C2** calendar + recommendations (R5.9's single entry point) |
| **5** Inventory | **C1** locations (warehouse→rack→bin) + stock states + **reservation as a ledger concept (R6.5/R6.6)** · **C2** weighted-average cost + ageing · **C3** operations (count/adjust/transfer) + health (ABC/dead stock/reorder reading R5.9) |
| **6** Customer depth | **C1** whole part (contacts, branches, credit limit + override, timeline) |
| **7** Sales workflow | **C1** quotation (create/revise/send/expire/convert) · **C2** returns + credit note + reservation wiring + health score + speed work |
| **8** Finance | **C1** customer/vendor ledgers + AR/AP ageing + collections + allocation · **C2** cash flow + working capital + CCC · **C3** margin by 4 dimensions + leakage + GST |
| **9** Command Center | **C1** tiles + alerts + activity + quick actions · **C2** query-count + render-time measurement, empty state, delete the placeholder |
| **10** Intelligence | **C1** the R13.1 audit + unifications (this is the real work) · **C2** radars + cockpits + forecasts + Morning Brief |
| **11** Polish | **C1** measure everything and write the findings down — no fixes · **C2** fix batch 1 (consistency, dedup, global search + Ctrl+K) · **C3** fix batch 2 (perf against C1's baselines, security review, summary) |
| **12** Product Challenge | **C1** the report. Report only, no code |

Part 11's C1 is deliberately measurement-only: R14.7/R14.8 forbid optimising without a baseline, and a
session that measures and fixes in one pass invariably loses the baseline.

### The resume block is the handoff

`PROGRESS.md` opens with a **CURRENT WORK** section holding a resume block for the part in flight, plus
the template. **Every session updates it before running out of room** — checkpoints done with their
commit SHAs, requirement IDs passed and outstanding, gotchas, mid-part decisions, and where the next
session starts. A session that dies with an accurate block costs nothing.

### Reading diet

The standing rules below are reproduced inside every part prompt, so a session does **not** need to
re-read the design corpus. Per session, read only:

1. The `PROGRESS.md` CURRENT WORK block — it names the files this checkpoint touches.
2. `docs/CODEBASE-MAP.md` — what exists and where. **Read this instead of exploring the tree.**
3. `docs/REQUIREMENTS.md` — **your part's sections only.** That is the acceptance contract.
4. `git diff <last-tag>..HEAD --stat` (e.g. `part-01-done..HEAD`) — the delta since the last part, in
   one command. Then `git log --oneline -5 --stat` if you need per-commit detail.
5. The one `08-module-breakdown.md` § named in your prompt, if you're touching that domain.
6. **The 4–6 source files you are actually going to modify.** These you read in full — you cannot
   design against a summary.

Anything beyond that only when you hit something you genuinely cannot resolve. The older `docs/` files
describe a retired stack; reaching for them mid-session usually costs more than it returns.

**The distinction that matters.** There are three reasons to read, and only one of them is unavoidable:

| Reason | Question | Cost |
|---|---|---|
| **Orientation** | What exists, where, how is it shaped? | **Should be near zero** — that's `CODEBASE-MAP.md`. A session that reads twenty files to learn the layout is re-deriving a committed document. |
| **Continuity** | What changed since last time? | **One `git diff --stat`.** Never explore for this. |
| **Working context** | What am I about to modify? | **Irreducible.** Read those files in full. |

Orientation and continuity are the waste. Working context is the job.

**Cheapest orientation of all: don't read, be told.** When a checkpoint calls something it doesn't
edit — a query helper, a uniqueness check — the resume block's `Call, don't read:` section carries the
verified signature. Four lines there replace opening a 300-line module to learn one function. So the
ideal reading list for a well-specified checkpoint is just:

1. the `PROGRESS.md` resume block (names the edit set, inlines the contracts),
2. `docs/REQUIREMENTS.md` § for your part (the rules you must not break — these are *not* in the files
   you're editing, which is why "only read what I edit" is not a complete policy on its own),
3. the edit set itself, in full.

`CODEBASE-MAP.md` is then the **fallback**, not a per-session tax — read it when starting an unfamiliar
part, or when the previous session couldn't name the edit set. Exploratory checkpoints ("find the margin
leakage indicators") genuinely can't have their files named in advance; that's when the map earns its
keep. Most checkpoints aren't like that.

**Whoever writes the resume block owes the next session that list.** Naming the edit set and inlining
the contracts takes two minutes at the end of a session and saves twenty file reads at the start of the
next one. Copy signatures from the source rather than recalling them — an inlined contract that's wrong
is worse than none, because the next session will trust it.

### Session hygiene

- **Commit at every checkpoint.** Uncommitted work dies with the session; committed work makes a blown
  session recoverable rather than restarted.
- **`pytest -q`, never verbose.** Full test output is one of the two biggest silent context drains.
- **Delegate wide searches.** When you need to find something across many files, dispatch a search
  rather than reading candidate files into the main context — you want the conclusion, not the dumps.
- **Don't re-read a file you just edited.** The edit tools error on failure; a successful edit needs no
  verification read.
- **Start each session fresh.** Continue a part via the resume block, not by carrying a long context.


---

## Standing rules — true for every part

These are already established in the codebase. A session should **follow** them, not redesign them.

**Stack (current, post stack-lightening):** FastAPI + SQLAlchemy + SQLite (`DATABASE_URL`-swappable
to Postgres for prod), server-rendered Jinja2 at `apps/api/app/web/`, no Alembic, no npm/node
anywhere in the run path. Domain logic lives in `apps/api/app/modules/<feature>/`
(model / repository / service / router / schemas). Web pages call **services directly**, never over HTTP.

**Architecture:** feature-based modules, repository pattern, thin routers + services, DI, 12-factor
config, typed `AppError` envelope, structlog + correlation-id, Pydantic v2, `ActivityService` audit
log, `EntityMixin` (soft-delete read filter) + `BusinessUnitMixin`. **Do not add abstractions that
aren't earned. Do not rebuild what exists.**

**Data rules:** money = integer minor units; keys = UUID v7; every table has audit + soft-delete +
`business_unit_id`; ledgers (`stock_movement`, `payment`, invoices, bills) are **append-only, never
mutated**; every state-changing service verb writes exactly **one** `activity_log` row in the same
transaction; nouns are data, never hardcoded (`customer_type`, `supplier_type`, … are rows).

**Schema changes:** SQLite dev self-initialises via `Base.metadata.create_all` in the `app.main`
lifespan, plus the additive-ALTER shim `_ensure_new_columns`. Add new models to the imports the
lifespan touches, and extend the seed so new screens have demo data — as a new
`app/seed/<domain>.py` section plus one call in `run()`, never by appending to `run()` itself
(see `app/seed/__init__.py`'s docstring).

**Explainability:** every score, alert, recommendation and forecast states its inputs, its formula,
its data window, and the records it reasoned from, **on screen**. Where it cannot be computed, it says
"unknown" — never a misleading default like 0 or 50. No black boxes, no decorative charts, no vanity
metrics. If a number does not change a decision, it does not belong on the page. No ML dependency and
no runtime LLM call for any number the product displays.

**Scope discipline (from D-A/D-B/D-C/D-D):** no batch/lot, no expiry, no FIFO layers; no per-role
permission UI; CSV import is P2 everywhere; QuickBooks bridge, notifications, saved views, ADR log and
SOP index are cut. A session that finds itself building one of these has drifted — stop and ask.

**Verify loop — run from `apps/api` with the venv activated, every part, no exceptions:**
```bash
# activate first — Windows: .venv\Scripts\Activate.ps1  ·  Linux/macOS: source .venv/bin/activate
python -m pytest -q                 # all green
python -m ruff check app/ tests/    # no new findings
python -m uvicorn app.main:app --port 8000
# then: every nav page 200s and renders; a bad id (e.g. /customers/<random-uuid>) renders error.html
```
Use plain `python` with the venv active rather than a hardcoded interpreter path — the build machine
is not guaranteed to be Windows.
Add tests for new behaviour in `apps/api/tests/`. Then update `PROGRESS.md` and commit to `main`.

**Name a test after the requirement it proves.** A test that verifies an `R`-number carries that
number in its name, lower-cased with an underscore:

```python
def test_r5_3_lead_time_is_measured_from_confirmed_at_to_received_at(...):
def test_r5_11_score_says_unknown_when_history_is_insufficient(...):
```

`pytest -q -k r5_` is then the evidence for Part 4, and `-k r5_3` the evidence for one requirement.
This exists so the closeout **stops hand-writing per-requirement prose tables** — Part 2's was 20
paragraphs restating what its assertions already asserted, several thousand tokens of a session's
budget spent describing tests instead of writing them. A requirement's evidence is a test node id.
Applies to new tests only; the 336 existing ones are not worth renaming.

**Repo/git:** personal GitHub only — `github.com/1992tushar/apexos`, personal credentials, never org
credentials. **One machine writes AND tests the code** — the same session that implements a change runs
pytest, ruff, and boots the app to verify it. There is no write-here/test-there split (an earlier
two-machine workflow is retired). The stack is self-contained — SQLite file + one uvicorn process, no
database server and no npm — so any machine with Python 3.11+ can do both. **All work is on `main` — no
feature branches, no PRs** (see "Git: one branch"). Commit at every checkpoint; tag `part-0N-done` when
a part completes.

**Docs to read at the start of a part (skim, they're the design record):**
`PROGRESS.md`, `docs/REQUIREMENTS.md` (**your part's sections — this is the acceptance contract**),
`docs/00-canonical-foundation.md`, `docs/08-module-breakdown.md` (the relevant §),
`docs/12-coding-standards.md`, `docs/17-design-system.md`. Note that the older `docs/` files still
describe the retired Postgres + Alembic + Next.js design — treat their *domain* content as
authoritative and their *delivery/stack* content as historical. `docs/06-feature-list.md` is
authoritative on features but its Phase column and several features are superseded or cut; see
`REQUIREMENTS.md` §17.


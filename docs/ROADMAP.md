# ApexOS — Product Roadmap & Session Prompts

> **This is the current roadmap.** `docs/BUILD-PHASES.md` is superseded (it describes the
> retired Next.js + Postgres + Alembic design; its Phases A/B/C are done).
> `PROGRESS.md` remains the source of truth for *status*; this file is the source of truth for
> *sequence*; `docs/REQUIREMENTS.md` is the source of truth for *acceptance*. Each part below has a
> self-contained prompt to paste into a fresh Claude Code session.

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

## How this is organised

The remaining work is divided into **12 parts**. Parts are the unit of delivery — one branch, one
session, one PR each.

The original roadmap put the Founder Command Center at Phase 1. **It has been resequenced** so that
procurement and inventory — the heart of the business — are built first, and every downstream module
consumes data that already exists. This minimises rework, and the cockpit is only meaningful once
real operational data flows into it.

| Part | Title | Phase | Requirements | Sessions | Tag when done | Status |
|---|---|---|---|---|---|---|
| **1** | Foundation finish | 0 | R1.x | 3 | `part-01-done` | **done** — R1.1–R1.10 all pass, tagged |
| **2** | Master data & shared machinery | 1 | R2.x, R3.x | 3 | `part-02-done` | not started |
| **3** | Procurement: pre-order → PO depth | 2 | R4.x | 2 | `part-03-done` | not started |
| **4** | Procurement: vendor intelligence + planning | 2 | R5.x | 2 | `part-04-done` | not started |
| **5** | Inventory: locations, states, operations, health | 3 | R6.x, R7.x | 3 | `part-05-done` | not started |
| **6** | Sales: customer depth | 4 | R8.x | 1 | `part-06-done` | not started |
| **7** | Sales: workflow completion + speed | 4 | R9.x | 2 | `part-07-done` | not started |
| **8** | Finance: ledgers, AR/AP, cash, margin, GST | 5 | R10.x, R11.x | 3 | `part-08-done` | not started |
| **9** | Founder Command Center | 6 | R12.x | 2 | `part-09-done` | not started |
| **10** | Intelligence Layer | 7 | R13.x | 2 | `part-10-done` | not started |
| **11** | Polish & Optimization | 8 | R14.x | 3 | `part-11-done` | not started |
| **12** | Product Challenge | X | R15.x | 1 | `part-12-done` | not started |

**12 parts · 27 sessions, of which 3 are done — 24 remaining.** A session is a token budget; a part is
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
3. `PROGRESS.md` is updated and the part's resume block is moved out of `CURRENT WORK` into the log.
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
- **Part 1 before everything.** Soft delete (WS3) and the web authz guard (WS4) are mechanisms every
  later part wires into.

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
lifespan touches, and extend `app/seed.py` so new screens have demo data.

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

---

## PROMPT — Part 1: Foundation finish (Phase 0, resume)

```
You are finishing Part 1 of 12 (Phase 0 — Foundation & Architecture) of ApexOS at
c:\Imp Data\Personal\apexos. All work happens on main — there are no feature branches and no PRs
(see "Git: one branch" in docs/ROADMAP.md). Origin is github.com/1992tushar/apexos, personal creds
only. The machine you are on both writes AND tests the code — you run pytest, ruff, and boot the app
yourself; do not hand verification off to anyone.

FIRST: git checkout main && git pull origin main.
Read docs/ROADMAP.md (standing rules + the product decisions D-A..D-D), docs/REQUIREMENTS.md §2
(requirements R1.1–R1.10 — your acceptance contract), and the memory note apexos-phase-0-foundation.
Baseline is green:
  cd apps/api   # with the venv activated — see the verify loop in the standing rules
  python -m pytest -q                  # expect 43 passed
  python -m ruff check app/ tests/     # only pre-existing E501 in untouched modules

The audit already established the foundation is strong — do NOT rebuild it or add unnecessary
abstractions. Two of five workstreams (WS1 tests, WS2 centralized web error handling) are done.
Implement the remaining three, in order, running pytest + ruff after each and adding tests for new
behaviour:

WS3 — Soft-delete write path. Only `documents` soft-deletes today; reads already filter deleted_at
  everywhere. Add ONE generic mechanism (a soft_delete(db, entity, actor_id) helper or a
  base-repository method — keep it minimal), then wire delete into the master-data entities where
  deletion is valid (customers, suppliers, products, tasks, leads, categories): service method +
  web POST route + a delete button in the list/detail template + activity log entry. DOCUMENT which
  entities are intentionally non-deletable and why (confirmed invoices/bills, posted sales/purchase
  orders, the stock ledger). Keep it minimal — do NOT pre-build Part 2's table/filter machinery.

WS4 — Web-route authorization. The JSON API guards mutations with require_permission; the Jinja UI
  does not. Add a web equivalent (e.g. require_web_permission) that renders a 403 error.html for GET
  or redirects with an err flash for POST, and wire it onto the web POST routes to mirror the API.
  NOTE (decision D-B): ApexOS has ONE user, the founder. This guard is a no-op in dev AND in prod.
  Build the mechanism once because it is cheap and establishes the prod pattern — but do NOT build a
  roles/permissions management UI, and do not gold-plate the coverage audit. R14.13/R14.14 demote the
  exhaustive route audit to SHOULD for exactly this reason.

WS5 — Migration-shim decision. app/main.py._ensure_new_columns hand-rolls additive ALTERs since
  Alembic was removed. Decide and DOCUMENT the strategy (dev SQLite: create_all + additive shim;
  prod Postgres: reintroduce Alembic via DATABASE_URL). Mostly docs; only add code if it clearly helps.

Also clean up: ~3 E501 lint nits in app/web/pages/settings.py left over from the WS2 form_action edits.

SESSION PROTOCOL — this is checkpoint C3 of 3 (C1 = WS1 tests, C2 = WS2 web errors, both done). Aim to
finish the part in this session. If you run low, commit what is green and update the CURRENT WORK
resume block in PROGRESS.md (requirement IDs passed/outstanding, gotchas, where to start next) rather
than pushing on. Read only REQUIREMENTS.md §2, the PROGRESS.md resume block, and
`git log --oneline -15`. pytest -q, never verbose.

EXIT CRITERIA (see REQUIREMENTS.md R1.1–R1.10): soft delete works from the UI on every entity where
it is valid and is refused with a clear reason where it is not; require_web_permission exists and is
wired onto the web POST routes; the migration strategy is written down; pytest + ruff green; app boots
and all nav pages 200.

FINALLY: boot the app (uvicorn app.main:app --port 8000), confirm all nav pages still 200, then
update PROGRESS.md, commit to main, and tag the part done (git tag part-01-done && git push origin
part-01-done). Update the apexos-phase-0-foundation memory note as you complete each workstream.

CAVEAT: WS2 changed GET detail handlers to let the global error handler render error.html on
not-found. Tests cover it, but when the app is booted, click a bad URL (e.g.
/customers/<random-uuid>) and eyeball the rendered error page.
```

---

## PROMPT — Part 2: Master data & shared machinery (Phase 1)

```
You are starting Part 2 of 12 (Phase 1 — Master data & shared machinery) of ApexOS at
c:\Imp Data\Personal\apexos. Part 1 (Foundation) is complete and merged to main. Read
docs/ROADMAP.md first — "Standing rules" and the product decisions D-A..D-D are binding. Then read
docs/REQUIREMENTS.md §3 and §4 (requirements R2.x and R3.x — your acceptance contract). Also read
PROGRESS.md, docs/08-module-breakdown.md (§2.1 Org/Config, §2.3 Products, §2.4 Customers,
§2.5 Suppliers), docs/12-coding-standards.md, docs/17-design-system.md.
Work on main — no branch, no PR. Start with: git checkout main && git pull origin main.

SESSION PROTOCOL — 3 checkpoints, ONE PER SESSION, each ending in a commit:
  C1 macros + query helper + dup prevention + change history
  C2 prove on products + customers, and RECORD the R2.14 line count
  C3 roll out to the remaining 8 masters + their special cases
Before you run low on room, update the CURRENT WORK resume block in PROGRESS.md: checkpoints done with
SHAs, requirement IDs passed and outstanding, gotchas, mid-part decisions, where the next session
starts. Read only REQUIREMENTS.md §3–§4, the PROGRESS.md resume block, and the module-breakdown §§
named above — the standing rules are reproduced in this prompt. Use pytest -q, never verbose.

GOAL: build ONCE the list/table machinery that parts 3–8 will all reuse, then apply it to every
master so they are complete, consistent and safe to grow on. Most masters ALREADY EXIST (see
app/modules/config, products, customers, suppliers) — this adds depth and uniformity, it is NOT a
rewrite. Audit what each master already has before adding code.

THIS PART HAS TWO STAGES AND THE ORDER IS THE POINT. Do not roll out first and generalise later —
that path ends in copy-paste, and five later parts inherit it.

STAGE 1 — the machinery (build, then prove on exactly TWO masters):
1. A reusable list/table pattern as macros in app/web/templates/_macros.html: search box, filter
   chips, sortable headers, pagination controls. Driven by declarative per-page config (columns,
   filters, default sort), NOT copy-pasted markup. Query-string driven (?q=&sort=&dir=&page=&<filter>=)
   so links and the back button behave.
2. One generic paginated/filtered/sorted query helper in the repository layer, composing with the
   EntityMixin soft-delete read filter and business_unit scoping. Pages must not hand-roll
   LIMIT/OFFSET or ORDER BY.
3. One generic CSV EXPORT path over that helper, so an export respects the filters on screen.
4. One duplicate-prevention approach: natural-key uniqueness plus a pre-save check surfacing a clean
   field-level error, not an IntegrityError or a 500. Applied per entity via configuration.
5. Change history: derive from the existing activity_log wherever possible. Only add a table if
   activity_log provably cannot answer "what changed on this record, when, by whom" — and if you do,
   say in PROGRESS.md why it was insufficient.

CSV IMPORT IS P2, NOT P0 (decision D-C: there is no data to migrate, we start fresh). Build it only
if stages 1 and 2 are fully done and green, and keep it minimal if you do. Do NOT let import shape
the design of the machinery.

Prove stage 1 on TWO masters (suggest products and customers) end to end: list with search + filter
+ sort + pagination, export, duplicate rejection, change-history panel. Then RECORD IN PROGRESS.md
how many lines of new code the SECOND master needed — a third master must be achievable in well
under 100 lines. That number is the gate for stage 2.

STAGE 2 — roll out to every master:
  business units, categories + subcategories (self-referencing tree), products, brands,
  manufacturers, warehouses, units of measure (+ conversions), tax masters (versioned slabs),
  customers, suppliers.

Each must uniformly support: search, filters, sorting, pagination, CSV export, audit trail, status
(active/inactive), soft delete (the part 1 mechanism), change history, validation, relationship
integrity, duplicate prevention. Via the stage-1 machinery — NOT bespoke code. If a master needs
substantially more code than your recorded figure, STOP and improve the machinery rather than working
around it, then say so in PROGRESS.md.

Where a master needs more than the generic treatment, build only that:
  - categories: reparent with cycle prevention, tree rendering, business-unit rollup.
  - uom_conversion: non-zero and non-cyclic factor validation.
  - tax_rate: versioned slabs — a new slab appends, never edits history.
  - relationship integrity: block or clearly explain deletion/deactivation of a master still
    referenced by live transactions (e.g. a product on an open PO). Never silently cascade.

DO NOT BUILD (decision D-B — ApexOS has one user, the founder): roles and permissions management
screens. Features 16.12 and 16.13 in docs/06-feature-list.md are cut.

Extend app/seed.py so each master has enough rows to exercise search/filter/pagination (hundreds for
products and customers, not five), including a multi-level category tree and at least two tax slab
versions.

Add tests: the query helper (filter + sort + pagination boundaries, soft-deleted rows excluded),
export respects active filters, duplicate rejection returns a field error not a 500, per-master list
filtering, category reparent rejects a cycle, uom conversion rejects zero/cyclic factors, tax slab
append preserves the prior version, soft delete then absent-from-list, blocked deletion of a
referenced master explains why.

Follow the ROADMAP verify loop, update PROGRESS.md, and commit directly to main — no branch, no PR
(see "Git: one branch" in docs/ROADMAP.md). When every P0/P1 requirement for the part passes, tag it
(git tag part-0N-done && git push origin part-0N-done). Update memory.
```

---

## PROMPT — Part 3: Procurement — pre-order → PO depth (Phase 2, first half)

```
You are starting Part 3 of 12 (Phase 2 — Procurement core) of ApexOS at
c:\Imp Data\Personal\apexos. Parts 1–2 are complete and merged. Read docs/ROADMAP.md first —
"Standing rules" and decisions D-A..D-D are binding. Then read docs/REQUIREMENTS.md §5 (R4.x — your
acceptance contract). Also read PROGRESS.md, docs/08-module-breakdown.md (§2.5 Suppliers/Procurement,
§2.6 Pricing). Work on main — no branch, no PR: git checkout main && git pull origin main.

SESSION PROTOCOL — 2 checkpoints, ONE PER SESSION, each ending in a commit:
  C1 requisition (request → approve → convert) + RFQ + quote capture + comparison
  C2 PO revisions + partial receipt + back orders + receipt-against-revision
Before you run low on room, update the CURRENT WORK resume block in PROGRESS.md (checkpoints + SHAs,
requirement IDs passed/outstanding, gotchas, mid-part decisions, where to start next). Read only
REQUIREMENTS.md §5, the PROGRESS.md resume block, and the module-breakdown §§ above. pytest -q.

GOAL: procurement is the heart of ApexOS. Make the buy-side workflow deep and extremely efficient —
the fewest clicks and keystrokes to get from "we need this" to "it's ordered and received".

WHAT EXISTS: app/modules/procurement (purchase_order, purchase_order_line, goods_receipt +
confirm/receive), app/modules/suppliers (supplier, contacts, evaluation), app/modules/pricing
(purchase_price). Web pages: /purchase-orders, /procurement, /suppliers. Extend these; do not rebuild.

BUILD:
1. Pre-order flow: purchase requisition (request → approve → convert to PO or RFQ), RFQ to multiple
   suppliers, quotation capture, side-by-side vendor comparison (price / lead time / MOQ / score),
   quotation history per product+supplier. Approval is a state change with an actor and a reason —
   one activity_log row each.
2. PO depth: PO revisions (versioned, append-only — never mutate a confirmed PO in place; each
   revision is a new version with a reason and an activity_log row), partial receipt, back orders
   (open quantity DERIVED as ordered − received, never a stored counter), receipt against a specific
   revision — and receipt against a superseded revision handled explicitly, not silently accepted.

UI: extend /purchase-orders and /procurement; add requisition, RFQ and comparison screens. Optimise
for speed — keyboard-first entry, product search-as-you-type, sensible defaults from history, bulk
line entry. Reuse the part 2 table/filter/pagination macros; do not hand-roll list markup.

Ledger discipline: goods receipt posts stock IN through the existing InventoryService.post_movement
(the ONLY stock writer). Receipts and revisions are append-only.

HANDOFF TO PART 4 (this is a requirement, R4.11): persist the timestamps part 4 needs — PO confirm
and each receipt — so lead time can be MEASURED there rather than typed in. Do NOT build vendor
scoring here; part 4 owns it.

Seed a requisition awaiting approval, an approved requisition converted to a PO, an RFQ with 2
supplier quotes, a revised PO, and a partial receipt with an outstanding back order.

Add tests: requisition→PO conversion, approval writes exactly one activity_log row, RFQ→quote
comparison pick, PO revision preserves the prior version verbatim, partial receipt leaves the correct
back-order quantity, receipt against a superseded revision is handled explicitly.

Follow the ROADMAP verify loop, update PROGRESS.md, and commit directly to main — no branch, no PR
(see "Git: one branch" in docs/ROADMAP.md). When every P0/P1 requirement for the part passes, tag it
(git tag part-0N-done && git push origin part-0N-done). Update memory.
```

---

## PROMPT — Part 4: Procurement — vendor intelligence + planning (Phase 2, second half)

```
You are starting Part 4 of 12 (Phase 2 — Vendor intelligence & planning) of ApexOS at
c:\Imp Data\Personal\apexos. Parts 1–3 are complete and merged, so requisitions, RFQs, quotes, PO
revisions and partial receipts all exist with real history. Read docs/ROADMAP.md first — "Standing
rules" and decisions D-A..D-D are binding. Then read docs/REQUIREMENTS.md §6 (R5.x — your acceptance
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

Follow the ROADMAP verify loop, update PROGRESS.md, and commit directly to main — no branch, no PR
(see "Git: one branch" in docs/ROADMAP.md). When every P0/P1 requirement for the part passes, tag it
(git tag part-0N-done && git push origin part-0N-done). Update memory.
```

---

## PROMPT — Part 5: Inventory — locations, states, operations, health (Phase 3)

```
You are starting Part 5 of 12 (Phase 3 — Inventory) of ApexOS at c:\Imp Data\Personal\apexos.
Parts 1–4 are complete and merged. Read docs/ROADMAP.md first — "Standing rules" and decisions
D-A..D-D are binding. Then read docs/REQUIREMENTS.md §7 and §8 (R6.x and R7.x — your acceptance
contract). Also read PROGRESS.md, docs/08-module-breakdown.md (§2.8 Inventory/Warehouse),
Work on main — no branch, no PR: git checkout main && git pull origin main.

SESSION PROTOCOL — 3 checkpoints, ONE PER SESSION, each ending in a commit:
  C1 locations (warehouse→rack→bin) + stock states + RESERVATION AS A LEDGER CONCEPT (R6.5/R6.6)
  C2 weighted-average cost + stock ageing
  C3 operations (count / adjust / transfer) + health (ABC, dead stock, reorder reading R5.9)
C1 is the checkpoint that matters — part 7 calls the reservation verb, so a wrong model here forces
rework there. Do not rush it to reach C2. Before you run low on room, update the CURRENT WORK resume
block in PROGRESS.md (checkpoints + SHAs, requirement IDs passed/outstanding, gotchas, mid-part
decisions — R6.3's location-nullability choice belongs there — and where to start next). Read only
REQUIREMENTS.md §7–§8, the PROGRESS.md resume block, and the module-breakdown § above. pytest -q.

GOAL: inventory must answer three questions — What do we have? Where is it? What is it worth?

READ DECISION D-A FIRST, IT CUTS A THIRD OF THE ORIGINAL SCOPE: there is NO batch/lot tracking, NO
expiry, and NO FIFO. Do not build them. Cost basis is simple WEIGHTED AVERAGE from movement history,
and it is needed only for the on-hand VALUE figure. Margin does not depend on it — MarginService.gp()
is selling − buying off the purchase price snapshotted onto the line. Requirements R6.7, R6.8 and R6.9
are struck; R6.16 (weighted average) replaces them.

WHAT EXISTS: app/modules/inventory (stock_movement ledger, post_movement as the single writer,
derived balances), multi-warehouse + transfer/adjust/count from an earlier phase. Web pages:
/inventory, /warehouse. Extend; do not rebuild. Balances stay DERIVED from the ledger — never a
stored mutable quantity.

BUILD:
1. Location depth: warehouse → rack location → bin, with stock addressed to a bin and the location
   carried on stock ledger entries. Existing movements without a location must keep working —
   backfill to a default bin per warehouse, or make location nullable with a documented meaning.
   Decide and say which in PROGRESS.md. Bin-level stock must roll up correctly to rack and warehouse.
2. Stock states, distinctly reported: available, reserved (committed to sales orders), in transit
   (between warehouses), damaged/quarantined. RESERVATION MUST BE A LEDGER CONCEPT, NOT A FLAG — an
   append-only entry that reduces available without reducing on-hand, released or consumed by a later
   entry. There must be no boolean "reserved" column.
   *** PART 7 CALLS THIS AT SALES-ORDER CONFIRM. Expose it as a clear service verb (R6.6). Getting
   this model wrong is the one mistake in this part that forces rework later. ***
3. Valuation: weighted-average cost from movement history, feeding the on-hand value figure.
4. Stock age buckets, derived from receipt dates on the ledger. Without lots this is APPROXIMATE —
   state the approximation on screen rather than implying precision. It feeds the dead-stock radar,
   which is why it survives D-A.
5. Operations: cycle count (count sheet → variance → adjustment), stock adjustment with a mandatory
   reason, warehouse transfer (two movements with in-transit between them, so stock is never
   invisible mid-flight). A count that matches produces NO adjustment movement; a variance produces
   exactly ONE. All operations write through InventoryService.post_movement — the single writer.
6. Inventory health, all explainable: ABC analysis (state the class boundaries), dead stock radar
   (state the window), fast/slow moving, reorder suggestions, low-stock alerts. Each must show the
   numbers it reasoned from and link to the affected records.

CONSOLIDATE, DO NOT DUPLICATE (requirement R7.11): part 4 already built purchase recommendations from
reorder level + open POs + measured lead time. The reorder suggestions here MUST READ that service
(R5.9), not reimplement it. If the two genuinely differ, unify them into one parameterised engine both
screens read, and say in PROGRESS.md what you unified. A test (R7.13) must prove both return identical
output for the same product. Part 10 will audit exactly this.

UI: extend /inventory and /warehouse — stock-by-location, ageing, health views, plus the count and
adjustment flows. Reuse the part 2 macros. Note decision D-B: the founder is the only user, so
"understandable without training" and printable count sheets are SHOULD, not MUST — but plain labels
and no jargon are still the house style.

Seed: two warehouses with racks and bins, a reservation against a confirmed sales order, an in-transit
transfer awaiting receipt, a completed cycle count with a variance plus one with none, dead stock, a
fast mover, and enough movement history for ABC classes and weighted-average cost to be non-trivial.
Do NOT seed batches or expiry dates — they no longer exist.

Add tests: reservation reduces available but not on-hand, release restores available, weighted-average
cost against hand-computed values, ageing bucket boundaries, bin→rack→warehouse rollup, post_movement
is still the only stock writer, variance produces exactly one adjustment, zero-variance produces none,
adjustment requires a reason, transfer sits in-transit then lands, ABC boundaries, dead-stock window
boundary, and R7.13 (reorder suggestion identical to part 4's engine).

Follow the ROADMAP verify loop, update PROGRESS.md, and commit directly to main — no branch, no PR
(see "Git: one branch" in docs/ROADMAP.md). When every P0/P1 requirement for the part passes, tag it
(git tag part-0N-done && git push origin part-0N-done). Update memory.
```

---

## PROMPT — Part 6: Sales — customer depth (Phase 4, first half)

```
You are starting Part 6 of 12 (Phase 4 — Customer depth) of ApexOS at c:\Imp Data\Personal\apexos.
Parts 1–5 are complete and merged. Read docs/ROADMAP.md first — "Standing rules" and decisions
D-A..D-D are binding. Then read docs/REQUIREMENTS.md §9 (R8.x — your acceptance contract). Also read
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

Follow the ROADMAP verify loop, update PROGRESS.md, and commit directly to main — no branch, no PR
(see "Git: one branch" in docs/ROADMAP.md). When every P0/P1 requirement for the part passes, tag it
(git tag part-0N-done && git push origin part-0N-done). Update memory.
```

---

## PROMPT — Part 7: Sales — workflow completion + speed (Phase 4, second half)

```
You are starting Part 7 of 12 (Phase 4 — Sales workflow & speed) of ApexOS at
c:\Imp Data\Personal\apexos. Parts 1–6 are complete and merged. Read docs/ROADMAP.md first —
"Standing rules" and decisions D-A..D-D are binding. Then read docs/REQUIREMENTS.md §10 (R9.x — your
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
2. Returns and credit notes: a return posts stock IN through InventoryService.post_movement and
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

Follow the ROADMAP verify loop, update PROGRESS.md, and commit directly to main — no branch, no PR
(see "Git: one branch" in docs/ROADMAP.md). When every P0/P1 requirement for the part passes, tag it
(git tag part-0N-done && git push origin part-0N-done). Update memory.
```

---

## PROMPT — Part 8: Finance — ledgers, AR/AP, cash, margin, GST (Phase 5)

```
You are starting Part 8 of 12 (Phase 5 — Finance) of ApexOS at c:\Imp Data\Personal\apexos.
Parts 1–7 are complete and merged, so sales, purchases, receipts, returns and credit notes all
produce real financial history. Read docs/ROADMAP.md first — "Standing rules" and decisions D-A..D-D
are binding. Then read docs/REQUIREMENTS.md §11 and §12 (R10.x and R11.x — your acceptance contract).
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

Follow the ROADMAP verify loop, update PROGRESS.md, and commit directly to main — no branch, no PR
(see "Git: one branch" in docs/ROADMAP.md). When every P0/P1 requirement for the part passes, tag it
(git tag part-0N-done && git push origin part-0N-done). Update memory.
```

---

## PROMPT — Part 9: Founder Command Center (Phase 6)

```
You are starting Part 9 of 12 (Phase 6 — Founder Command Center) of ApexOS at
c:\Imp Data\Personal\apexos. Parts 1–8 are complete and merged, so real operational data now exists
across procurement, inventory, sales and finance. Read docs/ROADMAP.md first — "Standing rules" and
decisions D-A..D-D are binding. Then read docs/REQUIREMENTS.md §13 (R12.x — your acceptance
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

Follow the ROADMAP verify loop, update PROGRESS.md, and commit directly to main — no branch, no PR
(see "Git: one branch" in docs/ROADMAP.md). When every P0/P1 requirement for the part passes, tag it
(git tag part-0N-done && git push origin part-0N-done). Update memory.
```

---

## PROMPT — Part 10: Intelligence Layer (Phase 7)

```
You are starting Part 10 of 12 (Phase 7 — Apex Intelligence) of ApexOS at
c:\Imp Data\Personal\apexos. Parts 1–9 are complete and merged. Read docs/ROADMAP.md first —
"Standing rules" and decisions D-A..D-D are binding. Then read docs/REQUIREMENTS.md §14 (R13.x — your
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

Follow the ROADMAP verify loop, update PROGRESS.md, and commit directly to main — no branch, no PR
(see "Git: one branch" in docs/ROADMAP.md). When every P0/P1 requirement for the part passes, tag it
(git tag part-0N-done && git push origin part-0N-done). Update memory.
```

---

## PROMPT — Part 11: Polish & Optimization (Phase 8)

```
You are starting Part 11 of 12 (Phase 8 — Polish & Optimization) of ApexOS at
c:\Imp Data\Personal\apexos. Parts 1–10 are complete and merged — the product is feature-complete.
Read docs/ROADMAP.md first — "Standing rules" and decisions D-A..D-D are binding. Then read
docs/REQUIREMENTS.md §15 (R14.x — your acceptance contract). Also read PROGRESS.md and
docs/17-design-system.md. Work on main — no branch, no PR: git checkout main && git pull origin main.

SESSION PROTOCOL — 3 checkpoints, ONE PER SESSION, each ending in a commit:
  C1 MEASURE EVERYTHING and write the findings down — NO FIXES IN THIS SESSION
  C2 fix batch 1 — UI consistency, de-duplication, global search + Ctrl+K palette
  C3 fix batch 2 — perf against C1's baselines, security review, the written summary
C1 is measurement-only on purpose: R14.7/R14.8 forbid optimising without a baseline, and a session that
measures and fixes in one pass invariably loses the baseline. Put every number from C1 into the
PROGRESS.md resume block — C3 is graded against them. Read only REQUIREMENTS.md §15, the PROGRESS.md
resume block, and the design system. pytest -q.

GOAL: make ApexOS feel like a premium internal operating system. Add NO new features. If you find
yourself designing a new screen, stop — that belongs nowhere.

READ DECISION D-B, IT RESIZES THIS PART: the founder is the only user. Accessibility narrows to form
labels and contrast — the screen-reader table work is cut. The exhaustive per-route authz audit and
the "every POST route is guarded" test are demoted to SHOULD (R14.13, R14.14): the guard mechanism
from part 1 exists and that is what matters with one user. Saved views are CUT (decision D-D).

IMPROVE:
  Experience — UI consistency (one spacing/type/colour system actually applied everywhere), UX flow,
    form labels and contrast, full keyboard navigation, responsive layout down to a tablet.
  Findability — global search across every entity, and a command palette (Ctrl+K) for
    navigate-and-act without the mouse. For a solo operator who lives in this app daily, these two
    are the highest-value items in the part.
  Speed — MEASURE FIRST, then fix: page timings, N+1 queries, missing indexes, template render cost,
    static asset size, all baselined BEFORE any change. Report before/after numbers; do not
    "optimise" without a measurement.
  Code — de-duplicate: by now EVERY list screen should be going through part 2's macros. Find the ones
    that are not and migrate them. Simplify workflows, count and reduce clicks on the top-10 most
    frequent tasks (report both numbers), delete unnecessary screens, tighten developer experience
    (one-command run, fast tests).
  Security — input validation, file-upload handling, error messages that don't leak internals,
    dependency audit for known vulnerabilities.

Method: audit → write down the findings with evidence → fix in reviewable batches → prove it with
measurements. Deliver a short written summary of what changed and what was measured.

The full test suite must stay green throughout — this part must not change behaviour, only its
quality. Add tests where refactors created risk, especially the de-duplication work.

Follow the ROADMAP verify loop, update PROGRESS.md, and commit directly to main — no branch, no PR
(see "Git: one branch" in docs/ROADMAP.md). When every P0/P1 requirement for the part passes, tag it
(git tag part-0N-done && git push origin part-0N-done). Update memory.
```

---

## PROMPT — Part 12: Product Challenge (Phase X)

```
You are running Part 12 of 12 (Phase X — Product Challenge) on ApexOS at
c:\Imp Data\Personal\apexos. Parts 1–11 are complete. Read docs/ROADMAP.md, docs/REQUIREMENTS.md §16
(R15.x) and PROGRESS.md.

SESSION PROTOCOL — 1 checkpoint, and it produces no code. Budget your room for READING the product and
WRITING the report; if you run low, commit the report as far as it goes with a note on which screens
are still unreviewed. Read the app itself (nav + templates + services) rather than the design docs —
this review is about what exists, not what was intended.

Forget that this codebase was built with your help. Pretend a different company hired you to REPLACE
it, and you are being paid to be right, not agreeable.

Review every screen and every feature. For each one, answer:
  - Should this exist at all?
  - Can it be merged into another screen?
  - Can it be simplified?
  - Can it be removed outright?
  - Would a FOUNDER actually use it? How often?
  - Would an OPERATIONS executive use it?
  - Would a PROCUREMENT executive use it?
  - Would a WAREHOUSE employee understand it without training?

NOTE on those last three seats: decision D-B means only the founder uses ApexOS today. Keep asking
the other three questions anyway — they are the test of whether a screen could survive the business
growing — but be honest that today they are hypothetical, and do not justify a screen's existence by
a user who does not exist yet.

Challenge every decision, including the architectural ones, and including decisions D-A..D-D
themselves — if dropping FIFO or batch tracking turned out to be wrong, say so with evidence. Name
the things that exist because they were on a roadmap rather than because someone needs them. Be
specific: cite the file and the screen, say what you would cut, and say what breaks if you cut it.

The goal is NOT more features. The goal is the simplest, most powerful operating system for a
procurement company. Fewer, sharper screens beat comprehensive ones.

START BY WRITING THE REVIEW ONLY — no code changes. Deliver a prioritised report:
  1. Cut (with the blast radius of each cut)
  2. Merge (which screens collapse into which)
  3. Simplify (the specific reduction)
  4. Keep as-is (and why it earns its place)
Then STOP and wait for a decision on what to act on. Do not start deleting.
```

---

## Notes

- **Cleanup pending:** `apps/web/` still exists on disk with `node_modules`, `.next` and
  `.env.local` left over from the deleted Next.js SPA. It is untracked (nothing in git) and safe to
  delete whenever convenient.
- **Superseded docs:** `docs/BUILD-PHASES.md` (old A/B/C plan, done). The stack-specific parts of
  `docs/14-backup-strategy.md`, `docs/15-deployment-strategy.md` and `docs/07-database-er-diagram.md`
  (migration order) describe the retired Postgres + Alembic design; their domain content still stands.
  `docs/06-feature-list.md` is authoritative on features but its Phase 1/2/3 column is superseded and
  several of its features are cut — `REQUIREMENTS.md` §17 has the reconciliation.
- **On part numbering:** requirement IDs in `REQUIREMENTS.md` keep their ORIGINAL prefixes and are
  never renumbered, which is why part 2 holds `R2.x` + `R3.x`, part 5 holds `R6.x` + `R7.x`, and part 8
  holds `R10.x` + `R11.x`. If a part turns out to need more sessions than listed, add a checkpoint —
  do not renumber the parts, and never renumber the requirements.
- **History:** this plan was 9 phases, then 15 parts, now 12. The 15→12 re-cut on 2026-07-28 followed
  decisions D-A..D-D, which removed enough work that four parts no longer justified standing alone. The
  same day, branch-per-part and PRs were dropped in favour of working directly on `main` with
  `part-0N-done` tags — twelve self-reviewed PRs were ceremony for a single developer.

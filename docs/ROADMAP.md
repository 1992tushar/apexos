# ApexOS — Product Roadmap & Session Prompts

> **This is the current roadmap.** `docs/BUILD-PHASES.md` is superseded (it describes the
> retired Next.js + Postgres + Alembic design; its Phases A/B/C are done).
> `PROGRESS.md` remains the source of truth for *status*; this file is the source of truth for
> *sequence*. Each part below has a self-contained prompt to paste into a fresh Claude Code session.

---

## How this is organised

The remaining work is divided into **15 parts**. Parts are the unit of delivery — one branch, one
session, one PR each. Parts map onto the nine original phases: the four single-session phases at the
tail stay whole, and each of the five large module phases is split in two — **depth first, then the
intelligence that reads it**.

The original roadmap put the Founder Command Center at Phase 1. **It has been resequenced** so that
procurement and inventory — the heart of the business — are built first, and every downstream module
consumes data that already exists. This minimises rework, and the cockpit is only meaningful once
real operational data flows into it.

| Part | Title | Phase | Branch | Status |
|---|---|---|---|---|
| **1** | Foundation finish | 0 | `phase-0/foundation-sweep` | **in progress** — WS1, WS2 done; WS3–WS5 remaining |
| **2** | Shared list & data machinery | 1 | `phase-1/shared-machinery` | not started |
| **3** | Masters made uniform | 1 | `phase-1/masters-uniform` | not started |
| **4** | Procurement: pre-order → PO depth | 2 | `phase-2/procurement-core` | not started |
| **5** | Procurement: vendor intelligence + planning | 2 | `phase-2/vendor-intelligence` | not started |
| **6** | Inventory: locations, states, traceability | 3 | `phase-3/inventory-core` | not started |
| **7** | Inventory: operations + health | 3 | `phase-3/inventory-ops-health` | not started |
| **8** | Sales: customer depth | 4 | `phase-4/customer-depth` | not started |
| **9** | Sales: workflow completion + speed | 4 | `phase-4/sales-workflow` | not started |
| **10** | Finance: ledgers + AR/AP | 5 | `phase-5/ledgers-arap` | not started |
| **11** | Finance: cash, margin, GST | 5 | `phase-5/cash-margin-gst` | not started |
| **12** | Founder Command Center | 6 | `phase-6/command-center` | not started |
| **13** | Intelligence Layer | 7 | `phase-7/intelligence` | not started |
| **14** | Polish & Optimization | 8 | `phase-8/polish` | not started |
| **15** | Product Challenge | X | `phase-x/product-challenge` | not started |

Each part ends green (tests + lint + app boots + all nav pages 200), updates `PROGRESS.md`, and
opens a PR to `main`.

### Dependencies that must not be reordered

- **Part 2 is load-bearing.** If its machinery is not genuinely reusable, parts 3, 5, 7, 9, 10 and 11
  each re-invent tables, filters and CSV handling. It is the one part worth over-investing in.
- **Part 6 before part 9.** Sales-order reservation (part 9) needs reservation to exist as a ledger
  concept (part 6) first. Building 9 first would produce a boolean flag that then has to be undone.
- **Parts 12 and 13 read; they do not compute.** Both consume the projections built in parts 5, 7, 10
  and 11. If either one starts recomputing business logic, the earlier part was left incomplete —
  fix it there instead.
- **Part 1 before everything.** Soft-delete (WS3) and the web authz guard (WS4) are mechanisms that
  every later part wires into.

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

**Explainability:** every score, alert, recommendation and forecast states its inputs, its formula
and the records it reasoned from, **on screen**. No black boxes, no decorative charts, no vanity
metrics. If a number does not change a decision, it does not belong on the page.

**Verify loop — run from `apps/api`, every part, no exceptions:**
```bash
./.venv/Scripts/python.exe -m pytest -q                 # all green
./.venv/Scripts/python.exe -m ruff check app/ tests/    # no new findings
./.venv/Scripts/python.exe -m uvicorn app.main:app --port 8000
# then: every nav page 200s and renders; a bad id (e.g. /customers/<random-uuid>) renders error.html
```
Add tests for new behaviour in `apps/api/tests/`. Then update `PROGRESS.md`, commit, open a PR to `main`.

**Repo/git:** personal GitHub only — `github.com/1992tushar/apexos`, personal credentials, never org
credentials. This machine both writes and tests the code.

**Docs to read at the start of a part (skim, they're the design record):**
`PROGRESS.md`, `docs/00-canonical-foundation.md`, `docs/08-module-breakdown.md` (the relevant §),
`docs/12-coding-standards.md`, `docs/17-design-system.md`. Note that the older `docs/` files still
describe the retired Postgres + Alembic + Next.js design — treat their *domain* content as
authoritative and their *delivery/stack* content as historical.

---

## PROMPT — Part 1: Foundation finish (Phase 0, resume)

```
You are finishing Part 1 of 15 (Phase 0 — Foundation & Architecture) of ApexOS at
c:\Imp Data\Personal\apexos. Work continues on the existing branch phase-0/foundation-sweep (already
pushed to origin, github.com/1992tushar/apexos — personal creds only). This machine both writes and
tests the code.

FIRST: git checkout phase-0/foundation-sweep && git pull origin phase-0/foundation-sweep.
Read docs/ROADMAP.md (standing rules) and the memory note apexos-phase-0-foundation for context.
Baseline is green:
  cd apps/api && ./.venv/Scripts/python.exe -m pytest -q   # expect 43 passed
  ./.venv/Scripts/python.exe -m ruff check app/ tests/     # only pre-existing E501 in untouched modules

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
  It is a no-op in dev (the dev actor has "*") but establishes the prod pattern.

WS5 — Migration-shim decision. app/main.py._ensure_new_columns hand-rolls additive ALTERs since
  Alembic was removed. Decide and DOCUMENT the strategy (dev SQLite: create_all + additive shim;
  prod Postgres: reintroduce Alembic via DATABASE_URL). Mostly docs; only add code if it clearly helps.

Also clean up: ~3 E501 lint nits in app/web/pages/settings.py left over from the WS2 form_action edits.

EXIT CRITERIA: soft delete works from the UI on every entity where it is valid and is refused (with a
clear reason) where it is not; require_web_permission exists and is wired onto every web POST route;
the migration strategy is written down; pytest + ruff green; app boots and all nav pages 200.

FINALLY: boot the app (uvicorn app.main:app --port 8000), confirm all nav pages still 200, then
update PROGRESS.md, commit, and open a PR to main. Update the apexos-phase-0-foundation memory note
as you complete each workstream.

CAVEAT: WS2 changed GET detail handlers to let the global error handler render error.html on
not-found. Tests cover it, but when the app is booted, click a bad URL (e.g.
/customers/<random-uuid>) and eyeball the rendered error page.
```

---

## PROMPT — Part 2: Shared list & data machinery (Phase 1a)

```
You are starting Part 2 of 15 (Phase 1a — Shared list & data machinery) of ApexOS at
c:\Imp Data\Personal\apexos. Part 1 (Foundation) is complete and merged to main. Read docs/ROADMAP.md
first — the "Standing rules" section is binding. Also read PROGRESS.md, docs/12-coding-standards.md,
docs/17-design-system.md. Branch: phase-1/shared-machinery off main.

GOAL: build ONCE the machinery that every master-data and transactional list screen in parts 3, 5, 7,
9, 10 and 11 will reuse. This part ships almost no new domain features — its deliverable is
infrastructure plus proof that the infrastructure works. THIS PART IS LOAD-BEARING: if the machinery
is not genuinely reusable, six later parts will each re-invent it.

BUILD:
1. A reusable list/table pattern as macros in app/web/templates/_macros.html: search box, filter
   chips, sortable column headers, pagination controls. Driven by declarative config passed from the
   page (columns, filters, default sort) — NOT copy-pasted markup per entity. Query-string driven
   (?q=&sort=&dir=&page=&<filter>=) so links and back-button behave.
2. One generic paginated/filtered/sorted query helper in the repository layer so pages do not
   hand-roll LIMIT/OFFSET and ORDER BY. Must compose with the EntityMixin soft-delete read filter and
   business_unit scoping.
3. One generic CSV import path: validating, per-row error reporting (row number + field + message),
   idempotent re-run, all-or-nothing per batch. Entity-specific behaviour comes from configuration
   (column map, required fields, resolvers for foreign keys), not a bespoke importer per entity.
4. One generic CSV export path over the same query helper, so an export respects the filters
   currently applied on screen.
5. One duplicate-prevention approach: natural-key uniqueness plus a pre-save check that surfaces a
   clean field-level error rather than an IntegrityError. Applied per entity via configuration.
6. Change history: derive it from the existing activity_log wherever possible. Only add a new table
   if the activity_log genuinely cannot answer "what changed on this record, when, by whom" — and if
   you do add one, say in PROGRESS.md why the activity_log was insufficient.

PROVE IT on exactly TWO existing masters (suggest products and customers) end to end: list with
search + filter + sort + pagination, CSV import with a deliberate bad row, CSV export, duplicate
rejection, change-history panel. Do NOT roll it out to the other masters — that is part 3. Resist
adding domain features here; if you find yourself designing a new screen, it belongs in part 3.

Extend app/seed.py so products and customers have enough rows to make pagination and filtering real
(hundreds, not five).

Add tests: the query helper (filter + sort + pagination boundaries, soft-deleted rows excluded),
import happy path, import with row errors reports every bad row and commits nothing, export respects
active filters, duplicate rejection returns a field error not a 500.

EXIT CRITERIA: a third master could be given the full treatment in well under 100 lines of new code.
State in PROGRESS.md how many lines the second master needed — that number is the reusability proof
that part 3 depends on.

Follow the ROADMAP verify loop, update PROGRESS.md, commit, open a PR to main, update memory.
```

---

## PROMPT — Part 3: Masters made uniform (Phase 1b)

```
You are starting Part 3 of 15 (Phase 1b — Masters made uniform) of ApexOS at
c:\Imp Data\Personal\apexos. Parts 1–2 are complete and merged. Read docs/ROADMAP.md first —
"Standing rules" is binding. Also read PROGRESS.md, docs/08-module-breakdown.md (§2.1 Org/Config,
§2.3 Products, §2.4 Customers, §2.5 Suppliers), docs/12-coding-standards.md, docs/17-design-system.md.
Branch: phase-1/masters-uniform off main.

GOAL: make every master-data entity complete, consistent, and safe to grow on, by applying the part 2
machinery everywhere. Most of these entities ALREADY EXIST (see app/modules/config, products,
customers, suppliers). This is depth and uniformity — it is NOT a rewrite. Audit what each master
already has before adding code.

MASTERS in scope: business units, categories + subcategories (self-referencing tree), products,
brands, manufacturers, warehouses, units of measure (+ conversions), tax masters (versioned slabs),
customers, suppliers.

Each master must support, uniformly, using the part 2 macros/helpers — NOT bespoke code:
  search, filters, sorting, pagination, CSV import, CSV export, audit trail, status
  (active/inactive), soft delete (the part 1 mechanism), change history, validation,
  relationship integrity, duplicate prevention.

WHERE A MASTER NEEDS MORE THAN THE GENERIC TREATMENT, build only that:
  - categories: reparent with cycle prevention, tree rendering, business-unit rollup.
  - uom_conversion: non-zero and non-cyclic factor validation.
  - tax_rate: versioned slabs — new slab appends, never edits history.
  - relationship integrity: block or clearly explain deletion/deactivation of a master still
    referenced by live transactions (e.g. a product on an open PO). Do not silently cascade.

If applying the machinery to a master takes substantially more code than part 2's proof suggested,
STOP and improve the machinery instead of working around it — then say so in PROGRESS.md.

Extend app/seed.py so each master has enough rows to exercise search/filter/pagination, including a
multi-level category tree and at least two tax slab versions.

Add tests: per-master list filtering, category reparent rejects a cycle, uom conversion rejects a
zero/cyclic factor, tax slab append preserves the prior version, duplicate rejection per master,
soft delete then absent-from-list, blocked deletion of a referenced master explains why, one export.

EXIT CRITERIA: no master is missing any item from the uniform list; nothing in the list is
implemented twice.

Follow the ROADMAP verify loop, update PROGRESS.md, commit, open a PR to main, update memory.
```

---

## PROMPT — Part 4: Procurement — pre-order → PO depth (Phase 2, first half)

```
You are starting Part 4 of 15 (Phase 2 — Procurement core) of ApexOS at
c:\Imp Data\Personal\apexos. Parts 1–3 are complete and merged. Read docs/ROADMAP.md first —
"Standing rules" is binding. Also read PROGRESS.md, docs/08-module-breakdown.md (§2.5
Suppliers/Procurement, §2.6 Pricing), docs/12-coding-standards.md. Branch: phase-2/procurement-core
off main.

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
   (open quantity tracked and visible), receipt against a specific revision.

UI: extend /purchase-orders and /procurement; add requisition, RFQ and comparison screens. Optimise
for speed — keyboard-first entry, product search-as-you-type, sensible defaults from history, bulk
line entry. Reuse the part 2 table/filter/pagination macros; do not hand-roll list markup.

Ledger discipline: goods receipt posts stock IN through the existing InventoryService.post_movement
(the ONLY stock writer). Receipts and revisions are append-only. Open/back-order quantity is DERIVED
from ordered minus received, never a stored mutable counter.

Note for part 5: record the timestamps it will need (PO confirm, each receipt) so lead time can be
measured later rather than typed in. Do not build the vendor scoring itself — that is part 5.

Seed a requisition awaiting approval, an approved requisition converted to a PO, an RFQ with 2
supplier quotes, a revised PO, and a partial receipt with an outstanding back order.

Add tests: requisition→PO conversion, requisition approval writes exactly one activity_log row,
RFQ→quote comparison pick, PO revision preserves the prior version verbatim, partial receipt leaves
the correct back-order quantity, receipt against a superseded revision is handled explicitly.

Follow the ROADMAP verify loop, update PROGRESS.md, commit, open a PR to main, update memory.
```

---

## PROMPT — Part 5: Procurement — vendor intelligence + planning (Phase 2, second half)

```
You are starting Part 5 of 15 (Phase 2 — Vendor intelligence & planning) of ApexOS at
c:\Imp Data\Personal\apexos. Parts 1–4 are complete and merged, so requisitions, RFQs, quotes, PO
revisions and partial receipts all exist with real history. Read docs/ROADMAP.md first — "Standing
rules" is binding. Also read PROGRESS.md, docs/08-module-breakdown.md (§2.5, §2.6).
Branch: phase-2/vendor-intelligence off main.

GOAL: make the buy side smart using the data part 4 now produces. Data and arithmetic, NOT ML.

BUILD:
1. Vendor intelligence: product↔supplier mapping with preferred + alternate vendors; vendor score
   built from the existing supplier_evaluation plus on-time receipt history; lead time MEASURED from
   PO-confirm → receipt (never typed in); MOQ; price history per product+supplier.
2. Planning: a procurement calendar (what is due to arrive, what is due to order) and purchase
   recommendations derived from reorder level + open POs + lead time.

EXPLAINABILITY IS THE FEATURE, not a nicety. Every score and every recommendation must state on
screen: what it means, the formula, the data window it used, and links to the records it reasoned
from ("reorder 40 units of X — stock 12, reorder level 50, 0 on open PO, supplier lead time 9 days
measured over 6 receipts"). Where there is not enough history to compute something, say so
explicitly — never emit a misleading default like 0 or 50.

Prefer transparent arithmetic (weighted ratios, trailing averages) over anything a founder cannot
audit by hand. Do NOT add an ML dependency. Do NOT call an LLM at runtime.

Keep this a projection layer: it should own few or no new mutable entities (the product↔supplier
mapping and MOQ are legitimately new master data; scores and lead times are derived, not stored —
unless you measure a real performance problem, and then say so in PROGRESS.md).

Note for parts 7 and 13: part 7 builds inventory reorder suggestions and part 13 consolidates all
recommendation engines. Write this so that logic can be READ by them, not copied — a single service
entry point with a clear signature.

UI: extend /procurement with the calendar and the recommendations list; add vendor comparison and
price history to the supplier and product detail pages. Reuse the part 2 macros.

Seed enough receipt history across at least two suppliers for lead time and on-time rate to be
non-trivial, plus one product below reorder level with an open PO and one without.

Add tests: lead time computed from confirm→receipt timestamps matches a hand-computed value, on-time
rate boundary (received exactly on the promised date counts as on time), recommendation quantity
arithmetic against known seed data, a recommendation always carries a non-empty explanation and at
least one linked record, insufficient-history path returns "unknown" rather than a number.

Follow the ROADMAP verify loop, update PROGRESS.md, commit, open a PR to main, update memory.
```

---

## PROMPT — Part 6: Inventory — locations, states, traceability (Phase 3, first half)

```
You are starting Part 6 of 15 (Phase 3 — Inventory core) of ApexOS at c:\Imp Data\Personal\apexos.
Parts 1–5 are complete and merged. Read docs/ROADMAP.md first — "Standing rules" is binding. Also
read PROGRESS.md, docs/08-module-breakdown.md (§2.8 Inventory/Warehouse), docs/12-coding-standards.md.
Branch: phase-3/inventory-core off main.

GOAL: inventory must always answer three questions — What do we have? Where is it? What is it worth?
This part answers all three at the ledger level. Part 7 builds the operations and the health views on
top of it, and part 9 depends on the reservation concept built here — SO GET THE LEDGER MODEL RIGHT.

WHAT EXISTS: app/modules/inventory (stock_movement ledger, post_movement as the single writer,
derived balances), multi-warehouse + transfer/adjust/count from an earlier phase. Web pages:
/inventory, /warehouse. Extend; do not rebuild. Balances stay DERIVED from the ledger — never a
stored mutable quantity.

BUILD:
1. Location depth: warehouse → rack location → bin, with stock addressed to a bin. Stock ledger
   entries carry the location. Existing movements without a location must keep working (backfill to a
   default bin per warehouse, or make location nullable with a documented meaning — decide and say
   which in PROGRESS.md).
2. Stock states, distinctly reported: available, reserved (committed to sales orders), in transit
   (between warehouses), damaged/quarantined. RESERVATION MUST BE A LEDGER CONCEPT, NOT A FLAG — a
   reservation is an append-only entry that reduces available without reducing on-hand, and is
   released or consumed by a later entry. Part 9 will call this when a sales order is confirmed, so
   expose it as a clear service verb.
3. Traceability: batch / lot, expiry, FIFO consumption + FIFO-based valuation, stock age buckets.
   FIFO consumption order is determined by the ledger, not by a nightly job.

UI: extend /inventory and /warehouse — stock-by-location view, batch/expiry view, ageing view.
Warehouse staff must be able to understand every screen without training: plain labels, no jargon,
no decorative charts. Reuse the part 2 macros.

InventoryService.post_movement remains the ONLY writer to the stock ledger. If a new operation needs
to write stock, it calls post_movement — it does not insert rows itself.

Seed: two warehouses with racks and bins, batched + expiring stock (including one already expired and
one expiring inside 30 days), a reservation against a confirmed sales order, and enough movement
history that FIFO layers are non-trivial.

Add tests: FIFO consumption order and the resulting valuation, reservation reduces available but not
on-hand, releasing a reservation restores available, expiry and ageing bucket boundaries (exactly on
the boundary date), stock addressed to a bin rolls up correctly to rack and warehouse totals,
post_movement is still the only code path that writes stock_movement.

Follow the ROADMAP verify loop, update PROGRESS.md, commit, open a PR to main, update memory.
```

---

## PROMPT — Part 7: Inventory — operations + health (Phase 3, second half)

```
You are starting Part 7 of 15 (Phase 3 — Inventory operations & health) of ApexOS at
c:\Imp Data\Personal\apexos. Parts 1–6 are complete and merged, so locations, stock states, batches
and FIFO valuation all exist. Read docs/ROADMAP.md first — "Standing rules" is binding. Also read
PROGRESS.md, docs/08-module-breakdown.md (§2.8), docs/12-coding-standards.md.
Branch: phase-3/inventory-ops-health off main.

GOAL: the day-to-day warehouse operations, plus inventory health that explains itself.

BUILD:
1. Operations: cycle count (count sheet → variance → adjustment), stock adjustment with a mandatory
   reason, warehouse transfer (two movements with the part 6 in-transit state between them, so stock
   is never invisible mid-flight). All go through InventoryService.post_movement — the single writer.
   A count that matches produces NO adjustment movement; a variance produces exactly one.
2. Inventory health, all explainable: ABC analysis, dead stock radar, fast/slow moving, reorder
   suggestions, low-stock alerts. Each must show the numbers it reasoned from, the window used, and
   link to the affected records.

CONSOLIDATE, DO NOT DUPLICATE: part 5 already built purchase recommendations from reorder level +
open POs + lead time. The reorder suggestions here must READ that service, not reimplement it. If the
two genuinely differ, unify them into one engine with parameters and have both screens read it — and
say in PROGRESS.md what you unified. Part 13 will audit exactly this.

UI: extend /inventory and /warehouse with the count and adjustment flows and the health views. Count
sheets are used on a warehouse floor — optimise for fast entry and for being printable/readable, not
for looking impressive. Reuse the part 2 macros.

Seed: a completed cycle count with a variance and its adjustment, a count with no variance, an
in-transit transfer awaiting receipt, dead stock (no movement in the window), and a fast mover — with
enough history that ABC classes are non-trivial.

Add tests: cycle-count variance produces exactly one adjustment movement and a matching activity_log
row, a zero-variance count produces none, transfer sits in-transit then lands on receipt, adjustment
requires a reason, ABC class boundaries, dead-stock window boundary, reorder suggestion matches the
part 5 engine's output for the same product (proving they share one implementation).

Follow the ROADMAP verify loop, update PROGRESS.md, commit, open a PR to main, update memory.
```

---

## PROMPT — Part 8: Sales — customer depth (Phase 4, first half)

```
You are starting Part 8 of 15 (Phase 4 — Customer depth) of ApexOS at c:\Imp Data\Personal\apexos.
Parts 1–7 are complete and merged. Read docs/ROADMAP.md first — "Standing rules" is binding. Also
read PROGRESS.md, docs/08-module-breakdown.md (§2.4 Customers/CRM, §2.7 Sales),
docs/12-coding-standards.md. Branch: phase-4/customer-depth off main.

GOAL: everything a salesperson needs to know about a customer, on one page, without asking anyone.

WHAT EXISTS: app/modules/customers, app/modules/crm (lead, opportunity, pipeline_stage,
convert/advance), app/modules/sales (the proven sales_order → fulfillment → invoice → payment spine).
Web pages: /customers, /leads, /sales. Extend; do not rebuild the proven spine.

BUILD:
1. Customer profile depth: multiple contacts, multiple branches / ship-to addresses, credit limit,
   payment terms, delivery preferences, documents, notes.
2. Credit limit enforcement at sales-order confirm, with an explicit override that is LOGGED (who
   overrode, when, by how much, and why — a reason is mandatory). The block must state the numbers:
   limit, current outstanding, this order's value, the shortfall.
3. A unified customer timeline: orders, invoices, payments, tasks, notes and activity in ONE
   chronological view, assembled from activity_log plus entity events. This is a read-only projection
   — do not add a new events table to make it easy.

Reuse the part 2 macros for the contact/branch/document lists and the part 1 soft-delete mechanism.
Documents reuse the existing DocKeeper/document module — do not build a second upload path.

Do NOT build the health score, quotations or returns here — those are part 9. If you find yourself
designing the quotation screen, stop.

Seed: a customer with multiple contacts and ship-to branches, a credit limit, and enough order/
invoice/payment history for the timeline to be worth reading; plus one order that breaches the credit
limit and one override that was recorded.

Add tests: credit-limit block fires at the boundary (exactly at the limit is allowed, one minor unit
over is not), override requires a reason and writes exactly one activity_log row, timeline ordering is
strictly chronological and includes every source type, a customer with no history renders an empty
timeline without errors.

Follow the ROADMAP verify loop, update PROGRESS.md, commit, open a PR to main, update memory.
```

---

## PROMPT — Part 9: Sales — workflow completion + speed (Phase 4, second half)

```
You are starting Part 9 of 15 (Phase 4 — Sales workflow & speed) of ApexOS at
c:\Imp Data\Personal\apexos. Parts 1–8 are complete and merged. Read docs/ROADMAP.md first —
"Standing rules" is binding. Also read PROGRESS.md, docs/08-module-breakdown.md (§2.4, §2.7),
docs/12-coding-standards.md. Branch: phase-4/sales-workflow off main.

GOAL: close the two gaps at the ends of the sales workflow, wire in reservation, and make order entry
genuinely fast.

WHAT EXISTS: lead → sales_order → fulfillment → invoice → payment works and is E2E-verified. The
gaps are at the two ends: QUOTATION (before the order) and RETURNS / CREDIT NOTE (after the invoice).

BUILD:
1. Quotation: create, revise (versioned, append-only), send, expire, and convert to a sales order in
   ONE action carrying the quoted prices forward.
2. Returns and credit notes: a return posts stock IN through InventoryService.post_movement and
   raises a credit note against the invoice. APPEND-ONLY — never edit the original invoice. Partial
   returns allowed. The credit note reduces the receivable through the ledger, not by mutation.
3. Reservation: confirming a sales order reserves stock using the part 6 reservation service verb —
   do not add a flag or a second mechanism. Fulfilment consumes the reservation; cancellation
   releases it.
4. Customer health score, fully explainable: order frequency, profitability (using the existing
   margin logic), outstanding + ageing, recency of activity. Show the inputs and the weighting ON
   SCREEN. Where there is not enough history, say "unknown" — never a misleading default.
5. Speed: keyboard-first order entry, product search-as-you-type showing price AND available stock
   inline, reorder-from-last-order, sensible defaults from customer history, bulk line entry.
   Measure the keystrokes for a 5-line repeat order before and after, and report both.

UI: extend /sales and /customers; add quotation and return screens. Reuse the part 2 macros.

Seed: a quotation, a revised quotation, a quotation converted to an order, a confirmed order holding
a reservation, and a partial return with its credit note.

Add tests: quotation→order conversion carries quoted prices, quotation revision preserves the prior
version, return posts stock IN and creates a credit note WITHOUT mutating the original invoice,
partial return leaves the correct returnable quantity, confirming an order creates a reservation and
cancelling releases it, health score arithmetic against known seed data, insufficient-history returns
"unknown".

Follow the ROADMAP verify loop, update PROGRESS.md, commit, open a PR to main, update memory.
```

---

## PROMPT — Part 10: Finance — ledgers + receivables/payables (Phase 5, first half)

```
You are starting Part 10 of 15 (Phase 5 — Ledgers & AR/AP) of ApexOS at
c:\Imp Data\Personal\apexos. Parts 1–9 are complete and merged, so sales, purchases, receipts,
returns and credit notes all produce real financial history. Read docs/ROADMAP.md first — "Standing
rules" is binding. Also read PROGRESS.md, docs/08-module-breakdown.md (§2.9 Finance),
docs/12-coding-standards.md. Branch: phase-5/ledgers-arap off main.

GOAL: OPERATIONAL finance, not accounting software. No chart of accounts, no journals, no
double-entry ledger. The question is always "who owes what, when, and who do I chase today" — never
"is the trial balance balanced".

WHAT EXISTS: app/modules/finance (invoice, bill, payment with direction, payment_allocation,
receivable/payable projections). Web page: /finance. Extend; do not rebuild.

BUILD:
1. Ledgers: customer ledger and vendor ledger — running statements per party, drillable to the source
   documents, derived from append-only invoices / bills / payments / credit notes. The running balance
   must be computed from the ledger, never stored.
2. Receivables and payables: outstanding with ageing buckets, due vs overdue split, a collections view
   (who to chase today, in priority order, WITH the reason stated) and a payments-due view.

Everything read-only-derived: these are projections over existing ledgers, so they own few or no new
entities and write NO activity_log rows for reads. Money stays integer minor units throughout — verify
no float arithmetic creeps into any total, percentage or ageing calculation.

Partial payment allocation across multiple invoices must be handled correctly, including a payment
that over-covers one invoice and spills to the next, and a credit note applied against an invoice.

UI: extend /finance with ledger, ageing and collections views + CSV export on each (reuse the part 2
export path so exports respect on-screen filters). Reuse the part 2 macros.

Add tests: ledger running balance across invoices/payments/credit notes, ageing bucket boundaries
INCLUDING exactly-on-due-date, partial payment allocated across multiple invoices, over-payment
spillover, credit note reduces the receivable without mutating the invoice, collections priority
ordering is deterministic and each entry carries a reason, no float appears in any money path.

Follow the ROADMAP verify loop, update PROGRESS.md, commit, open a PR to main, update memory.
```

---

## PROMPT — Part 11: Finance — cash, margin, GST (Phase 5, second half)

```
You are starting Part 11 of 15 (Phase 5 — Cash, margin & GST) of ApexOS at
c:\Imp Data\Personal\apexos. Parts 1–10 are complete and merged, so the ledgers and AR/AP
projections exist. Read docs/ROADMAP.md first — "Standing rules" is binding. Also read PROGRESS.md,
docs/08-module-breakdown.md (§2.9), docs/12-coding-standards.md. Branch: phase-5/cash-margin-gst
off main.

GOAL: answer "are we going to be short of cash" and "where are we losing money" — the two questions
a founder actually asks. Still operational finance, still no double-entry.

BUILD:
1. Cash: a cash-flow view (in vs out, actual + committed), a working-capital snapshot, and the cash
   conversion cycle (DSO + DIO − DPO) with EACH COMPONENT SHOWN, not just the total. "Committed" must
   be defined on screen (confirmed POs, confirmed orders, due invoices — say exactly which).
2. Margin and profitability: margin analysis by product / customer / category / business unit, using
   the existing margin logic and the part 6 FIFO valuation for cost.
3. Margin leakage indicators: sold below purchase price, discount creep, freight not recovered. Each
   must list the specific offending records — an indicator with nothing to click is noise.
4. GST summary: output tax, input tax, net position, by period. A REPORT, not a filing engine. Do not
   build return-filing workflows.

Read from the part 10 ledgers and the part 6/7 inventory valuation rather than recomputing either. If
you need a number those parts do not expose, add it THERE and read it here.

Money stays integer minor units. Percentages and ratios are the only place division appears — round
explicitly and say where, and never let a float round-trip back into a stored or displayed money
value.

UI: extend /finance with cash-flow, working-capital, margin and GST views + CSV export on each. Reuse
the part 2 macros. No decorative charts — if a chart does not change a decision, use a table.

Note for parts 12 and 13: they will consume these projections. Expose them as clean service methods
with explicit period parameters so the cockpit does not recompute anything.

Add tests: cash conversion cycle components each match hand-computed values, committed cash matches
its stated definition, margin computation matches known seed data across all four dimensions, each
leakage indicator fires on a seeded offender and stays silent otherwise, GST net position by period,
no float in any money path.

Follow the ROADMAP verify loop, update PROGRESS.md, commit, open a PR to main, update memory.
```

---

## PROMPT — Part 12: Founder Command Center (Phase 6)

```
You are starting Part 12 of 15 (Phase 6 — Founder Command Center) of ApexOS at
c:\Imp Data\Personal\apexos. Parts 1–11 are complete and merged, so real operational data now exists
across procurement, inventory, sales and finance. Read docs/ROADMAP.md first — "Standing rules" is
binding. Also read PROGRESS.md and docs/17-design-system.md. Branch: phase-6/command-center off main.

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

Implementation: this is a READ-ONLY PROJECTION LAYER. Reuse the part 10/11 finance projections, the
part 7 inventory health, and the part 5 vendor intelligence rather than recomputing anything. If a
number is not already exposed by those parts, add it there and read it here. Watch query count — one
page load must not fan out into dozens of queries; MEASURE it and state the number in PROGRESS.md.
Page must render fast on the seeded dataset; report the timing.

Delete the placeholder dashboard code you replace — do not leave two dashboards behind.

Add tests: each tile's arithmetic against known seed data, every alert's trigger boundary (fires at
the threshold, silent below it), empty-state (a fresh DB renders without errors and without fake
zeros-as-alerts), and a query-count assertion so the fan-out cannot silently regress.

Follow the ROADMAP verify loop, update PROGRESS.md, commit, open a PR to main, update memory.
```

---

## PROMPT — Part 13: Intelligence Layer (Phase 7)

```
You are starting Part 13 of 15 (Phase 7 — Apex Intelligence) of ApexOS at
c:\Imp Data\Personal\apexos. Parts 1–12 are complete and merged. Read docs/ROADMAP.md first —
"Standing rules" is binding. Also read PROGRESS.md and docs/16-future-roadmap.md.
Branch: phase-7/intelligence off main.

GOAL: turn accumulated operational data into recommendations a founder can trust. Much of this exists
in partial form from parts 5, 7, 9, 11 — THIS PART CONSOLIDATES, IT DOES NOT DUPLICATE.

NON-NEGOTIABLE: no black-box AI. Every score, forecast and recommendation must explain WHY it exists
in plain language, showing the inputs, the weights, and the records it reasoned from — rendered on
screen, not buried in a docstring. Prefer transparent arithmetic (weighted ratios, trailing averages,
simple linear projections) over anything a founder cannot audit by hand. Do NOT add an ML dependency.
Do NOT call an LLM at runtime for these numbers.

START WITH AN AUDIT: list every score, radar, suggestion and alert that parts 5–12 already produce,
and where each lives. Anything computed in two places gets unified into ONE engine that both screens
read. Write that list and the unifications into PROGRESS.md — it is a deliverable, not scaffolding.

THEN BUILD / CONSOLIDATE:
  Scores:      customer health, vendor reliability, inventory health.
  Radars:      dead stock, margin leakage, customer churn risk.
  Cockpits:    working capital, category performance, business-unit performance.
  Engines:     procurement recommendations — one engine, unifying part 5's purchase recommendations
               and part 7's reorder suggestions.
  Forecasts:   purchase, sales, cash requirement — trailing-window based, with the window stated and
               the confidence/limitation said out loud.
  Brief:       Founder Morning Brief — a short ranked list of "here is what changed and what to do
               today", assembled from the above. It is a VIEW over the other outputs, not new logic.

Each output needs: a stated definition, the formula, the data window, and a link to the underlying
records. Where a score cannot be computed (not enough history), say so explicitly — never emit a
misleading default like 0 or 50.

Add tests: each score against hand-computed seed values, each forecast against a known series,
insufficient-data path returns "unknown" not a number, every recommendation carries a non-empty
explanation and at least one linked record, and — for each unification — one test proving both
screens now return identical output for the same input.

Follow the ROADMAP verify loop, update PROGRESS.md, commit, open a PR to main, update memory.
```

---

## PROMPT — Part 14: Polish & Optimization (Phase 8)

```
You are starting Part 14 of 15 (Phase 8 — Polish & Optimization) of ApexOS at
c:\Imp Data\Personal\apexos. Parts 1–13 are complete and merged — the product is feature-complete.
Read docs/ROADMAP.md first — "Standing rules" is binding. Also read PROGRESS.md and
docs/17-design-system.md. Branch: phase-8/polish off main.

GOAL: make ApexOS feel like a premium internal operating system. Add NO new features. If you find
yourself designing a new screen, stop — that belongs nowhere.

IMPROVE:
  Experience — UI consistency (one spacing/type/colour system actually applied everywhere), UX flow,
    accessibility (labels, contrast, focus order, screen-reader-sane tables), full keyboard
    navigation, responsive layout down to a tablet.
  Findability — global search across every entity, and a command palette (Ctrl+K) for
    navigate-and-act without the mouse.
  Speed — MEASURE FIRST, then fix: page timings, N+1 queries, missing indexes, template render cost,
    static asset size. Report before/after numbers; do not "optimise" without a measurement.
  Code — de-duplicate (the same table/filter/form logic should exist once — by now every list screen
    should be going through the part 2 macros; find the ones that are not), simplify workflows, reduce
    clicks on the top-10 most frequent tasks, delete unnecessary screens, tighten developer experience
    (one-command run, fast tests).
  Security — review authz coverage on EVERY route (the part 1 require_web_permission guard must be
    wired everywhere it belongs — audit all of them, not a sample), input validation, file-upload
    handling, error messages that don't leak internals, dependency audit.

Method: audit → write down the findings with evidence → fix in reviewable batches → prove it with
measurements. Deliver a short written summary of what changed and what was measured.

The full test suite must stay green throughout — this part must not change behaviour, only its
quality. Add tests where refactors created risk (especially the de-duplication work) plus
keyboard/accessibility smoke coverage where testable, and one test asserting every web POST route
carries an authz guard.

Follow the ROADMAP verify loop, update PROGRESS.md, commit, open a PR to main, update memory.
```

---

## PROMPT — Part 15: Product Challenge (Phase X)

```
You are running Part 15 of 15 (Phase X — Product Challenge) on ApexOS at
c:\Imp Data\Personal\apexos. Parts 1–14 are complete. Read docs/ROADMAP.md and PROGRESS.md.

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

Challenge every decision, including the architectural ones. Name the things that exist because they
were on a roadmap rather than because someone needs them. Be specific: cite the file and the screen,
say what you would cut, and say what breaks if you cut it.

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
- **On the 15-part split:** parts within a phase share the phase's branch prefix, so the phase
  identity survives the split. If a part turns out to be two sessions' worth of work, split it and
  renumber in this table rather than silently overrunning — the part count is a planning aid, not a
  commitment.

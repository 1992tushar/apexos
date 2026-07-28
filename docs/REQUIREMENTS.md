# ApexOS — Requirements Register

> **Purpose:** the verifiable requirement list for all 12 delivery parts. `docs/ROADMAP.md` says
> *what order to build in and gives the session prompt*; this file says *what "done" means*, in
> checkable statements. `PROGRESS.md` remains the source of truth for *status*.
>
> **Version:** 1.1 · **Date:** 2026-07-28

---

## 0. How to read this

Requirement IDs are stable: **`R<n>.<m>`** for part requirements, **`G<n>`** for global invariants.
Once assigned, an ID is **never reused or renumbered** — if a requirement is dropped it is struck
through with a reason, not deleted.

**That rule outlived the part numbering.** The plan was re-cut from 15 parts to 12 on 2026-07-28, and
requirement prefixes were deliberately left alone. Consequently a part can hold two prefixes: part 2
holds `R2.x` + `R3.x`, part 5 holds `R6.x` + `R7.x`, part 8 holds `R10.x` + `R11.x`. The prefix tells
you the requirement's identity; the section heading tells you which part delivers it.

Each requirement has:

- **Requirement** — one statement using MUST / MUST NOT / SHOULD. MUST is binding; SHOULD may be
  traded away with a note in `PROGRESS.md` saying why.
- **Acceptance** — how a reviewer verifies it. If a requirement cannot be verified, it is not a
  requirement; it is a wish, and it belongs in prose.
- **Pri** — **P0** (no product without it) · **P1** (important) · **P2** (valuable, later).

A part is done when every P0 and P1 requirement in its section passes and the `docs/STANDING-RULES.md` verify loop
is green. P2 items may be deferred, but must be listed as deferred in `PROGRESS.md` — silent omission
is the failure mode this register exists to prevent.

### Product decisions (2026-07-28) — why requirements were cut

| # | Decision | Effect on this register |
|---|---|---|
| **D-A** | No batch/lot, no expiry, no FIFO. Simple weighted-average cost. | R6.7, R6.8, R6.9 struck. R6.16 added. R6.10, R6.14, R6.15, R11.6 rewritten |
| **D-B** | Single user — the founder. | R14.13, R14.14, G10 demoted. R6.13, R7.12, R14.2 relaxed. Roles/permissions UI cut |
| **D-C** | Starting fresh, no data migration. | R2.6, R2.7 demoted to P2. R2.15, R3.1 rewritten |
| **D-D** | QuickBooks bridge, notifications, saved views, ADR log and SOP index all **cut, not deferred**. | §17 rewritten — these are no longer a backlog |

### Relationship to the other docs

| Doc | Authority | Note |
|---|---|---|
| `00-canonical-foundation.md` | **Wins on conflict.** Decisions D1–D10, canonical entity names | Unchanged |
| `06-feature-list.md` | Authoritative on **domain features** (feature IDs cited below) | Its **Phase 1/2/3 column is superseded**; features 11.14, 14.5, 16.12, 16.13, 16.15, 16.16 and X.3 are **cut** (§17); its stack references (TanStack, Clerk, R2, Next.js) are historical |
| `08-module-breakdown.md` | Authoritative on **module ownership, service verbs, events** | Its §5 phase plan is superseded by `ROADMAP.md` |
| `ROADMAP.md` | Authoritative on **sequence**, the product decisions D-A..D-D, and session prompts | 12 parts |
| **This file** | Authoritative on **acceptance** | — |

---

## 1. Global invariants (G) — every part, every PR

These are not re-stated per part. A PR that violates one is not done, regardless of its own section.

| ID | Requirement | Acceptance | Pri |
|---|---|---|---|
| G1 | Money MUST be stored and computed as integer minor units with an explicit `currency`. No float in any money path — totals, allocations, ageing, valuation. | Grep the diff for float division on money; one test per new money computation asserting exact integer results | P0 |
| G2 | Primary keys MUST be UUID v7. | New model review | P0 |
| G3 | Every table MUST carry audit + soft-delete columns, and every operational table MUST carry `business_unit_id`. | New model review; list queries exclude `deleted_at IS NOT NULL` | P0 |
| G4 | Ledgers (`stock_movement`, `payment`, `invoice`, `bill`, credit notes, receipts, revisions) MUST be append-only. Corrections are new documents. | No UPDATE/DELETE against ledger tables anywhere in the diff | P0 |
| G5 | Every state-changing service verb MUST write exactly **one** `activity_log` row inside the same transaction as the state change. | One test per new verb asserting the row count is exactly 1 and the verb name matches `<entity>.<past_tense>` | P0 |
| G6 | Noun-lists (`customer_type`, `supplier_type`, `procurement_model`, …) MUST be rows, never hardcoded enums. | No new Python enum for a business noun; adding a value requires no code change | P0 |
| G7 | Derived quantities (stock balance, receivable, payable, running balance, back-order qty, available stock, returnable qty) MUST be derived from the ledger, never stored as a mutable number. | Model review; a test proving the derived value tracks after a new ledger entry | P0 |
| G8 | `InventoryService.record_movement` MUST remain the only writer of `stock_movement`. | Test asserting no other module inserts `stock_movement` rows | P0 |
| G9 | Web pages MUST call services directly, never over HTTP. | Route review — no HTTP client in `app/web/` | P0 |
| G10 | Web POST routes SHOULD carry the authorization guard from R1.4. | Spot-check on review. **Demoted from MUST/P0 by D-B** — with one user the guard is a no-op; the mechanism existing is what matters, exhaustive enforcement is ceremony | P1 |
| G11 | Every score, alert, recommendation and forecast MUST render its inputs, its formula, its data window, and links to the records it reasoned from. Where it cannot be computed, it MUST say "unknown" — never a misleading default such as 0 or 50. | Screen review; a test asserting a non-empty explanation and ≥1 linked record per output; a test for the insufficient-data path | P0 |
| G12 | No ML dependency, and no LLM call at runtime, for any number the product displays. | Dependency review | P0 |
| G13 | New behaviour MUST have tests in `apps/api/tests/`; `pytest -q` and `ruff check app/ tests/` MUST be green with no new findings. | CI / verify loop | P0 |
| G14 | New screens MUST have seed data sufficient to exercise them (including edge cases, not just a happy row), added as a new `app/seed/<domain>.py` section rather than appended to `run()`. | Boot the app on a fresh DB; every new screen shows meaningful data | P0 |
| G15 | Reads MUST NOT write `activity_log` rows. Projection layers own no entities. | Review; a test that loading a projection page writes no rows | P1 |
| G16 | A part MUST NOT reimplement logic an earlier part already owns; it calls the earlier service. | Named per part below; PR review cites the service reused | P0 |
| G17 | A part MUST NOT build anything cut by decisions D-A..D-D. Finding yourself building batch tracking, FIFO layers, a roles/permissions UI, a QBO bridge, notifications, saved views, an ADR log or an SOP index means the session has drifted. | Scope review of the diff | P0 |

---

## 2. Part 1 — Foundation finish · Phase 0 · tag `part-01-done`

**Goal:** the two mechanisms every later part wires into (soft delete, web authz), plus the migration
strategy written down. **Status: COMPLETE** — R1.1–R1.10 all pass, tagged `part-01-done`. See the Part 1
record in `PROGRESS.md` for how each was verified; `docs/DELETION-POLICY.md` and
`docs/MIGRATION-STRATEGY.md` are the written artifacts R1.3 and R1.8 call for.

| ID | Requirement | Acceptance | Pri |
|---|---|---|---|
| R1.1 | There MUST be exactly ONE generic soft-delete mechanism (a helper or base-repository method), not per-entity implementations. | One definition in the diff; every caller uses it | P0 |
| R1.2 | Deletion MUST be wired for the entities where it is valid — customers, suppliers, products, tasks, leads, categories — as service method + web POST route + a button in the list/detail template. | Click delete on each entity in the running app; the row leaves the list | P0 |
| R1.3 | Entities that MUST NOT be deletable MUST be documented with the reason: confirmed invoices/bills, posted sales/purchase orders, the stock ledger. Attempting it MUST fail with a clear reason, not a 500. | The written list exists; a test per class asserting refusal with a readable message | P0 |
| R1.4 | A web authorization guard (`require_web_permission`) MUST exist, rendering a 403 `error.html` for GET and redirecting with an error flash for POST. | Test both paths | P0 |
| R1.5 | The guard MUST be wired onto the web POST routes to mirror the JSON API's `require_permission` coverage. Per D-B this is establishing a prod pattern, not solving a live problem — do not gold-plate it. | Spot-check API vs web on the main mutation routes | P1 |
| R1.6 | Soft delete MUST write an `activity_log` row (G5). | Test | P0 |
| R1.7 | A soft-deleted record MUST disappear from lists and detail lookups without breaking referencing documents. | Test: delete a customer with an invoice; the invoice still renders | P0 |
| R1.8 | The schema-migration strategy MUST be documented — dev SQLite via `create_all` + the additive `_ensure_new_columns` shim; prod Postgres via Alembic reintroduced behind `DATABASE_URL`. | The written decision exists in `docs/` | P0 |
| R1.9 | The ~3 residual E501 findings in `app/web/pages/settings.py` MUST be cleared. | `ruff check` clean | P1 |
| R1.10 | A bad id on any GET detail route MUST render `error.html`, not a stack trace. | Visit `/customers/<random-uuid>` in the booted app and eyeball the page | P0 |

---

## 3. Part 2, stage 1 — Shared machinery · Phase 1 · tag `part-02-done`

**Goal:** build once what parts 3–8 all consume, and **prove reusability before rolling out**. The
build-then-prove-then-roll-out order is the point; §4 is stage 2 of the same part and the same branch.

| ID | Requirement | Acceptance | Pri |
|---|---|---|---|
| R2.1 | A reusable list/table pattern MUST exist as macros in `app/web/templates/_macros.html`: search box, filter chips, sortable headers, pagination controls. | One definition; no duplicated table markup per entity | P0 |
| R2.2 | The list pattern MUST be driven by declarative per-page config (columns, filters, default sort), not copy-pasted markup. | Adding a column is a config change | P0 |
| R2.3 | List state MUST live in the query string (`?q=&sort=&dir=&page=&<filter>=`) so links are shareable and the back button behaves. | Copy a filtered URL into a new tab — same view | P0 |
| R2.4 | One generic paginated/filtered/sorted query helper MUST exist in the repository layer; pages MUST NOT hand-roll LIMIT/OFFSET or ORDER BY. | Grep for raw LIMIT/OFFSET in `app/web/` | P0 |
| R2.5 | The query helper MUST compose with the `EntityMixin` soft-delete read filter and `business_unit` scoping. | Test: soft-deleted and other-BU rows never appear | P0 |
| R2.6 | ~~CSV import MUST validate, report every bad row (row number + field + message), be idempotent on re-run, and be all-or-nothing per batch.~~ **Demoted to P2 by D-C** (no data to migrate). Build only after stage 2 is green; keep it minimal. | Test: import with 3 bad rows reports all 3 and commits nothing | P2 |
| R2.7 | ~~Import behaviour per entity MUST come from configuration, not a bespoke importer per entity.~~ **Demoted to P2 by D-C.** Applies if R2.6 is built. | One import engine in the diff | P2 |
| R2.8 | One generic CSV export path MUST exist over the same query helper, so an export respects the filters currently on screen. | Test: filter then export, row count matches the filtered list | P1 |
| R2.9 | One duplicate-prevention approach MUST exist — natural-key uniqueness plus a pre-save check surfacing a clean field-level error, not an IntegrityError or a 500. | Test: submit a duplicate, get a field error | P0 |
| R2.10 | Change history MUST be derived from `activity_log` where it can answer "what changed on this record, when, by whom". A new table MUST NOT be added unless `activity_log` provably cannot, with the reason recorded in `PROGRESS.md`. | Review; the justification exists if a table was added | P0 |
| R2.11 | The machinery MUST be proven end-to-end on exactly TWO existing masters (suggest products and customers): list, export, duplicate rejection, change history. | All four work in the booted app on both masters | P0 |
| R2.12 | Stage 1 MUST NOT roll the machinery out to the remaining masters (that is stage 2, §4) and MUST NOT add new domain features. | Scope review of the stage-1 commits | P0 |
| R2.13 | Seed data MUST give products and customers enough rows (hundreds, not five) to make pagination and filtering real. | Fresh-DB boot: pagination has multiple pages | P0 |
| R2.14 | Reusability MUST be quantified before stage 2 begins: `PROGRESS.md` states the lines of new code the SECOND master needed, and a third master MUST be achievable in well under 100 lines. **This number is the gate for stage 2.** | The number is written down; §4 validates it | P0 |
| R2.15 | Tests MUST cover: filter/sort/pagination boundaries, soft-deleted exclusion, export respecting filters, duplicate rejection returning a field error. Import tests apply only if R2.6 is built. | `pytest -q` | P0 |

---

## 4. Part 2, stage 2 — Masters made uniform · Phase 1 · tag `part-02-done`

**Goal:** apply stage 1's machinery to every master. Depth and uniformity, **not** a rewrite — most of
these entities already exist in `app/modules/config`, `products`, `customers`, `suppliers`. Traces to
`06-feature-list.md` §4, §5, §16.

**Masters in scope:** business units, categories + subcategories, products, brands, manufacturers,
warehouses, units of measure + conversions, tax masters, customers, suppliers.

| ID | Requirement | Acceptance | Pri |
|---|---|---|---|
| R3.1 | Every master in scope MUST support, uniformly: search, filters, sorting, pagination, CSV export, audit trail, active/inactive status, soft delete, change history, validation, relationship integrity, duplicate prevention. (CSV **import** is excluded per D-C; add it per master only if R2.6 was built.) | A matrix in `PROGRESS.md` with no empty cells | P0 |
| R3.2 | Each capability MUST be implemented via stage 1's machinery, NOT per-entity code. | Review: no second table macro, no second query helper | P0 |
| R3.3 | If applying the machinery to a master needs substantially more code than R2.14's figure, the machinery MUST be improved rather than worked around, and the change noted. | `PROGRESS.md` note | P0 |
| R3.4 | Categories MUST support reparenting with cycle prevention, tree rendering, and business-unit rollup (`CategoryService.reparent`, feature 5.2). | Test: reparent to a descendant is rejected | P0 |
| R3.5 | UoM conversions MUST reject zero and cyclic factors (`UomConversionService.upsert`, feature 16.5). | Test both rejections | P0 |
| R3.6 | Tax rate slabs MUST be versioned — a new slab appends and never edits history (`TaxRateService.set_slab`, feature 16.9). | Test: prior version readable verbatim after a change | P0 |
| R3.7 | Deleting or deactivating a master still referenced by live transactions MUST be blocked or explained — never silently cascaded. | Test: deactivate a product on an open PO; the refusal names the PO | P0 |
| R3.8 | Duplicate prevention MUST be configured for every master's natural key. | Test per master | P0 |
| R3.9 | Products MUST retain SKU generation `BRAND-CAT-SEQ` and the status lifecycle Active/Draft/Discontinued (features 4.2, 4.4). | Existing tests still green | P0 |
| R3.10 | Seed data MUST include a multi-level category tree and at least two tax slab versions. | Fresh-DB boot | P0 |
| R3.11 | Tests MUST cover: per-master list filtering, category cycle rejection, UoM factor rejection, tax slab history preservation, per-master duplicate rejection, soft delete then absent-from-list, blocked deletion explaining itself, one export. | `pytest -q` | P0 |
| R3.12 | The uniform-capability list MUST have no item implemented twice across the codebase. | Review | P0 |
| R3.13 | A roles/permissions management UI MUST NOT be built. **Cut by D-B** — features 16.12 and 16.13 no longer apply. | Scope review | P0 |

---

## 5. Part 3 — Procurement: pre-order → PO depth · Phase 2 · tag `part-03-done`

**Goal:** fewest clicks from "we need this" to "it's ordered and received". Extends
`app/modules/procurement`, `suppliers`, `pricing` — does not rebuild them. Traces to
`06-feature-list.md` §8, §9.

| ID | Requirement | Acceptance | Pri |
|---|---|---|---|
| R4.1 | A purchase requisition MUST support request → approve → convert to PO or RFQ. | Walk the flow in the booted app | P0 |
| R4.2 | Requisition approval MUST record the actor and a reason, and write exactly one `activity_log` row. | Test | P0 |
| R4.3 | An RFQ MUST be issuable to multiple suppliers from one requisition or ad hoc. | Test + screen | P0 |
| R4.4 | Supplier quotations MUST be capturable against an RFQ. | Test + screen | P0 |
| R4.5 | A side-by-side vendor comparison MUST show price, lead time, MOQ and score per quoting supplier. | Screen review | P0 |
| R4.6 | Quotation history per product + supplier MUST be viewable. | Screen review | P1 |
| R4.7 | A confirmed PO MUST NOT be mutated in place. Changes create a new **revision** with a reason and an `activity_log` row; prior revisions stay readable verbatim. | Test: revise, then read version 1 unchanged | P0 |
| R4.8 | Partial receipt MUST be supported, posting stock IN through `InventoryService.record_movement` (G8). | Test | P0 |
| R4.9 | Back-order (open) quantity MUST be **derived** as ordered − received (G7) and visible on the PO. | Test after a partial receipt; screen shows it | P0 |
| R4.10 | A receipt MUST record which PO revision it was received against, and receipt against a superseded revision MUST be handled explicitly, not silently accepted. | Test | P0 |
| R4.11 | PO confirm and each receipt MUST persist their timestamps so part 4 can MEASURE lead time rather than have it typed in. | Field review; part 4 consumes them | P0 |
| R4.12 | Order entry MUST be optimised for speed: keyboard-first, product search-as-you-type, defaults from history, bulk line entry. | Manual walkthrough | P1 |
| R4.13 | New list screens MUST use part 2's macros — no hand-rolled table markup. | Review | P0 |
| R4.14 | Vendor scoring MUST NOT be built here (part 4 owns it). | Scope review | P0 |
| R4.15 | Seed MUST include: a requisition awaiting approval, one converted to a PO, an RFQ with 2 quotes, a revised PO, and a partial receipt with an outstanding back order. | Fresh-DB boot | P0 |
| R4.16 | Tests MUST cover: requisition→PO conversion, approval writing one log row, RFQ→quote comparison pick, revision preserving history, partial receipt back-order arithmetic, receipt against a superseded revision. | `pytest -q` | P0 |

---

## 6. Part 4 — Procurement: vendor intelligence + planning · Phase 2 · tag `part-04-done`

**Goal:** make the buy side smart from part 3's history. Data and arithmetic, not ML (G12). All outputs
bound by G11 (explainability).

| ID | Requirement | Acceptance | Pri |
|---|---|---|---|
| R5.1 | Product↔supplier mapping MUST support a preferred vendor and alternates. | Screen + test | P0 |
| R5.2 | Vendor score MUST be computed from the existing `supplier_evaluation` plus on-time receipt history, showing both inputs and the weighting on screen. | Screen shows the arithmetic; test against hand-computed seed values | P0 |
| R5.3 | Lead time MUST be MEASURED from PO-confirm → receipt. It MUST NOT be a typed-in field. | Test against known timestamps; no editable lead-time input exists | P0 |
| R5.4 | On-time rate MUST define its boundary explicitly — received exactly on the promised date counts as on time. | Boundary test | P0 |
| R5.5 | MOQ MUST be recordable per product+supplier and surfaced in the comparison from R4.5. | Screen + test | P1 |
| R5.6 | Price history per product+supplier MUST be viewable as a timeline (feature 8.2). | Screen review | P1 |
| R5.7 | A procurement calendar MUST show what is due to arrive and what is due to order. | Screen review | P0 |
| R5.8 | Purchase recommendations MUST be derived from reorder level + open POs + measured lead time, and MUST state the reasoning in plain language with the numbers (e.g. "reorder 40 of X — stock 12, reorder level 50, 0 on open PO, lead time 9 days over 6 receipts"). | Screen review; test asserting explanation + ≥1 linked record | P0 |
| R5.9 | The recommendation engine MUST have ONE service entry point with a clear signature, so parts 5 and 10 read it rather than copy it. | Signature review; R7.13 proves it | P0 |
| R5.10 | This part MUST own few or no new mutable entities — the product↔supplier mapping and MOQ are legitimate new master data; scores and lead times are derived (G7). Any stored derivation MUST be justified by a measured performance problem noted in `PROGRESS.md`. | Model review | P0 |
| R5.11 | Where history is insufficient, every output MUST say "unknown" rather than emit a number (G11). | Test the insufficient-history path | P0 |
| R5.12 | Vendor comparison and price history MUST appear on the supplier and product detail pages. | Screen review | P1 |
| R5.13 | Seed MUST include receipt history across ≥2 suppliers making lead time and on-time rate non-trivial, plus one product below reorder level with an open PO and one without. | Fresh-DB boot | P0 |
| R5.14 | Tests MUST cover: lead time from timestamps, on-time boundary, recommendation quantity arithmetic, explanation + linked record presence, insufficient-history path. | `pytest -q` | P0 |

---

## 7. Part 5, group A — Inventory: locations, states, valuation · Phase 3 · tag `part-05-done`

**Goal:** answer *what do we have, where is it, what is it worth* at the ledger level. **Part 7 depends
on the reservation model built here.** §8 is group B of the same part and branch. Traces to
`06-feature-list.md` §6, §7.

**Decision D-A cuts roughly a third of this group.** Struck requirements are left in place with their
reason so the omission is a recorded decision, not an oversight.

| ID | Requirement | Acceptance | Pri |
|---|---|---|---|
| R6.1 | Locations MUST support warehouse → rack → bin, with stock addressed to a bin. | Screen + test | P0 |
| R6.2 | `stock_movement` entries MUST carry the location. | Model + test | P0 |
| R6.3 | Existing movements without a location MUST keep working — either backfilled to a default bin per warehouse, or location nullable with a documented meaning. The choice MUST be recorded in `PROGRESS.md`. | Existing tests green; the decision is written down | P0 |
| R6.4 | Stock states MUST be distinctly reported: available, reserved, in transit, damaged/quarantined. | Screen review | P0 |
| R6.5 | **Reservation MUST be a ledger concept, not a flag** — an append-only entry that reduces available without reducing on-hand, released or consumed by a later entry. | Model review; no boolean reserved column exists | P0 |
| R6.6 | Reservation MUST be exposed as a clear service verb for part 7 to call at sales-order confirm. | Signature review; R9.8 calls it | P0 |
| R6.7 | ~~Batch / lot tracking MUST be supported, with expiry where applicable.~~ **DROPPED by D-A** — no date-sensitive or lot-traced lines in the catalog. | — | — |
| R6.8 | ~~FIFO consumption order MUST be determined by the ledger.~~ **DROPPED by D-A.** | — | — |
| R6.9 | ~~Valuation MUST be FIFO-based off those layers.~~ **DROPPED by D-A** — superseded by R6.16. | — | — |
| R6.10 | Stock age buckets MUST be reported, derived from receipt dates on the ledger, with boundary behaviour defined. Without lots this is **approximate** — the approximation MUST be stated on screen rather than implying precision. It survives D-A because R7.8's dead-stock radar consumes it. | Boundary test; screen states the approximation | P0 |
| R6.11 | Bin-level stock MUST roll up correctly to rack and warehouse totals. | Test | P0 |
| R6.12 | `/inventory` and `/warehouse` MUST gain stock-by-location and ageing views, using part 2's macros. | Screen review | P0 |
| R6.13 | Screens SHOULD use plain labels and avoid jargon. **Relaxed from MUST by D-B** — no untrained staff use the system, but plain language remains the house style. | Review against `17-design-system.md` | P1 |
| R6.14 | Seed MUST include two warehouses with racks and bins, a reservation against a confirmed order, and enough movement history for non-trivial weighted-average cost. It MUST NOT seed batches or expiry dates (D-A). | Fresh-DB boot | P0 |
| R6.15 | Tests MUST cover: reservation reduces available but not on-hand, release restores available, ageing boundaries, bin→rack→warehouse rollup, and that `record_movement` is still the sole stock writer (G8). | `pytest -q` | P0 |
| R6.16 | Cost basis MUST be **weighted average** computed from movement history, and is needed only for the on-hand **value** figure. Margin MUST NOT depend on it (see R11.6). *Added by D-A, replacing R6.9.* | Test against hand-computed values | P0 |

---

## 8. Part 5, group B — Inventory: operations + health · Phase 3 · tag `part-05-done`

**Goal:** day-to-day operations plus inventory health that explains itself.

| ID | Requirement | Acceptance | Pri |
|---|---|---|---|
| R7.1 | Cycle count MUST run count sheet → variance → adjustment (feature 6.9). | Walk the flow | P0 |
| R7.2 | A count with no variance MUST produce NO adjustment movement. | Test | P0 |
| R7.3 | A count with a variance MUST produce exactly ONE adjustment movement and one `activity_log` row. | Test | P0 |
| R7.4 | Stock adjustment MUST require a reason (feature 6.6). | Test rejecting a blank reason | P0 |
| R7.5 | Warehouse transfer MUST be two movements with the in-transit state between them, so stock is never invisible mid-flight. | Test: transfer then receive | P0 |
| R7.6 | All operations MUST write through `InventoryService.record_movement` (G8). | Test | P0 |
| R7.7 | ABC analysis MUST be reported with its class boundaries stated. | Boundary test; screen shows the thresholds | P0 |
| R7.8 | A dead-stock radar MUST report items with no movement in a stated window. | Boundary test | P0 |
| R7.9 | Fast/slow moving classification MUST show the window and the numbers behind it. | Screen review | P1 |
| R7.10 | Low-stock alerts MUST state trigger, threshold and affected records, and link to them (G11). | Screen review + test | P0 |
| R7.11 | Reorder suggestions MUST **read part 4's recommendation engine (R5.9)**, not reimplement it. If the two genuinely differ, they MUST be unified into one parameterised engine that both screens read, with the unification recorded in `PROGRESS.md`. | Review + R7.13 | P0 |
| R7.12 | Count sheets SHOULD be optimised for fast entry and be readable/printable. **Relaxed from MUST by D-B** — no warehouse staff, though the founder may still print for a helper. | Manual review | P1 |
| R7.13 | A test MUST prove the reorder suggestion here and part 4's recommendation return identical output for the same product. | `pytest -q` | P0 |
| R7.14 | Seed MUST include a count with a variance and its adjustment, a zero-variance count, an in-transit transfer awaiting receipt, dead stock, a fast mover, and enough history for non-trivial ABC classes. | Fresh-DB boot | P0 |

---

## 9. Part 6 — Sales: customer depth · Phase 4 · tag `part-06-done`

**Goal:** everything you need to know about a customer on one page. Traces to `06-feature-list.md` §3.

| ID | Requirement | Acceptance | Pri |
|---|---|---|---|
| R8.1 | A customer MUST support multiple contacts (feature 3.4). | Screen + test | P0 |
| R8.2 | A customer MUST support multiple branches / ship-to addresses (feature 3.5). | Screen + test | P0 |
| R8.3 | Credit limit, payment terms and delivery preferences MUST be settable and versioned (feature 3.6). | Test: prior version readable | P0 |
| R8.4 | Documents MUST attach to a customer through the EXISTING document module — no second upload path. | Review | P0 |
| R8.5 | Notes MUST be recordable against a customer. | Screen + test | P1 |
| R8.6 | Credit limit MUST be enforced at sales-order confirm (feature 3.7, `CreditPolicyService.check`). | Test | P0 |
| R8.7 | The credit block MUST state the numbers: limit, current outstanding, this order's value, the shortfall. | Screen review | P0 |
| R8.8 | An override MUST be possible, MUST require a reason, and MUST be logged with who, when and by how much. | Test: override without a reason is rejected; with one, writes exactly one log row | P0 |
| R8.9 | The credit boundary MUST be exact — at the limit is allowed, one minor unit over is not. | Boundary test | P0 |
| R8.10 | A unified customer timeline MUST present orders, invoices, payments, tasks, notes and activity in ONE chronological view, assembled from `activity_log` + entity events as a read-only projection. A new events table MUST NOT be added to make this easier. | Screen review; model review | P0 |
| R8.11 | A customer with no history MUST render an empty timeline without errors. | Test | P0 |
| R8.12 | Health score, quotations and returns MUST NOT be built here (part 7 owns them). | Scope review | P0 |
| R8.13 | Contact/branch/document lists MUST use part 2's macros and part 1's soft delete. | Review | P0 |
| R8.14 | Seed MUST include a customer with multiple contacts and branches, a credit limit, timeline-worthy history, one order breaching the limit, and one recorded override. | Fresh-DB boot | P0 |

---

## 10. Part 7 — Sales: workflow completion + speed · Phase 4 · tag `part-07-done`

**Goal:** close the two gaps at the ends of the workflow (quotation, returns), wire reservation, make
entry fast. The middle — order → fulfillment → invoice → payment — already works and is E2E-verified.

| ID | Requirement | Acceptance | Pri |
|---|---|---|---|
| R9.1 | Quotations MUST support create, revise, send and expire. | Walk the flow | P0 |
| R9.2 | Quotation revisions MUST be versioned and append-only, with prior versions readable verbatim. | Test | P0 |
| R9.3 | Quotation → sales order MUST be ONE action, carrying quoted prices forward. | Test asserting prices match | P0 |
| R9.4 | A return MUST post stock IN through `InventoryService.record_movement` (G8). | Test | P0 |
| R9.5 | A return MUST raise a credit note against the invoice. The original invoice MUST NOT be mutated (G4, feature 11.15). | Test asserting the invoice is unchanged after the return | P0 |
| R9.6 | Partial returns MUST be supported, leaving a correct derived returnable quantity (G7). | Test | P0 |
| R9.7 | A credit note MUST reduce the receivable through the ledger, not by mutation. | Test on the receivable projection | P0 |
| R9.8 | Confirming a sales order MUST reserve stock via **part 5's reservation verb (R6.6)** — no flag, no second mechanism. | Test; review confirms the call | P0 |
| R9.9 | Fulfilment MUST consume the reservation; cancellation MUST release it. | Two tests | P0 |
| R9.10 | Customer health score MUST combine order frequency, profitability (existing margin logic), outstanding + ageing, and recency, showing inputs and weighting on screen (G11). | Screen review; test against hand-computed seed values | P0 |
| R9.11 | Insufficient history MUST yield "unknown", not a default number. | Test | P0 |
| R9.12 | Order entry MUST be keyboard-first, with product search-as-you-type showing price AND available stock inline, reorder-from-last-order, and defaults from customer history. **D-B raises this in importance, not lowers it** — a solo operator enters every order personally. | Manual walkthrough | P0 |
| R9.13 | Keystrokes for a 5-line repeat order MUST be measured and reported before and after. | Both numbers in `PROGRESS.md` | P1 |
| R9.14 | Bulk line entry MUST be supported. | Manual check | P1 |
| R9.15 | Seed MUST include a quotation, a revised quotation, one converted to an order, a confirmed order holding a reservation, and a partial return with its credit note. | Fresh-DB boot | P0 |
| R9.16 | Tests MUST cover: conversion carrying prices, revision history, return posting IN + credit note without mutating the invoice, partial-return returnable quantity, reserve on confirm / release on cancel, health score arithmetic, insufficient-history path. | `pytest -q` | P0 |

---

## 11. Part 8, group A — Finance: ledgers + receivables/payables · Phase 5 · tag `part-08-done`

**Goal:** operational finance — *who owes what, when, who do I chase today*. **No chart of accounts,
no journals, no double-entry.** §12 is group B of the same part and branch. Traces to
`06-feature-list.md` §11, §12.

| ID | Requirement | Acceptance | Pri |
|---|---|---|---|
| R10.1 | Customer and vendor ledgers MUST present running statements per party. | Screen review | P0 |
| R10.2 | The running balance MUST be computed from the ledger, never stored (G7). | Model review + test | P0 |
| R10.3 | Every ledger line MUST drill through to its source document. | Click-through review | P0 |
| R10.4 | Ledgers MUST incorporate invoices, bills, payments AND credit notes. | Test covering all four | P0 |
| R10.5 | Receivables and payables MUST report outstanding with ageing buckets and a due vs overdue split (features 11.8, 11.13). | Screen review | P0 |
| R10.6 | Ageing bucket boundaries MUST be exact, including exactly-on-due-date. | Boundary test | P0 |
| R10.7 | A collections view MUST list who to chase today in priority order, with the reason stated per entry. | Screen review; test that ordering is deterministic and every entry has a reason | P0 |
| R10.8 | A payments-due view MUST exist for the payable side. | Screen review | P0 |
| R10.9 | Partial payment allocation across multiple invoices MUST be handled, including an over-payment spilling to the next invoice (feature 11.5). | Two tests | P0 |
| R10.10 | These views MUST be read-only projections owning few or no new entities and writing no `activity_log` rows (G15). | Model review + test | P0 |
| R10.11 | No float MUST appear in any total, percentage or ageing computation (G1). | Review + test | P0 |
| R10.12 | Ledger, ageing and collections views MUST offer CSV export via part 2's export path, respecting on-screen filters. | Test | P1 |
| R10.13 | Tests MUST cover: running balance across all four document types, ageing boundaries, multi-invoice allocation, over-payment spillover, credit note reducing the receivable without mutating the invoice, collections ordering + reasons. | `pytest -q` | P0 |
| R10.14 | The QuickBooks Online bridge MUST NOT be built or stubbed. **Cut by D-D** — feature 11.14 no longer applies. | Scope review | P0 |

---

## 12. Part 8, group B — Finance: cash, margin, GST · Phase 5 · tag `part-08-done`

**Goal:** *are we going to be short of cash* and *where are we losing money*.

| ID | Requirement | Acceptance | Pri |
|---|---|---|---|
| R11.1 | A cash-flow view MUST show in vs out, actual and committed. | Screen review | P0 |
| R11.2 | "Committed" MUST be defined ON SCREEN, naming exactly what it includes (confirmed POs, confirmed orders, due invoices, …). | Screen review; test that the figure matches the stated definition | P0 |
| R11.3 | A working-capital snapshot MUST be reported. | Screen review | P0 |
| R11.4 | Cash conversion cycle MUST show DSO, DIO and DPO **each individually**, not only the total. | Screen review; test each component against hand-computed values | P0 |
| R11.5 | Margin analysis MUST be available by product, customer, category and business unit (feature 2.14). | Test all four dimensions against seed data | P0 |
| R11.6 | Margin MUST use the existing `MarginService.gp` logic — **cost is the purchase price snapshotted onto the line, NOT an inventory valuation layer**. *Rewritten by D-A: FIFO is gone, and margin never needed it.* | Review; margin tests pass unchanged by the inventory work | P0 |
| R11.7 | Margin leakage indicators MUST cover sold-below-purchase-price, discount creep, and freight not recovered. | Screen review | P0 |
| R11.8 | Every leakage indicator MUST list the specific offending records. An indicator with nothing to click MUST be removed. | Screen review; test firing on a seeded offender and silent otherwise | P0 |
| R11.9 | A GST summary MUST report output tax, input tax and net position by period (feature 12.1). | Test net position by period | P0 |
| R11.10 | The GST summary MUST be a report only — no return-filing workflow. | Scope review | P0 |
| R11.11 | This part MUST read group A's ledgers and part 5's valuation rather than recomputing either. If a needed number is not exposed, it MUST be added THERE and read here (G16). | Review | P0 |
| R11.12 | Money MUST stay integer minor units; division MUST appear only in ratios, with rounding explicit and stated, and a float MUST NOT round-trip into a stored or displayed money value (G1). | Review + test | P0 |
| R11.13 | Projections MUST be exposed as clean service methods with explicit period parameters, so parts 9 and 10 consume rather than recompute. | Signature review | P0 |
| R11.14 | Views MUST use part 2's macros and offer CSV export. No decorative charts — if a chart does not change a decision, it MUST be a table. | Screen review | P0 |

---

## 13. Part 9 — Founder Command Center · Phase 6 · tag `part-09-done`

**Goal:** the homepage a founder actually opens. An operating cockpit, not a dashboard. Replaces the
placeholder `/dashboard` (`app/web/pages/dashboard.py`, `app/modules/dashboard`). Traces to
`06-feature-list.md` §1.

| ID | Requirement | Acceptance | Pri |
|---|---|---|---|
| R12.1 | The page MUST answer three questions in this order: what happened · what needs attention · what should I do now. | Screen review | P0 |
| R12.2 | "What happened" MUST show today's revenue, today's gross margin and collections today. | Test each against seed data | P0 |
| R12.3 | "What needs attention" MUST cover outstanding receivables, outstanding payables, inventory value, POs pending, sales orders pending, deliveries due, customer alerts, vendor alerts, low-stock alerts and margin alerts. | Screen review | P0 |
| R12.4 | Position MUST show cash-flow and working-capital snapshots. | Screen review | P0 |
| R12.5 | Recent activity MUST come from `activity_log` (feature 1.3). | Screen review | P0 |
| R12.6 | Quick actions MUST cover the four most frequent tasks: new order, new PO, record payment, receive stock (feature 1.10). | Screen review | P0 |
| R12.7 | Every number MUST drill through to the rows behind it (feature 1.11). | Click every tile | P0 |
| R12.8 | Every alert MUST state its trigger, its threshold and its affected records, and link straight to them. An alert with nothing to click MUST be removed. | Screen review; boundary test per alert | P0 |
| R12.9 | The page MUST contain no decorative charts, no donuts, no gradient hero tiles, no vanity metrics. A tile that does not change a decision MUST be deleted. | Screen review | P0 |
| R12.10 | The page MUST be a read-only projection reusing part 8's finance projections (R11.13), part 5's inventory health and part 4's vendor intelligence. Missing numbers MUST be added in those parts, not computed here (G16). | Review | P0 |
| R12.11 | The placeholder dashboard code being replaced MUST be deleted — two dashboards MUST NOT remain. | Review | P0 |
| R12.12 | Query count for one page load MUST be measured and stated in `PROGRESS.md`, and MUST NOT fan out into dozens of queries. | The number is written down | P0 |
| R12.13 | A test MUST assert the query count so the fan-out cannot silently regress. | `pytest -q` | P0 |
| R12.14 | Page render time on the seeded dataset MUST be measured and reported. | The number is written down | P1 |
| R12.15 | A fresh DB MUST render the page without errors and without fake zeros-as-alerts. | Empty-state test | P0 |

---

## 14. Part 10 — Intelligence Layer · Phase 7 · tag `part-10-done`

**Goal:** trustworthy recommendations from accumulated data. **This part consolidates; it does not
duplicate.** Bound throughout by G11 and G12.

| ID | Requirement | Acceptance | Pri |
|---|---|---|---|
| R13.1 | An audit MUST first list every score, radar, suggestion and alert that parts 4–9 already produce, and where each lives. This list is a deliverable in `PROGRESS.md`. | The list exists | P0 |
| R13.2 | Anything computed in two places MUST be unified into ONE engine that both screens read, with each unification recorded. | Review + R13.13 | P0 |
| R13.3 | Scores MUST cover customer health (part 7), vendor reliability (part 4) and inventory health (part 5) — consolidated, not rebuilt. | Review | P0 |
| R13.4 | Radars MUST cover dead stock, margin leakage and customer churn risk. | Screen review | P0 |
| R13.5 | Cockpits MUST cover working capital, category performance and business-unit performance. | Screen review | P1 |
| R13.6 | Procurement recommendations MUST be ONE engine unifying part 4's purchase recommendations and part 5's reorder suggestions. | Review + test | P0 |
| R13.7 | Forecasts MUST cover purchase, sales and cash requirement, be trailing-window based, and state the window used. | Screen review; test against a known series | P0 |
| R13.8 | Every forecast MUST state its confidence or limitation out loud. | Screen review | P0 |
| R13.9 | The Founder Morning Brief MUST be a short ranked list of what changed and what to do today, assembled as a VIEW over the other outputs — it MUST NOT contain new business logic. | Review | P0 |
| R13.10 | Every output MUST carry a stated definition, its formula, its data window, and links to the underlying records (G11). | Screen review; test per output | P0 |
| R13.11 | Where a score cannot be computed for want of history, it MUST say so explicitly — never 0, never 50 (G11). | Test the insufficient-data path | P0 |
| R13.12 | Arithmetic MUST be transparent — weighted ratios, trailing averages, simple linear projections. No ML dependency, no runtime LLM (G12). | Dependency review | P0 |
| R13.13 | For each unification, a test MUST prove both screens return identical output for the same input. | `pytest -q` | P0 |
| R13.14 | Tests MUST cover each score against hand-computed seed values and each forecast against a known series. | `pytest -q` | P0 |

---

## 15. Part 11 — Polish & Optimization · Phase 8 · tag `part-11-done`

**Goal:** make it feel like a premium internal operating system. **Add no new features.** Behaviour
must not change — only its quality. **D-B resizes this part substantially.**

| ID | Requirement | Acceptance | Pri |
|---|---|---|---|
| R14.1 | One spacing / type / colour system MUST be applied consistently across every screen. | Review against `17-design-system.md` | P0 |
| R14.2 | Form labels and colour contrast MUST be correct throughout. **Narrowed by D-B** — the screen-reader-sane-tables and focus-order work is cut; one known user on one machine. | Audit with findings listed | P1 |
| R14.3 | Full keyboard navigation MUST be possible — every primary action reachable without a mouse (feature X.6). | Manual walkthrough | P0 |
| R14.4 | Layout SHOULD be responsive down to a tablet. | Manual check | P2 |
| R14.5 | Global search across every entity MUST exist. **Highest-value item in this part** for a solo operator living in the app daily. | Manual check | P0 |
| R14.6 | A command palette (Ctrl+K) MUST support navigate-and-act (feature X.1). | Manual check | P0 |
| R14.7 | Performance work MUST be measurement-first: page timings, N+1 queries, missing indexes, template render cost, static asset size measured BEFORE any change. | Baseline numbers recorded | P0 |
| R14.8 | Before/after numbers MUST be reported for every optimisation. No change MUST be made without a measurement. | The numbers exist in `PROGRESS.md` | P0 |
| R14.9 | Every list screen MUST be going through part 2's macros. Screens that are not MUST be found and migrated. | Audit list + review | P0 |
| R14.10 | Duplicated table/filter/form logic MUST be reduced to one implementation. | Review | P0 |
| R14.11 | Clicks for the top-10 most frequent tasks MUST be counted and reduced, with both numbers reported. | The numbers exist | P1 |
| R14.12 | Unnecessary screens MUST be deleted. | Review | P1 |
| R14.13 | Authorization coverage SHOULD be reviewed across routes. **Demoted from MUST by D-B** — with one user the guard is a no-op; a spot-check replaces the exhaustive per-route audit. | Spot-check with findings noted | P2 |
| R14.14 | A test SHOULD assert web POST routes carry an authz guard (G10). **Demoted from MUST by D-B.** | `pytest -q` | P2 |
| R14.15 | Input validation, file-upload handling and error messages MUST be reviewed; errors MUST NOT leak internals. | Audit findings | P0 |
| R14.16 | Dependencies MUST be audited for known vulnerabilities. | Audit output | P0 |
| R14.17 | The full test suite MUST stay green throughout; tests MUST be added where refactors created risk, especially the de-duplication work. | `pytest -q` | P0 |
| R14.18 | No new features MUST be added. A new screen in the diff is a defect in this part. | Scope review | P0 |
| R14.19 | A written summary MUST state what changed and what was measured. | The summary exists | P0 |
| R14.20 | Saved views MUST NOT be built. **Cut by D-D** — feature X.3 no longer applies. | Scope review | P0 |

---

## 16. Part 12 — Product Challenge · Phase X · tag `part-12-done`

**Goal:** adversarial review of the finished product. **Report only — no code changes.**

| ID | Requirement | Acceptance | Pri |
|---|---|---|---|
| R15.1 | Every screen and feature MUST be reviewed against: should this exist · can it merge · can it simplify · can it be removed. | Coverage check against the nav | P0 |
| R15.2 | Each one MUST be judged from four seats: FOUNDER (and how often) · OPERATIONS executive · PROCUREMENT executive · WAREHOUSE employee understanding it without training. Per D-B only the founder seat is real today — ask the other three anyway as a growth test, but MUST NOT justify a screen by a user who does not exist. | Four verdicts per screen, with the hypothetical ones labelled | P0 |
| R15.3 | Architectural decisions MUST be challenged too, not only screens — **including decisions D-A..D-D themselves.** If dropping FIFO, batch tracking or the QBO bridge turned out to be wrong, say so with evidence. | Present in the report | P0 |
| R15.4 | Things that exist because they were on a roadmap rather than because someone needs them MUST be named explicitly. | Present in the report | P0 |
| R15.5 | Every recommendation MUST cite the file and the screen, say what would be cut, and say what breaks if it is cut. | Report review | P0 |
| R15.6 | The deliverable MUST be a prioritised report in four sections: Cut (with blast radius) · Merge (what collapses into what) · Simplify (the specific reduction) · Keep as-is (why it earns its place). | Report structure | P0 |
| R15.7 | NO code changes MUST be made. The session MUST stop after the report and wait for a decision. | Empty diff | P0 |
| R15.8 | The report MUST optimise for fewer, sharper screens — not for more features. | Review | P0 |

---

## 17. Traceability — `06-feature-list.md` → parts

The feature list's Phase 1/2/3 column is superseded. Current mapping of its sections:

| Feature list § | Goes to part(s) |
|---|---|
| §1 Dashboard | **9** (replaces the placeholder); 1.5 My tasks → 9 |
| §2 Sales | 2.10–2.11 pricing → **2**; 2.12–2.13 pipeline → **6**; 2.14 margin analytics → **8**; rest done |
| §3 Customers | 3.4–3.7 → **6**; 3.8 receivables view → **8**; 3.9–3.11 leads/competitors → **6**; 3.12 → **2** |
| §4 Products · §5 Categories | **2** |
| §6 Inventory · §7 Warehouse | 6.1–6.8, 7.1–7.4 largely done; 6.9 cycle counts → **5**; 7.5 → **3**; 7.6–7.7 → **5** |
| §8 Procurement · §9 Purchase Orders | 8.1–8.2, 8.5 → **3**; 8.3–8.4 → **4**; 9.x → **3** |
| §10 Suppliers | 10.1–10.4 → **2**; 10.5–10.6 evaluation → **4** |
| §11 Finance | 11.8, 11.13 ageing → **8**; 11.15 credit note → **7**; **11.14 QBO → CUT** |
| §12 Reports · §13 Analytics | 12.3 CSV export → **2**; 12.1–12.2, 12.5 → **8**; 13.x KPIs → **10** |
| §14 Tasks · §15 Documents | Largely done; **14.5 notifications → CUT** |
| §16 Settings | **2**, except **16.12/16.13 users+roles UI → CUT** and **16.15/16.16 ADR log + SOP index → CUT** |
| §17 Cross-cutting | X.1 palette + X.6 keyboard → **11**; **X.3 saved views → CUT**; X.2/X.4/X.5/X.7/X.8 done or in **1** |

### Cut features — closed, not deferred

Decision **D-D** cut these outright on 2026-07-28. They are **not a backlog**. Reintroducing any of
them is a new product decision requiring its own justification — not a matter of "getting to it".

| Feature | Source | Why cut |
|---|---|---|
| QuickBooks Online bridge | 11.14, `09-api-architecture.md` §QBO | Not in use; a feature-flagged bridge to a system of record we do not keep |
| Notifications / inbox | 14.5 | D-B: one user. Nobody to notify |
| Saved views | X.3 | Query-string state (R2.3) already makes filters shareable by URL; a persistence layer on top earns nothing for one operator |
| Decisions log (ADRs) | 16.15 | `docs/` already serves this purpose in git |
| SOP index | 16.16 | No staff to hold to an SOP |
| Users & roles management UI | 16.12, 16.13 | D-B: one user. The authz *mechanism* survives (R1.4); the management screens do not |

### Cut capabilities within surviving parts

Decision **D-A** removed these from the inventory work. Recorded here so their absence reads as a
decision, not an oversight:

| Capability | Requirement | Why cut |
|---|---|---|
| Batch / lot tracking | R6.7 | No date-sensitive or lot-traced lines in the catalog; no customer demands lot traceability |
| Expiry dates + expiring-soon alerts | R6.7 | Same |
| FIFO consumption order | R6.8 | No lots to consume in order |
| FIFO valuation layers | R6.9 | Replaced by weighted average (R6.16). Margin never depended on it — `MarginService.gp` uses the line's snapshotted purchase price (R11.6) |

---

## 18. Change log

| Date | Version | Change |
|---|---|---|
| 2026-07-28 | 1.0 | Register created for the 15-part split; `06-feature-list.md` phase column superseded; deferred items made explicit |
| 2026-07-28 | 1.2 | Corrected the stock-writer's name throughout: the method is `InventoryService.record_movement`, not `post_movement`, which has never existed in the codebase. Named wrongly in 18 places across 5 docs, including the **G8, R4.8, R6.15, R7.6 and R9.4 acceptance criteria** — P0 gates naming a method no session could call. No requirement changed meaning; `record_movement` is what all 6 callers use |
| 2026-07-28 | 1.1 | Product decisions D-A..D-D applied. Re-cut to 12 parts (requirement IDs deliberately NOT renumbered). R6.7/R6.8/R6.9 struck; R6.16 added; R6.10, R6.14, R11.6 rewritten. R2.6/R2.7 demoted to P2. G10, R1.5, R14.13, R14.14 demoted; R6.13, R7.12, R14.2, R14.4 relaxed. R9.12 raised to P0. G17, R3.13, R10.14, R14.20 added as explicit do-not-build guards. §17 rewritten: five deferred items are now **cut**, with the reason per item |

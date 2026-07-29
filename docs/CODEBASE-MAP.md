# ApexOS — Codebase Map

> **Read this instead of exploring.** It exists so a session can orient in ~200 lines rather than
> reading 25 files to rediscover what's where. If you find yourself opening files just to learn the
> layout, that's what this is for — and if it turned out to be wrong or missing something, fix it in
> the same session, because a stale map is worse than none.
>
> **Deliberately structural.** No line counts, no exact signatures, no "current state" — those rot
> within a part. Volatile facts belong in the `▶ CURRENT WORK` block in `PROGRESS.md`, which gets
> rewritten every session. This file changes only when the *shape* of the code changes.

---

## Routing table — "I need to…"

| I need to… | Read | Don't read |
|---|---|---|
| Build or change a list screen | `app/modules/<feature>/listing.py` (the spec — usually the only file you touch), then `app/db/listing.py` / `app/web/listing.py` for the contracts | Any individual page module "for an example" — the usage block at the top of the list-macro section is the example |
| Add a master to the uniform treatment | `app/web/pages/masters.py` — a `MasterPage(...)` registry entry is the whole screen (~6 lines) | Writing a page module; nine masters already share one |
| Add a master with its own domain page | `app/modules/products/listing.py` + `app/web/pages/products.py` — the reference pair (~80 lines total) | Re-deriving the pattern from the machinery; copy the pair and change the config |
| Work on the buy side | `app/modules/procurement/preorder.py` for requisition/RFQ/quotation, `service.py` for PO → receive → bill. The two halves are independent | The other half. That seam exists so you only read one |
| Show a score, rate, recommendation or forecast | `app/db/explain.py` (the shape) + the `explain_panel` macro (the rendering). Build an `Explained`; never format a number into a template | Inventing per-screen explanation markup — G11 has exactly one implementation |
| Ask "what should I buy" | `app/modules/procurement/recommend.py` — `RecommendationService(db).recommend(*, product_id=None, limit=None)` | Writing a second reorder calculation. R5.9 makes this the only one and R7.11/R13.6 check |
| Read a supplier's measured performance | `app/modules/suppliers/vendor.py` — `VendorIntelService` (score, lead time, on-time rate, price history). Read-only | Storing any of it; it is derived (G7, R5.10) |
| Ask "what does this party owe" | `CustomerRepository.outstanding_minor` / `.outstanding_by_customer()`, or the supplier pair. **These are THE receivable and THE payable** | Re-deriving `Σ invoice − Σ allocations − Σ credit_notes` anywhere. Two screens disagreeing is what R10.x exists to prevent |
| Ask "which documents make up that total" | `app/modules/finance/ledger.py` — `open_invoices(db, …)` / `open_bills(db, …)`, four queries whatever the row count | A `select()` per invoice; and do not write a second per-document balance |
| Age something, or say what is overdue | `app/modules/finance/ageing.py` — `AgeingService`; buckets are `AR_AGE_BUCKETS` in `finance/schemas.py` | Inventing a bucket boundary. Due **today** is not overdue, the bound is inclusive, and `bucket_for()` is the one rule |
| Apply money to documents | `app/modules/finance/allocation.py` — `AllocationService`, oldest due first, surplus refused | Editing an invoice. Money applied is a new `PaymentAllocation` row (G4) |
| Ask "will we be short of cash" | `app/modules/finance/cash.py` — `CashFlowService`. Flows take `date_from`/`date_to`, balances take `as_of` (R11.13) | Accruing anything into "actual" — cash is payments only, there is no bank ledger |
| Compute a cost of goods | `cash.py:_cogs` — `Σ line_subtotal − Σ MarginService.gp` | A second cost basis. It would put margin *and* DIO out of step |
| Report margin, or where it leaks | `app/modules/finance/margin.py` — `MarginAnalysisService.by_dimension` (product/customer/category/business_unit) and `.leakage` | Trusting `MarginService.gp` on a product with no purchase price — it reports **100% margin**. Check `purchase_prices_by_product()` first |
| Report GST | `app/modules/finance/gst.py` — `GstService.summary(*, date_from, date_to)`, by month | Anything that files, submits or reconciles against a portal (R11.10) |
| Show the founder what today needs | `app/modules/command_center/service.py` — the docstring's table says which part owns which number | Adding a figure here. A number the homepage wants goes in the OWNING service and is read here (R12.10); the projection has no `select()` and a namespace-walk test keeps it that way |
| Block deleting/deactivating something in use | `app/db/references.py` — `REFERENCES` is the policy | Writing a count query in a service; that is what this replaced |
| Delete something | `app/db/soft_delete.py` (its docstring is the contract) | Per-module delete code — there isn't any, by design |
| Prevent duplicates | `app/db/duplicates.py` — `NATURAL_KEYS` is the config | — |
| Show change history | `app/modules/activity/history.py` + `ActivityService.history()` | Any new table — there is none (R2.10) |
| Add a web page | `app/web/core.py` (render/redirect/filters), one existing page module in `app/web/pages/` | The other 16 page modules |
| Guard a web mutation | `app/web/security.py` | The JSON API's `require_permission` — the web one mirrors it |
| Add seed data | `app/seed/__init__.py`'s docstring, then write your own `app/seed/<domain>.py` | `core.py` end to end, and appending to `run()` |
| Understand a domain module | `docs/08-module-breakdown.md` § for that module | The module's four files, until you're actually changing them |
| Know what "done" means | `docs/REQUIREMENTS.md` § for your part | — |
| Know what changed recently | `git log --oneline -5 --stat`, `git diff part-0N-done..HEAD --stat` | Anything, until you've run those |

---

## Layout

```
apps/api/app/
  main.py            FastAPI app + lifespan (create_all, _ensure_new_columns, model imports)
  api.py             JSON API router assembly
  seed/              demo data, one module per section — see § Seed
  core/              config, database (engine/Session), errors, logging, security, money
  db/                cross-cutting persistence machinery — see § Shared machinery
  modules/<feature>/ domain logic: models · repository · service · router · schemas
                     + listing.py where the feature has a list screen (its `ListSpec`)
  web/               server-rendered UI
    core.py          Jinja env, filters, render(), redirect() helpers
    listing.py       request→view adapter + CSV export
    security.py      require_web_permission
    errors.py        centralized web error rendering (→ error.html)
    pages/*.py       one module per screen, auto-discovered by build_web_router
    templates/       base.html, error.html, _macros.html, <feature>/*.html
    static/app.css
  tests/             see § Tests
```

**One process.** The same FastAPI app serves the JSON API and the Jinja UI. **Web pages call services
directly, never over HTTP** (G9).

**Module ownership** (which module may *write* which entity) is in `docs/08-module-breakdown.md`
§ "Module → entity ownership". Not duplicated here — that file is authoritative and hasn't drifted.

---

## Shared machinery

Built in Part 1 and Part 2 C1. **These are one-definition-each by requirement.** If you're about to
write a second one, stop — you've misread R2.1/R2.4 or R1.1.

### `app/db/listing.py` — the query helper (R2.4)

Declarative list config and the only place `LIMIT` / `OFFSET` / `ORDER BY` appear.

- `Column`, `Filter`, `ListSpec` — the declarative config. `Column.kind` selects the renderer, so
  adding a column is a config line, not markup (R2.2).
- `build_select` — the single query builder. Applies `deleted_at IS NULL` for any model with the
  column and `business_unit_id` for any model with the mixin, automatically (R2.5).
- `query_page` / `query_rows` / `count_rows` — execution, all over `build_select`.
- `coerce` / `is_valid` — filter-value parsing; an invalid value degrades rather than raising.
- `static_options` / `model_options` / `distinct_options` / `active_options` — the `Filter.options`
  providers (fixed choices · another table's live rows · the values a column actually holds · an
  `is_active` boolean). A filter dropdown should need none of its own SQL.
- `Column.kind` renderers: `text · mono · money · number · date · datetime · badge · bool · bps · link`.
  `bool` is for `is_active`, `bps` for integer basis points (a GST rate). Both render identically on the
  list, on a detail page's `<dl>` and in the CSV — add a kind here rather than formatting in a template.

### `app/web/listing.py` — request → view (R2.3, R2.8)

- `params_from_request` / `view_from_request` — parse `?q=&sort=&dir=&page=&<filter>=`. **Query-string
  only** — no session, no cookies, so URLs are shareable and the back button works.
- `ListView` — what templates consume. `url()`, `sort_url()`, `page_url()`, `clear_url()`,
  `export_url()`, `chips()` each rebuild current state with one thing changed.
- `csv_response` / `csv_response_from_request` — export over the same `build_select` with pagination
  removed, so an export matches the filters on screen.
- `wants_csv` — a GET list route has two branches: CSV if this is true, HTML otherwise.

### `app/modules/<feature>/listing.py` — one master's list, as config (R2.2, R2.11)

**Where a `ListSpec` lives, and the only file a new list screen usually needs.** In the module rather
than beside the page because both halves consume it: the service's `list()` runs it through
`query_page`, and the page renders the same columns. `products/listing.py` and `customers/listing.py`
are the two worked examples.

- `Column.key` reads the **projected** row (`ProductRead`), so a computed field can be a column.
  `Column.sort` and `Filter.column` name real **model** attributes — a projection can't be sorted in SQL.
- A service passes `replace(SPEC, page_size=n)` when a caller wants a different page size (a form's
  product dropdown asks for 300); everything else comes from the spec.
- Projection happens in one place: `Service.to_read_many(rows)`, handed to `view_from_request(project=)`
  and `csv_response_from_request(project=)` so the screen and the file show the same values.

### `app/web/pages/masters.py` — nine config masters, one screen definition (R3.1, R3.2)

`MASTERS` is a tuple of `MasterPage(slug, title, label, entity_type, spec, fields, …)`. From it come
`/masters/{slug}` (list + export), `/masters/{slug}/{id}` (detail + change history), create, delete and
activate/deactivate — generically. **Adding a master is a registry entry**, not a page module.

- `/settings` is the hub, not a list: each `ListView` owns `?q=`, `?sort=` and `?page=`, so several
  lists on one URL would fight over them (R2.3). It kept the typed key/value settings.
- `deletable=False` / `toggleable=False` turn off the verbs a master should not have — tax slabs are
  version records (R3.6).
- Writes go to `ConfigService.create_master` / `set_master_active` / `delete_master`, which are one
  implementation across every master, guarded by `references.py`.

### `app/db/references.py` — relationship integrity (R3.7)

`REFERENCES` maps table → the references that block retiring a row, and `ensure_unreferenced` raises a
`ConflictError` **naming the documents in the way**. Read its module docstring; the rule is Part 1's:
*does anything read this row live?* A confirmed invoice snapshotted what it needed and never blocks
(which is what keeps R1.7 true); an open purchase order will read the master again at receipt, so it
does. `live_statuses` defines "open" per document type; `via=Via(...)` reaches a master through a
document *line* so the message quotes the document number.

**Every new model owes this map an entry, even an empty tuple** — a missing table reads as "not yet
considered", and silently permits deleting something live depends on. Deletion and deactivation ask the
same question, deliberately.

**A `Reference` names a column by string, so a wrong one fails at *check* time, not import time.** The
`warehouse` entry named `PurchaseOrder.warehouse_id`, which does not exist — a purchase order carries no
warehouse, the goods receipt does — so from Part 2 C3 until Part 3 C1 every warehouse deactivation died
with `AttributeError` instead of refusing. Fixed by reaching the warehouse through `GoodsReceipt` with
`via=Via(PurchaseOrder, ...)`. When adding an entry, exercise it (`blocking_references(db, row)`) rather
than only reading it; `tests/test_preorder.py` now does for warehouses.

### `app/db/soft_delete.py` — the delete write path (R1.1)

**`soft_delete(db, instance, *, actor_id, label=None)` is the only thing in the codebase that assigns
`deleted_at`.** Reads already filtered deleted rows (G3); this owns the write side. Read its module
docstring — it's the contract, and it explains three guarantees a hand-rolled assignment wouldn't give:

- Exactly one `activity_log` row, flushed in the caller's transaction (G5, R1.6).
- `PROTECTED_TABLES` refuses append-only tables with a readable reason via `ConflictError`, so the UI
  shows a sentence rather than a 500 (R1.3, G4). The guard is table-level and unconditional.
- Double deletion is refused rather than silently re-stamped.

**No cascade, no inbound-reference check, by design.** A deleted row keeps its primary key, so an
invoice for a deleted customer still renders the customer's name (R1.7). Policy rationale is in
`docs/DELETION-POLICY.md`.

### `app/db/duplicates.py` — duplicate prevention (R2.9)

`NATURAL_KEYS` maps table → natural keys; `ensure_unique` is the pre-save check. Raises
`DuplicateError` carrying `.field`, so the UI renders a field-level error and **no `IntegrityError`
ever reaches the caller**. Adding a master's dup rule is a `NATURAL_KEYS` entry, not new code.

### `app/modules/activity/history.py` — change history (R2.10)

Derived from `activity_log`. **No history table exists, and a test fails if one appears.**
`field_changes(instance, updates)` records field-level before/after into the `data` JSON column that
already existed; `ActivityService.history()` reads it back with actor names; `changes_from_data`
rehydrates. Render with the `history_panel` macro.

### `app/db/explain.py` — the one explained-number shape (G11)

`Explained(what, value, formula, window, inputs=(), records=(), unknown_reason=None, caveat=None)`
plus `Input` and `SourceRecord`. `value` is the **rendered** value — services format, templates never
compute — and `value is None` means unknown, which `Explained.unknown(...)` builds with the reason and
still with the formula, because "here is what I would need" is the useful half of an unknown (R5.11).
Pure: no session, no models, no queries.

Rendered by exactly one macro, `explain_panel`. G11 is P0 on every score, alert, recommendation and
forecast in the product, so **a new one builds an `Explained` and passes it to that macro** — inventing
per-screen markup for the arithmetic is the duplication R13.1 was scheduled to clean up.

### `app/modules/inventory/` — two append-only ledgers and the location tree (Part 5 C1)

Inventory owns **two** ledgers, both append-only, and stores no balance of any kind:

| Table | What it records | Read as |
|---|---|---|
| `stock_movement` | physical movement, signed | on-hand = `SUM(qty_delta)` |
| `stock_reservation` | commitment, signed (`RESERVE` + / `RELEASE` − / `CONSUME` −) | reserved = `SUM(qty_delta)` |

`StorageRack` → `StorageBin` hang under `Warehouse` (which stays in `config/models.py` — racks and bins
live here because they exist only to address stock). `stock_movement.bin_id` is **nullable and means
"bin not recorded"**: backfilling it would UPDATE an append-only ledger (G4). `StorageBin.kind` is
`stock | transit | quarantine`, and that column is what makes R6.4's four states derivable without a
state column anywhere — including the mechanism for a two-step transfer (OUT of a stock bin, IN to a
transit bin).

**`valuation.py` (Part 5 C2) is the read-only half**, beside `service.py`'s write half — the same split
`suppliers/vendor.py` has from `suppliers/service.py`. It derives two things and stores neither:

- **Weighted-average cost (R6.16)** — `SUM(qty × unit_cost) / SUM(qty)` over **purchases only**.
  `ACQUISITION_REASONS = ("PURCHASE",)`: a transfer moves the same units and would weight one purchase
  twice, putaway is net-zero, an adjustment or count corrects quantity without buying at a price.
  Uncosted purchases are excluded from both sides and disclosed, never counted as zero. No purchase at
  all ⇒ **unknown**, and the total excludes it rather than valuing stock at nothing.
  **Margin must never read this** (R11.6/D-A) — a source-walk test enforces it.
- **Age buckets (R6.10)** — `AGE_BUCKETS`, **upper bounds inclusive**. The balance is attributed to
  arrivals newest-first (older stock assumed to leave first); `PUTAWAY` is excluded or every put-away
  product looks like it landed today. Balance no arrival covers is reported as `unattributed`, not aged.
  **Not a FIFO layer** (D-A struck those): nothing stored, nothing consumed from a layer, valuation
  does not read it. The approximation is one string, rendered on screen and as `Explained.caveat`.

**`health.py` (Part 5 C3b) is the other read-only half** — ABC, dead stock, fast/slow movers and
low-stock alerts, every one of them derived per read and rendered through the one `explain_panel`
shape (G11). It adds no model: a class, a rate and a dead-stock verdict are all computed.

- **One definition of demand**, `CONSUMPTION_REASONS = ("SALE",)`, shared by ABC, the radar and the
  fast/slow split so they cannot disagree about what "moves" means.
- **ABC ranks by value consumed**, cumulative-share boundaries with inclusive upper bounds
  (80/95/100) — the same edge convention as `AGE_BUCKETS`.
- **The dead-stock radar reads the last SALE**, not the last movement: a cycle count must not make
  year-old stock look alive. `last_consumption_at()` vs `last_movement_at()` — two different questions.
- **Low stock triggers on AVAILABLE**, not on hand: committed stock cannot cover a new order.
- **`reorder_suggestions` is a bare delegation** to `RecommendationService.recommend` (R7.11). Never
  reimplement it — a source walk fails on a second `def recommend` anywhere in `app/`.

The verbs other modules call:

- `InventoryService.record_movement(...)` — **the only writer of `stock_movement`** (G8). A source-walk
  test fails if anything else constructs one. `bin_id` and `occurred_at` are both optional;
  `occurred_at` is how the seed fabricates aged history at insert time instead of UPDATE-ing a ledger.
- `ReservationService.reserve / release / consume` — **the only reservation mechanism** (R6.6). Sales
  calls `reserve` at order confirm, `consume` at fulfilment, `release` at cancellation (R9.8/R9.9).
  Adding a flag or a second path is the specific failure R6.5 exists to prevent.
- `InventoryService.states()` / `.bin_stock()` / `.location_rollup()` / `.available()` — derived reads
  for the screens; each is one or two grouped queries for a whole page, never a query per row.

### `app/modules/finance/` — statements, ageing, collections, allocation (Part 8 C1)

Four modules, and the split is by *question asked* rather than by layer:

- **`repository.py`** — the grouped reads everything else is built on. `allocated_by_invoice()`,
  `credited_by_invoice()`, `allocated_by_bill()` return dicts, so a per-document open balance costs
  three sums for the whole table rather than three per row.
- **`ledger.py`** — `open_invoices` / `open_bills` (the per-document open balance, **clamped at
  zero**) and `PartyLedgerService` (the running statement). A statement's closing balance IS
  `outstanding_minor`; its lines are that method's own terms itemised, so `Σ(debit − credit)` equals
  it by construction and `statement_note()` exists only to shout if it ever stops.
- **`ageing.py`** — `AgeingService.ar_ageing / ap_ageing / collections / payments_due`.
  `unaged_minor` is the deliberate residual: it makes `Σ buckets + unaged == the one receivable`
  hold **unconditionally**, so a bucket total can never quietly disagree with the party total.
- **`allocation.py`** — one receipt across many documents, **oldest due date first**. More than the
  total open is refused naming the applicable figure, because unallocated cash would be money the
  receivable definition cannot see.

Two disagreements already in the tree were fixed here, and both are worth knowing about because they
are the shape of mistake this area invites: `ReportService._ar_aging` had its own arithmetic, never
subtracted credit notes, and aged nothing at all despite the name (both ageing reports now delegate);
and `InvoiceService`'s `balance_minor` was `total − paid`, so an invoice reduced by a return showed a
balance the customer did not owe — and `add_payment` would have collected it.

- **`cash.py`** (Part 8 C2) — `CashFlowService`: cash flow, working capital, and the cash conversion
  cycle. The split that matters is **flows take `date_from`/`date_to`, balances take `as_of`**
  (R11.13), because a window on a balance looks rigorous and means nothing. "Actual" cash is
  payments — there is no bank ledger, so nothing is accrued and the screen says so. "Committed" is
  documents that exist with a due date inside the window; confirmed-but-uninvoiced orders and
  confirmed-but-unbilled POs are reported beside it as *pipeline* and excluded, because no due date
  exists for either. `COMMITTED_TERMS` is that definition in prose, kept next to the arithmetic
  because the test asserting the figure matches its definition reads the same words the screen prints.

`AR_AGE_BUCKETS` lives in `finance/schemas.py` beside `bucket_for()`, matching `AGE_BUCKETS` in
`inventory/schemas.py`: `(key, label, inclusive_upper_bound)`, printed on screen, every edge tested.
The first bound is `0`, which is R10.6's whole point — **an invoice due today is not overdue.** A NULL
`due_date` is aged from the invoice date and the screen says so, because zero-day terms already
produce exactly that due date.

- **`margin.py`** (Part 8 C3) — `MarginAnalysisService`. `by_dimension` is **one** projection
  parameterised by `MARGIN_DIMENSIONS`, not four near-copies; the only thing that varies is which key
  a line is filed under. Cost is `MarginService.gp` (R11.6) and revenue is the **tax-exclusive**
  subtotal, because GST is collected for the government rather than earned. **The trap:** `gp` reads
  a missing purchase price as zero and therefore reports a 100% margin, so every line is checked
  against `purchase_prices_by_product()` and an unpriced one is *counted and excluded*, never
  averaged in. `leakage` builds only indicators that can produce clickable records — freight has no
  field anywhere in the schema, so it is named under `not_measured` rather than shipped empty
  (R11.8), and the indicators are deliberately never summed into one figure because they measure
  different quantities about overlapping lines.
- **`gst.py`** (Part 8 C3) — `GstService.summary`, by calendar **month**, because that is the period
  GST is paid for. `ReportService._gst_summary` delegates to it; it used to return one lump for the
  whole window, which no monthly return can be reconciled against.

**Three habits this area established, worth copying.** `_days()` in `cash.py` and `_bps()` in
`margin.py` are each the only division in their module: one explicit rounding step with its reasoning
written down, returning `None` rather than a flattering `0` when the denominator is empty — and
neither goes through `round_minor`, which is the one *money* rounding step. `_thin_window_caveat()`
marks any day count longer than the window it was measured over, because DIO lands near 10,000 days
on the seeded data — arithmetically right, useless as a precise figure — so the screen calls it a
direction rather than looking authoritative. And when two figures measure different things, they are
shown separately with a sentence saying why, never added.

### `app/modules/command_center/` — the homepage, which computes nothing (Part 9 C1)

Three files and no fourth: `schemas.py` (`Figure`, `Alert`, `AlertRecord`, `QuickAction`,
`ActivityEntry`, `CommandCenter`), `service.py` (`CommandCenterService.load(*, as_of=None)`), and
`__init__.py`. **No model, no repository, no router** — `app/web/pages/command_center.py` is a
two-line page that calls `load()` and renders. The module owns no entity and holds no arithmetic;
`service.py`'s docstring carries the table of which part owns which number, and that table is the
design.

The three questions R12.1 fixes are three fields, in the order they are asked: `happened` ·
`attention` + `alerts` · `actions`. `position` and `activity` both answer "what happened" — one as a
balance, one as a log.

**Two requirements are enforced by validators rather than by review**, which is the part worth
copying:

- `Figure` raises unless its `href` starts with `/`, so R12.7's "every number drills through" cannot
  be forgotten on a tile added later.
- `Alert` raises on empty `records`, and again if `count` is below the list it carries. R12.8's "an
  alert with nothing to click MUST be removed" is therefore structural: a family that finds nothing
  is **omitted**, and the page shows an empty state, which is information. `hidden_count` states
  what a capped list is not showing so the cap is never silent.

**Where the numbers come from** — never recomputed here (R12.10, G16): `MarginAnalysisService`
(today's revenue and gross margin off ONE one-day report, so they cannot disagree about which lines
they counted, and `leakage` for the margin alerts) · `CashFlowService` (`cash_flow` for collections
today and the trailing window, `committed` for the **forward** window, `working_capital` for both
the position figure and the inventory tile — reading its inventory term rather than
`ValuationService.stock_value()` means tile and position cannot disagree) · `AgeingService`
(`ar_ageing`/`ap_ageing` for the two totals, `collections` for the customer alert) ·
`InventoryHealthService.low_stock` · `ProcurementCalendarService.arrivals` (**not** `calendar()`,
which also runs the recommendation engine this page does not show; the `overdue` bucket is the
vendor alert, and `unpromised` is excluded because R5.7 says an order nobody promised is not due) ·
`pending_count()` on the sales and procurement repositories · `ActivityService.recent`.

**The empty state distinguishes a measured zero from no measurement** (R12.15). `is_empty` is an
empty `activity_log` (G5 makes it the most reliable "nothing has happened" evidence in the schema)
plus no alerts plus no figure carrying a value; the template then says so once, at the top, and
leaves the tiles visible rather than presenting them as measurements. A business with a hundred
invoices and nothing due today still sees its zeros, because those are facts. Loading the page
against a schema-only DB is what found three hints that read as measurements of records that did
not exist — "no line today has a purchase price behind it" on a system with no lines is simply
false, and the seeded data cannot reach that branch.

**Measured at 81 queries and a ~51 ms median warm render** (R12.12/R12.14) — thirteen grouped
projections of 1–14 queries each, none growing with the row count.
`test_r12_13_one_page_load_stays_inside_its_query_budget` holds a ceiling of 120, loose on purpose:
what it catches is a per-row read, and with 311 products and 273 stock states those land in the
hundreds.

Building it found the fan-out it was measuring for. `InventoryHealthService.low_stock` called
`stock()` — a grouped read of the whole catalogue — **inside** its loop over `states()`: 274 queries
and 979 ms of what was a 344-query, 1,096 ms page, and `/inventory` had paid it since Part 5. The
lesson generalises: a per-row read hides inside a loop-invariant *call*, not only inside an obvious
`select()`.

`app/web/templates/command_center/index.html` renders it with Part 2's macros and one local `figure`
macro that switches on `kind` exactly as `cell` does for list columns. **No `<svg>`, `<canvas>` or
chart marker reaches the page (R12.9)**, and a test asserts it.

### `app/modules/sales/fast_entry.py` — what makes order entry quick (Part 7 C2c)

Reads only, and every helper is **bulk** — the entry form shows ~300 products, so a per-product query
would be 300 round trips to render one page. A test counts the statements rather than grepping the
source, because a text match cannot tell a call from a comment.

- **`picker_hints`** puts the price and **how much is AVAILABLE** beside every SKU in the datalist.
  Available, not on-hand: confirming an order reserves (R9.8), so on-hand would offer stock already
  promised to somebody else.
- **`last_order_lines`** is reorder-from-last-order, excluding cancelled orders, ordered by
  `(order_date, id)` because seeded orders share a date.
- The form posts `product_code` (a SKU) and resolves it through **Part 3's `_lines`** — one resolver,
  which names an unknown SKU back to the founder instead of dropping the row.
- **`autofocus` is the single biggest saving**: without it the caret starts outside the form, behind
  19 focusable sidebar links. See `docs/parts/part-07.md` for R9.13's measured before/after.

### `app/modules/sales/returns.py` — the gap after the invoice (Part 7 C2a)

**The invoice is never mutated** (G4/R9.5). A return posts stock IN through `record_movement` and
raises a `CreditNote`; the receivable falls because
`CustomerRepository.outstanding_minor` = `Σ invoice − Σ allocations − Σ credit_notes`. An invoice is
a document the customer already holds, and editing it destroys the record of what was billed.

- **`returnable_qty(invoiced, already)` is THE definition** (R9.6), clamped at zero — the shape
  `PurchaseOrderService.open_qty` gave back orders. Do not inline a second subtraction.
- **The whole payload is validated before anything is written**, so a partly-invalid return does not
  leave half its stock posted.
- **Returns are priced as invoiced**, never re-resolved: a credit is for what the customer paid.
- **The credit note carries no lines** — the return holds them.

**Reservation is wired here too** (R9.8/R9.9): `SalesOrderService.confirm` reserves *after* the
credit gate, `fulfill` consumes then posts stock OUT (reservation first, or `available` would
double-count), and `cancel` releases — refusing a fulfilled order, because shipped stock is undone
by a return, not a status change.

### `app/modules/sales/quotation.py` — the gap before the order (Part 7 C1)

create → send → (revise…) → convert, or → expire. Sits beside `service.py`'s order spine.

- **Revisions mirror Part 3's append-only shape** (`QuotationRevision`, current =
  `max(revision_no)`, **no `superseded_at`**), not Part 6's `valid_from`/`valid_to`. A credit policy
  is a *period*; a quotation is a *sequence of offers*. **Two versioning idioms is the limit — do
  not add a third.** A test asserts neither `superseded_at` nor `valid_to` is on the table.
- **`revision_no` 1 is written by `send`**, not `create`, and `revise` requires a *sent* quotation:
  a draft nobody has seen has no agreement to preserve (R4.7's reasoning).
- **Conversion calls `SalesOrderService.create`** and passes each quoted `unit_price_minor`
  explicitly (R9.3). Re-resolving would honour today's list price instead of what was agreed — a
  source walk asserts the conversion does not build order lines itself.
- **Its document type is `SQT`.** `QUO` already numbers Part 3's *supplier* quotations, and sharing
  it would interleave two unrelated sequences in `number_sequence`.

### `app/modules/customers/health.py` — the customer health score (Part 7 C2b)

Four measured inputs — frequency, profitability, payment, recency — each on a 0–100 scale with the
conversion **shown**, weighted 25/30/25/20 and **renormalising over whichever inputs exist**. The
house pattern for a weighted figure, taken from `suppliers/vendor.py`. Stores nothing (G7).

- **Profitability goes through `MarginService.gp`** — the existing margin logic (R11.6), never a
  valuation layer. A source walk enforces it.
- **"Never invoiced" is a MISSING input, not perfect payment behaviour.** Collapsing the two made a
  brand-new customer score 100 — worse than the default R9.11 forbids, because it reads as praise.
  Invoiced-and-settled earns full marks; never-invoiced is unmeasurable.
- **No input at all ⇒ `Explained.unknown`**, and the panel still lists every input it would have
  used with the reason each is missing.
- **The partial-basis caveat names what was left out**, and a test re-derives the published score
  from its own published inputs — so "the numbers are on screen" means they can be redone.

### `app/modules/customers/` — versioned terms, the credit gate, the timeline (Part 6)

`credit.py` and `timeline.py` sit beside `service.py` for the same reason `valuation.py` and
`health.py` sit beside the inventory service: derivation and enforcement, kept out of the CRUD half.

- **`CustomerCreditPolicy` is VERSIONED** (`valid_from` / `valid_to`; current is `valid_to IS NULL`).
  `CreditPolicyService.set_policy` **appends** a version and closes the previous one, with a mandatory
  reason. `CustomerService.update` delegates to it — it used to edit the row in place, which made
  "prior version readable" untrue despite the columns looking right.
- **`CreditPolicyService.check` is integer arithmetic on minor units** (G1): at the limit is allowed,
  one minor unit over is not. **A limit of zero means none recorded, not "refuse everything".**
  `enforce` passes, refuses with all four numbers, or records an override as ONE activity row against
  the customer — which is how the override reaches the timeline.
- **`SalesOrderService.confirm` runs the gate first** and leaves a refused order in `draft`. R9.8 must
  reserve stock **after** it passes.
- **`CustomerTimelineService.events` is a projection**, six sources and six queries, with **no events
  table** — the requirement forbids one. Its sort key carries a per-kind causal rank because several
  sources default to `func.now()` and tie.

### `app/web/security.py` — web authz (R1.4)

`require_web_permission(permission)` — a FastAPI dependency that renders 403 `error.html` on GET and
redirects with an error flash on POST, mirroring the JSON API's `require_permission`. **A no-op in
practice** (decision D-B: one user, whose actor holds `*`); it exists as the prod pattern. Do not build
a roles/permissions UI on top of it — that's cut.

### `templates/_macros.html` — the UI vocabulary

Imported as `ui` in templates. General: `page_header`, `stat`, `badge`, `empty`, `delete_button`.
List machinery: `list_toolbar`, `list_table`, `pagination`, `list_empty`, `cell`. History:
`history_panel`. Explainability: `explain_panel`.

`{% call(row) ui.list_table(view) %}` is the shape that keeps a bespoke Actions column (so
`ui.delete_button` survives) while the rest of the table stays generic. **A usage block sits at the top
of the list-macro section in the file — copy that rather than reverse-engineering a page.**

---

## Patterns

**List page** (the shape every master now follows): `<feature>/listing.py` declares the spec; the GET
route is two branches over it —

```python
project = ProductService(db).to_read_many
if wants_csv(request):
    return csv_response_from_request(request, db, PRODUCT_LIST, project=project)
return render(request, "products/list.html",
              view=view_from_request(request, db, PRODUCT_LIST, project=project))
```

— and the template is `list_toolbar` / `list_table` / `list_empty` / `pagination`, with the `{% call(row) %}`
block carrying the per-entity Actions verbs. No page holds a query or table markup.

**Page module** (`app/web/pages/<screen>.py`): module-level `router`, auto-discovered by
`app.web.build_web_router`, mounted at root. Handlers take `Request` + `Session` + the current actor,
call a service directly, and return `render(...)` or `redirect(...)` from `web/core.py`. Forms POST to
a server route → call the service → 303 redirect (PRG).

**Service verb that changes state:** does the work and writes **exactly one** `activity_log` row in the
same transaction, verb named `<entity>.<past_tense>` (G5). Services flush; the request boundary commits.

**Errors:** raise the typed errors in `app/core/errors.py` (`ConflictError`, `NotFoundError`, …). The
web layer's `errors.py` renders them into `error.html` centrally — **handlers don't try/except for
presentation.** A bad id therefore renders the error page, not a stack trace (R1.10).

**Money:** integer minor units everywhere, helpers in `app/core/money.py`. No floats in any money path
(G1).

**Derived, never stored:** stock balances, receivables/payables, back-order quantities, running
balances, vendor scores, measured lead times, on-time rates and purchase recommendations (G7). If
you're adding a mutable counter for something computable, re-read G7.

**Every number that is a judgement carries its reasoning** (G11). A score, rate, recommendation or
forecast is returned as an `Explained` (`app/db/explain.py`) and rendered by `explain_panel`, so the
formula, the data window, each input with its weight and links to the source records are on the same
screen as the figure. Where it cannot be computed the answer is `Explained.unknown(...)` and the screen
says "unknown" — **never 0, never 50, never a blank**. `VendorIntelService` and `RecommendationService`
are the two worked examples; parts 5/7/8/9/10 add more and must not invent a second shape.

**A domain module may split its service file by *flow*, not by layer.** `procurement/` has three:
`service.py` (PurchaseOrderService + GoodsReceiptService — create → confirm → receive → bill),
`preorder.py` (RequisitionService + RfqService — everything in front of the PO) and `recommend.py`
(RecommendationService + ProcurementCalendarService — planning, which reads all of it and writes none
of it). The repository does
the same: `ProcurementRepository` and `PreorderRepository`. The test is whether a session working on
one half needs to read the other; here it doesn't, and that is the only justification. Shared
primitives move to module level rather than being reached across classes — `default_business_unit`,
`tax_bps_for` and `_round_minor` in `service.py` are called by `preorder.py`, so a quotation and the
PO it becomes cannot disagree about tax. **Do not split a module that has no such seam.**

**A document that must not change in place gets a revision table, not a mutable row** (R4.7, G4).
`purchase_order_revision` + `purchase_order_revision_line` hold a verbatim snapshot of the lines as
agreed; the live `purchase_order_line` rows carry current figures, and `PurchaseOrderService.revise`
appends a snapshot rather than overwriting one. Two rules that make the claim true rather than
decorative: revision 1 is written by `confirm` (a draft has no agreement to preserve), and there is **no
`superseded_at`** — the next revision's `created_at` already says when a version stopped applying, and a
column written after insert would mean the table is not append-only after all. The current version is
`max(revision_no)`, derived, so no pointer can drift. `goods_receipt.purchase_order_revision_id` records
which version goods were accepted against, and naming a superseded one is refused (R4.10). Copy this
shape for sales-order amendments and credit notes rather than inventing a second one.

**One definition of "open"**: `PurchaseOrderService.open_qty(line)` — ordered − received, clamped at
zero, called by `receive` too. Adding a second subtraction inline is how the screen and the guard start
disagreeing.

**Conversion between documents calls the target's service; it never rebuilds it** (G16).
`RequisitionService.convert_to_po` and `RfqService.award` both assemble a `PurchaseOrderCreate` and
hand it to `PurchaseOrderService.create`, so document numbering, price snapshotting, tax and totals
have one implementation. A conversion writes one `activity_log` row on the *source* document; the
target service writes its own on the target.

**Where a number can't be computed yet, render "unknown"** (G11). The vendor comparison shows a `score`
of `None` and a `score_note` saying part 4 owns scoring — never a placeholder 0 or 50 that reads as
computed. Best-in-row/column marking (`is_cheapest`, `is_fastest`) is computed in the service, not the
template, and marks **every** tied entry: silently picking one would be advice the data doesn't support.

---

## Seed (`app/seed/`)

A package since Move 0 (2026-07-28), because G14 makes every part extend the seed and the old
single 1,075-line module had to be read in full to append to it:

```
app/seed/
  __init__.py    the docstring that tells you how to ADD a section — read this one
  core.py        run() — the orchestrator, plus sections not yet extracted
  helpers.py     SeedContext + get_or_create + record_creation
  catalogue.py   the static data tables + the deterministic bulk generators
  preorder.py    seed_preorder(ctx) — Part 3's section, the worked example
  vendor.py      seed_vendor(ctx) — Part 4's: mapping + MOQ, receipt history,
                 scorecards, price timeline, the two reorder cases, one late arrival
  inventory.py   seed_locations(ctx) — Part 5's: racks + bins in both warehouses (incl.
                 one transit and one quarantine bin), putaway of 12 products as NET-ZERO
                 movement pairs, one live reservation, four BACKDATED purchases at four
                 prices, sales demand across 10 products (so ABC forms real classes), an
                 in-transit transfer awaiting receipt, a variance count and a clean one
  customers.py   seed_customer_depth(ctx) — Part 6's: contacts, ship-to branches, notes,
                 two credit-policy VERSIONS, and a breaching order overridden on a
                 DIFFERENT customer (see the note below)
  quotations.py  seed_quotations(ctx) — Part 7 C1's: one sent, one revised twice, one
                 converted at the quoted price (on a third customer, same note)
```

**The putaway is a net-zero pair on purpose** — out of the unaddressed pool, into a bin — because
addressing existing stock must change its location without changing on-hand, and rewriting the
original movement would break G4. A test asserts `SUM(qty_delta) WHERE reason='PUTAWAY'` is 0.

**Seeding a document in an OPEN status can break unrelated tests.** Part 6's breaching order left a
*confirmed* order on the first customer, which made it undeletable (`references.py` treats confirmed
as open) and broke two Part 1/3 tests that encode "that customer's work is closed". Part 7 C1 then
hit the identical edge with a *draft* order from a quotation conversion — **draft counts as open
too**. Both now target a different customer. **Before seeding an open document, ask which tests treat
that party as quiet.** Twice is a pattern, not a coincidence.

**Adding a section:** write `app/seed/<domain>.py` exposing
`def seed_<domain>(ctx: SeedContext) -> dict | None`, guard it on its own emptiness check, and add one
call in `run()` **before** the master-change-history pass. Do **not** append to `run()`. You then read
your own module plus `run()`'s call order — not the whole seed.

`run()` is idempotent via `get_or_create`, and builds in this order — each block is a
`# --- section ---` comment, so jump to the one you need:

reference data → founder user → org/config → categories → products + prices + opening stock →
demo customers + credit policies → demo suppliers → one complete buy loop (PO → confirm → receive →
bill → partial payment) → **the pre-order flow (3 requisitions + 1 RFQ with 2 quotes)** → one complete
sell loop (order → confirm → fulfill → invoice → partial payment) → second warehouse + transfer,
tasks, a document → pipeline stages, leads, opportunity, competitors → **vendor history (Part 4)** →
**locations + putaway + one reservation (Part 5 C1)** → master change history (always last).

Two passes run **last**, after every section: the master change-history backfill
(`record_creation` over the ten master tables) and the tax-slab window repair. Later sections create
masters too, so a mid-file pass would miss them.

**Bulk master rows** (R2.13): products and customers are ~311 and ~253 rows. The named demo rows stay
as literal lists (`PRODUCTS`, `DEMO_CUSTOMERS`) because other seed steps order and invoice them by
code; the rest come from `bulk_products()` / `bulk_customers()` in the reference-data section —
deterministic index arithmetic, **no randomness**, so a re-seed is idempotent and a test can name a row.
Status, stock and credit are deliberately uneven (draft/discontinued rows, zero-stock rows, a
credit-limit-zero account, accounts with no credit policy) so filters and empty states have something
to bite on (G14). `record_creation()` gives the *named* masters their `created` history line, since
`get_or_create` bypasses the services that would have logged it.

**The pre-order section seeds every state a screen can be in**, not one happy row: a requisition still
awaiting approval (so `/requisitions` has a decision to make), one approved and converted to a PO, and
one approved and out as an RFQ with two quotes back. The two quotes are deliberately asymmetric — the
cheaper unit price carries the slower lead time and the higher MOQ — so the comparison screen shows a
real trade-off rather than one obviously-best column (R4.15, G14).

**The vendor section seeds the shape of an answer, not just data** (R5.13): three suppliers, one with
both a scorecard and receipts (score 75, lead 4 days, on time 67%), one with receipts only (50 / 14 days
/ 50%, so the renormalisation caveat shows), one with neither (all three "unknown"). One receipt lands
**exactly** on the promised date, which is R5.4's boundary. Two products sit below their reorder level —
one with an open PO so the recommendation must subtract it, one without — both mapped to a supplier so
R5.8's sentence can name a measured lead time, and one of them with an MOQ *above* its shortfall so the
MOQ raise is on screen. One order is deliberately overdue so the calendar's worst column is not empty.
History is fabricated at INSERT time via `confirm(confirmed_at=…)` / `receive(received_at=…)`; the seed
never UPDATEs a ledger row (G4).

**`command_center.py` (Part 9) is the smallest section and the best one to copy** — 170 lines for a
single invoice, and the docstring is mostly *why*. Its whole purpose: `Payment.paid_at` defaults to
`now()`, so every seeded receipt is already dated today and "collections today" had a figure — but
every seeded invoice is placed by offset from its due date and the newest lands 30 days ago, so the
homepage's revenue and gross-margin tiles read ₹0.00. A headline section of three zeros cannot fail
visibly when the arithmetic behind it is wrong.

It adds **one invoice dated today, settled in full today**, on the customer at code-order offset 9.
Settled deliberately: it then touches no ageing screen, no chase list, and leaves the receivable
exactly as it was. Priced at list, so it adds no leakage offender — C3's two indicators must keep
firing on exactly the three lines seeded for them. Its second line is on `SKU-NOBUY-01`, so the
"lines with no purchase price are excluded" caveat is visible on the demo and not only in a test. It
imports `_make_invoice` / `_pay_invoice` / `_totals` from `finance.py` rather than writing a second
invoice path — the tax rounding has to be identical everywhere (G1).

**Don't read the file end to end to add rows** — read the one section.

---

## Tests (`apps/api/tests/`)

| File | Covers |
|---|---|
| `conftest.py` | Fixtures: in-memory DB, seeded session, test client, actor |
| `test_core.py` | Config, money, errors, uuid7, base mixins |
| `test_web_smoke.py` | Every nav page returns 200 and renders |
| `test_api_contract.py` | JSON API response shapes |
| `test_customers_service.py` | Customer service behaviour |
| `test_sales_flow.py` | order → confirm → fulfill → invoice → payment |
| `test_purchase_flow.py` | PO → confirm → receive → bill → payment |
| `test_soft_delete.py` | R1.1–R1.7: one mechanism, one activity row, protected tables refuse, double-delete refuses, referencing docs still render |
| `test_web_authz.py` | R1.4/R1.5: 403 render on GET, error-flash redirect on POST |
| `test_listing.py` | R2.3–R2.5, R2.8: filter/sort/pagination boundaries, soft-delete + BU scoping, export matches filters |
| `test_duplicates.py` | R2.9: field-level error, no `IntegrityError` escapes |
| `test_change_history.py` | R2.10: derived from `activity_log`, fails if a history table appears |
| `test_list_macros.py` | R2.1/R2.2: each macro renders against a real `ListView` |
| `test_master_pages.py` | R2.11: the machinery through the real `/products` and `/customers` pages — search/filter/sort/pagination, export matching the screen, duplicate rejection as a flash, history panel |
| `test_masters.py` | R3.1–R3.12: the same capabilities parametrised over **every** master in the registry, plus category reparent/tree, UoM factors, tax-slab versioning, and relationship integrity naming its blockers |
| `test_preorder.py` | R4.1–R4.6: requisition request/approve/reject/convert (to PO and to RFQ), RFQ issue to many suppliers, quote capture and its guards, the comparison's cheapest/fastest marking, award → PO at the quoted price, quotation history, and the `REFERENCES` entry per new model |
| `test_po_revisions.py` | R4.7–R4.11: revision preserves the prior version verbatim, revisions accumulate, one activity row per revise, partial receipt's back-order arithmetic, the back order derived and absent as a column, receipt-against-revision including the superseded refusal, `confirmed_at` persisted, and `blocking_references` run against a real revision |
| `test_vendor_intel.py` | R5.1–R5.6, R5.10–R5.14: the mapping and its exclusive preferred, MOQ, lead time measured from `confirmed_at`→`received_at`, the on-time boundary (`received <= promised` is on time) and the excluded unpromised receipt, the 60/40 score and its renormalisation, price history, the unknown paths, and that no writable lead-time field exists anywhere |
| `test_vendor_screens.py` | R5.12 + R5.5 on screen: each figure reaching its page **with** its formula, window and source records, the vendor comparison preferred-first, the price timeline, "unknown" rendering as the word, the three mapping POST verbs end to end, and the agreed MOQ reaching R4.5's grid |
| `test_procurement_planning.py` | R5.7–R5.9: the shortfall arithmetic with every term non-zero, an open PO not double-ordered, a draft not counted as on order, the MOQ raise, the calendar's five buckets and its never-bucket-unpromised-as-today rule, R5.8's sentence, and a source walk asserting no second recommendation engine exists |
| `test_command_center.py` | R12.1–R12.13 + G11/G15: the three questions in order; each of the twelve figures asserted **equal to the service that owns it AND non-zero on the seed**, because an equality between two code paths only tests what the data distinguishes; the ageing tiles' `side=` (the one pair a swap would hide); committed cash forward, and proven to differ from the trailing figure; the unknown-margin branch driven directly with a stub, since the seed cannot reach it; every href rendered *and* resolving; every alert's trigger and threshold on screen with linked records; the two schema validators refusing an unclickable figure and an empty alert; no chart marker; a namespace walk proving the projection holds no query and no model; no `activity_log` row written by a page load; and the query-count ceiling. `_rendered` / `_linked` are the escaping helpers — Jinja escapes what it interpolates, not the quotes you typed. `fresh_db` + `fresh_client` are R12.15's pattern: a second engine with `create_all` and nothing seeded, reached through a `get_db` dependency override so the real route, template and filters are what gets tested |
| `_web_routes.py` | Not a test — the shared route walk both `test_web_authz.py` and `test_web_smoke.py` use. FastAPI ≥ 0.140 wraps `include_router` in `_IncludedRouter`, so a shallow walk of `.routes` sees nothing; recurse via `.original_router`. Both callers assert a floor on what they found, because the R1.5 walk silently became `[] == []` when that changed |

Run `pytest -q`, never verbose.

---

## Known debt

**35 pre-existing `ruff` findings**, all in modules the current work hasn't touched — 30 `E501`, 4
`F841`, 1 `B007`. It was 39 through Part 2 C1; C2 deleted `CustomerRepository.search`, which held one
of the `E501`s, taking it to 38. Move 0 took it to 37: splitting `seed.py` into `app/seed/` moved
`import_all_models()` into the package `__init__`, so `core.py`'s imports sit at the top of their file
and the one `E402` is gone. Part 8 C3 rewrote `_gst_summary` and dropped two over-long lines, taking
it to **35**. **New work has added zero findings through nine parts, and that's the bar.** Part 11
(`R14.x`) clears them; until then `ruff check app/ tests/` reporting exactly 35 is a *pass*, and 36 is
a regression to fix before committing.

**`/analytics` still renders bar "charts" from `div` heights** (`.chart-bars` in `app.css`). R12.9
banned decorative charts from the *Command Center* and C1 obeyed it; `/analytics` was out of that
scope, so the CSS stays for now. Whichever part owns that screen should decide whether those bars
change a decision or should be a table.

**`/warehouse` and `/inventory` render every product** (`page_size=300`, no pagination) — harmless at
17 rows, now ~170 KB of HTML at 311. They are not list-machinery pages yet; whichever part owns them
should wire them onto `ListSpec` rather than raising the page size again.

**`/categories` renders a full parent dropdown per row** (~90 KB at 24 categories). Fine now, quadratic
later: a category picker that loads once and is reused, or a reparent form on the detail page only, is
the fix when it stops being fine.

**`/settings` renders eight master lists on one page**, so none of them can own `?q=`/`?sort=`/`?page=`.
Part 2 split them onto `/masters/{slug}` for exactly that reason; `/settings` is the hub. Any new
multi-list screen inherits the same constraint — decide the namespace before writing the page.

---

## Retired — do not follow

- `apps/web/` — deleted Next.js SPA. Gone from git; a stale local copy may still be on disk.
- Postgres + Alembic. Dev is SQLite via `create_all` + the additive `_ensure_new_columns` shim in
  `main.py`; prod Postgres reintroduces Alembic behind `DATABASE_URL`. See `docs/MIGRATION-STRATEGY.md`.
- `docs/BUILD-PHASES.md`, and the delivery/stack content of `docs/07`, `docs/14`, `docs/15`. Their
  *domain* content still stands; their *stack* content is historical.
- `PROGRESS.md`'s "How to run it" section — flagged superseded in-file; it still names `alembic` and
  `npm`, neither of which exists.

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

The verbs other modules call:

- `InventoryService.record_movement(...)` — **the only writer of `stock_movement`** (G8). A source-walk
  test fails if anything else constructs one. `bin_id` and `occurred_at` are both optional;
  `occurred_at` is how the seed fabricates aged history at insert time instead of UPDATE-ing a ledger.
- `ReservationService.reserve / release / consume` — **the only reservation mechanism** (R6.6). Sales
  calls `reserve` at order confirm, `consume` at fulfilment, `release` at cancellation (R9.8/R9.9).
  Adding a flag or a second path is the specific failure R6.5 exists to prevent.
- `InventoryService.states()` / `.bin_stock()` / `.location_rollup()` / `.available()` — derived reads
  for the screens; each is one or two grouped queries for a whole page, never a query per row.

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
                 movement pairs, one live reservation, and (C2) four BACKDATED purchases
                 at four prices on two products, straddling the age-bucket edges
```

**The putaway is a net-zero pair on purpose** — out of the unaddressed pool, into a bin — because
addressing existing stock must change its location without changing on-hand, and rewriting the
original movement would break G4. A test asserts `SUM(qty_delta) WHERE reason='PUTAWAY'` is 0.

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
| `_web_routes.py` | Not a test — the shared route walk both `test_web_authz.py` and `test_web_smoke.py` use. FastAPI ≥ 0.140 wraps `include_router` in `_IncludedRouter`, so a shallow walk of `.routes` sees nothing; recurse via `.original_router`. Both callers assert a floor on what they found, because the R1.5 walk silently became `[] == []` when that changed |

Run `pytest -q`, never verbose.

---

## Known debt

**37 pre-existing `ruff` findings**, all in modules the current work hasn't touched — 32 `E501`, 4
`F841`, 1 `B007`. It was 39 through Part 2 C1; C2 deleted `CustomerRepository.search`, which held one
of the `E501`s, taking it to 38. Move 0 took it to **37**: splitting `seed.py` into `app/seed/` moved
`import_all_models()` into the package `__init__`, so `core.py`'s imports sit at the top of their file
and the one `E402` is gone. **New work has added zero findings, and that's the bar.** Part 11 (`R14.x`)
clears them; until then `ruff check app/ tests/` reporting exactly 37 is a *pass*, and 38 is a
regression to fix before committing.

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

# Part 2 - Master data & shared machinery

> Closed record. Tagged `part-02-done`. Includes the R3.1 capability matrix, the R2.14 cost table, and Part 2's signature catalogue.

## Part 2 — Master data & shared machinery · **COMPLETE** · on `main` · tagged `part-02-done`

**Part 1 is COMPLETE and tagged `part-01-done`.** Its record is in the log below.

- [x] **C1** the machinery: list/table macros + generic query helper + CSV export + duplicate
      prevention + change history → commit `7419f67`
- [x] **C2** proven on products + customers, seed extended to 311/253 rows, R2.14 recorded →
      commit `5a1f89e`
- [x] **C3** rolled out to every remaining master + the special cases → commit `de73c23`

**Every P0/P1 requirement in §3 and §4 passes.** R2.6/R2.7 (CSV import) stay unbuilt — P2 by D-C.
R3.13 is a "do not build" and was not built.

### ▶ R3.1 — the capability matrix (no empty cells)

`S` search · `F` filters · `O` sort · `P` pagination · `X` CSV export · `A` audit trail (activity_log)
· `T` status · `D` soft delete · `H` change history · `V` validation · `I` relationship integrity
· `U` duplicate prevention

| Master | Screen | S | F | O | P | X | A | T | D | H | V | I | U |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Products | `/products` | ✅ | 3 | ✅ | 25 | ✅ | ✅ | 3-state | ✅ | ✅ | ✅ | open SO/PO | SKU + name/spec/brand |
| Customers | `/customers` | ✅ | 3 | ✅ | 25 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | open SO | code + name/city |
| Suppliers | `/suppliers` | ✅ | 3 | ✅ | 25 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | open PO | code + name/city |
| Categories | `/categories` | ✅ | 3 | ✅ | 25 | ✅ | ✅ | ✅ | ✅ | ✅ | cycle | products, children | code + name/parent |
| Business units | `/masters/business-units` | ✅ | 1 | ✅ | 25 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | cats, products, custs | code + name |
| Brands | `/masters/brands` | ✅ | 1 | ✅ | 25 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | products | code + name |
| Manufacturers | `/masters/manufacturers` | ✅ | 2 | ✅ | 25 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | none yet | code + name/city |
| Procurement models | `/masters/procurement-models` | ✅ | 1 | ✅ | 25 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | cats, products | code + name |
| Units of measure | `/masters/units` | ✅ | 1 | ✅ | 25 | ✅ | ✅ | ✅ | ✅ | ✅ | factor | products, conversions | code + name |
| Customer types | `/masters/customer-types` | ✅ | 1 | ✅ | 25 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | customers, leads | code + name |
| Supplier types | `/masters/supplier-types` | ✅ | 1 | ✅ | 25 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | suppliers | code + name |
| Warehouses | `/masters/warehouses` | ✅ | 2 | ✅ | 25 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | movements, open POs ¹ | code + name |
| Tax slabs | `/masters/tax-slabs` | ✅ | 1 | ✅ | 25 | ✅ | ✅ | ✅ | ⛔ versioned | ✅ | ✅ | products | n/a — code reuse **is** a version |

¹ **This cell was broken until Part 3 C1** — the reference named `PurchaseOrder.warehouse_id`, a column
that does not exist, so every warehouse deactivation raised `AttributeError` instead of refusing. See
"A pre-existing bug C1 found and fixed" in the Part 3 section above. The other twelve rows were fine.

Two deliberate non-✅s. **Tax slabs are not deletable** (`deletable=False` in the registry): a slab is a
version record, and R3.6 forbids editing history — a rate change appends. **Manufacturers have no
integrity guard** because nothing references them yet; their `references.py` entry is an explicit empty
tuple, so a later part that adds `product.manufacturer_id` finds the place to declare it.

**Requirements passed at C3:**

| ID | How it was verified |
|---|---|
| R3.1 | The matrix above; `tests/test_masters.py` parametrises the first five columns over every registry entry, so a master added without a spec, an export or a history panel fails. |
| R3.2 | One route set, one list template, one detail template for nine masters. Each list test asserts `html.count("<tbody>") == 1` and the presence of markers only the shared macros emit. |
| R3.3 | Applied three times rather than worked around: `model_options`/`distinct_options` (C2), then `kind="bool"` + `kind="bps"` + `active_options` + a `cell` that works with no `ListView`. Each is ~5 lines in the machinery and removes ~10 per master. |
| R3.4 | `CategoryService.reparent` (pre-existing) + `tree()` (new): depth-first, `sort_order` then code, carrying the business unit each row rolls up to. Rendered above the list. Tests: reparent to a descendant and to self both raise; the seeded tree is three levels deep and a child's BU equals its parent's. |
| R3.5 | `UomConversionService.upsert` rejects `from == to` and a non-positive factor; both asserted. |
| R3.6 | `TaxRateService.set_slab` appends and closes the prior window. Test: after a revision the prior row's code, name, `rate_bps` and `valid_from` are unchanged and only `valid_to` is set. The list shows every version with its window; `NATURAL_KEYS` deliberately has no `tax_rate` entry. |
| R3.7 | `app/db/references.py`. Refusals name the blockers: *"Cannot deactivate brand Apex — it is still used by 268 products (Black Garbage Bag 19x21, …, and 265 more)"*. Verified in the booted app, and by a test that puts a product on a draft PO and asserts the PO number appears in the refusal. Closed documents never block, so R1.7 still holds. |
| R3.8 | `NATURAL_KEYS` covers every master. Parametrised test posts a duplicate code per master and asserts a readable flash with no `IntegrityError` — including the tax-slab exception, where a reused code must *succeed*. |
| R3.9 | SKU generation untouched; `ProductService.set_status` makes Active/Draft/Discontinued a real verb with one activity row, a field-level diff and the R3.7 guard. Existing product tests still green. |
| R3.10 | 12 sub-categories + 3 sub-sub-categories, and GST_12 as two versions (12% from 2025-04-01, closed 2026-04-01; 5% from then). Seeded through `set_slab`, not hand-authored. |
| R3.11 | `tests/test_masters.py` — 65 tests. |
| R3.12 | `SupplierRepository.search` was the last old-path query; a test asserts none of the three repositories has a `search` attribute any more. Category deletion's two hand-rolled counts and four hand-rolled `code already exists` checks are gone. |
| R3.13 | Not built. |

**Verify loop at Part 2 close:** 251 tests passing; `ruff check app/ tests/` at 38 findings (the C2
baseline), zero new; app boots on `--port 8013`; all 26 web routes 200 including the nine new
`/masters/*` screens and `/products/{id}`; deactivating a referenced brand refuses with a message that
names the products; an unreferenced manufacturer deactivates and re-activates cleanly.

### ▶ R2.14 — what the second master cost (this is C3's gate)

**Customers, the second master: 82 lines added, 61 deleted, net +21.** It is net-positive-tiny because
the hand-rolled query and table markup left with it.

| Where | Added | What |
|---|---|---|
| `modules/customers/listing.py` | 41 | the whole spec — 7 columns, 3 filters, search, default sort (14 of the 41 are docstring + imports) |
| `web/pages/customers.py` | 16 | the CSV branch, `view_from_request`, the history call on detail |
| `modules/customers/service.py` | 12 | `to_read_many` + `list()` via `query_page` + 2 imports |
| `web/templates/customers/list.html` | 8 | four macro calls, replacing 28 lines of `<table>` |
| `modules/customers/repository.py` | 3 | a comment where `search()` was (−23) |
| `web/templates/customers/detail.html` | 2 | the history panel |

**A third master is ~60–80 lines** — the same rows minus the spec's docstring, or ~40 if it has no
detail page yet. Well inside R2.14's 100-line gate, so **C3 rolls out as-is; do not redesign.**
Products cost more (146 added) only because it had *no detail page at all* — 38 lines of new template
plus a route. That is a missing screen, not machinery friction.

**Where C3 should spend, if a master resists:** improve `app/db/listing.py`, never the page. C2 already
did this twice — `model_options` / `distinct_options` mean a filter dropdown needs no SQL of its own
(that alone took ~15 lines out of each spec), and `export_text` now normalises `Decimal`. If a master
needs a new *kind* of column or filter, add it there and every later master gets it (R3.3).

**Requirements passed at C1 (stage 1 machinery — built and tested, wired to pages in C2):**

| ID | How it was verified |
|---|---|
| R2.1 | `list_toolbar` / `list_table` / `pagination` / `list_empty` / `cell` / `history_panel` in `_macros.html` — search box, filter selects, chips, sortable headers, pagination controls. One definition; `tests/test_list_macros.py` renders each against a real `ListView`. |
| R2.2 | Driven by `ListSpec(columns=, filters=, sort=, page_size=)` in `app/db/listing.py`. `Column.kind` picks the renderer, so adding a column is a config line. Test asserts headers/cells/sortability all come from the spec. |
| R2.3 | `?q=&sort=&dir=&page=&<filter>=` only — no session, no cookie. `ListView.url/sort_url/page_url/clear_url` rebuild current state with one thing changed; tests assert sorting keeps the search, a new sort resets to page 1, and a stale filter value degrades instead of raising. |
| R2.4 | One helper: `query_page` / `query_rows` / `count_rows` over one `build_select`. No `LIMIT`/`OFFSET`/`ORDER BY` anywhere else. |
| R2.5 | `build_select` applies `deleted_at IS NULL` for any model with the column and `business_unit_id ==` for any model with the mixin. Tests: soft-deleting a row drops it from the count, the page and the search; another BU sees zero; a model without the column ignores the scope. |
| R2.8 | `csv_response` runs the same `build_select` with pagination removed. Tests: a filtered export's row count equals the on-screen count, and an unfiltered one is strictly larger. |
| R2.9 | `NATURAL_KEYS` + `ensure_unique` in `app/db/duplicates.py`; `DuplicateError` carries `.field` and `details={"field","value"}`. Wired into `ProductService.create`, `CustomerService.create` and `CustomerService.update`, replacing three hand-rolled checks. Tests assert the field, the message and that no `IntegrityError` ever reaches the caller. |
| R2.10 | Derived from `activity_log` — **no new table**, and `test_history_uses_the_activity_log_and_nothing_else` fails if one appears. `ActivityService.history()` reads it back with actor names; `field_changes()` records field-level before/after into the `data` JSON column that already existed. |
| R2.15 | `tests/test_listing.py` (29), `tests/test_duplicates.py` (17), `tests/test_change_history.py` (16), `tests/test_list_macros.py` (22) = 84 new tests. |

**Requirements passed at C2:**

| ID | How it was verified |
|---|---|
| R2.11 | `/products` and `/customers` are the machinery end to end. `tests/test_master_pages.py` (20 tests) goes through the real pages: page 2 shares no row ids with page 1, `?q=` narrows and survives a page link, a filter renders a removable chip, an unpublished `?sort=` degrades to the spec's default, `?export=csv` matches the on-screen count and carries *projected* columns, a duplicate POST comes back as a readable flash with no `IntegrityError`, and both detail pages render a history panel — the customer one showing a real before → after diff. Each test also asserts a marker only the shared macros emit, so a page that quietly grew its own table would fail. Confirmed in the booted app on `--port 8010`. |
| R2.13 | **311 products, 253 customers** from `bulk_products()` / `bulk_customers()` in `seed.py`. Deterministic index arithmetic, no randomness, `get_or_create`-idempotent. Uneven on purpose: draft/discontinued rows, zero-stock rows (no movement at all), a zero-credit-limit account, accounts with no credit policy. `/products` shows "Showing 1–25 of 311" with working Next/Prev. |
| R2.14 | The table above. 82 lines for the second master, net +21, a third at ~60–80. |

**Requirements outstanding:** all of §4 (R3.1–R3.13) is C3. R2.6/R2.7 are **P2** and deliberately not
built (D-C). Nothing from §3 is left.

**Verify loop at C2 close:** 186 tests passing (166 + 20); `ruff check app/ tests/` at **38** findings
(was 39 — the deleted `CustomerRepository.search` held one `E501`), zero new; app boots on `--port 8010`;
all 19 web routes 200 including the new `/products/{id}`; an unknown product id renders `error.html`.

**New files at C2:** `app/modules/products/listing.py`, `app/modules/customers/listing.py`,
`app/web/templates/products/detail.html`, `tests/test_master_pages.py`.

**New files at C3:** `app/db/references.py`, `app/modules/config/listing.py`,
`app/modules/suppliers/listing.py`, `app/web/pages/masters.py`,
`app/web/templates/masters/{list,detail}.html`, `app/web/templates/categories/detail.html`,
`tests/test_masters.py`.

**Changed at C2** (`git show --stat 5a1f89e` — 17 files, +755/−147; use
`git diff part-01-done..HEAD --stat` for the whole part):
`db/listing.py` (+41, the two options providers) · `web/listing.py` (+5, `Decimal` in the export) ·
`modules/products/{listing.py*,service.py,repository.py}` · `modules/customers/{listing.py*,service.py,repository.py}` ·
`web/pages/{products,customers}.py` · `web/templates/products/{list,detail*}.html` ·
`web/templates/customers/{list,detail}.html` · `seed.py` (+189) · `tests/test_master_pages.py`* ·
`tests/test_list_macros.py` (one seed-dependent assertion)
  *(`*` = new file)*

**Changed at C3** (`git show --stat de73c23` — 32 files, +1816/−252). Whole part:
`git diff part-01-done..HEAD --stat` — 52 files, +5634/−432.

**Read for the next part (Part 3 — Procurement: pre-order → PO depth)** — these and nothing else:
- `docs/REQUIREMENTS.md` §5 (R4.x) — the acceptance contract for Part 3.
- `docs/ROADMAP.md` → PROMPT for Part 3, and its SESSION PROTOCOL (2 checkpoints).
- `docs/08-module-breakdown.md` § Procurement.
- **The edit set:** `app/modules/procurement/{models,repository,service,schemas,router}.py` ·
  `app/web/pages/{procurement,purchase_orders}.py` and their templates · `seed.py`'s buy-loop section.
- **Reference only, and only if you add a list screen:** `app/modules/products/listing.py` +
  `app/web/pages/products.py` — the pattern for one, `app/web/pages/masters.py` — the pattern for many.
- **Already built, do not rewrite:** `PurchaseOrderService` covers create → confirm → receive → bill
  with the status vocabulary `draft / confirmed / partially_received / received`. Part 3 adds depth to
  it; read those methods before adding a verb that already exists (G16).

**Call, don't read** — verified signatures, so you don't have to open these files:

```python
# app/db/listing.py — declare the spec as a module-level constant beside the page
ListSpec(entity: str, model: type, columns: tuple[Column, ...], search=(), filters=(),
         sort="created_at", dir="desc", page_size=25, search_hint="Search")
Column(key: str, label: str, kind="text", sort=None, href=None, export=True)
#   kind: text | mono | money | number | date | datetime | badge | link
#   sort names the MODEL attribute; omit it and the header isn't clickable
#   key is read off the row the page renders (may be a projection, not the ORM row)
Filter(key: str, label: str, column: str, coerce="str", options=None, all_label="All")
#   coerce: str | uuid | int | bool     options: Callable[[Session], Sequence[tuple[str,str]]]
static_options(*pairs: tuple[str, str])                    # a fixed dropdown
model_options(model, *, label="name", value="id", order_by=None)   # another table's live rows
distinct_options(model, column: str)                       # the values a column actually holds
#   all three return a `Filter.options` provider; a filter needs no SQL of its own
ListParams(q="", sort="", dir="asc", page=1, filters: Mapping[str,str] = {})
query_page(db, spec, params, *, business_unit_id=None) -> ListPage
#   ListPage(.rows .total .page .page_size) — page_size comes from the SPEC, so a
#   caller wanting a different one passes replace(SPEC, page_size=n) (dataclasses.replace)

# app/web/listing.py
view_from_request(request, db, spec, *, business_unit_id=None, project=None) -> ListView
#   "the one call a GET list route makes". project: Callable[[Sequence[row]], list[row]]
#   — the WHOLE page of ORM rows at once, not one row at a time
wants_csv(request) -> bool                     # branch the GET route on this
csv_response_from_request(request, db, spec, *, business_unit_id=None, project=None) -> Response
#   pass the same `project` as the view, or projected columns export blank

# app/modules/{products,customers}/listing.py — the two worked specs
PRODUCT_LIST: ListSpec   ·   CUSTOMER_LIST: ListSpec
ProductService(db).to_read_many(rows) -> list[ProductRead]     # the projector
CustomerService(db).to_read_many(rows) -> list[CustomerRead]

# app/modules/activity/service.py
ActivityService(db).history(entity_type: str, entity_id: uuid.UUID, *, limit=50)
#   -> list[HistoryEntry(occurred_at, verb, summary, actor, changes)]; pass straight
#   to ui.history_panel(entries). A pure read (G15).

# app/seed.py
record_creation(db, activity, *, entity_type, entity_id, summary, actor_id) -> None
#   the `created` history line for a get_or_create'd master; idempotent, skips if the
#   row already has any activity

# app/db/references.py — relationship integrity (R3.7). ADD AN ENTRY PER NEW MODEL.
ensure_unreferenced(db, instance, *, action: str, label: str) -> None
#   raises ConflictError naming the live documents that block `action`
blocking_references(db, instance) -> list[str]      # the phrases, without raising
Reference(model, column, noun, plural, label="name", live_statuses=(), via=None)
Via(model, child_column, label, live_statuses=())   # a reference through a document LINE
REFERENCES: dict[tablename, tuple[Reference, ...]]  # the whole policy, as data

# app/modules/config/service.py — one creator/toggle/delete for nine masters
ConfigService(db).create_master(entity_type, *, code, name, extra=None, actor_id)
ConfigService(db).set_master_active(entity_type, row_id, *, active: bool, actor_id)
ConfigService(db).delete_master(entity_type, row_id, *, actor_id)
MASTER_LABELS: dict[entity_type, str]               # the label messages use
CategoryService(db).tree() -> list[(depth, Category, business_unit_name)]
CategoryService(db).get(category_id) -> CategoryRow
ProductService(db).set_status(product_id, status, *, actor_id)   # R3.9 lifecycle

# app/modules/config/listing.py
simple_master_spec(entity, model, *, plural, extra=(), search=(), filters=()) -> ListSpec
#   a code/name/is_active master's whole list, in one call

# app/db/duplicates.py
ensure_unique(db, model, values, *, exclude_id=None) -> None
#   raises DuplicateError(.field); pass exclude_id on update so a row isn't its own duplicate

# app/db/soft_delete.py
soft_delete(db, instance, *, actor_id, label=None) -> None
#   raises ConflictError for PROTECTED_TABLES or an already-deleted row
```

`build_select` applies `deleted_at IS NULL` and `business_unit_id` itself — do not re-add either.

**Do NOT read:**
- `docs/CODEBASE-MAP.md` covers the layout, the shared machinery, the patterns, `seed.py`'s section
  structure and the test inventory. **Read it instead of exploring the tree.** If it's wrong, fix it.
- `seed.py` end to end (750 lines). Jump to the `# --- section ---` blocks you need; the bulk
  generators are in the reference-data section at the top.
- The other 14 page modules "for an example" — `web/pages/products.py` + `modules/products/listing.py`
  are now *the* example, and they're in the read list above.
- `db/listing.py` / `web/listing.py` internals. C2 read them so C3 doesn't have to; everything a page
  calls is in the signature block above. Open them only to *add* a column kind or filter coerce.
- `db/soft_delete.py`, `web/security.py`, `activity/history.py`, `db/duplicates.py` internals — C1
  wired them and C2 didn't change them; the map's one-line contracts are enough.
- `_macros.html` — C2 changed nothing in it. Four calls (`list_toolbar`, `list_table`, `list_empty`,
  `pagination`) plus `history_panel`; copy them from `products/list.html`.
- The older `docs/` design files (`00`, `07`, `08` beyond §2.3/§2.4, `09`–`17`). Retired stack.
- Anything in this file below the `▶ CURRENT WORK` section — historical log.

**Gotchas for the next session:**
- **Do not build a second query helper or a second table macro.** R2.1/R2.4 are one definition each.
  All three repository `search()` methods are gone and `tests/test_masters.py` fails if one returns.
  A new list screen is a `ListSpec` + `view_from_request`; a new *set* of list screens is a
  `MasterPage` entry in `app/web/pages/masters.py`.
- **Every new model owes `app/db/references.py` an entry** — even an empty tuple. R3.7's guard reads
  that map, so a model missing from it silently permits deletion of something live points at. An
  explicit `(): nothing reads this live` is the difference between decided and forgotten.
- **A reference through a document line needs `via=`**, or the refusal quotes a line id instead of the
  document number the founder can act on.
- **`live_statuses` is what "open" means.** `("draft", "confirmed", "partially_received")` for a PO,
  `("draft", "confirmed", "partially_fulfilled")` for an SO. A part that adds a status to either
  vocabulary must decide whether it is open here too — otherwise a new state silently stops blocking.
- **One route set can serve many screens.** `/masters/{slug}` handles nine masters; `/settings` is the
  hub. Before adding a page module, check whether a registry entry does it.
- **`ListSpec.columns` read the *projected* row; `sort`/`filters`/`search` read the *model*.** On
  products, `category_name` and `stock_on_hand` exist only on `ProductRead`, so they are columns with
  no `sort=`. A `?sort=` naming a projection-only key silently falls back to the spec default — that's
  by design (C1 decision 2), so don't "fix" it by sorting in Python.
- **`page_size` lives on the spec, not in `query_page`.** A service `list()` that ignores its own
  `page_size` argument silently truncates its callers — `/sales`, `/purchase-orders` and `/warehouse`
  all ask `ProductService.list` for 300 rows to fill a `<select>`. Use `replace(SPEC, page_size=n)`.
- **Keep each service's `list()` signature.** C2 changed both implementations without touching a single
  caller (10 routers + 8 pages call these). Same for suppliers in C3.
- **A GET list route needs two branches** — `view_from_request` for HTML, `csv_response_from_request`
  when `wants_csv(request)` — and **both need the same `project=`**, or the CSV's projected columns
  come out blank. There's a test for that (`test_the_export_carries_projected_columns...`).
- **The CSV export leads with a UTF-8 BOM** (deliberate, so Excel opens it correctly). Read it back
  with `utf-8-sig` or the first header cell compares as `"﻿SKU"`.
- **Templates escape, so assert accordingly.** A filter chip for "Garbage Bags & Waste Management"
  renders `&amp;`. And a search term echoes into the toolbar's `value=`, so "the deleted row is gone"
  must be asserted against the `<tbody>`, not `in html`.
- **Multi-master screens need a query-string namespace.** `/settings` renders eight master lists on one
  page. `?q=` and `?page=` are per-`ListView`, so eight specs on one route would fight over them.
  Decide this before writing code — separate routes per master is the cheap answer.
- **The seed's masters bypass their services**, so `get_or_create` writes no `activity_log` row and the
  history panel would be empty on demo rows. `record_creation()` backfills the named rows and every
  config master, in a pass that runs **last** in `run()` — later sections create masters too (the
  Phase B warehouse), and a mid-file pass misses them. The generated hundreds are deliberately not
  logged; they would bury the activity feed.
- **A re-seed can't recover a real `occurred_at`.** `ActivityService.log` has no `occurred_at`
  parameter (it defaults to now), so a backfilled `created` line on an already-seeded DB reads
  "just now". A fresh DB is correct. Don't add the parameter to make demo data prettier.
- **Every web POST route carries `require_web_permission`.** A new mutation route added without one
  fails `tests/test_web_authz.py::test_every_web_post_route_carries_the_guard`. Add the guard, don't
  weaken the test. (A GET export route needs no guard — the test only walks POSTs.)
- **Port 8000 may be occupied** on the current build machine by an unrelated app. `uvicorn` logs the
  bind failure but the shell may still report success — check the log, or just use `--port 8010`.
- **Python is per-user installed** at `C:\Users\Administrator\AppData\Local\Programs\Python\Python312`
  and is not on `PATH` in a fresh shell; the venv at `apps/api/.venv` is what to activate.

**Decisions made mid-part (Part 2 — do not silently reverse):**
1. **`ListSpec` is shared by the query and the presentation**, not duplicated. `app/db/listing.py`
   owns the spec + the query; `app/web/listing.py` owns URL building and CSV over the same object.
   A column that can be sorted in SQL is therefore clickable in the header by construction — the two
   halves cannot drift into disagreeing.
2. **Sorting is whitelisted, filters degrade.** `?sort=` is honoured only if a column published it;
   anything else silently falls back to the spec's default. A filter value that no longer parses is
   dropped rather than raising, so a stale bookmark renders the list (R2.3) instead of an error page.
3. **Every order-by appends the primary key as a tiebreak.** Without it, rows sharing a sort value
   swap between pages and the same row shows twice — or never — while paging. Tested by walking every
   page and asserting the id set is exactly the total.
4. **The duplicate check matches the database constraint, not the read filter.** A soft-deleted row
   still occupies a `UNIQUE` column, so a `NaturalKey` marked `db_unique=True` counts deleted rows as
   collisions and says so ("a deleted product still holds this SKU"). Checking only live rows would
   pass and then hit the `IntegrityError` R2.9 exists to prevent. Keys with no DB constraint (the
   composite business identity) only consider live rows, which is all they promise.
5. **Code generators now count rows *ever* created, not live rows.** `repo.count_ever()` on products
   and customers. `count_all()` excludes deleted rows, so after one deletion the next generated code
   was one a deleted row still held — a latent duplicate that decision 4 would now surface as a user
   error. Fixed at the generator.
6. **Change history added no table (R2.10).** `activity_log` already answers all three questions;
   the only gap was field-level detail, and its `data` JSON column existed for exactly that. Services
   call `field_changes(instance, updates)` **before** applying the update and pass
   `data={CHANGES_KEY: changes}` to the *same* activity row — one row per verb still (G5), not a
   second row for the diff.
7. **An unresolvable actor says "Unknown user"; a null actor says "System".** No invented attribution
   (G11). Reading history writes nothing (G15), asserted by a test.
8. **`app/core/money.py:minor_to_text`** is the one minor-units→decimal-string conversion, integer
   arithmetic only (G1). Used by the CSV export and the history panel. `app/web/core.py:money` is
   left alone — it presents a figure with the ₹ symbol and Indian grouping, a different job.
9. **`number()` now normalises `Decimal`.** A `Numeric(18,4)` quantity was rendering as `20.0000`
   on screen. It now shows `20` and `1.25`; every quantity column benefits. **C2 extended the same
   normalisation to the CSV export** — a file carrying `40.0000` for a stock of 40 exports the column's
   scale rather than the number.
10. **A master's `ListSpec` lives in `app/modules/<feature>/listing.py`, not beside the page.** C1's
   note said "beside the page"; C2 moved it because R2.4 requires the *service* to run its `list()`
   through `query_page` too, and a service importing `app.web` would invert the layering. `app.db.listing`
   has no web dependency, so the module can own the spec and the page can import it. One spec means the
   JSON API's filters and the screen's headers cannot drift (this is decision 1, applied).
11. **The projector is a public service method** (`to_read_many`), not a lambda over a private one.
   Both the HTML and the CSV branch need the same projection, and `_to_read`-per-row in a page would
   have put N+1 query knowledge in the template layer.
12. **`/products/{id}` is new.** Products had no detail page, so the change-history panel R2.11 requires
   had nowhere to live. Its 38-line template is *not* counted as machinery cost in R2.14 — it is a
   screen that was missing.
13. **Filter dropdowns are three providers, not per-page SQL.** `model_options` (another table's live
   rows) and `distinct_options` (the values a column actually holds) joined `static_options` in
   `app/db/listing.py`. This is R3.3 applied before C3 rather than after: it took ~15 lines out of each
   spec, and every master C3 touches inherits it.
14. **The seed generates rather than lists.** 311 products and 253 customers come from
   `bulk_products()` / `bulk_customers()` — deterministic index arithmetic, no `random`, so re-seeding
   is idempotent, tests can name a row, and diffs stay readable. The named demo rows stay literal
   because later seed steps order and invoice them by code.
15. **Nine config masters are one route set, not nine page modules** (`/masters/{slug}` over the
   `MASTERS` registry). Eight lists on `/settings` could not each own `?q=`, `?sort=` and `?page=`, so
   the split was forced by R2.3 rather than chosen for tidiness. `/settings` kept the typed key/value
   settings and became the hub. The registry entry is the whole per-master cost: a spec plus a field
   list, ~6 lines.
16. **"Still referenced" is a question about *live* work, not about foreign keys** —
   `app/db/references.py`. A confirmed invoice snapshotted what it needed, so it never blocks (that is
   what keeps R1.7 true); an open purchase order will read the master again at receipt, so it does.
   Every refusal names the documents in the way, because "cannot delete: still referenced" is not
   something the founder can act on.
17. **Deactivation is guarded exactly like deletion.** Hiding a master from every picker breaks an open
   order as thoroughly as removing it, and two policies would drift. One question, one map.
18. **`tax_rate` has no `NATURAL_KEYS` entry, and slabs are not deletable.** Reusing a code *is* how a
   new version is expressed (R3.6), so a duplicate check there would forbid the feature; and deleting a
   slab would delete history. The registry's `deletable=False` keeps the button off the page.
19. **`create_master` grew an `extra` dict rather than a second creator.** Warehouses and manufacturers
   are the same master with extra text columns; `create_warehouse` is now a two-line wrapper kept for
   its callers. The four hand-rolled `code already exists` checks are gone — they each phrased the error
   differently and none of them noticed a soft-deleted row still holding the `UNIQUE` code.
20. **`kind="bool"` and `kind="bps"` are machinery, not per-page formatting.** Config masters carry
   `is_active` (a boolean, not a status string) and tax slabs carry integer basis points. Both now
   render in the shared `cell` macro and in the CSV export, so no page formats a value itself. The
   `bps` filter uses integer arithmetic — 1800 → "18%", never a float.
21. **`cell` works without a `ListView`.** A detail page renders the same spec columns as a `<dl>`
   (`masters/detail.html`), which means a new column appears on both screens. Duplicating the kind
   switch for detail pages was the alternative, and it would have drifted within a part.

**Decisions made mid-part (Part 1 — do not silently reverse):**
1. **Soft delete is one function, not a base-repository method** — `soft_delete()` in
   `app/db/soft_delete.py`. It owns the append-only guard, the already-deleted guard and the single
   `activity_log` row. `documents` was migrated off its own `repository.soft_delete` onto it, so
   there is one implementation rather than one plus a legacy.
2. **The non-deletable guard is table-level and unconditional**, keyed on `__tablename__` in
   `PROTECTED_TABLES`. Stricter than R1.3's "*posted* orders", which is fine because no delete path
   exists for drafts either. A part that wants draft deletion makes that entry status-aware **inside**
   the dict rather than adding a bypassing delete path.
3. **Categories refuse deletion while they have children or products**; customers do not refuse while
   they have invoices. The test is "does anything read this row *live*", not "does anything reference
   it" — an invoice snapshots what it needs, a product reads its category name now.
4. **A converted lead cannot be deleted** — it is the origin record of a real customer.
5. **Category web writes use `config.write`**, mirroring the JSON API (categories are a config-module
   master). Only `category.delete` uses the `<entity>.delete` shape, since deletion has no API twin.
6. **Web 404/422 rendering was widened beyond R1.10's letter** — `app/web/errors.py` now also handles
   `RequestValidationError` (a malformed id like `/customers/not-a-uuid` never reaches the service,
   so it needed its own path) and `StarletteHTTPException` (an unrouted web path). API, `/docs`,
   `/health` and `/static` keep their JSON.

**NEXT SESSION:** **Part 2 is complete and tagged `part-02-done`. Start Part 3** (Procurement:
pre-order → PO depth, Phase 2) using the Part 3 prompt in `docs/ROADMAP.md` — 2 checkpoints, one per
session. Read this block + `docs/REQUIREMENTS.md` §5 + the read list above, then the procurement module.
**Do not re-read the list machinery** — the signature block above is what C2 and C3 verified against
source, and Part 3 is domain work, not screen work.

Two things Part 3 inherits and must not break: every new model needs an `app/db/references.py` entry
(even an empty one), and if it adds a status to the PO vocabulary it must decide whether that status is
"open" in `REFERENCES` — a new state that silently stops blocking is R3.7 quietly regressing.

Do **not** re-read the older `docs/` design files, `docs/DELETION-POLICY.md`, or
`docs/MIGRATION-STRATEGY.md` — Part 1 resolved those. Do not re-read `docs/17-design-system.md` §6
either: it specifies the retired TanStack/React table, and its server-side-via-query-params rule is
already what the macros do.

---


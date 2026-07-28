# ApexOS — Build Progress

> Working log so any session can pick up where the last one stopped.
> This file is the source of truth for status.

_Last updated: 2026-07-28_

---

# ▶ CURRENT WORK — read this first

A **session** is a token budget; a **part** is a group of sessions. Most parts take several sessions
with a checkpoint commit between each. See the *Session protocol* in `docs/ROADMAP.md` for the
checkpoint list per part.

**All work is on `main`** — no feature branches, no PRs. A part is "done" when every P0/P1 requirement
passes, the verify loop is green, this file is updated, and the part is tagged `part-0N-done`. Those
tags are the rollback points.

**Every session ends by updating the block below, before it runs out of room.** A session that dies
with an accurate resume block costs nothing; one that dies without it costs a re-derivation.

### Fresh clone — one-time setup

The build machine both writes and tests the code; there is no write-here/test-there split. The stack
is self-contained (SQLite file + one uvicorn process, no database server, no npm), so any machine with
**Python 3.11+** can do everything.

```bash
git clone https://github.com/1992tushar/apexos.git    # personal creds only, never org
cd apexos/apps/api
python -m venv .venv
# Windows: .venv\Scripts\Activate.ps1   ·   Linux/macOS: source .venv/bin/activate
pip install -e ".[dev]"
python -m app.seed          # creates apexos.db with demo data
```

Then verify the baseline before writing any code:

```bash
python -m pytest -q                  # count is in the CURRENT WORK block below (186 at Part 2 C2)
python -m ruff check app/ tests/     # expect exactly 38 pre-existing findings — 39 is a regression
python -m uvicorn app.main:app --port 8000   # http://localhost:8000/ — click through every nav page
```

If the baseline is not green, stop and report what failed — do not start feature work on top of it.

### ▶ How to start the next session

Open a fresh Claude Code session in your clone of the repo and paste **exactly this**:

```
Continue the ApexOS build. Do this in order:
1. git checkout main && git pull origin main
2. Read the "CURRENT WORK" block at the top of PROGRESS.md — it names the part in flight, the
   checkpoint to start at, which requirement IDs are outstanding, and what NOT to re-read.
3. Open docs/ROADMAP.md, find the PROMPT for that part, and follow it from that checkpoint.
   Its SESSION PROTOCOL block tells you what this session is expected to finish.
4. Work on main — no branches, no PRs. Commit when the checkpoint is done.
5. Before you run low on context, update the CURRENT WORK block in PROGRESS.md.
```

That works unchanged for every remaining session — the resume block carries the state, so the starter
never has to. Nothing to look up, nothing to keep in your head.

**If you'd rather be explicit:** open `docs/ROADMAP.md`, copy the whole ```-fenced PROMPT for the part
you want, and paste that instead. More deterministic, more typing. Use it if a session has drifted and
you want a hard reset on the scope.

**Rules of thumb.** One checkpoint per session — don't push a session past its checkpoint to "just
finish the part". Start each session fresh (`/clear` or a new window) rather than continuing a long
one. And if a session ends messy, the recovery is `git log --oneline -5` plus the resume block, not
re-reading the design docs.

## Part 2 — Master data & shared machinery · on `main` · checkpoint 2 of 3 · tag when done: `part-02-done`

**Part 1 is COMPLETE and tagged `part-01-done`.** Its record is in the log below.

- [x] **C1** the machinery: list/table macros + generic query helper + CSV export + duplicate
      prevention + change history → commit `7419f67`
- [x] **C2** proven on products + customers, seed extended to 311/253 rows, R2.14 recorded →
      commit `5a1f89e`
- [ ] **C3** roll out to the remaining 8 masters + their special cases

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

**Changed since last checkpoint** (`git show --stat 5a1f89e` — 17 files, +755/−147; use
`git diff part-01-done..HEAD --stat` for the whole part):
`db/listing.py` (+41, the two options providers) · `web/listing.py` (+5, `Decimal` in the export) ·
`modules/products/{listing.py*,service.py,repository.py}` · `modules/customers/{listing.py*,service.py,repository.py}` ·
`web/pages/{products,customers}.py` · `web/templates/products/{list,detail*}.html` ·
`web/templates/customers/{list,detail}.html` · `seed.py` (+189) · `tests/test_master_pages.py`* ·
`tests/test_list_macros.py` (one seed-dependent assertion)
  *(`*` = new file)*

**Read for the next checkpoint (C3)** — these and nothing else:
- **The reference pair, in full:** `app/modules/products/listing.py` + `app/web/pages/products.py`.
  Together they are ~130 lines and they are the whole pattern. Copy them per master.
- **Modify:** three page modules hold every remaining master — **verified, not guessed:**
  - `web/pages/settings.py` → `GET /settings` renders business_units, brands, uoms, customer_types,
    supplier_types, warehouses, tax_rates, settings in one template (`settings/index.html`), with
    `POST /settings/masters/{entity_type}`, `/settings/warehouses`, `/settings/tax-rates`.
    **This page is the bulk of C3.** Eight card-lists on one screen is the thing to decide first —
    one `ListSpec` per master with its own query string namespace, or a page per master.
  - `web/pages/categories.py` → `GET /categories`, `POST /categories`,
    `POST /categories/{id}/reparent` (R3.4's cycle prevention already has a route), `.../delete`.
  - `web/pages/suppliers.py` → `GET /suppliers` (still hand-rolled; `SupplierRepository.search` is
    the last surviving old-path query — delete it the way C2 deleted the other two).
  - Plus a `listing.py` per module, and `seed.py`'s category / tax-rate sections for R3.10 (multi-level
    category tree + two tax slab versions).
  - **Manufacturers do not exist yet** — `ConfigService` has no `manufacturers()`. R3.1 lists them as
    in scope, so C3 either adds the model or records why not. Check before planning the session.
- **Reference only:** `docs/CODEBASE-MAP.md` § Shared machinery → the `<feature>/listing.py` entry.
- **Already built, do not rewrite:** `CategoryService.reparent` (R3.4), `UomConversionService.upsert`
  (R3.5), `TaxRateService.set_slab` (R3.6) all exist in `app/modules/config/service.py`. C3 may only
  owe them *tests* and a list screen — read those three methods before writing any new validation.

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
  `SupplierRepository.search` is the **last surviving old-path query** — C2 deleted the product and
  customer ones. Delete it the same way: `list()` builds `ListParams` and calls `query_page`.
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
  history panel is empty on demo rows. `record_creation()` fixes that for the *named* rows only; if C3
  wants history on a config master, call it there too. Don't log the generated hundreds.
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

**NEXT SESSION:** start Part 2 at **C3** using the Part 2 prompt in `docs/ROADMAP.md`, from STAGE 2.
Read this block + `docs/REQUIREMENTS.md` §4 (R3.1–R3.13 is everything C3 owes) + the read list above.
**Do not re-read the machinery** — the signature block above is what C2 verified against source.

C3's work, in order: (1) decide the `/settings` question — eight masters on one page need either a
query-string namespace per list or a route per master; (2) suppliers first, since it's the closest twin
of what C2 did and its `SupplierRepository.search` must go; (3) categories, whose `reparent` service
already exists (R3.4 may be tests only); (4) the config masters, cheapest last; (5) `seed.py` for R3.10
(multi-level category tree + two tax slab versions); (6) R3.7 relationship integrity — deactivating a
product on an open PO must refuse *and name the PO*; (7) the R3.1 capability matrix in this file, no
empty cells. If a master needs materially more than the ~60–80 lines R2.14 measured, **fix
`app/db/listing.py` and say so here** (R3.3) rather than working around it.

Do **not** re-read the older `docs/` design files, `docs/DELETION-POLICY.md`, or
`docs/MIGRATION-STRATEGY.md` — Part 1 resolved those. Do not re-read `docs/17-design-system.md` §6
either: it specifies the retired TanStack/React table, and its server-side-via-query-params rule is
already what the macros do.

---

## Resume-block template

Copy this at the start of a new part; update it at every checkpoint. Keep only the current part's
block in the `CURRENT WORK` section — move finished parts down into the chronological log below.

```
## Part <n> — <title> · on `main` · checkpoint <i> of <k> · tag when done: `part-0<n>-done`

- [x] **C1** <what it delivered> → commit `<sha>`
- [ ] **C2** <next chunk>

**Requirements passed:**      <IDs verified, e.g. R6.1–R6.6, R6.16>
**Requirements outstanding:** <IDs left>
**Gotchas for the next session:** <signature changes, migrations, half-finished refactors>
**Decisions made mid-part:**     <choices a later session must not silently reverse>

**Changed since last checkpoint:** <paths — paste from `git diff <last-tag>..HEAD --stat`>
**Read for the next checkpoint:**  <the 4–6 files it will actually modify. Be specific.>
**Call, don't read:**              <verified signatures of anything the next checkpoint calls but does
                                    not edit — copy them from the source so they're exact. Four lines
                                    here replaces a 250-line orientation read.>
**Do NOT read:**                   <what CODEBASE-MAP.md already covers; files listed above that
                                    the next checkpoint won't touch; docs already resolved>

**NEXT SESSION:** start at C<i+1>. Read this block + `docs/CODEBASE-MAP.md` + `docs/REQUIREMENTS.md` §<n>,
              then `git diff <last-tag>..HEAD --stat` for the delta. Nothing else.
```

Rules that make the block worth writing:

1. **Commit at every checkpoint**, not at part end. Uncommitted work dies with the session.
2. **Requirement IDs, not prose.** "Did the inventory stuff" is not resumable; "R6.1–R6.6 pass,
   R6.10 outstanding" is.
3. **Record decisions, not just progress.** A later session that silently reverses a mid-part
   decision is the expensive failure mode.
4. **Say what NOT to read.** Resuming sessions burn most of their budget re-establishing context they
   do not need.
5. **Name the files.** `Read for the next checkpoint` is the single highest-value line in the block.
   A session that has to *discover* which four files it needs will read twenty-five finding out.
6. **Keep `docs/CODEBASE-MAP.md` true.** If a checkpoint changes the *shape* of things — a new piece
   of shared machinery, a new pattern, a module that moved — amend the map in the same session. It is
   what lets the next session skip orientation entirely, and it is only worth reading if it's right.

---

## Part 1 — Foundation finish · COMPLETE · tagged `part-01-done` (2026-07-28)

Three checkpoints, three sessions. Delivered the two mechanisms every later part wires into (soft
delete, web authz) plus the migration strategy written down.

- [x] **C1** WS1 — test suite → commit `edf51ea`
- [x] **C2** WS2 — centralized web error handling → commit `edf51ea`
- [x] **C3** WS3 soft delete + WS4 web authz guard + WS5 migration strategy → commit `9670314`

**Requirements passed: R1.1–R1.10, all of them** (§2 of `docs/REQUIREMENTS.md`). R1.1–R1.10 were all
marked outstanding at the start of C3 because WS1/WS2 predated the register, so C3 verified the whole
section rather than just its own workstreams.

| ID | How it was verified |
|---|---|
| R1.1 | One definition: `soft_delete()` in `app/db/soft_delete.py`. `documents` migrated onto it and `DocumentRepository.soft_delete` deleted, so there is no second implementation. |
| R1.2 | Service verb + web POST route + `ui.delete_button` for customers, suppliers, products, tasks, leads, categories. Each POSTed against the booted app: 303, `ok=` flash, row count drops by one. |
| R1.3 | `PROTECTED_TABLES` (16 tables, reason each) + `docs/DELETION-POLICY.md` §3. Tests assert `ConflictError` with a readable message for invoices, bills, payments, sales orders, purchase orders, stock movements — and that a refusal writes no activity row. |
| R1.4 | `require_web_permission` in `app/web/security.py`. Tests drive a permission-less actor: GET → 403 `error.html`; POST → 303 with `err=` flash, and only the referer's *path* is used so an offsite referer cannot pick the redirect target. |
| R1.5 | All **36** web POST routes carry the guard, codes mirroring the API's. `test_every_web_post_route_carries_the_guard` walks the router and fails on any unguarded POST. |
| R1.6 | `soft_delete` writes exactly one `activity_log` row in the caller's transaction; tests assert the count goes 0→1 and that `entity_type`/`summary` are right. |
| R1.7 | Test deletes the seeded customer that has an invoice, then asserts `FinanceRepository.customer_name` still resolves and `/invoices/{id}` still 200s. |
| R1.8 | `docs/MIGRATION-STRATEGY.md` — dev SQLite `create_all` + the additive `_ensure_new_columns` shim (with its rules), prod Postgres via Alembic reintroduced behind `DATABASE_URL` (with the 6-step reintroduction and the "gate `create_all` to SQLite" step). |
| R1.9 | **Already clean on arrival** — longest line in `app/web/pages/settings.py` is 86 chars and `ruff check app/web/` passes. The "~3 E501" in the roadmap was stale; a previous checkpoint had cleared them. No change needed. |
| R1.10 | Verified in the booted app on five URLs. Two gaps found and fixed beyond the letter of the requirement: a **malformed** uuid returned a raw JSON 422 (FastAPI rejects it before the handler), and an **unrouted** web path returned raw JSON 404. Both now render `error.html`; API/docs/health/static keep JSON. |

**Verify loop at close:** 82 tests passing (43 baseline + 39 new); `ruff check app/ tests/` at exactly
the 39 pre-existing findings, zero new; app boots; all 17 nav pages 200.

**New files:** `app/db/soft_delete.py`, `app/web/security.py`, `tests/test_soft_delete.py`,
`tests/test_web_authz.py`, `docs/DELETION-POLICY.md`, `docs/MIGRATION-STRATEGY.md`.

**Scope held (G17):** no roles/permissions UI was built — D-B says the guard is a no-op with one user
and the mechanism existing is the whole point. No batch/lot, no FIFO, no notifications, no saved views.

---

## Stack Lightening — Postgres→SQLite + Next.js→Jinja (2026-07-23)

Goal: make ApexOS as light to run as the sister project **OrdeRR** — one command,
no database server, no frontend build. Delivery-layer only; **no business logic or
service behavior changed.** Done in two commits.

### Phase 1 — Postgres + Alembic → SQLite
- `database_url` default is now `sqlite:///./apexos.db` (still `DATABASE_URL`-overridable,
  so PostgreSQL remains a drop-in for production).
- Engine adds `connect_args={"check_same_thread": False}` conditionally for SQLite.
- All Postgres-only column types made dialect-agnostic: `PGUUID(as_uuid=True)` → `Uuid()`
  (17 model files), `JSONB` → `JSON` (activity, config), `ARRAY(String)` → `JSON` (identity
  `permission_codes`).
- **Alembic removed entirely** (`alembic/`, `alembic.ini`, the `alembic` dep, `db.ps1`).
  The schema now self-initializes: `app.main`'s lifespan imports every model and calls
  `Base.metadata.create_all(engine)` on startup (also still run by `app.seed`). A fresh
  `apexos.db` bootstraps itself.
- De-Postgres'd infra: `docker-compose.yml` (dropped the Postgres service), `Dockerfile`
  (dropped `libpq`/`psycopg` build deps), `.env.example`, `start.ps1`, run docs; removed
  `psycopg` from `pyproject.toml`.

### Phase 2 — Next.js SPA → server-rendered Jinja2
- New web layer at `apps/api/app/web/` (mirrors OrdeRR): `pages/*.py` route handlers call the
  existing domain **services directly** (never over HTTP) and render `templates/*.html`;
  shared plumbing in `core.py` (Jinja env + money/date/status filters + `render`/`redirect`
  helpers), `templates/base.html` app shell + sidebar nav, `_macros.html`, and `static/app.css`.
  Routers are auto-discovered by `app.web.build_web_router` and mounted at root by `app.main`;
  `/static` serves assets. Added `jinja2` to `pyproject.toml`.
- Recreated every former page for parity (17 page modules): dashboard, sales (list/new/detail
  + confirm/fulfill/invoice), customers (+detail), leads (+convert + opportunity pipeline),
  products, categories (+reparent), inventory, warehouse (transfer/adjust/count), procurement,
  purchase-orders (list/new/detail + confirm/receive/bill), suppliers (+detail + evaluate),
  finance (invoices/bills + payments + detail), reports (run + CSV export), analytics, tasks
  (+complete), documents (upload/download), settings (masters/warehouses/tax-rates/config).
  Forms POST to server routes → call service with the current actor → 303 redirect (PRG).
- **Deleted `apps/web/` entirely** (Next.js SPA, npm/TS build, and the hand-maintained TS DTO
  layer — the biggest source of drift bugs). No npm/node anywhere in the run path.

### Run it now — one command
```bash
cd apps/api
pip install -e ".[dev]"          # once
python -m app.seed               # optional: demo data (also self-creates apexos.db)
uvicorn app.main:app             # UI at http://localhost:8000/ , API docs at /docs
```
No Postgres, no `alembic upgrade`, no `npm`. See `RUNNING.md` / `QUICKSTART.md`.

> Note: the deeper design docs under `docs/` (deployment/backup strategy, ER migration order,
> build-phases) still describe the original Postgres+Alembic+Next.js design and are retained as
> historical design record; production can still target PostgreSQL via `DATABASE_URL`.

---

_Historical log below (pre-lightening; references to Alembic migrations, `apps/web`, and
`npm` predate the changes above)._

## Phase A (Buy side) — CODE REVIEWED, awaiting E2E verification (2026-07-22)

Reviewed the pre-existing, never-run buy-side code against the Phase A spec
(`docs/BUILD-PHASES.md`) and the architectural rules. **Verdict: complete and
correct as written; no code changes were needed.** It faithfully mirrors the
verified Sales spine. Detailed checks performed (all pass):

- **Backend modules** `suppliers`, `procurement`, `pricing` (buy), `finance` (bills)
  each have model/repository/service/router/schemas mirroring Sales. Buy loop:
  `PurchaseOrderService.create/confirm/bill` + `GoodsReceiptService.receive`
  (posts IN movement via the single `InventoryService.record_movement`; partial
  receipts accrue `qty_received`). `BillService.add_payment` writes a
  `direction="out"` payment allocated to the bill. One `activity_log` row per
  state change, in-transaction.
- **Migration** `0002_procurement_buy_side` chains `down_revision="0001_initial"`,
  creates the 9 buy-side tables via `metadata.create_all(checkfirst=True)`, and
  conditionally adds `payment.supplier_id` + `payment_allocation.bill_id`. Correct
  for both a fresh DB (0001 already creates the full metadata) and the existing
  33-table Phase-1 DB (0002 backfills). Idempotent.
- **Router wiring** (`app/api.py`) and **metadata registration** (`db/metadata.py`)
  include suppliers + procurement.
- **Seed** (`app/seed.py`) adds 3 demo suppliers, supplier-specific purchase
  prices for the paper SKUs, and a full completed buy loop (PO → confirm → receive
  → bill) with a half-payment to the supplier.
- **Web DTO contract** (`apps/web/src/lib/dto.ts`) matches the FastAPI
  `response_model` shapes field-for-field — incl. the envelope split: `/suppliers`
  and `/purchase-orders` return `{items,...}` (paginated) while `/bills`,
  `/invoices`, `/goods-receipts` return plain arrays; the pages consume each
  correctly. Feature dialogs/forms mirror verified spine components.
- **Nav** flips Suppliers / Purchase Orders / Procurement to `active:true`.

Still **UNVERIFIED** because this machine has no runtime — the test machine must
run migrate + seed, curl the new endpoints (incl. PO confirm→receive→bill and a
supplier payment), and confirm `npm run build` passes. See the test prompt handed
off with this session.

## Phase B (Operations & Config) — CODE WRITTEN, awaiting E2E (2026-07-22)

Migration **0003_operations_and_config** (down_revision 0002) creates `task` +
`document`; everything else reuses Phase-1 tables. Built:

- **Warehouse/Inventory widen** — `StockTransferService.transfer` (two ledger
  movements), `StockAdjustmentService.adjust` + `.count` (cycle count), all via
  the single `InventoryService.record_movement`; `GET /inventory/warehouse-stock`,
  `POST /inventory/transfers|adjustments|counts`.
- **Full Settings CRUD** in config — create/update for the code/name masters,
  warehouses, `CategoryService` (create/update/reparent, cycle-safe),
  `UomConversionService.upsert`, `TaxRateService.set_slab` (versioned),
  `SettingService.set`. All GET+POST/PATCH under the config router.
- **Tasks** module (create/complete/update, polymorphic link) and **Documents**
  module (`DocumentService.upload` → R2 when `R2_*` set, else local-disk fallback
  under gitignored `var/`; multipart upload + list + download). Added
  `python-multipart` dep.
- Frontend: `/warehouse`, `/categories`, `/settings`, `/tasks`, `/documents` with
  dialogs; DTOs added in parity; nav flipped for those five.

## Phase C (Intelligence & Growth) — CODE WRITTEN, awaiting E2E (2026-07-22)

Migration **0004_intelligence_and_growth** (down_revision 0003) creates
`pipeline_stage`, `lead`, `opportunity`, `competitor`, `notification`. Built:

- **CRM** module — leads (create/convert→customer), opportunities
  (create/advance through data-driven stages), competitors; pipeline stages seeded.
- **Notifications** module — push (emits `notification.sent`), list w/ unread
  count, mark read / read-all; a bell + slide-over inbox in the app shell.
- **Reports** (read-only, no entities) — `ReportService.run` with CSV/JSON over
  sales register, purchase register, stock ledger, AR/AP aging, GST summary.
- **Analytics** (read-only) — `AnalyticsService.board`: revenue/purchases, gross
  profit + margin, receivables/payables, DSO, fill rate, 6-month trends, top
  customers/suppliers/products; `/analytics` KPI board with a Recharts trend chart.
- **QuickBooks bridge** — `QuickBooksSyncService` behind `FLAG_QUICKBOOKS`,
  no-ops cleanly when off; manual sync endpoints. No core flow depends on it.
- Frontend: `/reports`, `/analytics`, `/leads` (pipeline board), notification
  inbox; DTOs in parity; nav flipped for Reports, Analytics, and a new Leads item.

**All of B and C are UNVERIFIED (no runtime here).** The test machine must run
`alembic upgrade head` (applies 0003 then 0004), `python -m app.seed`, curl the new
endpoints, and confirm `npm run build` passes. See the handoff test prompt.


## Where the build came from

- **2026-07-19 (session `1b3999ee`, run from `C:\Users\tthopte`):** Built ApexOS end-to-end in one
  autonomous run. Produced the full `docs/` design set (Phase 0), the base scaffold, the initial
  Alembic migration, then fanned out two parallel agents ("backend spine" + "frontend spine") that
  wrote all the code under `apps/api` and `apps/web`.
- **Where it stopped:** during **E2E run/verify**. No Docker on this machine; PostgreSQL 18 is
  installed but `initdb` refused because the shell ran under an **admin token**. The API stream then
  timed out and the session died. **Result: all code was written but never run or verified.**
- **2026-07-20 (this session, run from the project folder):** Recovered the history, resumed the
  unfinished E2E verification.

## Environment (this machine)

- Python 3.12.7, Node 24 — OK. **No Docker.** PostgreSQL 18 installed (binaries only, at
  `C:\Program Files\PostgreSQL\18`), no cluster, no service.
- **Admin-token gotcha:** Postgres refuses to run under an elevated token. Fix that works:
  run `initdb` / `pg_ctl start` via a **Windows Scheduled Task with `/RL LIMITED`** (forces the
  standard non-admin token). `runas /trustlevel` is NOT enough — the bootstrap child still sees admin.
- **Throwaway DB cluster:** initialized in the session scratchpad, **port 5433**, user `apex`,
  trust auth, db `apexos`. This is disposable — see "How to bring the DB back up" below.
- `apps/api/.env` and `apps/web/.env.local` are written pointing at port 5433 / API 8000.

## Status by area

- [x] Design docs (`docs/00`–`17`) — complete
- [x] Backend code (`apps/api`) — all modules written: identity, customers, products, pricing,
      inventory, sales, fulfillment, finance, dashboard, activity, config
- [x] Frontend code (`apps/web`) — app shell + spine pages (dashboard, customers, products,
      inventory, sales list/new/detail, finance)
- [x] Backend deps installed (venv + `pip install -e ".[dev]"`)
- [x] Web deps installed (`npm install`)
- [x] Postgres cluster up (5433) + `apexos` db created
- [x] Alembic migration applied (33 tables)
- [x] Seed data loaded (17 products, 3 customers, 1 order → invoice → part-payment)
- [x] API runs + endpoints verified (E2E backend) — reads, writes, and the full
      order→confirm→fulfill→invoice→payment workflow all return 200 with real data
- [x] Web builds/typechecks + runs — all 10 routes serve live API data, no runtime errors
- [x] Bugs found in audit fixed; **final smoke test green (every page HTTP 200)**

## ✅ E2E VERIFIED — 2026-07-20

The unfinished work from the 2026-07-19 session is complete. The whole stack runs and is verified.

### Bugs found & fixed during E2E (frontend/backend contract drift between the two build agents)

1. **`next.config.mjs`** — removed `experimental.typedRoutes`. It's incompatible with the
   data-driven nav (routes as data, `[module]` catch-all) and blocked the build on every shared
   component. (Confirmed by the frontend audit as the correct fix.)
2. **`apps/web/src/app/(app)/finance/page.tsx`** — `GET /invoices` returns a plain array, but the
   page treated it as a paginated `{items}` envelope → `.reduce` on `undefined` → 500. Now fetched
   as an array.
3. **`apps/web/src/app/(app)/sales/[id]/page.tsx` + `lib/dto.ts`** — backend `SalesOrderDetail`
   serves flat `customer_id`/`customer_name` and **arrays** `fulfillments`/`invoices`; the page
   expected a nested `customer` object and singular `fulfillment`/`invoice` → 500 on
   `order.customer.id`. DTO + page realigned to the real contract (uses `[0]` of each array; also
   `fulfilled_at` → `shipped_at`).
4. **`apps/web/src/features/products/products-table.tsx`** — removed `rowHref` to `/products/[id]`
   (no such route exists; it dead-ended at the `[module]` placeholder).

Backend audit was clean; only a non-blocking Dockerfile layer-ordering nit remains (see below).

## How to run it (verified working on this machine)

> ⚠️ **SUPERSEDED — do not follow these commands.** This section predates the stack lightening:
> Postgres, Alembic and the Next.js frontend are all gone. `alembic` is not installed and
> `apps/web/` no longer exists. For the current one-process SQLite setup see `RUNNING.md`, or the
> fresh-clone steps in the `▶ CURRENT WORK` section at the top of this file. Kept as historical record.

**1. Bring up Postgres** (only if `pg_isready -p 5433` fails — see recipe below).

**2. Backend** (from `apps/api`):
```
./.venv/Scripts/python.exe -m alembic upgrade head      # if DB is fresh
./.venv/Scripts/python.exe -m app.seed                  # if DB is empty
./.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```
Docs at http://localhost:8000/docs · OpenAPI at http://localhost:8000/api/v1/openapi.json

**3. Frontend** (from `apps/web`): `npm run dev` (or `npm run build && npx next start -p 3000`) →
http://localhost:3000

## Known non-blocking follow-ups (not needed to run)

- `apps/api/Dockerfile`: `pip install -e .` runs before `COPY . .`, so the editable package has no
  source at build time. Reorder for container builds. Local run is unaffected.
- `duration-[120ms]` Tailwind class is ambiguous → harmless build warning.
- Products have no detail page (`/products/[id]`) yet — by design (not in the spine).
- Nav modules marked `active: false` (Categories, Warehouse, Procurement, POs, Suppliers, Reports,
  Analytics, Tasks, Documents, Settings) render the "coming soon" placeholder — future work.

## How to bring the DB back up (new session)

The cluster lives in a session-scratchpad dir that may be cleaned up. If `pg_isready -p 5433` fails,
re-create it with the LIMITED-scheduled-task trick (init in a user-writable dir, `-U apex -A trust`,
set `port = 5433`, `pg_ctl start`, `createdb apexos`). See this session's commands for the exact recipe.

## Next steps

1. `alembic upgrade head` → `python -m app.seed`
2. `uvicorn app.main:app` → curl `/health` and `/api/v1/dashboard/summary`
3. `npm run build` (web) → `npm run dev`, verify pages load against the API

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
| Block deleting/deactivating something in use | `app/db/references.py` — `REFERENCES` is the policy | Writing a count query in a service; that is what this replaced |
| Delete something | `app/db/soft_delete.py` (its docstring is the contract) | Per-module delete code — there isn't any, by design |
| Prevent duplicates | `app/db/duplicates.py` — `NATURAL_KEYS` is the config | — |
| Show change history | `app/modules/activity/history.py` + `ActivityService.history()` | Any new table — there is none (R2.10) |
| Add a web page | `app/web/core.py` (render/redirect/filters), one existing page module in `app/web/pages/` | The other 16 page modules |
| Guard a web mutation | `app/web/security.py` | The JSON API's `require_permission` — the web one mirrors it |
| Add seed data | § Seed below, then the one `# --- section ---` you need | `seed.py` end to end |
| Understand a domain module | `docs/08-module-breakdown.md` § for that module | The module's four files, until you're actually changing them |
| Know what "done" means | `docs/REQUIREMENTS.md` § for your part | — |
| Know what changed recently | `git log --oneline -5 --stat`, `git diff part-0N-done..HEAD --stat` | Anything, until you've run those |

---

## Layout

```
apps/api/app/
  main.py            FastAPI app + lifespan (create_all, _ensure_new_columns, model imports)
  api.py             JSON API router assembly
  seed.py            demo data — see § Seed
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

### `app/web/security.py` — web authz (R1.4)

`require_web_permission(permission)` — a FastAPI dependency that renders 403 `error.html` on GET and
redirects with an error flash on POST, mirroring the JSON API's `require_permission`. **A no-op in
practice** (decision D-B: one user, whose actor holds `*`); it exists as the prod pattern. Do not build
a roles/permissions UI on top of it — that's cut.

### `templates/_macros.html` — the UI vocabulary

Imported as `ui` in templates. General: `page_header`, `stat`, `badge`, `empty`, `delete_button`.
List machinery: `list_toolbar`, `list_table`, `pagination`, `list_empty`, `cell`. History:
`history_panel`.

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
balances (G7). If you're adding a mutable counter for something computable, re-read G7.

---

## Seed (`app/seed.py`)

`run()` is idempotent via `get_or_create`, and builds in this order — each block is a
`# --- section ---` comment, so jump to the one you need:

reference data → founder user → org/config → categories → products + prices + opening stock →
demo customers + credit policies → demo suppliers → one complete buy loop (PO → confirm → receive →
bill → partial payment) → one complete sell loop (order → confirm → fulfill → invoice → partial
payment) → second warehouse + transfer, tasks, a document → pipeline stages, leads, opportunity,
competitors.

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

Run `pytest -q`, never verbose.

---

## Known debt

**38 pre-existing `ruff` findings**, all in modules the current work hasn't touched — 32 `E501`, 4
`F841`, 1 `B007`, 1 `E402` (the last two in `seed.py`). It was 39 through Part 2 C1; C2 deleted
`CustomerRepository.search`, which held one of the `E501`s. **New work has added zero findings, and
that's the bar.** Part 11 (`R14.x`) clears them; until then `ruff check app/ tests/` reporting exactly
38 is a *pass*, and 39 is a regression to fix before committing.

**`/warehouse` and `/inventory` render every product** (`page_size=300`, no pagination) — harmless at
17 rows, now ~170 KB of HTML at 311. They are not list-machinery pages yet; whichever part owns them
should wire them onto `ListSpec` rather than raising the page size again.

**`/categories` renders a full parent dropdown per row** (~90 KB at 24 categories). Fine now, quadratic
later: a category picker that loads once and is reused, or a reparent form on the detail page only, is
the fix when it stops being fine.

---

## Retired — do not follow

- `apps/web/` — deleted Next.js SPA. Gone from git; a stale local copy may still be on disk.
- Postgres + Alembic. Dev is SQLite via `create_all` + the additive `_ensure_new_columns` shim in
  `main.py`; prod Postgres reintroduces Alembic behind `DATABASE_URL`. See `docs/MIGRATION-STRATEGY.md`.
- `docs/BUILD-PHASES.md`, and the delivery/stack content of `docs/07`, `docs/14`, `docs/15`. Their
  *domain* content still stands; their *stack* content is historical.
- `PROGRESS.md`'s "How to run it" section — flagged superseded in-file; it still names `alembic` and
  `npm`, neither of which exists.

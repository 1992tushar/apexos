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
python -m pytest -q                  # expect 43 passed
python -m ruff check app/ tests/     # only pre-existing E501 in untouched modules
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

## Part 2 — Master data & shared machinery · on `main` · checkpoint 0 of 3 · tag when done: `part-02-done`

**Part 1 is COMPLETE and tagged `part-01-done`.** Its record is in the log below.

- [ ] **C1** table/filter macros + generic query helper + duplicate prevention + change history
- [ ] **C2** prove the machinery on products + customers, record the R2.14 line count
- [ ] **C3** roll out to the remaining 8 masters + their special cases

**Requirements passed:** R2.x / R3.x — none yet, part not started.
**Requirements outstanding:** all of `docs/REQUIREMENTS.md` §3 (R2.1–R2.15) and §4 (R3.1–R3.x).
**Baseline:** 82 tests passing; `ruff check app/ tests/` reports 39 findings, **all pre-existing** in
untouched modules (`app/seed.py` ×17, `app/modules/*`; E501/E402/B007/F841). `app/web/` is fully
clean. That 39 is the number to compare against — do not add to it (G13).

**Gotchas for the next session:**
- **Do not build a second query helper or a second table macro.** R2.1/R2.4 are explicit that these
  are one definition each. Part 1 set the precedent with soft delete (one mechanism in
  `app/db/soft_delete.py`, every caller uses it) — follow that shape.
- **`ui.delete_button` in `_macros.html` already exists.** When C1 builds the list/table macros, the
  Actions column has to keep rendering it; don't replace the column wholesale and drop delete.
- **Every web POST route now carries `require_web_permission`.** A new mutation route added without
  one fails `tests/test_web_authz.py::test_every_web_post_route_carries_the_guard`. That test is the
  coverage guarantee — add the guard, don't weaken the test.
- **R2.13 wants hundreds of products/customers** in the seed to make pagination real. The seed
  currently loads 17 products and 3 customers, so this is a real seed extension, not a tweak.
- **Port 8000 may be occupied** on the current build machine by an unrelated app. `uvicorn` logs the
  bind failure but the shell may still report success — check the log, or just use `--port 8010`.
- **Python is per-user installed** at `C:\Users\Administrator\AppData\Local\Programs\Python\Python312`
  and is not on `PATH` in a fresh shell; the venv at `apps/api/.venv` is what to activate.

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

**NEXT SESSION:** start Part 2 at **C1** using the Part 2 prompt in `docs/ROADMAP.md`. Read this block
+ `docs/REQUIREMENTS.md` §3 and §4 + `git log --oneline -15`. Do **not** re-read the older `docs/`
design files, and do not re-read `docs/DELETION-POLICY.md` or `docs/MIGRATION-STRATEGY.md` — Part 1
resolved both and the standing rules are reproduced in the prompt.

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

**NEXT SESSION:** start at C<i+1>. Read this block + `docs/REQUIREMENTS.md` §<n> + `git log --oneline -15`.
              Do NOT re-read <the docs this session already resolved>.
```

Rules that make the block worth writing:

1. **Commit at every checkpoint**, not at part end. Uncommitted work dies with the session.
2. **Requirement IDs, not prose.** "Did the inventory stuff" is not resumable; "R6.1–R6.6 pass,
   R6.10 outstanding" is.
3. **Record decisions, not just progress.** A later session that silently reverses a mid-part
   decision is the expensive failure mode.
4. **Say what NOT to read.** Resuming sessions burn most of their budget re-establishing context they
   do not need.

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

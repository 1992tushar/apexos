# ApexOS — Folder Structure

> **Status:** Approved · **Owner:** Architecture · **Version:** 1.0 · **Date:** 2026-07-19
>
> Conforms to `00-canonical-foundation.md`. Where this document and the foundation disagree,
> the foundation wins. This document defines the **physical layout** of the monorepo and the
> exact place every file for a new feature goes, end-to-end.

---

## 1. Principles

- **Feature-based, not layer-based.** Group by business capability (`sales-order`,
  `product`), not by technical role (`controllers/`, `models/`). A feature owns its full
  vertical.
- **One slice, one place.** A feature's route, UI, hook, client-schema (frontend) and
  router, service, repository, models, schemas (backend) live together. You should never
  hunt across five top-level folders to change one behavior.
- **Shared is earned, not assumed.** Code moves to `packages/` or `lib/` only when a second
  consumer appears. No speculative shared layers.
- **The spine (D4) is the reference implementation.** `sales-order` is built first and to
  production quality; every later module copies its shape.

---

## 2. Monorepo Root

```
apexos/
├── apps/
│   └── api/                    # FastAPI backend + server-rendered web UI (app/web/, Jinja2)
├── packages/                   # Shared, versioned workspace packages (earned, not default)
│   ├── types/                  # Generated TS types from OpenAPI (single source of truth)
│   ├── config-eslint/          # Shared ESLint config
│   └── config-ts/              # Shared tsconfig base
├── docs/                       # This directory — canonical foundation + standards
├── infra/                      # IaC: Railway/Render config, K8s manifests (later), R2 buckets
├── docker/                     # Dockerfiles + compose for local dev (postgres, redis, api, web)
│   ├── docker-compose.yml
│   ├── web.Dockerfile
│   └── api.Dockerfile
├── .github/
│   └── workflows/              # ci.yml (lint+test+typecheck), deploy.yml
├── .env.example                # Every env var, documented, no secrets
├── package.json                # Workspace root (pnpm workspaces)
├── pnpm-workspace.yaml
├── turbo.json                  # Task pipeline (build/lint/test/typecheck)
└── README.md
```

**Rules**

- `apps/*` are deployables. `packages/*` are libraries consumed by apps.
- The API contract flows one way: `apps/api` emits OpenAPI → `packages/types` is generated
  from it → `apps/web` imports `@apexos/types`. Frontend never hand-writes DTO types.
- No app imports another app. Cross-app sharing goes through `packages/`.

---

## 3. Frontend — `apps/web` (superseded)

> **Historical.** The standalone Next.js SPA below was replaced by a server-rendered
> **Jinja2** UI that lives inside the API at `apps/api/app/web/` (`pages/*.py` route
> handlers calling the domain services directly + `templates/` + `static/`), mounted by
> `app.main`. There is no longer a separate `apps/web`, npm build, or generated TS DTO
> layer. The structure below is retained only as a record of the original design.

```
apps/web/
├── src/
│   ├── app/                          # App Router: routing, layouts, pages ONLY (thin)
│   │   ├── layout.tsx                # Root layout (providers, fonts, theme)
│   │   ├── globals.css
│   │   ├── (auth)/                   # Clerk sign-in/up route group
│   │   ├── (app)/                    # Authenticated shell
│   │   │   ├── layout.tsx            # Sidebar + topbar shell
│   │   │   ├── dashboard/page.tsx
│   │   │   └── sales-orders/
│   │   │       ├── page.tsx          # List — renders features/sales-order/components
│   │   │       ├── new/page.tsx      # Create
│   │   │       └── [salesOrderId]/
│   │   │           └── page.tsx      # Detail
│   │   └── api/                      # Route handlers (BFF/webhooks only, not domain logic)
│   │
│   ├── features/                     # THE feature layer — one folder per capability
│   │   └── sales-order/
│   │       ├── components/           # Feature-scoped UI (SalesOrderTable.tsx, …)
│   │       ├── hooks/                # Data + behavior hooks (use-sales-orders.ts)
│   │       ├── api/                  # Typed client calls to the backend (sales-order-api.ts)
│   │       └── schema/               # Zod schemas + inferred form/DTO types
│   │
│   ├── components/
│   │   └── ui/                       # shadcn/ui primitives (button.tsx, table.tsx, …)
│   ├── components/shared/            # Cross-feature composite components (PageHeader, …)
│   │
│   ├── lib/                          # Cross-cutting utilities
│   │   ├── api-client.ts             # fetch wrapper: base URL, auth header, error envelope parse
│   │   ├── query-client.ts           # TanStack Query config
│   │   ├── format.ts                 # money (minor→display), dates (Asia/Kolkata)
│   │   └── utils.ts                  # cn(), misc
│   │
│   ├── styles/                       # Tailwind layers, design tokens
│   └── env.ts                        # Zod-validated client env (NEXT_PUBLIC_*)
│
├── public/
├── tests/
│   ├── unit/                         # Component + hook tests (Vitest + RTL)
│   └── e2e/                          # Playwright specs (sales-order.spec.ts)
├── components.json                   # shadcn/ui config
├── next.config.mjs
├── tailwind.config.ts
├── tsconfig.json
├── vitest.config.ts
├── playwright.config.ts
├── .eslintrc.cjs                     # extends @apexos/config-eslint
└── package.json
```

**Rules**

- `app/` is routing only. A `page.tsx` imports from `features/<feature>` and composes —
  it holds no data-fetching logic, no business rules, no ad-hoc `fetch`.
- `features/<feature>/api` is the **only** place that calls the backend for that feature.
  Components and hooks call the feature `api`, never `fetch` directly.
- shadcn primitives stay unmodified in `components/ui`. Feature styling wraps them in
  `features/*/components` or `components/shared`.
- Colocate a feature's tests next to nothing surprising: unit tests in `tests/unit` mirror
  the feature path; e2e in `tests/e2e`.

---

## 4. Backend — `apps/api`

```
apps/api/
├── app/
│   ├── main.py                       # FastAPI app factory, router registration, middleware
│   ├── core/                         # Cross-cutting infrastructure (no domain logic)
│   │   ├── config.py                 # Pydantic Settings (env → typed config)
│   │   ├── security.py               # Clerk token verify → current_user
│   │   ├── logging.py                # structlog setup, correlation-id processor
│   │   ├── errors.py                 # Typed exception base + error-envelope handler
│   │   ├── pagination.py             # Shared page params + envelope
│   │   └── ids.py                    # UUID v7 generation, code sequence helpers
│   │
│   ├── db/                           # Persistence infrastructure (no domain logic)
│   │   ├── base.py                   # DeclarativeBase, audit-column mixin, soft-delete mixin
│   │   ├── session.py                # Engine, sessionmaker, get_session dependency
│   │   └── types.py                  # Custom column types (MoneyMinor, etc.)
│   │
│   ├── modules/                      # THE feature layer — one package per capability
│   │   └── sales_order/
│   │       ├── __init__.py
│   │       ├── router.py             # HTTP: thin. Parse → call service → return schema.
│   │       ├── service.py            # Business logic, transactions, orchestration.
│   │       ├── repository.py         # SQLAlchemy queries ONLY. No business rules.
│   │       ├── models.py             # SQLAlchemy ORM models (sales_order, sales_order_line)
│   │       ├── schemas.py            # Pydantic v2: SalesOrderCreate/Update/Read
│   │       ├── dependencies.py       # FastAPI Depends providers (get_sales_order_service)
│   │       └── events.py             # Domain event names + emit helpers (activity_log)
│   │
│   └── shared/                       # Reusable domain-adjacent code (earned)
│       └── ledger.py                 # Append-only ledger helpers (D3): stock/finance
│
├── tests/
│   ├── conftest.py                   # Fixtures: db session, client, factories
│   ├── factories/                    # factory_boy / polyfactory model factories
│   ├── unit/                         # Pure logic (service with mocked repo)
│   ├── integration/                  # Router + real test DB
│   └── e2e/                          # Full-stack contract tests (optional; usually web/e2e)
├── pyproject.toml                    # deps + ruff + black config
├── .env.example
└── Dockerfile -> ../../docker/api.Dockerfile
```

**Rules (the layering contract — see `12-coding-standards.md` §3)**

- `router.py` is thin: validate input via schema, resolve dependencies, call one service
  method, map the result to a `Read` schema. **No ORM, no queries, no business rules.**
- `service.py` owns logic, transaction boundaries, cross-repository orchestration, event
  emission. It depends on repositories, never on the request/response objects.
- `repository.py` owns SQLAlchemy queries and persistence. It returns models or primitives,
  takes/returns no Pydantic schemas, contains no business decisions.
- `models.py` = database shape. `schemas.py` = API shape. They are **separate on purpose**
  (D6/D7 columns are not necessarily exposed).
- A module never imports another module's `repository` or `models`. Cross-module needs go
  through the other module's `service` (its public interface).

---

## 5. Worked Example — Adding the `sales-order` Slice End-to-End

Task: implement Sales Order create + list (the D4 spine step). Every file, in order.

### 5.1 Backend (`apps/api`)

| Step | File | What goes in |
|------|------|--------------|
| 1 | `app/modules/sales_order/models.py` | `SalesOrder`, `SalesOrderLine` ORM (audit + `business_unit_id`, `order_no`, `_minor` money cols). |
| 2 | `alembic/versions/xxxx_create_sales_order.py` | `alembic revision --autogenerate`; review; tables + indexes on `order_no`, FKs. |
| 3 | `app/modules/sales_order/schemas.py` | `SalesOrderLineCreate`, `SalesOrderCreate`, `SalesOrderRead`, `SalesOrderUpdate`. |
| 4 | `app/modules/sales_order/repository.py` | `SalesOrderRepository`: `add`, `get`, `list_by_business_unit`, `next_order_no`. |
| 5 | `app/modules/sales_order/service.py` | `SalesOrderService`: validate customer/credit, allocate `SO-YYYYMM-#####`, compute line totals in minor units, persist in one transaction, emit `sales_order.created`. |
| 6 | `app/modules/sales_order/events.py` | `SALES_ORDER_CREATED = "sales_order.created"` + `emit()` into `activity_log`. |
| 7 | `app/modules/sales_order/dependencies.py` | `get_sales_order_service(session, ...)` provider. |
| 8 | `app/modules/sales_order/router.py` | `POST /`, `GET /`, `GET /{sales_order_id}` — thin. |
| 9 | `app/main.py` | `app.include_router(sales_order.router, prefix="/api/v1/sales-orders")`. |
| 10 | `tests/factories/sales_order.py`, `tests/unit/…`, `tests/integration/…` | Service unit tests (mocked repo) + router integration tests (real test DB). |

### 5.2 Frontend (`apps/web`)

| Step | File | What goes in |
|------|------|--------------|
| 1 | *(generated)* `packages/types` | Regenerate from OpenAPI after backend ships. Provides `SalesOrderReadDTO`. |
| 2 | `features/sales-order/schema/sales-order-schema.ts` | `salesOrderCreateSchema` (Zod) + inferred `SalesOrderCreateInput`. |
| 3 | `features/sales-order/api/sales-order-api.ts` | `createSalesOrder`, `listSalesOrders` using `lib/api-client`. |
| 4 | `features/sales-order/hooks/use-sales-orders.ts` | TanStack Query hooks: `useSalesOrders`, `useCreateSalesOrder`. |
| 5 | `features/sales-order/components/SalesOrderTable.tsx`, `SalesOrderForm.tsx` | UI, RHF + Zod resolver, money display via `lib/format`. |
| 6 | `app/(app)/sales-orders/page.tsx`, `new/page.tsx`, `[salesOrderId]/page.tsx` | Routes that compose the feature. |
| 7 | `tests/unit/sales-order/…`, `tests/e2e/sales-order.spec.ts` | Hook/component units + Playwright happy path. |

**Direction of dependency (never reversed):**
`page.tsx → components → hooks → api → schema/types` and
`router → service → repository → models`.

---

## 6. Config, Env, and Test Placement (quick reference)

| Concern | Frontend | Backend |
|---------|----------|---------|
| Runtime config | `src/env.ts` (Zod-validated) | `app/core/config.py` (Pydantic Settings) |
| Env template | `apps/web/.env.example` | `apps/api/.env.example` (+ root `.env.example`) |
| Lint/format | `.eslintrc.cjs`, prettier (root) | `pyproject.toml` (ruff + black) |
| Type config | `tsconfig.json` (extends `@apexos/config-ts`) | `pyproject.toml` (mypy strict) |
| Unit tests | `apps/web/tests/unit/` | `apps/api/tests/unit/` |
| Integration | — | `apps/api/tests/integration/` |
| E2E | `apps/web/tests/e2e/` (Playwright) | — |
| Factories/fixtures | RTL render helpers in `tests/` | `apps/api/tests/factories/`, `conftest.py` |

**Never** commit real secrets. `.env.example` documents every key with a dummy value;
real values live in the deploy platform's secret store and local untracked `.env`.

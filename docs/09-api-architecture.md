# ApexOS — API Architecture

> **Status:** Draft for build · **Owner:** Backend Architecture · **Version:** 1.0 · **Date:** 2026-07-19
>
> Conforms to `00-canonical-foundation.md` (source of truth). Resource names are the canonical
> entities (§5); paths follow the naming standard (§6); auth follows D8; ledgers follow D3;
> money follows D5; keys follow D6. Cross-checked against `02-information-architecture.md` (route
> map) and `08-module-breakdown.md` (services, spine call-chain). Where this document and the
> foundation disagree, **the foundation wins.**

---

## 1. API Conventions

### 1.1 Base, versioning, resource naming

- **Base URL:** `/api/v1` — the version is in the path (Foundation §6). Breaking changes bump to
  `/api/v2`; `/v1` remains until deprecation window closes (§9).
- **Resources:** plural, `kebab-case` nouns mirroring canonical entities:
  `/api/v1/sales-orders`, `/api/v1/purchase-orders`, `/api/v1/customer-credit-policies`.
- **Sub-resources** nest one level where lifecycle is owned by the parent:
  `/api/v1/sales-orders/{id}/lines`, `/api/v1/purchase-orders/{id}/goods-receipts`.
- **Identifiers in paths are UUID v7 surrogates** (D6). Human codes (`SO-YYYYMM-#####`, SKU) are
  attributes and query filters, never the path key.
- **Actions that are not plain CRUD** are modeled as sub-resource POSTs (verbs as resources):
  `POST /api/v1/sales-orders/{id}/confirm`, `POST /api/v1/fulfillments`,
  `POST /api/v1/payments/{id}/allocations`. This keeps the golden path (§5.2 of the module
  breakdown) explicit while staying RESTful.

### 1.2 Collections: pagination, filtering, sorting

All list endpoints share one contract:

- **Pagination** — cursor-based (keyset on UUID v7 creation order):
  `?limit=50&cursor=<opaque>`. `limit` default 25, max 100. Response envelope carries
  `page.next_cursor` (null at end) and `page.has_more`.
- **Filtering** — `?field=value`, repeatable for `IN` (`?status=confirmed&status=fulfilling`),
  range suffixes `?created_at.gte=…&created_at.lt=…`, and free text `?q=` (federated across the
  human code + name index, ⌘K scope). Every operational list is implicitly filtered by the
  active **Business Unit** via `?business_unit_id=` (or `all`), and always by the caller's
  `permission` set (D1).
- **Sorting** — `?sort=-created_at,code`; `-` prefix = descending. Whitelisted per resource.
- **Field selection (optional)** — `?fields=id,code,status,total_minor` for lean payloads.

### 1.3 Money, dates, scope

- **Money** is always an integer minor-unit field suffixed `_minor` plus a sibling `currency`
  (D5): `{ "total_minor": 4218000, "currency": "INR" }`. No floats, ever.
- **Timestamps** are UTC ISO-8601 (`timestamptz`), suffixed `_at` (D9). Clients render in
  `Asia/Kolkata`.
- **Business Unit** is a first-class query/body dimension on operational resources (D1).

### 1.4 Idempotency (mutations)

- Every **POST that creates or posts to a ledger** requires an `Idempotency-Key` header
  (client-generated UUID). The server stores `{key → (status, response)}` for 24h keyed by
  route + actor; a repeat returns the original response with `Idempotency-Replayed: true`.
- This is mandatory on the ledger writers (`fulfillments`, `invoices`, `payments`,
  `payment allocations`, `bills`, `goods-receipts`, `stock-movements`) so retries never
  double-post (D3). PUT/PATCH/DELETE are naturally idempotent and do not require the header.

### 1.5 Error envelope

All errors share one shape (centralized handler, Foundation §3 patterns):

```json
{
  "error": {
    "code": "credit_limit_exceeded",
    "message": "Order total exceeds available credit for customer.",
    "status": 422,
    "request_id": "req_01J...",
    "details": [
      { "field": "total_minor", "issue": "exceeds available credit 150000" }
    ]
  }
}
```

- `code` — stable machine string (snake_case), not the HTTP number.
- `request_id` — correlates to structured logs.
- `details[]` — per-field validation issues (Pydantic v2 → this shape).

### 1.6 Status codes

| Code | Used for |
|---|---|
| 200 | Successful GET / PUT / PATCH / action returning a body |
| 201 | Resource created (POST) — `Location` header set |
| 202 | Accepted, async (e.g. QBO push queued) |
| 204 | Successful DELETE (soft-delete) with no body |
| 400 | Malformed request / bad query params |
| 401 | Missing/invalid Clerk session |
| 403 | Authenticated but lacks required `permission` |
| 404 | Not found or soft-deleted (or out of BU scope) |
| 409 | Conflict — duplicate code, version conflict, over-allocation |
| 422 | Business-rule violation (credit gate, over-ship, tax mismatch) |
| 429 | Rate limited |
| 500 | Unhandled — carries `request_id` only, never internals |

### 1.7 DTO naming

Request/response DTOs mirror the Python schema suffixes (Foundation §6): `Create`, `Update`,
`Read`. In the tables below, `XxxCreate` is the request body for POST, `XxxUpdate` for PUT/PATCH,
`XxxRead` the response representation. List responses are `Page<XxxRead>` (the §1.2 envelope).

---

## 2. Auth Model

Authentication is delegated to **Clerk** (D8); **authorization is owned by ApexOS**
(`08-module-breakdown.md` §2.2).

### 2.1 Request flow

```
Client (Next.js) ──Clerk session JWT──▶ FastAPI dependency: verify_clerk_session()
        │                                       │ verifies signature + expiry against Clerk JWKS
        │                                       ▼
        │                          UserProvisioningService.sync_from_clerk()
        │                                       │ upsert `user` on clerk_user_id (idempotent)
        │                                       ▼
        │                          AuthorizationService.resolve_permissions(user)
        │                                       │ flatten user_role → role_permission → permission set
        │                                       ▼
        └──────────────────────────▶ AuthorizationService.require("<permission>")  (per route)
```

- **Server-side verification only.** The Clerk session token is verified on every request against
  Clerk's JWKS; we never trust a client-asserted identity.
- The verified Clerk identity is mapped to our own `user` row (`clerk_user_id` unique). All
  authorization decisions read **our** `role` / `permission` / `role_permission` / `user_role`
  tables — we own authZ even though Clerk owns authN.
- `AuthorizationService.resolve_permissions(user)` produces the permission set (Redis-cached
  later); `AuthorizationService.require(permission)` is a FastAPI dependency on every route.
- A denied permission writes `permission.denied` to `activity_log` (security trail, D10) and
  returns 403.

### 2.2 Permission naming

Permissions are `<resource>:<action>` strings, e.g. `sales_order:create`, `invoice:issue`,
`payment:record`, `customer_credit_policy:set`, `setting:manage`. They are rows in `permission`
(D2 — data-driven), grouped into roles (Admin, Sales, Procurement, Finance, Viewer for Phase 1).
The **required permission** column in §4 names the exact string each endpoint calls `require()`
with.

### 2.3 Scoping

Every operational query is scoped to (a) the caller's permitted **Business Units** and (b) the
requested `business_unit_id`. Cross-BU access requires an explicitly BU-unscoped role. Records
outside scope return 404 (not 403) to avoid leaking existence.

---

## 3. Resource Overview

| Resource (path) | Owning module | CRUD | Ledger (D3, no edit) |
|---|---|---|---|
| `/api/v1/business-units` | Org/Config | full | — |
| `/api/v1/brands` · `/categories` · `/procurement-models` · `/uoms` · `/uom-conversions` | Org/Config | full | — |
| `/api/v1/customer-types` · `/supplier-types` · `/warehouses` · `/tax-rates` · `/settings` | Org/Config | full | `tax-rates` versioned |
| `/api/v1/users` · `/roles` · `/permissions` · `/user-roles` · `/role-permissions` | Identity | full | — |
| `/api/v1/products` · `/products/{id}/spec-attributes` · `/products/{id}/barcodes` | Products | full | — |
| `/api/v1/customers` · `/customers/{id}/contacts` · `/addresses` · `/customer-credit-policies` | Customers | full | credit policy versioned |
| `/api/v1/leads` · `/opportunities` · `/pipeline-stages` · `/competitors` | Customers/CRM | full | — |
| `/api/v1/suppliers` · `/suppliers/{id}/contacts` · `/supplier-evaluations` | Suppliers | full | — |
| `/api/v1/purchase-prices` · `/selling-prices` | Pricing | append | versioned (append) |
| `/api/v1/sales-orders` · `/sales-orders/{id}/lines` | Sales | full pre-confirm | — |
| `/api/v1/fulfillments` · `/fulfillments/{id}/lines` | Sales | create/read | **ledger** |
| `/api/v1/purchase-orders` · `/purchase-orders/{id}/lines` | Procurement | full pre-confirm | — |
| `/api/v1/goods-receipts` | Procurement | create/read | **ledger** |
| `/api/v1/stock-movements` · `/stock-balances` | Inventory | create/read | **ledger** / derived |
| `/api/v1/invoices` · `/bills` · `/payments` · `/payments/{id}/allocations` | Finance | create/read | **ledger** |
| `/api/v1/receivables` · `/payables` | Finance | read | derived |
| `/api/v1/tax-lines` | Finance | read | derived from documents |
| `/api/v1/activity-log` · `/tasks` · `/documents` · `/notifications` · `/decision-logs` · `/sops` | Platform | mixed | `activity-log` append |
| `/api/v1/reports` · `/kpis` · `/dashboard/*` | Dashboard/Reports | read | projections |

Ledger resources expose **no PUT/PATCH** (D3) — corrections are new movements, credit notes, or
voids, mirroring the IA route map (`02-information-architecture.md` §4).

---

## 4. Endpoint Tables

> **Legend:** 🔵 = spine endpoint (Phase 1, D4). Permission column = the `permission` string the
> route's `require()` guard checks. `Page<T>` = the §1.2 paginated envelope.

### 4.1 Spine — Customers (🔵)

| Method | Path | Purpose | Request DTO | Response DTO | Permission |
|---|---|---|---|---|---|
| GET | `/api/v1/customers` | List customers (BU + filter/sort/paginate) | — (query) | `Page<CustomerRead>` | `customer:read` |
| POST | `/api/v1/customers` | Create customer | `CustomerCreate` | `CustomerRead` (201) | `customer:create` |
| GET | `/api/v1/customers/{id}` | Get customer + summary | — | `CustomerRead` | `customer:read` |
| PATCH | `/api/v1/customers/{id}` | Update customer | `CustomerUpdate` | `CustomerRead` | `customer:update` |
| DELETE | `/api/v1/customers/{id}` | Soft-delete customer | — | (204) | `customer:delete` |
| GET | `/api/v1/customer-credit-policies?customer_id=` | Current + history credit policy | — | `Page<CustomerCreditPolicyRead>` | `customer_credit_policy:read` |
| POST | `/api/v1/customer-credit-policies` | Set credit policy (new version) | `CustomerCreditPolicyCreate` | `CustomerCreditPolicyRead` (201) | `customer_credit_policy:set` |

### 4.2 Spine — Products (🔵)

| Method | Path | Purpose | Request DTO | Response DTO | Permission |
|---|---|---|---|---|---|
| GET | `/api/v1/products` | List SKUs (category/brand/status filters) | — | `Page<ProductRead>` | `product:read` |
| POST | `/api/v1/products` | Create product; generates SKU `BRAND-CAT-SEQ` | `ProductCreate` | `ProductRead` (201) | `product:create` |
| GET | `/api/v1/products/{id}` | Product detail (specs, prices, stock) | — | `ProductRead` | `product:read` |
| PATCH | `/api/v1/products/{id}` | Update product | `ProductUpdate` | `ProductRead` | `product:update` |
| POST | `/api/v1/products/{id}/status` | Set Active/Draft/Discontinued | `ProductStatusUpdate` | `ProductRead` | `product:update` |
| GET/POST | `/api/v1/products/{id}/spec-attributes` | List/upsert spec attributes | `ProductSpecCreate` | `ProductSpecRead` | `product:update` |
| GET/POST | `/api/v1/products/{id}/barcodes` | List/attach barcodes | `ProductBarcodeCreate` | `ProductBarcodeRead` | `product:update` |

### 4.3 Spine — Pricing (🔵 resolve)

| Method | Path | Purpose | Request DTO | Response DTO | Permission |
|---|---|---|---|---|---|
| GET | `/api/v1/selling-prices/resolve?product_id=&customer_id=&at=` | Effective price (customer→segment→list) | — (query) | `SellingPriceResolveRead` | `selling_price:read` |
| GET | `/api/v1/selling-prices?product_id=` | List selling-price versions | — | `Page<SellingPriceRead>` | `selling_price:read` |
| POST | `/api/v1/selling-prices` | Set selling price (append version) | `SellingPriceCreate` | `SellingPriceRead` (201) | `selling_price:set` |
| GET | `/api/v1/purchase-prices?product_id=&supplier_id=` | List buy-price versions | — | `Page<PurchasePriceRead>` | `purchase_price:read` |
| POST | `/api/v1/purchase-prices` | Set purchase price (append version) | `PurchasePriceCreate` | `PurchasePriceRead` (201) | `purchase_price:set` |

### 4.4 Spine — Sales Orders (🔵)

| Method | Path | Purpose | Request DTO | Response DTO | Permission |
|---|---|---|---|---|---|
| GET | `/api/v1/sales-orders` | List orders (BU/status filters) | — | `Page<SalesOrderRead>` | `sales_order:read` |
| POST | `/api/v1/sales-orders` | Create order; resolves line prices + tax preview; assigns `SO-YYYYMM-#####` | `SalesOrderCreate` | `SalesOrderRead` (201) | `sales_order:create` |
| GET | `/api/v1/sales-orders/{id}` | Order detail (lines, margin, fulfillment, invoice) | — | `SalesOrderRead` | `sales_order:read` |
| PATCH | `/api/v1/sales-orders/{id}` | Edit draft order (pre-confirm only) | `SalesOrderUpdate` | `SalesOrderRead` | `sales_order:update` |
| GET/POST/PATCH | `/api/v1/sales-orders/{id}/lines` | Manage `sales_order_line` (pre-confirm) | `SalesOrderLineCreate/Update` | `SalesOrderLineRead` | `sales_order:update` |
| POST | `/api/v1/sales-orders/{id}/confirm` | Confirm — runs `CreditPolicyService.check()` gate | `SalesOrderConfirm` (idempotent) | `SalesOrderRead` (or 422 `credit_limit_exceeded`) | `sales_order:confirm` |
| POST | `/api/v1/sales-orders/{id}/cancel` | Cancel with reason | `SalesOrderCancel` | `SalesOrderRead` | `sales_order:cancel` |

### 4.5 Spine — Fulfillment (🔵, ledger)

| Method | Path | Purpose | Request DTO | Response DTO | Permission |
|---|---|---|---|---|---|
| GET | `/api/v1/fulfillments?sales_order_id=` | List fulfillments for an order | — | `Page<FulfillmentRead>` | `fulfillment:read` |
| POST | `/api/v1/fulfillments` | Ship — creates `fulfillment` + lines, posts OUT `stock_movement` per line (reason `SALE`), triggers invoice issue | `FulfillmentCreate` (**Idempotency-Key**) | `FulfillmentRead` (201, or 422 over-ship) | `fulfillment:ship` |
| GET | `/api/v1/fulfillments/{id}` | Fulfillment detail (shipped vs ordered) | — | `FulfillmentRead` | `fulfillment:read` |

### 4.6 Spine — Inventory (🔵, ledger + derived)

| Method | Path | Purpose | Request DTO | Response DTO | Permission |
|---|---|---|---|---|---|
| GET | `/api/v1/stock-balances?product_id=&warehouse_id=` | Derived on-hand balances | — | `Page<StockBalanceRead>` | `stock_balance:read` |
| GET | `/api/v1/stock-movements?product_id=&warehouse_id=&ref_type=` | Movement ledger | — | `Page<StockMovementRead>` | `stock_movement:read` |
| POST | `/api/v1/stock-movements` | Manual adjustment (reason `ADJUSTMENT`/`COUNT`) — internal writer for SALE/PO refs | `StockMovementCreate` (**Idempotency-Key**) | `StockMovementRead` (201) | `stock_movement:adjust` |

> `stock_movement` rows for `SALE`/`GOODS_RECEIPT` are written only through `InventoryService`
> invoked by Fulfillment/Goods-Receipt — never posted directly by clients. Direct POST is the
> manual-adjustment path only.

### 4.7 Spine — Finance: Invoices, Payments, Receivables (🔵, ledger)

| Method | Path | Purpose | Request DTO | Response DTO | Permission |
|---|---|---|---|---|---|
| GET | `/api/v1/invoices` | List invoices (status/customer filters) | — | `Page<InvoiceRead>` | `invoice:read` |
| POST | `/api/v1/invoices` | Issue invoice from fulfilled qty; `INV-YYYYMM-#####`; computes `tax_line` | `InvoiceCreate` (**Idempotency-Key**) | `InvoiceRead` (201) | `invoice:issue` |
| GET | `/api/v1/invoices/{id}` | Invoice detail (lines, tax, allocations) | — | `InvoiceRead` | `invoice:read` |
| POST | `/api/v1/invoices/{id}/void` | Void (ledger correction, no edit — D3) | `InvoiceVoid` | `InvoiceRead` | `invoice:void` |
| GET | `/api/v1/payments` | List payments (direction/party filters) | — | `Page<PaymentRead>` | `payment:read` |
| POST | `/api/v1/payments` | Record payment (`direction: in\|out`) | `PaymentCreate` (**Idempotency-Key**) | `PaymentRead` (201) | `payment:record` |
| GET | `/api/v1/payments/{id}` | Payment detail + allocations | — | `PaymentRead` | `payment:read` |
| POST | `/api/v1/payments/{id}/allocations` | Allocate cash to invoice/bill; over-allocation → 409 | `PaymentAllocationCreate` (**Idempotency-Key**) | `PaymentAllocationRead` (201) | `payment:allocate` |
| GET | `/api/v1/receivables?customer_id=` | Derived AR (invoice − allocations) + aging | — | `Page<ReceivableRead>` | `receivable:read` |
| GET | `/api/v1/payables?supplier_id=` | Derived AP (bill − allocations) + aging | — | `Page<PayableRead>` | `payable:read` |

### 4.8 Spine — Dashboard (🔵, read-only)

| Method | Path | Purpose | Request DTO | Response DTO | Permission |
|---|---|---|---|---|---|
| GET | `/api/v1/dashboard/spine-tiles?business_unit_id=&period=` | AR outstanding, GP, on-hand value, open orders | — | `SpineTilesRead` | `dashboard:read` |
| GET | `/api/v1/activity-log?business_unit_id=&limit=` | "What happened?" feed | — | `Page<ActivityLogRead>` | `activity_log:read` |
| GET | `/api/v1/kpis/{kpi}?period=` | Computed KPI (margin, DSO, fill-rate) | — | `KpiRead` | `kpi:read` |

### 4.9 Procurement mirror (Phase 2)

| Method | Path | Purpose | Request DTO | Response DTO | Permission |
|---|---|---|---|---|---|
| GET/POST | `/api/v1/suppliers` | List/create suppliers | `SupplierCreate` | `SupplierRead` | `supplier:read` / `supplier:create` |
| POST | `/api/v1/supplier-evaluations` | Score a supplier | `SupplierEvaluationCreate` | `SupplierEvaluationRead` | `supplier_evaluation:create` |
| GET/POST | `/api/v1/purchase-orders` | List/create PO; `PO-YYYYMM-#####` | `PurchaseOrderCreate` | `PurchaseOrderRead` | `purchase_order:read` / `purchase_order:create` |
| POST | `/api/v1/purchase-orders/{id}/confirm` | Confirm PO | `PurchaseOrderConfirm` | `PurchaseOrderRead` | `purchase_order:confirm` |
| POST | `/api/v1/goods-receipts` | Receive — posts IN `stock_movement` (ledger) | `GoodsReceiptCreate` (**Idempotency-Key**) | `GoodsReceiptRead` (201) | `goods_receipt:receive` |
| GET/POST | `/api/v1/bills` | List/issue bills (ledger) | `BillCreate` (**Idempotency-Key**) | `BillRead` | `bill:read` / `bill:issue` |

### 4.10 Org/Config, Identity, Platform (representative)

| Method | Path | Purpose | Request DTO | Response DTO | Permission |
|---|---|---|---|---|---|
| GET/POST/PATCH/DELETE | `/api/v1/business-units` | Manage BUs | `BusinessUnitCreate/Update` | `BusinessUnitRead` | `business_unit:*` |
| GET/POST/PATCH | `/api/v1/categories` | Manage categories (→BU, →procurement-model) | `CategoryCreate/Update` | `CategoryRead` | `category:*` |
| GET/POST/PATCH | `/api/v1/customer-types` | Manage segments (add vertical = one row, D2) | `CustomerTypeCreate/Update` | `CustomerTypeRead` | `customer_type:manage` |
| GET/POST/PATCH | `/api/v1/tax-rates` | Manage GST slabs (versioned) | `TaxRateCreate/Update` | `TaxRateRead` | `tax_rate:manage` |
| GET/PUT | `/api/v1/settings/{key}` | Typed get/set of a `setting` | `SettingUpdate` | `SettingRead` | `setting:manage` |
| POST | `/api/v1/users/sync` | Provision `user` from verified Clerk identity (idempotent) | `UserSync` | `UserRead` | (internal, session) |
| GET/POST | `/api/v1/roles` · `/user-roles` | Manage roles & assignments | `RoleCreate` / `UserRoleCreate` | `RoleRead` | `role:manage` |
| GET/POST | `/api/v1/tasks` | List/create tasks (polymorphic link) | `TaskCreate` | `TaskRead` | `task:*` |
| POST | `/api/v1/documents` | Upload to R2, record metadata (polymorphic link) | `DocumentCreate` (multipart) | `DocumentRead` | `document:upload` |

---

## 5. QuickBooks Online Bridge (Finance system-of-record)

> **This is a documented integration boundary, not an implementation.** The QuickBooks Online
> (QBO) connector is available in this environment (Foundation §3) and is the candidate
> **system-of-record bridge for Finance**. ApexOS remains the source of truth for the operational
> spine; QBO is the accounting book of record for invoices, bills, and payments.

### 5.1 Boundary and direction

- The bridge lives entirely inside the **Finance module** as `QuickBooksSyncService`
  (`08-module-breakdown.md` §2.9). No other module touches QBO.
- **Push (ApexOS → QBO)** is the primary direction: when an ApexOS `invoice`, `bill`, or
  `payment` is issued/recorded, it is mirrored into QBO as the accounting entry.
- **Pull (QBO → ApexOS)** is read-only reporting: AR/AP aging, P&L, balance sheet, sales
  summaries surfaced on the Finance dashboard and Reports/Analytics — never mutating ApexOS
  ledgers.
- The bridge is **feature-flagged and non-blocking**: a spine invoice issues and settles fully in
  ApexOS whether or not QBO is connected. QBO sync failures never fail the ApexOS transaction.

### 5.2 Sync surfaces (mapping)

| ApexOS entity | Direction | QBO object / connector capability |
|---|---|---|
| `invoice` (+ `invoice_line`, `tax_line`) | push | Create/Update/Send Invoice |
| `bill` (+ `bill_line`) | push | Bill (via transaction import) |
| `payment` (direction `in`) + `payment_allocation` | push | Payment applied to invoice |
| `payment` (direction `out`) | push | Bill payment |
| `customer` | push (upsert) | Create/Search Customer |
| `product` (SKU) | push (upsert) | Create/Search Product/Service |
| `receivable` aging | pull | AR Aging Summary/Detail |
| `payable` aging | pull | AP Aging Summary/Detail |
| Sales KPIs | pull | Sales by Customer/Product Summary |
| Finance dashboard | pull | P&L, Balance Sheet, Cash Flow |

### 5.3 Sync contract

- **Idempotent, keyed mapping.** ApexOS stores a `qbo_ref` (QBO id + sync token) per synced
  entity in a bridge mapping table (a `setting`/side-table, not a canonical entity). Re-pushing
  the same ApexOS document updates the same QBO object — never creates a duplicate (uses the
  §1.4 idempotency discipline on our side, QBO sync token on theirs).
- **Async & retried.** Pushes are enqueued (202 Accepted on the triggering ApexOS call) and
  retried with backoff. On success we write `qbo.synced` to `activity_log` (D10).
- **Money & tax.** Amounts cross the boundary as major-unit decimals with explicit `currency`
  (D5 minor units converted at the edge); GST maps to QBO tax codes derived from `tax_rate`.
- **Auth.** QBO OAuth tokens are stored as encrypted `setting` values and configured from
  **Settings → Finance → QuickBooks Connector** (`02-information-architecture.md` §7).
- **Reconciliation.** A scheduled pull compares QBO AR/AP aging against ApexOS derived
  `receivable`/`payable`; drift raises a `notification` and a `task` for Finance.

### 5.4 Internal bridge endpoints

| Method | Path | Purpose | Permission |
|---|---|---|---|
| GET | `/api/v1/integrations/quickbooks/status` | Connection + last-sync health | `setting:manage` |
| POST | `/api/v1/integrations/quickbooks/connect` | Start/refresh OAuth (stores encrypted `setting`) | `setting:manage` |
| POST | `/api/v1/invoices/{id}/qbo-sync` | Force-push one invoice (202) | `invoice:issue` |
| POST | `/api/v1/integrations/quickbooks/reconcile` | Trigger AR/AP reconciliation pull (202) | `setting:manage` |

> Implementation of the actual QBO calls uses the environment's QuickBooks connector; those
> connector tools require an authorized connection and are invoked only by
> `QuickBooksSyncService`. This document defines the boundary and contract — not the connector
> wiring.

---

## 6. OpenAPI Docs & Versioning Policy

### 6.1 OpenAPI

- FastAPI generates the **OpenAPI 3.1** schema automatically from Pydantic v2 DTOs. Served at
  `/api/v1/openapi.json`, with interactive docs at `/api/v1/docs` (Swagger UI) and
  `/api/v1/redoc`. Non-prod only by default; prod behind auth.
- Every route declares its `response_model`, status codes, and the required `permission` (surfaced
  in the OpenAPI description via a custom `x-required-permission` extension) so the contract and
  the authZ guard never drift.
- The error envelope (§1.5) is a shared component schema (`ErrorResponse`) referenced by every
  4xx/5xx response. The pagination envelope (§1.2) is `Page<T>` via a generic component.
- DTOs are the single source: `XxxCreate`/`XxxUpdate`/`XxxRead` schemas appear verbatim in the
  spec; the frontend generates TypeScript `XxxDTO` types + Zod schemas from `openapi.json`.

### 6.2 Versioning policy

- **URI versioning** at the major level only: `/api/v1`, later `/api/v2`. The path version is the
  sole version signal (no header/media-type versioning).
- **Backward-compatible changes** (new optional field, new endpoint, new enum value from a
  data-driven master, new optional query param) ship within `v1` — clients must tolerate unknown
  fields.
- **Breaking changes** (removing/renaming a field, changing a type, tightening validation,
  changing an error `code`'s meaning) require `/api/v2`. `v1` and `v2` run in parallel.
- **Deprecation window:** a deprecated version/endpoint returns a `Deprecation` header and a
  `Sunset` date; minimum 6-month overlap before removal. Deprecations are recorded in
  `20-decisions-log.md` (ADR).
- **Additive-first discipline:** because nouns are data-driven (D2), new `*_type` values,
  categories, warehouses, etc. are runtime data — they never require an API version bump.

---

## 7. Conformance checklist

- [ ] Every path is `/api/v1` + plural `kebab-case` resource named for a canonical entity (§6).
- [ ] Path keys are UUID v7; human codes are attributes/filters (D6).
- [ ] All money fields are `_minor` integers + `currency` (D5).
- [ ] Ledger resources (`fulfillments`, `invoices`, `payments`, allocations, `bills`,
      `goods-receipts`, `stock-movements`) expose no PUT/PATCH; corrections are new records (D3).
- [ ] Ledger-writing POSTs require an `Idempotency-Key` (§1.4).
- [ ] Every route calls `AuthorizationService.require(<permission>)`; Clerk verified server-side (D8).
- [ ] Every mutation writes one `activity_log` row in-transaction (D10).
- [ ] Every operational list is BU- and permission-scoped (D1).
- [ ] Errors use the shared envelope; codes are stable strings (§1.5).
- [ ] QBO bridge is Finance-only, feature-flagged, non-blocking, idempotent (§5).

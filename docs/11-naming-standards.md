# ApexOS — Naming Standards

> **Status:** Approved · **Owner:** Architecture · **Version:** 1.0 · **Date:** 2026-07-19
>
> This document **extends** `00-canonical-foundation.md` §6. It does not contradict it.
> Where a rule here is more specific than the foundation, follow it; where they conflict,
> the foundation wins. Every example uses real Apex constructs from the domain glossary (§4).

---

## 1. Database Objects

Foundation §6: `snake_case`, singular tables, `id` PK (UUID v7), FKs `<entity>_id`, money
`_minor`, booleans `is_*`/`has_*`, timestamps `*_at`, enum-likes in `*_type` tables.

| Object | Convention | DO | DON'T |
|--------|-----------|----|-------|
| Table | singular, `snake_case` | `sales_order`, `product`, `stock_movement` | `SalesOrders`, `products`, `tblProduct` |
| Junction table | `<a>_<b>` alphabetical | `role_permission`, `user_role` | `permission_role`, `RolePerms` |
| Primary key | `id` (UUID v7) | `id` | `sales_order_id` (as PK), `pk`, `uuid` |
| Foreign key | `<referenced_table>_id` | `customer_id`, `business_unit_id` | `customer`, `fk_customer`, `cust` |
| Money column | `<name>_minor` (integer paise) | `unit_price_minor`, `total_minor` | `price`, `amount`, `price_inr` (float) |
| Currency | `currency` (char(3), default `INR`) | `currency` | `curr`, `ccy` |
| Boolean | `is_*` / `has_*` | `is_active`, `has_credit_hold` | `active`, `deleted`, `flag_active` |
| Timestamp | `*_at` (`timestamptz`, UTC) | `created_at`, `fulfilled_at` | `create_date`, `timestamp`, `dt` |
| Actor column | `*_by` (UUID → user) | `created_by`, `updated_by` | `creator`, `user` |
| Quantity delta | `qty_delta` (signed) | `qty_delta` | `quantity`, `qty_change` |
| Enum-like value | row in `*_type` master table | `customer_type`, `supplier_type` | Postgres `ENUM`, free-text string |
| Truly-fixed enum | inline, documented | `payment.direction` (`in`\|`out`) | over-engineering it into a table |
| Index | `ix_<table>_<cols>` | `ix_sales_order_order_no` | `idx1`, `sales_order_index` |
| Unique constraint | `uq_<table>_<cols>` | `uq_product_sku_code` | `unique_sku` |

Every table carries the D7 audit set: `created_at, created_by, updated_at, updated_by,
deleted_at`. Operational tables also carry `business_unit_id` (D1).

---

## 2. Python (backend)

Foundation §6: modules `snake_case`; classes `PascalCase`; funcs/vars `snake_case`;
Pydantic `Create`/`Update`/`Read`; services `XxxService`; repos `XxxRepository`.

### 2.1 Modules & files

| Item | DO | DON'T |
|------|----|-------|
| Module package | `app/modules/sales_order/` | `salesOrder/`, `sales-order/`, `SalesOrder/` |
| File names | `router.py`, `service.py`, `repository.py`, `models.py`, `schemas.py` | `SalesOrderService.py`, `ctrl.py`, `db.py` |

### 2.2 Classes, services, repositories

```python
# models.py — ORM class = singular PascalCase, table = singular snake_case
class SalesOrder(Base):
    __tablename__ = "sales_order"

class SalesOrderLine(Base):
    __tablename__ = "sales_order_line"

# service.py
class SalesOrderService: ...        # DO      DON'T: SalesOrderManager, SalesOrderLogic, SOService

# repository.py
class SalesOrderRepository: ...     # DO      DON'T: SalesOrderRepo, SalesOrderDAO, SalesOrderStore
```

Method names are verbs, `snake_case`, intent-revealing:

```python
# repository (data verbs)              # service (business verbs)
def add(order): ...                    def create_order(payload, actor): ...
def get(id): ...                       def place_order(...): ...
def list_by_business_unit(bu_id): ...  def cancel_order(id, reason): ...
def next_order_no(bu_id): ...          def recompute_totals(order): ...
```

DON'T: `getOrder`, `fetchData`, `doStuff`, `handle`, `process` (vague).

### 2.3 Pydantic v2 schemas

One base per entity, three role suffixes. Never reuse a `Create` schema as a response.

```python
class SalesOrderBase(BaseModel):        # shared fields
    customer_id: UUID
    business_unit_id: UUID

class SalesOrderCreate(SalesOrderBase):  # request in — no id, no server fields
    lines: list[SalesOrderLineCreate]

class SalesOrderUpdate(BaseModel):       # partial — all optional
    status: SalesOrderStatus | None = None

class SalesOrderRead(SalesOrderBase):    # response out — includes id, order_no, totals
    id: UUID
    order_no: str
    total_minor: int
    created_at: datetime
```

DON'T: `SalesOrderSchema`, `SalesOrderDTO`, `SalesOrderIn`/`SalesOrderOut`, `SalesOrderModel`
(collides with ORM). DON'T expose money as float — `total_minor: int`.

---

## 3. TypeScript / React (frontend)

Foundation §6: components `PascalCase`; hooks `useXxx`; component files `PascalCase.tsx`,
other files `kebab-case.ts`; Zod schemas `xxxSchema`; types `XxxDTO`.

| Item | DO | DON'T |
|------|----|-------|
| Component | `SalesOrderTable`, `SalesOrderForm` | `salesOrderTable`, `SOTable`, `Table1` |
| Component file | `SalesOrderTable.tsx` | `sales-order-table.tsx`, `salesOrderTable.tsx` |
| Hook | `useSalesOrders`, `useCreateSalesOrder` | `salesOrdersHook`, `getSalesOrders` |
| Hook file | `use-sales-orders.ts` | `useSalesOrders.ts`, `hooks.ts` |
| Utility file | `sales-order-api.ts`, `format.ts` | `salesOrderApi.ts`, `Format.ts` |
| Zod schema | `salesOrderCreateSchema` | `SalesOrderSchema`, `salesOrderValidator` |
| Inferred input type | `SalesOrderCreateInput` (from Zod) | `SalesOrderForm`, `ISalesOrder` |
| DTO type | `SalesOrderReadDTO` (generated) | `SalesOrder` (ambiguous), `SalesOrderType` |
| Event handler | `onSubmit`, `handleRowClick` | `submitit`, `clicked`, `doSubmit` |
| Boolean prop | `isLoading`, `hasError` | `loading` (ok as native), `flag` |

```ts
// schema/sales-order-schema.ts
export const salesOrderCreateSchema = z.object({ /* ... */ });
export type SalesOrderCreateInput = z.infer<typeof salesOrderCreateSchema>;

// DTO types are generated from the backend OpenAPI, never hand-written:
import type { SalesOrderReadDTO } from "@apexos/types";
```

DON'T prefix interfaces with `I` (`ISalesOrder`). DON'T suffix everything `Type`. DON'T
hand-author response DTOs — import from `@apexos/types`.

---

## 4. API Routes

Foundation §6: REST, plural resources, `kebab-case`, versioned `/api/v1`.

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/v1/sales-orders` | List |
| `POST` | `/api/v1/sales-orders` | Create |
| `GET` | `/api/v1/sales-orders/{sales_order_id}` | Read one |
| `PATCH` | `/api/v1/sales-orders/{sales_order_id}` | Partial update |
| `POST` | `/api/v1/sales-orders/{sales_order_id}/fulfillments` | Sub-resource action |
| `GET` | `/api/v1/purchase-orders`, `/api/v1/products`, `/api/v1/customers` | Other resources |

DO: plural nouns, kebab-case, nest sub-resources under parents, path params `snake_case`
matching the FK name. DON'T: `/api/v1/getSalesOrders`, `/api/v1/salesOrder`, `/sales_orders`,
verbs in paths (`/create-order`), unversioned paths. Actions that aren't CRUD are POSTs to a
sub-resource or a `:verb` suffix (`/sales-orders/{id}:cancel`) — sparingly.

---

## 5. Event Names

Domain events (D10, written to `activity_log`) are `entity.past_tense_verb`, dot-namespaced,
`snake_case` segments.

| DO | DON'T |
|----|-------|
| `sales_order.created` | `SalesOrderCreated`, `create_sales_order`, `NEW_ORDER` |
| `sales_order.fulfilled` | `order.fulfill`, `fulfillmentEvent` |
| `invoice.issued` | `invoicing`, `inv_done` |
| `stock.moved` | `stockMovement`, `inventory_change` |
| `payment.received` | `paid`, `payment` |

Defined as constants in the module's `events.py`:
`SALES_ORDER_CREATED = "sales_order.created"`.

---

## 6. Git Branches & Commits (Conventional Commits)

### 6.1 Branches

`<type>/<short-kebab-summary>` — optionally `<type>/<ticket>-<summary>`.

| DO | DON'T |
|----|-------|
| `feat/sales-order-create` | `feature_SalesOrder`, `tushar-branch` |
| `fix/invoice-rounding` | `bugfix`, `patch-1` |
| `chore/bump-pydantic` | `misc`, `wip` |
| `feat/APX-142-credit-policy` | `142`, `new-stuff` |

### 6.2 Commits — Conventional Commits

`<type>(<scope>): <subject>` — imperative, lower-case, no trailing period, ≤ 72 chars.

**Types:** `feat`, `fix`, `refactor`, `chore`, `docs`, `test`, `perf`, `build`, `ci`.
**Scope:** the module/feature (`sales-order`, `product`, `db`).

```
feat(sales-order): allocate SO number and compute line totals
fix(invoice): round GST per line before summing
refactor(repository): extract next_order_no into shared sequence helper
test(sales-order): cover credit-hold rejection path
docs(naming): add event-name examples
```

Breaking changes: `feat(api)!: …` + `BREAKING CHANGE:` footer. DON'T: `update`, `fixes`,
`wip`, `asdf`, `final commit`, mixed-concern commits.

---

## 7. Codes & Sequence Formats

Foundation §6/§4: SKU `BRAND-CAT-SEQ`; documents `SO-/PO-/INV-YYYYMM-#####`.

### 7.1 SKU — `BRAND-CAT-SEQ`

- `BRAND` = 3-letter brand code (`AUR` Aura, `APX` Apex).
- `CAT` = 2–3-letter category code (`TIS` Tissue & Paper, `GB` Garbage Bags).
- `SEQ` = zero-padded 3-digit sequence within brand+category.

| DO | DON'T |
|----|-------|
| `AUR-TIS-001` (Aura Toilet Roll) | `aur-tis-1`, `AURTIS001`, `AUR_TIS_001` |
| `APX-GB-001` (Apex Black Garbage Bag 19x21) | `APX-GARBAGE-1`, `1001` |

Uppercase, hyphen-delimited, fixed-width sequence. Brand & category codes come from the
`brand`/`category` master tables, not invented ad hoc.

### 7.2 Document numbers — `<PREFIX>-YYYYMM-#####`

Zero-padded 5-digit sequence, **per Business Unit**, reset monthly.

| Prefix | Example | Entity |
|--------|---------|--------|
| `SO-` | `SO-202607-00042` | Sales Order |
| `PO-` | `PO-202607-00017` | Purchase Order |
| `INV-` | `INV-202607-00042` | Invoice |
| `BILL-` | `BILL-202607-00009` | Bill (supplier) |
| `GRN-` | `GRN-202607-00011` | Goods Receipt |

DO: uppercase prefix, `YYYYMM` (not `YY` or `YYYY-MM`), 5-digit zero pad, allocate inside the
creating transaction. DON'T: `so-2607-42`, `SO/2026/42`, sequences shared across BUs, or
gaps treated as errors (gaps are acceptable; uniqueness is mandatory).

---

## 8. Quick Reference Card

| Layer | Case | Example |
|-------|------|---------|
| DB table/column | `snake_case` singular | `sales_order.total_minor` |
| Python class | `PascalCase` | `SalesOrderService` |
| Python func/var/file | `snake_case` | `next_order_no`, `service.py` |
| Pydantic schema | `PascalCase` + role suffix | `SalesOrderCreate` |
| React component | `PascalCase` (`.tsx`) | `SalesOrderTable.tsx` |
| Hook | `useXxx` (`kebab-case.ts`) | `use-sales-orders.ts` |
| Zod schema | `xxxSchema` | `salesOrderCreateSchema` |
| TS DTO type | `XxxDTO` / `XxxInput` | `SalesOrderReadDTO` |
| API path | plural `kebab-case`, `/v1` | `/api/v1/sales-orders` |
| Event | `entity.past_verb` | `sales_order.created` |
| Branch | `type/kebab` | `feat/sales-order-create` |
| Commit | `type(scope): subject` | `feat(sales-order): …` |
| SKU | `BRAND-CAT-SEQ` | `AUR-TIS-001` |
| Doc no. | `PREFIX-YYYYMM-#####` | `SO-202607-00042` |

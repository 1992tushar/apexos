# ApexOS — User Roles & Permissions (RBAC)

> **Status:** Approved · **Owner:** Security + Ops · **Version:** 1.0 · **Date:** 2026-07-19
>
> Conforms to `00-canonical-foundation.md`. Auth is Clerk (D8), wrapped behind our own
> `user` / `role` / `permission` / `role_permission` / `user_role` tables so **we own
> authorization**. Single-tenant (D1); `business_unit` is a first-class scoping dimension.
> Every access decision is recorded per D10 in `activity_log`.

---

## 1. Model

RBAC = **who** (`user`) has **which roles** (`user_role`), each role grants **permissions**
(`role_permission` → `permission`). Permissions are the only thing code checks. Roles are a
convenience grouping; they carry no logic of their own.

```
user ──< user_role >── role ──< role_permission >── permission
              │
       (optional business_unit_id scope)
```

**Canonical tables (from foundation §5):**

| Table | Purpose | Key columns (beyond D7 audit) |
|---|---|---|
| `user` | Internal team member. 1:1 with a Clerk user via `clerk_user_id`. | `clerk_user_id` (unique), `email`, `full_name`, `is_active`, `default_business_unit_id` |
| `role` | Named permission bundle. | `code` (unique, e.g. `ops_manager`), `name`, `is_system` |
| `permission` | Atomic capability as `resource.action`. | `code` (unique), `module`, `resource`, `action`, `description` |
| `role_permission` | Role → permission grants. | `role_id`, `permission_id` |
| `user_role` | User → role, optionally scoped to a BU. | `user_id`, `role_id`, `business_unit_id` (nullable = all BUs) |

**Rules**

- A permission code is immutable once shipped (it is referenced in code). New capability = new code.
- `role.is_system = true` roles (Founder/Admin, Read-only/Auditor) cannot be deleted; their grants
  are seeded by migration, editable only by a Founder/Admin.
- A user with **no** active `user_role` has **zero** access (deny by default).
- `user_role.business_unit_id = NULL` means the role applies across **all** business units.
  A non-null value scopes every permission granted by that role to that one BU.
- Effective permissions = union of all permissions from all of a user's active roles.
  **Deny never appears** — absence of a grant is the deny. There are no negative permissions.

---

## 2. Roles

| Role `code` | Name | Purpose | System? |
|---|---|---|---|
| `founder_admin` | Founder / Admin | Full control incl. settings, users, roles, approvals of any threshold. | ✅ |
| `ops_manager` | Ops Manager | Runs day-to-day across Sales/Procurement/Inventory for their BU(s); mid-tier approvals. | |
| `sales_rep` | Sales Rep | Creates customers, quotes, sales orders; requests discounts above their limit. | |
| `procurement_officer` | Procurement Officer | Manages suppliers, purchase orders, goods receipts, buy prices. | |
| `warehouse_operator` | Warehouse Operator | Executes fulfillment and goods receipt; records stock movements. | |
| `finance_accounts` | Finance / Accounts | Invoices, bills, payments, credit policy, GST/tax, QuickBooks bridge. | |
| `auditor` | Read-only / Auditor | Read everything, including `activity_log`; change nothing. | ✅ |

Users may hold **multiple** roles (e.g. an Ops Manager who is also a Sales Rep). Permissions
union. BU scoping is per `user_role` row, so one person can be Ops Manager for BU-A only.

---

## 3. Permission Catalogue (`resource.action`, grouped by module)

Naming: `resource.action`, both `snake_case`. Actions are a small closed set —
`view, create, update, delete, export, approve, issue, void, post, receive, adjust, manage`.
`manage` is a coarse admin grant used only in Settings/Identity.

### Platform & Identity
- `user.view` · `user.create` · `user.update` · `user.deactivate`
- `role.view` · `role.manage`
- `permission.view`
- `setting.view` · `setting.manage`
- `activity_log.view`
- `business_unit.view` · `business_unit.manage`

### Products & Config
- `product.view` · `product.create` · `product.update` · `product.delete` · `product.export`
- `category.view` · `category.manage`
- `brand.view` · `brand.manage`
- `uom.view` · `uom.manage`
- `procurement_model.view` · `procurement_model.manage`
- `tax_rate.view` · `tax_rate.manage`

### Customers & CRM
- `customer.view` · `customer.create` · `customer.update` · `customer.delete` · `customer.export`
- `customer_credit_policy.view` · `customer_credit_policy.update` · `customer_credit_policy.approve`
- `lead.view` · `lead.create` · `lead.update`
- `opportunity.view` · `opportunity.create` · `opportunity.update`
- `competitor.view` · `competitor.manage`

### Pricing
- `selling_price.view` · `selling_price.create` · `selling_price.update` · `selling_price.approve`
- `purchase_price.view` · `purchase_price.create` · `purchase_price.update`
- `margin.view`

### Sales
- `sales_order.view` · `sales_order.create` · `sales_order.update` · `sales_order.approve` · `sales_order.void`
- `sales_order.discount_approve` *(threshold-gated, see §5)*
- `fulfillment.view` · `fulfillment.create` *(picks/ships → stock-out)*

### Procurement
- `supplier.view` · `supplier.create` · `supplier.update` · `supplier.delete`
- `supplier_evaluation.view` · `supplier_evaluation.create` · `supplier_evaluation.update`
- `purchase_order.view` · `purchase_order.create` · `purchase_order.update` · `purchase_order.approve` · `purchase_order.void`
- `goods_receipt.view` · `goods_receipt.create`

### Inventory
- `warehouse.view` · `warehouse.manage`
- `stock_movement.view` · `stock_movement.adjust` *(manual correction; always logged)*
- `stock_balance.view`

### Finance
- `invoice.view` · `invoice.create` · `invoice.issue` · `invoice.void` · `invoice.export`
- `bill.view` · `bill.create` · `bill.post` · `bill.void`
- `payment.view` · `payment.create` *(record in/out)* · `payment.approve`
- `payment_allocation.view` · `payment_allocation.create`
- `receivable.view` · `payable.view`
- `tax_line.view` · `finance.export`
- `quickbooks.sync` *(QBO bridge, D8/foundation §3)*

### Platform Work Surfaces
- `task.view` · `task.create` · `task.update`
- `document.view` · `document.upload` · `document.delete`
- `notification.view`
- `dashboard.view` · `report.view` · `report.export`

---

## 4. Role × Permission Matrix

Legend: **F** Founder/Admin · **O** Ops Manager · **S** Sales Rep · **P** Procurement Officer ·
**W** Warehouse Operator · **A** Finance/Accounts · **R** Read-only/Auditor.
`●` full · `○` view-only implied by module column · `+` gated by threshold (§5). Blank = no access.

| Permission group | F | O | S | P | W | A | R |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| Users / Roles / Settings (`user.*`, `role.*`, `setting.*`, `business_unit.manage`) | ● | | | | | | |
| `activity_log.view` | ● | ● | | | | ● | ● |
| Products (`product.*`) | ● | ● | ○ | ○ | ○ | ○ | ○ |
| Config masters (`category/brand/uom/procurement_model/tax_rate.manage`) | ● | ● | | | | ○ (tax) | ○ |
| Customers (`customer.*`) | ● | ● | ● | ○ | | ○ | ○ |
| Credit policy (`customer_credit_policy.*`) | ● | ●+ | ○ | | | ● | ○ |
| CRM (`lead/opportunity/competitor.*`) | ● | ● | ● | | | | ○ |
| Selling price (`selling_price.*`) | ● | ●+ | ○ create/update | | | ○ | ○ |
| Purchase price (`purchase_price.*`) | ● | ● | | ● | | ○ | ○ |
| `margin.view` | ● | ● | | ● | | ● | ● |
| Sales orders (`sales_order.*`) | ● | ● approve+ | ● create/update | ○ | ○ | ○ | ○ |
| `sales_order.discount_approve` | ● | ●+ | | | | | |
| Fulfillment (`fulfillment.*`) | ● | ● | ○ | | ● | ○ | ○ |
| Suppliers (`supplier.*`, `supplier_evaluation.*`) | ● | ● | | ● | ○ | ○ | ○ |
| Purchase orders (`purchase_order.*`) | ● | ● approve+ | | ● create/update | ○ | ○ | ○ |
| Goods receipt (`goods_receipt.*`) | ● | ● | | ● | ● | ○ | ○ |
| Warehouses (`warehouse.*`) | ● | ● | | | ○ | | ○ |
| Stock (`stock_movement.adjust`, `stock_balance.view`) | ● | ● | ○ | ○ | ● adjust | ○ | ○ |
| Invoices (`invoice.*`) | ● | ○ | ○ | | | ● | ○ |
| Bills (`bill.*`) | ● | ○ | | ○ | | ● | ○ |
| Payments (`payment.*`, `payment_allocation.*`) | ● | ○ | | | | ● approve+ | ○ |
| Receivable/Payable/Tax/`finance.export` | ● | ○ | | | | ● | ○ |
| `quickbooks.sync` | ● | | | | | ● | |
| Tasks / Documents / Notifications | ● | ● | ● | ● | ● | ● | ○ |
| Dashboard / Reports (`report.export`) | ● | ● | ● (own) | ● (own) | ○ | ● | ○ export |

> The matrix is the human-readable spec. The **executable** source of truth is the seed
> migration `seed_roles_permissions.py`, which must match this table cell-for-cell. CI diff-checks
> the two (see `15-deployment-strategy.md`).

---

## 5. Approval-Authority Thresholds

Some actions are permitted only up to a monetary/percentage ceiling. The permission grants the
*right to act*; the **threshold** (a `setting` row per BU) decides whether the actor may
**self-approve** or must **escalate**. Thresholds are money in minor units (paise, D5) or percent.

| Setting key | Sales Rep | Ops Manager | Founder/Admin |
|---|---|---|---|
| `approval.discount_pct.max` | ≤ 5% | ≤ 15% | unlimited |
| `approval.sales_order.value_minor.max` | ≤ ₹50,000 | ≤ ₹5,00,000 | unlimited |
| `approval.credit_limit.value_minor.max` | — | ≤ ₹2,00,000 | unlimited |
| `approval.purchase_order.value_minor.max` | — | ≤ ₹5,00,000 | unlimited |
| `approval.payment_out.value_minor.max` | — | — (Finance ≤ ₹1,00,000) | unlimited |

**Mechanics**

1. Actor submits an action (e.g. Sales Rep applies 8% discount).
2. Service computes the required approval tier from the value vs. the BU's `setting` thresholds.
3. If the actor's roles satisfy the tier → auto-approved, `activity_log` records `self_approved`.
4. Else the record enters `pending_approval`; a `task` + `notification` is raised to the lowest
   role that holds the needed `*.approve` (or `*.discount_approve`) permission **and** clears the
   threshold. Approver's decision is logged with before/after.
5. Thresholds are data (`setting`), not code (D2) — editable in Settings by Founder/Admin only.

---

## 6. Business-Unit Scoping

- Every operational query is filtered by the caller's **BU scope** = set of `business_unit_id`
  across their active `user_role` rows (`NULL` row ⇒ all BUs).
- Enforced in the **repository layer** (single choke point), not per-endpoint, so it cannot be
  forgotten. `XxxRepository` methods take a `bu_scope` and add `WHERE business_unit_id = ANY(:scope)`.
- Config/master tables that are BU-owned (`category`) inherit the same filter; global masters
  (`uom`, `tax_rate`) are unscoped-readable.
- Cross-BU reporting requires an unscoped role (Founder/Admin, Auditor, or a BU-null grant).

---

## 7. Enforcement — API + UI Gating

**Authoritative check is server-side. UI gating is convenience only.**

**Backend (FastAPI):**
- A `require(*permission_codes)` dependency resolves the Clerk session → `user` → effective
  permissions (cached per request) and rejects with `403` if any required code is missing.
- BU scope is injected into the repository layer as in §6.
- Threshold checks live in the **service layer** (§5), never in the route.
- Every allow/deny on a state-changing route writes to `activity_log` (D10).

```python
@router.post("/sales-orders")
async def create_sales_order(
    body: SalesOrderCreate,
    ctx: AuthContext = Depends(require("sales_order.create")),
):
    return await sales_service.create(body, ctx)   # service applies §5 thresholds + BU scope
```

**Frontend (Next.js):**
- Server components fetch the user's effective permission set once (from `/api/v1/me`) and expose
  a `can(code)` helper + `<Can perm="...">` guard.
- Nav items, buttons, and route segments hide/disable on missing permission — **purely cosmetic**.
- The API re-checks every call; a hidden button that is called directly still returns `403`.

**Failure semantics:** unknown permission code in code = deploy-blocking CI error (it must exist
in the seed). Missing grant at runtime = `403` + audit entry, never a silent empty result
(except BU-scope filtering, which legitimately narrows lists).

---

## 8. Lifecycle

- **Onboard:** create Clerk user → webhook creates `user` row (inactive) → Founder/Admin assigns
  `user_role`(s) with BU scope → user becomes active.
- **Offboard:** deactivate in Clerk → webhook sets `user.is_active = false`; roles retained for
  audit (soft, D7). No hard delete of users.
- **Role change:** logged in `activity_log`; effective permissions recomputed on next request
  (no long-lived permission cache beyond a request; Clerk session TTL applies).
- **Break-glass:** only Founder/Admin can grant `founder_admin`; such grants raise a high-priority
  `notification` to all existing admins.

# ApexOS — Feature List

> **Status:** Draft for build · **Owner:** Product · **Version:** 1.0 · **Date:** 2026-07-19
>
> Conforms to `00-canonical-foundation.md` (source of truth). Entity names are canonical (§5);
> sidebar/module order is the foundation Module Map (§7). Where this document and the foundation
> disagree, **the foundation wins.** Cross-checked against `02-information-architecture.md` and
> `08-module-breakdown.md`.

---

## 0. How to read this

Features are grouped by **sidebar module** (Foundation §7). Each feature lists:

- **Description** — one line, what it does for the user.
- **Priority** — **P0** (must-have, no product without it) · **P1** (important, near-term) ·
  **P2** (valuable, later).
- **Phase** — delivery wave from D4 / `08-module-breakdown.md` §5:
  **Phase 1 = Spine** · **Phase 2 = Buy side + widen** · **Phase 3 = Intelligence**.
- **🔵 Spine** — marks a feature that is part of the Phase 1 vertical slice
  `Customer → Product → Sales Order → Fulfillment → Invoice → Receivable → Dashboard tile` (D4).

**Legend:** 🔵 = spine-slice feature · P0/P1/P2 = priority · Phase 1/2/3 = delivery wave.

Rules that bind every feature (from the foundation):

- Money is integer minor units + `currency` (D5); keys are UUID v7 (D6); every table has audit +
  soft-delete columns (D7) and (where operational) `business_unit_id` (D1).
- Financial/stock changes append to ledgers, never mutate balances (D3).
- Every state-changing action writes one `activity_log` row in-transaction (D10).
- Every noun-list (`*_type`, master) is a Settings-managed table, never a hardcoded enum (D2).
- Every screen answers: **What happened? · What needs attention? · What should I do?** (§8).

---

## 1. Dashboard
*(absorbs 00 Dashboard, 18 Finance Dashboard, 19 KPI Dashboard)*

| # | Feature | Description | Priority | Phase | Spine |
|---|---|---|---|---|---|
| 1.1 | Command dashboard | Company-scale home answering the three questions with tiles + feeds | P0 | Phase 1 | 🔵 |
| 1.2 | Spine StatTiles | AR outstanding, GP this period, on-hand value, open orders to fulfill | P0 | Phase 1 | 🔵 |
| 1.3 | Activity feed ("What happened?") | Live stream from `activity_log`, BU- and permission-scoped | P0 | Phase 1 | 🔵 |
| 1.4 | Attention strip ("What needs attention?") | Overdue AR, low stock, credit holds, SOs awaiting fulfillment | P0 | Phase 1 | 🔵 |
| 1.5 | My tasks panel ("What should I do?") | Assigned open `task` items with quick-create | P1 | Phase 2 | |
| 1.6 | Business Unit switcher | Global BU filter across every tile (default "All Units") (D1) | P0 | Phase 1 | 🔵 |
| 1.7 | Period/date-range selector | Scopes tiles and KPIs to a period (this month, quarter, custom) | P0 | Phase 1 | 🔵 |
| 1.8 | Finance dashboard | Cash position, AR/AP aging buckets, margin trend | P1 | Phase 2 | |
| 1.9 | KPI dashboard | GP %, DSO, fill rate, pipeline value, cash — KPI board | P1 | Phase 3 | |
| 1.10 | Quick-create launcher | Keyboard quick-create (new SO, record payment, new customer) | P1 | Phase 2 | |
| 1.11 | Tile drill-through | Click a tile to open the filtered underlying list/report | P1 | Phase 2 | |

---

## 2. Sales
*(16 Sales Pipeline, 09 Selling Price, 10 Margin)*

| # | Feature | Description | Priority | Phase | Spine |
|---|---|---|---|---|---|
| 2.1 | Sales Order list | Filterable TanStack table of `sales_order` with saved views | P0 | Phase 1 | 🔵 |
| 2.2 | Create Sales Order | Customer → lines; prices resolve via `PricingService.resolve()`; assigns `SO-YYYYMM-#####` | P0 | Phase 1 | 🔵 |
| 2.3 | Sales Order line editor | Add/edit `sales_order_line` with qty, UOM, resolved price, live GP% | P0 | Phase 1 | 🔵 |
| 2.4 | Tax preview on order | GST preview via `TaxService.compute()` before confirm | P0 | Phase 1 | 🔵 |
| 2.5 | Confirm Sales Order | Runs `CreditPolicyService.check()`; moves to Confirmed on pass | P0 | Phase 1 | 🔵 |
| 2.6 | Cancel Sales Order | `SalesOrderService.cancel()` with reason, logged | P1 | Phase 1 | 🔵 |
| 2.7 | Sales Order detail | Header (status, customer, total, margin) + Lines/Fulfillment/Invoice/Activity tabs | P0 | Phase 1 | 🔵 |
| 2.8 | Margin / GP per order | `MarginService.gp()` per line and aggregated on the order | P0 | Phase 1 | 🔵 |
| 2.9 | Fulfillment trigger from order | "Fulfill" action hands shipped qty to Fulfillment (see Warehouse) | P0 | Phase 1 | 🔵 |
| 2.10 | Selling price lists | Manage `selling_price` (customer / segment / list) with versioned history (D3) | P1 | Phase 2 | |
| 2.11 | Effective-price resolution view | Show which price won: customer-specific → segment → list | P1 | Phase 2 | |
| 2.12 | Pipeline board | Kanban of `opportunity` by `pipeline_stage` | P2 | Phase 3 | |
| 2.13 | Opportunity detail & advance | `OpportunityService.advance(stage)` with competitor tracking | P2 | Phase 3 | |
| 2.14 | Margin analytics | GP by product/category/customer over time | P2 | Phase 3 | |

---

## 3. Customers
*(11 Customer Segments, 12 Target Customers, 17 Credit Policy, 13 Competitor Tracker)*

| # | Feature | Description | Priority | Phase | Spine |
|---|---|---|---|---|---|
| 3.1 | Customer list | `customer` table segmented by `customer_type`, saved views | P0 | Phase 1 | 🔵 |
| 3.2 | Create/Edit customer | `CustomerService.create/update()`; segment (never hardcoded to restaurants) | P0 | Phase 1 | 🔵 |
| 3.3 | Customer detail | Contacts, addresses, credit policy, orders, receivables, activity | P0 | Phase 1 | 🔵 |
| 3.4 | Customer contacts | Manage `customer_contact` records | P1 | Phase 1 | 🔵 |
| 3.5 | Customer addresses | Manage `customer_address` (billing/shipping) | P1 | Phase 1 | 🔵 |
| 3.6 | Credit policy editor | Set `customer_credit_policy` (limit, payment-term days, status); versioned | P0 | Phase 1 | 🔵 |
| 3.7 | Live credit exposure | `CreditPolicyService.check()` reads derived `receivable` for available credit | P0 | Phase 1 | 🔵 |
| 3.8 | Customer receivables view | Outstanding invoices + aging for one customer | P1 | Phase 2 | |
| 3.9 | Leads list & detail | `lead` (target customers) capture and qualification | P2 | Phase 3 | |
| 3.10 | Lead conversion | `LeadService.convert()` → customer, closing the opportunity | P2 | Phase 3 | |
| 3.11 | Competitor tracker | `competitor` records linked to opportunities | P2 | Phase 3 | |
| 3.12 | Customer type management | Redirect into Settings → Customer Types (`customer_type`) | P1 | Phase 2 | |

---

## 4. Products
*(01 Product Portfolio, 02 Category Master, 03 SKU Master)*

| # | Feature | Description | Priority | Phase | Spine |
|---|---|---|---|---|---|
| 4.1 | Product (SKU) list | `product` master table with category/brand/status filters | P0 | Phase 1 | 🔵 |
| 4.2 | Create product | `ProductService.create()` generates SKU `BRAND-CAT-SEQ` (e.g. `AUR-TIS-001`) | P0 | Phase 1 | 🔵 |
| 4.3 | Product detail | Specs, barcodes, selling & purchase price history, stock across warehouses | P0 | Phase 1 | 🔵 |
| 4.4 | Product status lifecycle | `set_status()` Active/Draft/Discontinued; respects `launch_phase`/priority | P1 | Phase 1 | 🔵 |
| 4.5 | Spec attributes | `product_spec_attribute` key/value ("2 Ply", "19x21", "M Fold") | P1 | Phase 1 | 🔵 |
| 4.6 | Barcodes | Attach `product_barcode` to a product | P2 | Phase 2 | |
| 4.7 | Portfolio view | Products grouped by `category` (portfolio rollup) | P1 | Phase 2 | |
| 4.8 | Launch phase / priority | Surface `launch_phase` + 1–5 priority for rollout planning | P2 | Phase 2 | |
| 4.9 | Selling price on product | Inline view/set of effective `selling_price` for the SKU | P1 | Phase 2 | |

---

## 5. Categories
*(02 Category Master — data-driven noun owned by Org/Config, surfaced in Settings)*

| # | Feature | Description | Priority | Phase | Spine |
|---|---|---|---|---|---|
| 5.1 | Category list | The 9 real categories rolling up to `business_unit` | P0 | Phase 1 | 🔵 |
| 5.2 | Create/reparent category | `CategoryService.create/reparent()` enforcing `→business_unit` rollup | P1 | Phase 1 | 🔵 |
| 5.3 | Category → procurement model | Link `category` to `procurement_model` (Private Label, Master Distributor, …) | P1 | Phase 2 | |
| 5.4 | Brand master | Manage `brand` (Aura, Apex) | P1 | Phase 2 | |
| 5.5 | Procurement model master | Manage `procurement_model` values | P2 | Phase 2 | |
| 5.6 | Category usage count | Show product count per category (soft-delete guard) | P2 | Phase 2 | |

---

## 6. Inventory
*(15 Inventory Master — append-only stock ledger, D3)*

| # | Feature | Description | Priority | Phase | Spine |
|---|---|---|---|---|---|
| 6.1 | Stock balances list | Derived `stock_balance` per product per warehouse (read-only) | P0 | Phase 1 | 🔵 |
| 6.2 | On-hand value tile source | Feeds the Dashboard on-hand value tile | P0 | Phase 1 | 🔵 |
| 6.3 | Movements ledger | `stock_movement` append-only ledger with reason/ref filters | P0 | Phase 1 | 🔵 |
| 6.4 | Post movement (internal) | `InventoryService.record_movement()` — the only writer; IN(+)/OUT(−) | P0 | Phase 1 | 🔵 |
| 6.5 | Product-in-warehouse detail | Movement history, on-hand, incoming/outgoing for one SKU/warehouse | P1 | Phase 2 | |
| 6.6 | Stock adjustment | `StockAdjustmentService.adjust()` with reason (`ADJUSTMENT`, `COUNT`) | P1 | Phase 2 | |
| 6.7 | Low-stock signals | Threshold-based low-stock flags feeding the attention strip | P1 | Phase 2 | |
| 6.8 | Balance projection refresh | `StockBalanceProjection.refresh()` rebuild of derived balances | P1 | Phase 2 | |
| 6.9 | Cycle counts | Count sessions reconciling physical vs ledger | P2 | Phase 3 | |

---

## 7. Warehouse
*(14 Warehouse Master + fulfillment posting)*

| # | Feature | Description | Priority | Phase | Spine |
|---|---|---|---|---|---|
| 7.1 | Warehouse master | Manage `warehouse` locations (Settings-managed noun) | P0 | Phase 1 | 🔵 |
| 7.2 | Fulfillment (ship) | `FulfillmentService.ship()` creates `fulfillment` + lines, posts OUT movement per line (reason `SALE`) | P0 | Phase 1 | 🔵 |
| 7.3 | Fulfillment detail | `fulfillment` + `fulfillment_line` shipped-vs-ordered view | P0 | Phase 1 | 🔵 |
| 7.4 | Partial / short-ship | Ship fewer than ordered; short-ship flagged on order | P1 | Phase 1 | 🔵 |
| 7.5 | Goods receipt posting | `GoodsReceiptService.receive()` posts IN movement (buy side) | P1 | Phase 2 | |
| 7.6 | Multi-warehouse transfers | Move stock between warehouses via paired movements | P2 | Phase 3 | |
| 7.7 | UOM conversion on stock | Case → Pack conversions via `uom_conversion` | P2 | Phase 3 | |

---

## 8. Procurement
*(07 Procurement Strategy, 08 Purchase Price — the buy-side mirror of Sales)*

| # | Feature | Description | Priority | Phase | Spine |
|---|---|---|---|---|---|
| 8.1 | Purchase price management | `PurchasePriceService.set()` per SKU per supplier, versioned (D3) | P1 | Phase 2 | |
| 8.2 | Purchase price history | Timeline of buy prices per product/supplier | P1 | Phase 2 | |
| 8.3 | Procurement strategy view | Category × procurement model sourcing overview | P2 | Phase 3 | |
| 8.4 | Reorder suggestions | Low-stock + lead-time driven reorder hints | P2 | Phase 3 | |
| 8.5 | Buy-price → margin feed | Purchase price feeds `MarginService.gp()` | P1 | Phase 2 | |

---

## 9. Purchase Orders
*(the `PO → Goods Receipt → Bill` chain — mirrors Sales structurally)*

| # | Feature | Description | Priority | Phase | Spine |
|---|---|---|---|---|---|
| 9.1 | Purchase Order list | `purchase_order` table with status/supplier filters | P1 | Phase 2 | |
| 9.2 | Create Purchase Order | `PurchaseOrderService.create()`; snapshots `purchase_price` onto lines; `PO-YYYYMM-#####` | P1 | Phase 2 | |
| 9.3 | PO line editor | Add/edit `purchase_order_line` with qty, UOM, buy price | P1 | Phase 2 | |
| 9.4 | Confirm Purchase Order | `PurchaseOrderService.confirm()` | P1 | Phase 2 | |
| 9.5 | Purchase Order detail | Lines, goods receipt status, bill tabs | P1 | Phase 2 | |
| 9.6 | Goods receipts | `goods_receipt` + `goods_receipt_line`; partial receipts allowed | P1 | Phase 2 | |
| 9.7 | Receive → stock IN | Receipt posts `stock_movement` IN via `InventoryService` | P1 | Phase 2 | |
| 9.8 | Bill from receipt | `BillService.enter()` hands off to Finance | P1 | Phase 2 | |

---

## 10. Suppliers
*(04 Manufacturer DB, 05 Distributor DB, 06 Vendor Evaluation)*

| # | Feature | Description | Priority | Phase | Spine |
|---|---|---|---|---|---|
| 10.1 | Supplier list | `supplier` by `supplier_type` (Manufacturer / Distributor) | P1 | Phase 2 | |
| 10.2 | Create/Edit supplier | `SupplierService.create/update()` | P1 | Phase 2 | |
| 10.3 | Supplier detail | Contacts, evaluations, purchase prices, POs | P1 | Phase 2 | |
| 10.4 | Supplier contacts | Manage `supplier_contact` records | P2 | Phase 2 | |
| 10.5 | Vendor evaluation | `VendorEvaluationService.score()` quality/price/reliability scorecard | P1 | Phase 2 | |
| 10.6 | Evaluation history | `supplier_evaluation` timeline per supplier | P2 | Phase 3 | |
| 10.7 | Supplier type management | Redirect into Settings → Supplier Types (`supplier_type`) | P2 | Phase 2 | |

---

## 11. Finance
*(17 Credit Policy, 18 Finance Dashboard — append-only ledgers, QBO bridge)*

| # | Feature | Description | Priority | Phase | Spine |
|---|---|---|---|---|---|
| 11.1 | Issue invoice | `InvoiceService.issue()` freezes fulfilled qty, `INV-YYYYMM-#####`, computes `tax_line` | P0 | Phase 1 | 🔵 |
| 11.2 | Invoice list | `invoice` ledger with status/customer filters (no edit — D3) | P0 | Phase 1 | 🔵 |
| 11.3 | Invoice detail | Lines, tax, allocations, linked sales order | P0 | Phase 1 | 🔵 |
| 11.4 | Record payment (IN) | `PaymentService.record(in, …)` appends `payment` | P0 | Phase 1 | 🔵 |
| 11.5 | Allocate payment | `PaymentAllocationService.allocate()` links cash to invoice; over-allocation guard | P0 | Phase 1 | 🔵 |
| 11.6 | Receivable projection | `ReceivableProjection.for(customer)` — derived (invoice − allocations) | P0 | Phase 1 | 🔵 |
| 11.7 | Tax computation (GST) | `TaxService.compute()` using `tax_rate` slabs, GST-aware from day one | P0 | Phase 1 | 🔵 |
| 11.8 | Receivables aging | AR aging buckets across customers | P1 | Phase 2 | |
| 11.9 | Issue bill | `BillService.issue()` supplier-side mirror from goods receipt | P1 | Phase 2 | |
| 11.10 | Bills list & detail | `bill` + `bill_line` ledger | P1 | Phase 2 | |
| 11.11 | Record payment (OUT) | `payment` direction out for supplier bills | P1 | Phase 2 | |
| 11.12 | Payable projection | `PayableProjection.for(supplier)` — derived (bill − allocations) | P1 | Phase 2 | |
| 11.13 | Payables aging | AP aging buckets across suppliers | P1 | Phase 2 | |
| 11.14 | QuickBooks Online bridge | `QuickBooksSyncService.push_invoice/bill/payment()` — feature-flagged, non-blocking (see `09-api-architecture.md` §QBO) | P1 | Phase 2 | |
| 11.15 | Credit note / void | Ledger corrections via new documents, never edits (D3) | P2 | Phase 3 | |

---

## 12. Reports
*(19 KPI Dashboard — read-only projections)*

| # | Feature | Description | Priority | Phase | Spine |
|---|---|---|---|---|---|
| 12.1 | Report catalog | Catalog of standard reports (Margin, GP by category, Fill rate, AR aging, Supplier scorecard) | P1 | Phase 2 | |
| 12.2 | Report canvas + filters | `ReportService.run()` tabular report with BU + date filters | P1 | Phase 2 | |
| 12.3 | CSV export | Export any report/list to CSV over the ledgers | P1 | Phase 2 | |
| 12.4 | Saved report definitions | Save report/filter combinations as reusable views | P2 | Phase 3 | |
| 12.5 | AR / AP aging reports | Aging detail + summary (mirrors QBO aging reports) | P1 | Phase 2 | |

---

## 13. Analytics
*(19 KPI Dashboard — derived KPIs)*

| # | Feature | Description | Priority | Phase | Spine |
|---|---|---|---|---|---|
| 13.1 | KPI compute engine | `KpiService.compute(kpi, period)` — margin, DSO, fill-rate | P1 | Phase 3 | |
| 13.2 | GP % trend | Gross-profit percentage over time, by BU/category | P1 | Phase 3 | |
| 13.3 | Fill rate | Fulfilled vs ordered quantity ratio | P2 | Phase 3 | |
| 13.4 | Pipeline value | Weighted `opportunity` value by stage | P2 | Phase 3 | |
| 13.5 | Sales by customer / product | Aggregations (mirrors QBO sales summaries) | P2 | Phase 3 | |
| 13.6 | Cash position | Derived cash view from `payment` ledger | P2 | Phase 3 | |

---

## 14. Tasks
*(part of the Platform module)*

| # | Feature | Description | Priority | Phase | Spine |
|---|---|---|---|---|---|
| 14.1 | Task list | `task` list with assignee/status/due filters | P1 | Phase 2 | |
| 14.2 | Create/complete task | `TaskService.create/complete()` | P1 | Phase 2 | |
| 14.3 | Polymorphic entity link | Link a task to any entity (`entity_type`/`entity_id`) | P1 | Phase 2 | |
| 14.4 | My tasks on dashboard | Feeds the "What should I do?" panel | P1 | Phase 2 | |
| 14.5 | Notifications | `NotificationService.push()` for assignments/alerts | P2 | Phase 3 | |

---

## 15. Documents
*(part of the Platform module — Cloudflare R2)*

| # | Feature | Description | Priority | Phase | Spine |
|---|---|---|---|---|---|
| 15.1 | Document upload | `DocumentService.upload()` to R2 with metadata | P1 | Phase 2 | |
| 15.2 | Polymorphic entity link | Attach a document to any entity | P1 | Phase 2 | |
| 15.3 | Document list & detail | Browse/preview stored `document` records | P1 | Phase 2 | |
| 15.4 | Per-record Documents tab | Documents surfaced on any entity detail screen | P2 | Phase 2 | |

---

## 16. Settings
*(20 Decisions Log, 21 Roadmap, 22 SOP Index + all data-driven nouns and access)*

| # | Feature | Description | Priority | Phase | Spine |
|---|---|---|---|---|---|
| 16.1 | Business Units | Manage `business_unit` (first-class dimension, D1) | P0 | Phase 1 | 🔵 |
| 16.2 | Brands | Manage `brand` master | P1 | Phase 1 | 🔵 |
| 16.3 | Categories | Manage `category` (→business_unit, →procurement_model) | P0 | Phase 1 | 🔵 |
| 16.4 | Procurement Models | Manage `procurement_model` values | P1 | Phase 2 | |
| 16.5 | Units of Measure | Manage `uom` + `uom_conversion` | P1 | Phase 1 | 🔵 |
| 16.6 | Warehouses | Manage `warehouse` master | P0 | Phase 1 | 🔵 |
| 16.7 | Customer Types | Manage `customer_type` (add a market vertical = one row, no code) | P0 | Phase 1 | 🔵 |
| 16.8 | Supplier Types | Manage `supplier_type` | P1 | Phase 2 | |
| 16.9 | Tax Rates (GST) | Manage `tax_rate` slabs, versioned | P0 | Phase 1 | 🔵 |
| 16.10 | QuickBooks Connector | `setting`-backed QBO connector config (Finance bridge) | P1 | Phase 2 | |
| 16.11 | Pipeline Stages | Manage `pipeline_stage` | P2 | Phase 3 | |
| 16.12 | Users & roles | Manage `user`, `user_role` (Clerk-synced); `RoleService.assign/revoke()` | P0 | Phase 1 | 🔵 |
| 16.13 | Roles & permissions | Manage `role`, `role_permission`, `permission` | P0 | Phase 1 | 🔵 |
| 16.14 | Preferences | Free-form `setting` key/values via `SettingService.get/set()` | P1 | Phase 2 | |
| 16.15 | Decisions Log (ADRs) | Manage `decision_log` entries | P2 | Phase 2 | |
| 16.16 | SOP Index | Manage `sop` index | P2 | Phase 3 | |
| 16.17 | Type-list screen pattern | Uniform master editor (name, code, usage count, active toggle, reorder) | P1 | Phase 2 | |

---

## 17. Cross-cutting features (span all modules)

| # | Feature | Description | Priority | Phase | Spine |
|---|---|---|---|---|---|
| X.1 | Command palette (⌘K) | Navigate / find-record / run-action, BU- and permission-scoped | P0 | Phase 1 | 🔵 |
| X.2 | Global BU switcher | `?bu=<id>` scope on every operational screen (D1) | P0 | Phase 1 | 🔵 |
| X.3 | Saved views | List filters serialize to shareable URLs | P1 | Phase 2 | |
| X.4 | Activity tab everywhere | Per-record `activity_log` timeline on every detail screen (D10) | P0 | Phase 1 | 🔵 |
| X.5 | Dark mode | Theme-aware UI, blue primary + status colors | P1 | Phase 1 | 🔵 |
| X.6 | Keyboard-first navigation | `g s`, `g c`, `c` quick-create chords | P1 | Phase 2 | |
| X.7 | Permission-gated UI | Actions/routes hidden per resolved `permission` set | P0 | Phase 1 | 🔵 |
| X.8 | Audit & soft-delete | Recoverability + traceability on every entity (D7) | P0 | Phase 1 | 🔵 |

---

## 18. Spine feature summary (D4 — build these first)

The Phase 1 vertical slice, in order, with its defining features:

| Spine node | Defining features |
|---|---|
| **Customer** | 3.1 Customer list · 3.2 Create customer · 3.6 Credit policy · 3.7 Credit exposure |
| **Product** | 4.1 Product list · 4.2 Create product (SKU) · 5.1 Categories · 16.5 UOM |
| **Sales Order** | 2.1 SO list · 2.2 Create SO · 2.3 Line editor · 2.4 Tax preview · 2.5 Confirm (credit gate) · 2.8 Margin |
| **Fulfillment** | 7.1 Warehouse · 7.2 Ship (post OUT movement) · 7.3 Fulfillment detail · 6.3/6.4 Movements ledger |
| **Invoice** | 11.1 Issue invoice · 11.2 Invoice list · 11.7 GST tax compute |
| **Receivable** | 11.4 Record payment IN · 11.5 Allocate · 11.6 Receivable projection |
| **Dashboard tile** | 1.2 Spine StatTiles (AR + GP) · 1.3 Activity feed · 1.6 BU switcher |

Everything after the spine is a **variation of this proven pattern** (Procurement mirrors Sales;
Bill mirrors Invoice; Payable mirrors Receivable; Goods Receipt mirrors Fulfillment).

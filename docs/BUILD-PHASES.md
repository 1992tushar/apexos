# ApexOS — Remaining Build, in 3 Phases

> Phase 1 (the Spine) is **done and E2E-verified**: Dashboard, Sales, Customers, Products,
> Inventory, Finance — the `Customer → Product → SalesOrder → Fulfillment → Invoice → Payment`
> loop. Everything below is the pending work, regrouped into three deliverable phases that respect
> the dependency graph in `08-module-breakdown.md`. Each phase has a self-contained prompt you can
> paste into a fresh Claude Code session.

## Overview

| Phase | Theme | Modules that go live | Why this order |
|---|---|---|---|
| **A** | **Buy side** (mirror of Sales) | Suppliers, Purchase Orders, Procurement (Goods Receipt), Bills/Payables, Purchase Pricing + Margin | The highest-value gap: closes the full trade loop (buy → receive → bill → pay). Structurally mirrors the proven Sales spine. |
| **B** | **Operations & config** | Warehouse (transfers/adjustments/counts), Settings (full config CRUD), Categories, Tasks, Documents | Operational depth + lets you configure the system without code and manage stock properly across warehouses. |
| **C** | **Intelligence & growth** | Reports, Analytics (KPI board), CRM pipeline (leads/opportunities), Notifications, QBO bridge | Read-only projections + pre-sale funnel + external sync. Builds on all data the first two phases produce. |

Build A → B → C. Each phase ends green (migrated, seeded, running, smoke-tested) and updates
`PROGRESS.md`.

---

## PROMPT — Phase A: Buy Side (Procurement mirror)

```
You are continuing ApexOS at c:\Imp Data\Personal\apexos. Read these first: PROGRESS.md,
docs/00-canonical-foundation.md, docs/08-module-breakdown.md (§2.5 Suppliers/Procurement, §2.6
Pricing, §2.9 Finance), docs/07-database-er-diagram.md, docs/09-api-architecture.md,
docs/12-coding-standards.md, docs/17-design-system.md. The Sales module (apps/api/app/modules/sales
+ apps/web/src/features/sales) is your reference pattern — Procurement mirrors it exactly.

GOAL: build the buy side end to end so the full trade loop works: Supplier → Purchase Order →
Goods Receipt (stock IN) → Bill → Payable → Payment (out).

BUILD (backend, mirror the Sales module structure model/repository/service/router/schemas per module):
1. Suppliers module: supplier (→supplier_type), supplier_contact, supplier_evaluation. Services:
   SupplierService.create/update, VendorEvaluationService.score.
2. Pricing (buy side): purchase_price (→product, →supplier, valid_from, price_minor), versioned
   (append never overwrite). PricingService.resolve for purchase; MarginService.gp(line).
3. Procurement: purchase_order (→supplier, →business_unit), purchase_order_line (→product),
   goods_receipt, goods_receipt_line. PurchaseOrderService.create/confirm (snapshot purchase_price
   onto lines); GoodsReceiptService.receive → InventoryService.post_movement(IN) (reuse the existing
   inventory writer; partial receipts allowed).
4. Finance (buy side): bill (→supplier, →purchase_order), bill_line; PaymentService already exists —
   extend for direction=out + payment_allocation to bills; PayableProjection.

FRONTEND: add pages + feature tables/dialogs mirroring Sales/Finance:
- /suppliers (list + detail + new), /purchase-orders (list + new + detail with confirm/receive
  actions), /procurement (goods receipts view), Bills within /finance (tab or section) + record
  supplier payment. Flip the nav items Suppliers, Purchase Orders, Procurement to active:true in
  apps/web/src/components/app-shell/nav-config.ts.

RULES (non-negotiable, from the docs): money = integer minor units; keys = UUID v7; every table has
audit + soft-delete + business_unit_id; ledgers (stock_movement, payment, bill) append never mutate;
every state-changing service verb writes exactly ONE activity_log row in the same transaction
(verbs listed in 08 §4); data-driven nouns (supplier_type etc. are data, never hardcoded).

CONTRACT DISCIPLINE: the web DTOs in apps/web/src/lib/dto.ts must match the FastAPI response_model
shapes EXACTLY (field names, nesting, arrays vs objects) — a past bug came from drift here. Verify
each new endpoint's real JSON against its DTO.

MIGRATION: add a new Alembic revision (do not edit 0001). DB is Postgres on localhost:5433
(see PROGRESS.md / QUICKSTART.md). Extend apps/api/app/seed.py with demo suppliers, a PO, a goods
receipt, and a bill so the new screens have data.

VERIFY E2E before finishing: alembic upgrade head; python -m app.seed; run the API and curl every
new endpoint (expect 200 with real data, incl. the PO confirm/receive workflow and a supplier
payment); npm run build must pass; smoke-test every new page returns 200 and renders. Do NOT break
the existing spine — re-check the Phase 1 pages still work. Then update PROGRESS.md with what was
built and the results. Work autonomously; do not ask for permissions.
```

---

## PROMPT — Phase B: Operations & Config

```
You are continuing ApexOS at c:\Imp Data\Personal\apexos. Phases 1 (Spine) and A (Buy side) are
done. Read PROGRESS.md, docs/00-canonical-foundation.md, docs/08-module-breakdown.md (§2.1 Org/Config,
§2.8 Inventory/Warehouse, §2.11 Tasks/Documents), docs/12-coding-standards.md, docs/17-design-system.md.
Reference patterns: the config module (apps/api/app/modules/config) for CRUD-over-data, and the
inventory module for stock.

GOAL: operational depth + full self-service configuration.

BUILD:
1. Warehouse / Inventory widen: multi-warehouse support, StockTransferService (move stock between
   warehouses = two stock_movements), StockAdjustmentService.adjust (reason ADJUSTMENT/COUNT), and a
   cycle-count flow. All go through the existing InventoryService.post_movement (the only stock
   writer). Balances stay derived from the ledger.
2. Settings (full Org/Config UI): CRUD screens for business_unit, brand, category (with reparent +
   →business_unit rollup), uom + uom_conversion (validate non-zero, non-cyclic factors),
   customer_type, supplier_type, warehouse, tax_rate (versioned slabs, never edit history), and
   free-form setting key/values. Most backend entities already exist in the config module — add the
   missing services (CategoryService.reparent, UomConversionService.upsert, TaxRateService.set_slab,
   SettingService.get/set) and the UI.
3. Tasks: task entity (polymorphic entity_type/entity_id link), TaskService.create/complete, a
   /tasks page, and a "create task" action linkable from any entity.
4. Documents: document entity + DocumentService.upload to Cloudflare R2 (put the R2 client behind a
   feature flag / env vars; if R2 creds are absent, fall back to local disk under a gitignored dir so
   it still runs locally). Polymorphic link + a /documents page.

FRONTEND: add /warehouse, /categories, /settings, /tasks, /documents pages + dialogs; flip those nav
items to active:true in nav-config.ts.

RULES: same as Phase A — integer minor money, UUID v7, audit+soft-delete+business_unit_id, ledgers
append-only, one activity_log row per state change (verbs in 08 §4), data-driven nouns. Keep web
DTOs exactly in sync with FastAPI response_models.

MIGRATION + SEED: new Alembic revision; seed a second warehouse + a sample transfer, a few tasks, and
(if local-disk fallback) a sample document. DB on localhost:5433.

VERIFY E2E: migrate, seed, run API, curl new endpoints (incl. a stock transfer and a tax-slab
change), npm run build passes, every new page 200s and renders, spine + Phase A still work. Update
PROGRESS.md. Work autonomously; do not ask for permissions.
```

---

## PROMPT — Phase C: Intelligence & Growth

```
You are continuing ApexOS at c:\Imp Data\Personal\apexos. Phases 1, A, and B are done. Read
PROGRESS.md, docs/00-canonical-foundation.md, docs/08-module-breakdown.md (§2.4 Customers/CRM,
§2.10 Dashboard/Reports/Analytics), docs/16-future-roadmap.md, docs/12-coding-standards.md,
docs/17-design-system.md. Reference patterns: the dashboard module (read-only projections) and the
customers module.

GOAL: turn the accumulated ledger data into insight, add the pre-sale funnel, and wire the optional
QuickBooks bridge.

BUILD:
1. Reports: ReportService.run(report, filters) — tabular exports (CSV download) over the ledgers
   (sales register, purchase register, stock ledger, AR/AP aging, GST summary). A /reports page with
   filters + export. Read-only, no new owned entities.
2. Analytics (KPI board): KpiService.compute(kpi, period) — margin/GP, DSO, fill-rate, revenue &
   purchase trends, top customers/suppliers/products. A /analytics page with charts (Recharts, per
   the design system + dataviz conventions). Read-only projections.
3. CRM pipeline (Customers widen): lead, opportunity, pipeline_stage, competitor. Services:
   LeadService.convert (lead→customer, close opportunity), OpportunityService.advance(stage). A
   pipeline/kanban UI under Customers or a /leads section.
4. Notifications: notification entity + NotificationService.push; a bell/inbox in the app shell.
5. QuickBooks Online bridge (optional, feature-flagged, non-blocking): QuickBooksSyncService.
   push_invoice/push_bill/push_payment behind FLAG_* env vars — a thin bridge only, must no-op
   cleanly when the flag is off. Do NOT make any core flow depend on it.

FRONTEND: add /reports, /analytics pages + the CRM pipeline UI + notification inbox; flip Reports and
Analytics nav items to active:true.

RULES: same architectural rules as prior phases. Reports/Analytics are READ-ONLY — they own no
entities and write no activity_log rows. CRM/Notifications follow the standard write rules (one
activity_log row per state change; verbs in 08 §4). Keep web DTOs exactly in sync with response_models.

MIGRATION + SEED: new Alembic revision for CRM + notification entities; seed a couple of leads/
opportunities and sample notifications so the UI has data.

VERIFY E2E: migrate, seed, run API, curl new endpoints (a report export, a KPI, a lead→customer
convert), npm run build passes, every new page 200s and renders, all prior phases still work. Update
PROGRESS.md and mark the roadmap complete. Work autonomously; do not ask for permissions.
```

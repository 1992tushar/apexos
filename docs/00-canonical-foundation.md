# ApexOS — Canonical Foundation (Source of Truth)

> **Status:** Approved baseline · **Owner:** Architecture · **Version:** 1.0 · **Date:** 2026-07-19
>
> This document is the single source of truth for ApexOS. Every other document, schema,
> API, and screen MUST conform to the decisions, domain glossary, entity model, and naming
> standards defined here. If any other document conflicts with this one, **this one wins**.
> Changes here are logged in `20-decisions-log.md` (ADR format).

---

## 1. What ApexOS Is

ApexOS is the **internal operating system** of **Apex Supply Solutions Pvt. Ltd.** — a B2B
procurement company supplying recurring operational consumables. It is **not** an ERP clone
and **not** a SaaS product. It is bespoke software that models Apex's business exactly.

- **First market:** HoReCa (Hotels, Restaurants, Cafés).
- **Future markets:** Hospitals, Manufacturing, Corporate Offices, Educational Institutions,
  Facility Management, Industrial. → **Nothing may be hardcoded to restaurants.**
- **Design north star:** Linear / Stripe / Notion / Vercel — minimal, fast, keyboard-first,
  large whitespace, subtle motion, blue primary.

## 2. Locked Architectural Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| D1 | **Single-tenant** with **Business Unit** as a first-class dimension on every operational table. | It is one company's OS. Avoids 3× multi-tenant complexity while preserving unit-level segmentation and the option to go multi-tenant later. |
| D2 | **Data-drive the nouns, code the verbs.** Entity *types* (customer type, supplier type, category, UOM, procurement model, etc.) are rows in tables editable from Settings. Business *workflows* stay as code until a second real variant appears, then get promoted to config. | Configurable where it pays; avoids unmaintainable "config soup". |
| D3 | **Append-only ledgers** for anything financial or stock-affecting. Never mutate a balance — record movements and derive balances. | Auditability and correctness over 20 years. |
| D4 | **Spine-first delivery.** Build one vertical slice end-to-end to production quality before widening: `Customer → Product → Sales Order → Fulfillment (stock move) → Invoice → Receivable → Dashboard tile`. | Proves the architecture with real code; every later module is a variation of a proven pattern. |
| D5 | **Money as integer minor units** (paise) + explicit `currency` (default `INR`). No floats for money. | Eliminates rounding drift. |
| D6 | **UUID v7 surrogate primary keys** on all tables; human-facing codes (SKU, order no.) are separate, indexed, unique columns. | Stable keys, sortable by creation time, no business meaning in PKs. |
| D7 | **Soft-delete + full audit columns** on every table: `created_at, created_by, updated_at, updated_by, deleted_at`. | Recoverability and traceability. |
| D8 | **Auth:** Clerk for the internal team (small, known user set) → fastest path to production; wrapped behind our own `User`/`Role` tables so we own authorization. | Speed now, control retained. |
| D9 | **Timezone `Asia/Kolkata`**, store all timestamps in UTC (`timestamptz`). Currency `INR`. GST-aware from day one (India B2B). | Correct for the business's jurisdiction. |
| D10 | **Every domain event is recorded** in an `activity_log` (actor, verb, entity, before/after) to power the Dashboard "What happened?" feed and audit. | Command-center requirement. |

## 3. Tech Stack (locked)

- **Frontend:** Next.js (App Router) · React · TypeScript · Tailwind · shadcn/ui · Lucide ·
  React Hook Form · Zod · TanStack Table · Recharts.
- **Backend:** Python · FastAPI · SQLAlchemy 2.0 · Pydantic v2 · SQLite by default (schema self-initialized from the models on startup; `DATABASE_URL` can point at PostgreSQL in production).
  Redis later.
- **Patterns:** Feature-based folders · Repository pattern · Service layer · DTO/schema
  separation · centralized error handling · structured logging.
- **Storage:** Cloudflare R2 (S3-compatible). **Deploy:** Docker → Railway/Render → K8s later.
- **External:** QuickBooks Online connector is available in this environment and is the
  candidate system-of-record bridge for Finance (see Finance module & `09-api-architecture.md`).

## 4. Domain Glossary (grounded in Apex's real data)

> Source: `Apex_Operating_System_Master_v1.xlsx` (23-sheet founder blueprint) and the filled
> SKU master. These are **real** Apex constructs — model them faithfully.

- **Business Unit** — an internal operating line of Apex (e.g., a brand line or market vertical).
  First-class dimension per D1. Categories roll up to Business Units.
- **Brand** — Apex's own or house brands. Real values today: **Aura** (tissue & paper),
  **Apex** (house brand for most categories). Data value, not code.
- **Category** — top-level product grouping owned by a Business Unit. Real values (9):
  Tissue & Paper Consumables · Garbage Bags & Waste Management · Food Packaging ·
  Food Service Disposables · Cleaning Chemicals · Cleaning Tools · Washroom Solutions ·
  Gloves & Safety Consumables · Guest Amenities.
- **Procurement Model** — how a product is sourced. Real values (data): **Private Label**,
  **Master Distributor**, **Manufacturer + Master Distributor**, **Contract Manufacturer**.
  Attribute of Category/Product; drives procurement strategy.
- **Product / SKU** — a sellable/purchasable item. Real SKU code scheme: `BRAND-CATEGORY-SEQ`
  e.g. `AUR-TIS-001` (Aura Toilet Roll), `APX-GB-001` (Apex Black Garbage Bag 19x21).
  Fields observed: Category, Brand, SKU Code, Product Name, **Specification** (e.g. "2 Ply",
  "19x21", "M Fold"), **UOM** (Pack, Roll, …), Procurement Model, **Launch Phase**, **Status**.
- **UOM** (Unit of Measure) — data value. Real: Pack, Roll. Support UOM conversions
  (e.g. Case → Pack) later.
- **Launch Phase / Launch Priority** — Apex rolls out SKUs in phases (Phase 1 …). Priority is a
  1–5 rank. Both are data on the product.
- **Supplier** — external party Apex buys from. **Two supplier types** (data): **Manufacturer**
  and **Distributor** (incl. Master Distributor). Real examples: PaperWings, Sanaswadi (paper);
  Baroda Packaging (garbage bags); K K Sales Corporation (disposables); Narendra Surfactant &
  Speciality Chemicals Pvt. Ltd. (chemicals).
- **Vendor Evaluation** — supplier scorecard/audit (quality, price, reliability). First-class.
- **Purchase Price (Buy Price)** — latest buying price per SKU per supplier; **versioned** (history kept).
- **Selling Price** — customer-facing price per SKU; may vary by customer/segment; **versioned**.
- **Margin / GP** — gross profit = selling − buying, per line and aggregated. Central KPI.
- **Customer** — a buyer. Belongs to a **Customer Type/Segment** (data): Restaurant, Hotel,
  Café, Hospital, Factory, Corporate, School, Facility Mgmt, … (extensible, NOT hardcoded).
- **Target Customer / Lead** — prospective customer in the sales pipeline.
- **Credit Policy** — per-customer credit terms: credit limit, payment terms (days), status.
- **Warehouse** — a stocking location. **Inventory** is tracked per warehouse per SKU as a
  **derived balance** over an append-only `stock_movement` ledger (D3).
- **Sales Order** → **Fulfillment** (stock-out movement) → **Invoice** → **Receivable/Payment**.
- **Purchase Order** → **Goods Receipt** (stock-in movement) → **Bill** → **Payable/Payment**.
- **Activity** — a recorded domain event (D10). **Task** — an actionable to-do, optionally
  linked to any entity. **Document** — a stored file (R2) linked to any entity.

## 5. Canonical Entity List (the model everything hangs off)

> Names are final. Use these exact table/entity names. All tables carry the D7 audit columns
> and (where operational) a `business_unit_id`. FKs shown as `→`.

**Org & Config (data-driven types):**
`business_unit` · `brand` · `category (→business_unit, →procurement_model)` ·
`procurement_model` · `uom` · `uom_conversion` · `customer_type` · `supplier_type` ·
`warehouse` · `tax_rate` (GST slabs) · `setting`

**Identity & Access:**
`user` · `role` · `permission` · `role_permission` · `user_role`

**Product:**
`product (SKU) (→category, →brand, →uom, →procurement_model)` · `product_spec_attribute` ·
`product_barcode`

**Partners:**
`customer (→customer_type)` · `customer_contact` · `customer_address` ·
`customer_credit_policy (→customer)` ·
`supplier (→supplier_type)` · `supplier_contact` · `supplier_evaluation (→supplier)`

**Pricing:**
`purchase_price (→product, →supplier, valid_from, price_minor)` ·
`selling_price (→product, [→customer|→customer_type], valid_from, price_minor)`

**Sales:**
`sales_order (→customer, →business_unit)` · `sales_order_line (→sales_order, →product)` ·
`fulfillment (→sales_order)` · `fulfillment_line`

**Procurement:**
`purchase_order (→supplier)` · `purchase_order_line (→purchase_order, →product)` ·
`goods_receipt (→purchase_order)` · `goods_receipt_line`

**Inventory (append-only ledger):**
`stock_movement (→product, →warehouse, qty_delta, reason, ref_type, ref_id)` ·
`stock_balance` (materialized/derived view per product per warehouse)

**Finance (append-only ledgers):**
`invoice (→customer, →sales_order)` · `invoice_line` ·
`bill (→supplier, →purchase_order)` · `bill_line` ·
`payment (direction: in|out, →party)` · `payment_allocation (→invoice|→bill)` ·
`receivable`/`payable` derived from invoices/bills minus allocations · `tax_line`

**CRM / Pipeline:**
`lead (target customer)` · `opportunity` · `pipeline_stage` · `competitor`

**Platform:**
`activity_log` · `task` · `document` · `notification` · `decision_log` (ADRs) ·
`sop` (SOP index)

## 6. Naming Standards (final)

- **DB:** `snake_case`, singular table names, `id` PK (UUID v7), FKs `<entity>_id`,
  money columns suffixed `_minor` (integer paise), booleans `is_*`/`has_*`, timestamps
  `*_at` (`timestamptz`). Enum-like values live in `*_type`/master tables, not DB enums,
  unless truly fixed (e.g. `payment.direction`).
- **Python:** modules/files `snake_case`; classes `PascalCase`; functions/vars `snake_case`;
  Pydantic schemas suffixed `Create` / `Update` / `Read`; services `XxxService`;
  repositories `XxxRepository`.
- **TypeScript/React:** components `PascalCase`; hooks `useXxx`; files for components
  `PascalCase.tsx`, others `kebab-case.ts`; Zod schemas `xxxSchema`; types `XxxDTO`.
- **API:** REST, plural resources, `kebab-case` paths: `/api/v1/sales-orders`. Versioned `/v1`.
- **Codes:** SKU `BRAND-CAT-SEQ` (`AUR-TIS-001`); order numbers `SO-YYYYMM-#####`,
  `PO-YYYYMM-#####`, `INV-YYYYMM-#####` (zero-padded, per-BU sequence).

## 7. Module Map (from the 23-sheet blueprint)

| Sidebar | Founder sheets it absorbs |
|---|---|
| Dashboard | 00 Dashboard, 18 Finance Dashboard, 19 KPI Dashboard |
| Sales | 16 Sales Pipeline, 09 Selling Price, 10 Margin |
| Customers | 11 Customer Segments, 12 Target Customers, 17 Credit Policy, 13 Competitor Tracker |
| Products | 01 Product Portfolio, 02 Category Master, 03 SKU Master |
| Inventory / Warehouse | 14 Warehouse Master, 15 Inventory Master |
| Procurement / Purchase Orders / Suppliers | 04 Manufacturer DB, 05 Distributor DB, 06 Vendor Evaluation, 07 Procurement Strategy, 08 Purchase Price |
| Finance | 17 Credit Policy, 18 Finance Dashboard |
| Reports / Analytics | 19 KPI Dashboard |
| Tasks / Documents / Settings | 20 Decisions Log, 21 Roadmap, 22 SOP Index |

## 8. Design Principles (enforced on every screen)

Every page answers: **What happened? · What needs attention? · What should I do?**
Minimal, fast, keyboard-first, responsive, dark-mode. Blue primary; green/amber/red/grey status.
Rounded cards, beautiful tables (TanStack), excellent typography, subtle animation only.

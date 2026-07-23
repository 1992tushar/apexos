# ApexOS — Product Demo Walkthrough

> A plain-language tour of what ApexOS is and everything it does today.
> Written for someone seeing the system for the first time.

---

## 1. What ApexOS is (in one minute)

ApexOS is the **internal operating system for Apex Supply Solutions** — a B2B company
that supplies recurring operational consumables (tissue, garbage bags, food packaging,
cleaning chemicals, gloves, etc.) to businesses like hotels, restaurants and cafés
(the "HoReCa" market), with hospitals, factories, offices and schools planned next.

It is **not** an off-the-shelf ERP. It's bespoke software that models exactly how Apex
runs — buying goods, holding stock, selling to customers, invoicing, collecting money,
and watching the numbers — all in one place, as a single fast "command center."

**How it runs:** one program. It serves both the web screens you click through *and*
the underlying data — no separate database server, no separate frontend to build.
You start it with one command and open `http://localhost:8000/`.

**The guiding idea behind every screen:** answer three questions —
**What happened? · What needs attention? · What should I do?**

---

## 2. The big picture — two "loops" that meet in the middle

Everything in ApexOS hangs off two mirror-image workflows plus the money and stock that
tie them together:

```
BUY SIDE  (money & goods coming in)         SELL SIDE (money & goods going out)
────────────────────────────────           ─────────────────────────────────
Supplier                                    Customer
   → Purchase Order                            → Sales Order
   → Goods Receipt  ──┐                ┌──     → Fulfillment
   → Bill            │                 │       → Invoice
   → Payment (out)   │                 │       → Payment (in)
                     ▼                 ▼
                  INVENTORY (one shared stock ledger)
                     │                 │
                     └──── FINANCE ────┘
                     (receivables / payables / GST)
                             │
                   DASHBOARD · REPORTS · ANALYTICS
```

- The **sell side** creates a Sales Order, ships it (which *removes* stock), invoices the
  customer, and records payments coming *in*.
- The **buy side** is the exact mirror: a Purchase Order to a supplier, a Goods Receipt
  (which *adds* stock), a Bill, and payments going *out*.
- Both meet at **Inventory** (one shared stock ledger) and **Finance** (one shared money
  ledger), which then feed the **Dashboard, Reports and Analytics**.

Two principles make this trustworthy:

1. **Nothing is ever silently overwritten.** Stock levels and account balances aren't
   stored as a single editable number — they're *derived* by adding up an append-only list
   of movements (every stock in/out, every payment). This gives a permanent audit trail.
2. **Money is stored exactly**, as whole paise (integer minor units), never as decimals
   that can drift. Everything is INR, GST-aware, formatted the Indian way (`₹12,34,567.00`).

---

## 3. The screens — a guided tour

The left sidebar is grouped into **Main**, **Work**, and **System**. Here's what each screen does.

### Dashboard (the command center)

![ApexOS Dashboard](screenshots/dashboard.png)

The landing page. At a glance it shows:
- **Today's sales**, **outstanding receivables** (money owed to Apex), and total
  **inventory value** on hand.
- **What needs attention:** count of **low-stock products** (below reorder level),
  **pending sales orders**, and **pending purchase orders**.
- A **14-day revenue trend**, the **top 5 customers**, and a **recent activity feed**
  (the last 10 things that happened anywhere in the system).

### Sales

![Sales orders list](screenshots/sales-list.png)

![Create a new sales order](screenshots/sales-new.png)

![Sales order detail](screenshots/sales-detail.png)

The heart of the sell side. You can:
- See all sales orders (with customer, status, total, line count).
- **Create a new order** — pick a customer and add product lines; prices and GST are
  filled in automatically from the customer's price list.
- Walk an order through its lifecycle with one click each:
  **Draft → Confirm → Fulfill → Invoice.**
  - *Confirm* locks the order.
  - *Fulfill* ships it and **automatically removes the stock** from the warehouse.
  - *Invoice* generates the customer invoice with a due date calculated from that
    customer's payment terms.

### Customers

![Customers directory](screenshots/customers.png)

The customer directory (name, type/segment, city, status) with a detail page per customer.
Each customer has a **credit policy** — credit limit and payment terms in days — which is
what drives invoice due dates. Customer *types* (Restaurant, Hotel, Café, Hospital,
Corporate, School, Facility Management…) are configurable data, not hardcoded.

### Leads (CRM pipeline)

![Leads and CRM pipeline](screenshots/leads.png)

The pre-customer sales pipeline. Track **leads** (prospective customers) and
**opportunities** as they move through stages — **New → Qualified → Proposal → Won / Lost** —
on a pipeline board. A won lead can be **converted into a real customer** in one step.
Also tracks **competitors** with a strength rating.

### Products

![Products catalog](screenshots/products.png)

The full catalog of sellable/purchasable items (SKUs). Each product carries an SKU code
(`AUR-TIS-001`), name, specification (e.g. "2 Ply"), unit of measure, brand, category,
default GST rate, and reorder level. The demo ships with 17 real Apex products across
tissue/paper and garbage-bag lines.

### Categories

![Categories tree](screenshots/categories.png)

The category tree (9 real Apex categories such as *Tissue & Paper Consumables*,
*Cleaning Chemicals*, *Guest Amenities*). Categories roll up to a Business Unit and carry
a procurement model. You can create, rename, and **re-parent** categories (safely — it
won't let you create loops).

### Inventory

![Inventory](screenshots/inventory.png)

The live stock picture — on-hand quantity per product, and which items are **below their
reorder level** and need buying. Every number here is derived from the underlying stock
movement ledger.

### Warehouse

![Warehouse operations](screenshots/warehouse.png)

Multi-location stock operations across warehouses (the demo has **Pune Main** and
**Mumbai Central**):
- **Transfer** stock between warehouses (records one stock-out and one stock-in).
- **Adjust** stock (corrections, damage, etc.).
- **Cycle count** — reconcile counted quantity against system quantity.

### Procurement

![Procurement](screenshots/procurement.png)

The buy-side working view — what needs to be reordered and the sourcing picture, feeding
into purchase orders.

### Purchase Orders

![Purchase orders list](screenshots/purchase-orders.png)

![Purchase order detail](screenshots/purchase-order-detail.png)

The mirror of Sales, for buying:
- Create a PO to a supplier with product lines.
- Walk it through **Draft → Confirm → Receive → Bill.**
  - *Receive* (Goods Receipt) **automatically adds the stock** to the warehouse; it
    supports **partial receipts** (receive some now, the rest later).
  - *Bill* creates the supplier bill (a payable).

### Suppliers

![Suppliers directory](screenshots/suppliers.png)

The supplier directory (two types: **Manufacturer** and **Distributor**), each with a
detail page, GSTIN, and a **vendor evaluation** scorecard so you can rate suppliers on
quality/price/reliability. Suppliers can have their own **negotiated purchase prices** per
product (kept as versioned history).

### Finance

![Finance hub](screenshots/finance.png)

![Invoice detail](screenshots/finance-invoice.png)

The money hub, both directions:
- **Invoices** (money owed *to* Apex) and **Bills** (money Apex owes).
- Record **payments** against either; supports **partial payments** — an invoice moves to
  "partially paid" and shows the remaining balance.
- Detail pages per invoice/bill show paid-to-date, balance, and due date.
- Balances are derived (invoice/bill total minus payments allocated to it), never edited
  directly.

### Reports

![Reports](screenshots/reports.png)

Read-only operational reports you can **run and export to CSV or JSON**:
- **Sales register**, **Purchase register**
- **Stock ledger** (every movement)
- **AR aging** (receivables by age) and **AP aging** (payables by age)
- **GST summary**

### Analytics

![Analytics KPI board](screenshots/analytics.png)

The KPI board — the "how is the business doing?" view:
- **Revenue** and **purchases** totals, **gross profit** and **margin %**.
- **Receivables** and **payables**, plus **DSO** (days sales outstanding — how long money
  takes to come in) and **fill rate** (share of orders actually fulfilled).
- **6-month revenue & purchase trends** and **top customers / suppliers / products**.

### Tasks

![Tasks](screenshots/tasks.png)

A lightweight to-do list. Tasks have a priority and can be **linked to any record** (e.g.
"Verify goods received for PO-202607-00001" linked to that purchase order). Mark them done
when finished.

### Documents

![Documents](screenshots/documents.png)

File storage. Upload and download documents, optionally attached to any record. Files go to
Cloudflare R2 cloud storage when configured, otherwise to local disk — so it works out of
the box.

### Settings

![Settings](screenshots/settings.png)

The control panel that makes the system *Apex's own* without touching code. Manage the
master lists and configuration: business units, brands, categories, units of measure and
their conversions, customer/supplier types, warehouses, **GST tax slabs** (versioned), and
general settings. This is the "data-drive the nouns" principle — new customer types,
categories, or tax rates are added here, not by a developer.

---

## 4. A live demo script (what to actually click)

With the seeded demo data loaded, here's a 5-minute story that touches every part:

1. **Dashboard** — point out today's sales, receivables, low-stock alert, and the recent
   activity feed. "Every action in the system lands here."
2. **Products / Inventory** — show the 17 SKUs and current on-hand stock (100 units each
   from opening stock, minus what the demo order already shipped).
3. **Sales → New order** — create an order for *Blue Fig Restaurant*, add a couple of
   products. Note prices and GST auto-fill.
4. **Confirm → Fulfill → Invoice** — walk it through. Flip back to **Inventory** and show
   the stock dropped automatically when you fulfilled.
5. **Finance** — open the resulting invoice, record a **partial payment**, and show the
   balance and due date update.
6. **Purchase Orders** — show the seeded PO to *PaperWings*, already **Confirmed → Received
   → Billed**; note the received goods increased stock.
7. **Warehouse** — show the **Pune → Mumbai transfer** the seed created.
8. **Leads** — show the pipeline board with *Sunrise Banquets* in "Qualified."
9. **Analytics** — finish on the KPI board: revenue, gross profit/margin, DSO, fill rate,
   and the trend charts.

**Seeded demo data includes:** the founder user, 1 business unit, 9 categories, 17 products
(with opening stock, sell & buy prices), 3 customers with credit policies, 3 suppliers,
2 warehouses, GST slabs, one **complete sell loop** (order → invoice → part-payment), one
**complete buy loop** (PO → receipt → bill → part-payment), an inter-warehouse transfer,
demo tasks, a document, CRM leads/opportunity/competitor, and notifications.

---

## 5. Under the hood (for the technically curious)

- **One process:** Python · FastAPI serving server-rendered **Jinja2** HTML pages **and** a
  JSON API (browsable at `/docs`). No build step, no Node.
- **Data:** SQLAlchemy 2.0 + Pydantic v2 over **SQLite** by default (a single self-creating
  file, `apexos.db`). The schema builds itself on startup. Can point at **PostgreSQL** in
  production by setting `DATABASE_URL`.
- **Clean architecture:** each feature is a self-contained module with the same shape —
  `models` (tables) · `repository` (queries) · `service` (business rules) · `schemas`
  (data shapes) · `router` (API). The web pages call the *same services* the API does, so
  there's one source of truth for behavior.
- **Design decisions that matter:** append-only ledgers for stock & money; money as integer
  paise; UUID v7 primary keys; soft-delete + full audit columns on every table; every domain
  event recorded to an activity log; GST-aware and INR from day one; single-tenant with
  Business Unit as a first-class dimension so nothing is hardcoded to restaurants.
- **Run it:**
  ```bash
  cd apps/api
  pip install -e ".[dev]"      # once
  python -m app.seed           # optional demo data
  uvicorn app.main:app         # UI at http://localhost:8000/ , API docs at /docs
  ```

---

## 6. What's real vs. planned

- **Built and working today:** everything in the tour above — the full sell loop, full buy
  loop, inventory & multi-warehouse ops, finance with partial payments, CRM pipeline,
  reports, analytics, tasks, documents, notifications, and settings.
- **Optional integration:** a **QuickBooks Online** bridge exists behind a feature flag for
  syncing finance data; it's off by default and no core workflow depends on it.
- **Design intent for later:** the docs describe future markets (hospitals, factories,
  offices), richer auth/roles, Redis, and cloud deployment. The nouns are already
  data-driven so widening to new markets is configuration, not a rewrite.
```
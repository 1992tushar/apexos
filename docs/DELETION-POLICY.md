# ApexOS — Deletion Policy

> What can be deleted, what cannot, and why. Satisfies **R1.2** and **R1.3**.
> Implementation: `apps/api/app/db/soft_delete.py` — the single mechanism (R1.1).
>
> **Version:** 1.0 · **Date:** 2026-07-28 · Part 1, checkpoint C3

---

## 1. There is no hard delete

ApexOS never issues `DELETE`. Every entity table carries `deleted_at` (G3), and
"deleting" means stamping it. Reads already exclude `deleted_at IS NOT NULL`
everywhere, so a deleted row leaves the lists and the detail lookups immediately.

The row itself stays. That is the point: it keeps its primary key, so every
document that references it keeps rendering. An invoice raised for a customer who
is later deleted still shows that customer's name — `FinanceRepository.customer_name`
resolves the name without a `deleted_at` filter, deliberately (**R1.7**). A hard
delete would either break those documents or force a cascade that destroys
financial history.

**One mechanism, not per-entity code (R1.1).** `soft_delete(db, instance, *,
actor_id, label=None)` in `app/db/soft_delete.py` is the only writer of
`deleted_at` in the codebase. It stamps the column, sets `updated_by`, and writes
exactly one `activity_log` row inside the caller's transaction (G5, **R1.6**).
Services call it in three lines: fetch, 404 if missing, delegate. `documents` —
which had its own `repository.soft_delete` before Part 1 — was migrated onto it,
so there is genuinely one implementation rather than one plus a legacy.

---

## 2. Deletable entities

Master data. These describe the business rather than record what happened to it,
so removing one rewrites no history.

| Entity | Service verb | Web route | Extra condition |
|---|---|---|---|
| Customer | `CustomerService.delete` | `POST /customers/{id}/delete` | — |
| Supplier | `SupplierService.delete` | `POST /suppliers/{id}/delete` | — |
| Product | `ProductService.delete` | `POST /products/{id}/delete` | — |
| Task | `TaskService.delete` | `POST /tasks/{id}/delete` | — |
| Lead | `CrmService.delete_lead` | `POST /leads/{id}/delete` | not already converted |
| Category | `CategoryService.delete` | `POST /categories/{id}/delete` | no subcategories, no products |
| Document | `DocumentService.delete` | `POST /documents/{id}/delete` | — (predates Part 1) |

Each has a Delete button rendered by the one `ui.delete_button` macro in
`_macros.html`, on the list row and — for customers and suppliers — the detail
page header.

### The two conditional refusals

**A converted lead** is the origin record of a real customer, and its won
opportunities point back at it. Hiding the lead hides where that customer came
from, so the deletion is refused and the message says to delete the customer
instead.

**A category with children or products** is refused because a category is a live
classification, not a snapshot. Unlike an invoice — which keeps rendering because
it stored what it needed at the time — a product reads its category name *now*.
Deleting an occupied category would orphan a subtree or blank the category column
on rows that are still for sale. Reparent or reassign first.

Note the asymmetry with customers: a customer *can* be deleted while invoices
reference it precisely because those invoices don't depend on the customer row
staying visible. "Does anything still read this row live?" is the test, not
"does anything reference it".

---

## 3. Non-deletable entities, and why (R1.3)

These are refused unconditionally. `PROTECTED_TABLES` in
`app/db/soft_delete.py` holds the table name and the user-facing reason; a call
raises `ConflictError`, which the web layer turns into an error flash and the API
into a 409 envelope. **It is never a 500** — that is the specific failure R1.3
exists to prevent, and there is a test per class asserting the readable message.

| Class | Tables | Why |
|---|---|---|
| **Invoices** | `invoice`, `invoice_line` | A permanent financial record. Correct with a credit note; cancel the invoice if it should not have existed. |
| **Bills** | `bill`, `bill_line` | Same, from the payables side. Correct with a debit note. |
| **Payments** | `payment`, `payment_allocation` | Append-only ledger (G4). Money either moved or it didn't; reverse it with a new entry. |
| **Sales orders** | `sales_order`, `sales_order_line` | A posted document with downstream fulfilments and invoices. Cancel it. |
| **Purchase orders** | `purchase_order`, `purchase_order_line` | A posted document with downstream receipts and bills. Cancel it. |
| **Receipts & fulfilments** | `goods_receipt`, `goods_receipt_line`, `fulfillment`, `fulfillment_line` | Record stock that physically moved and have already written to the stock ledger. Adjust the stock or raise a return. |
| **Stock ledger** | `stock_movement` | Append-only and the only source of truth for stock on hand (G4, G7, G8). Post a correcting adjustment. |
| **Audit trail** | `activity_log` | Records what happened. An audit log you can edit is not an audit log. |

### Why the guard is table-level

R1.3 says "*posted* sales/purchase orders", which suggests a status check. The
guard is unconditional instead, because ApexOS exposes no delete path for an
unposted draft either — nothing is foreclosed by the stricter rule, and a flat
dict of table → reason is far easier to audit than a set of status predicates.

A later part that genuinely wants draft-order deletion should make that entry
status-aware **inside `PROTECTED_TABLES`**, not add a second delete path that
bypasses the mechanism.

### What is not in the table

Config noun-lists (`customer_type`, `supplier_type`, `procurement_model`, `uom`,
`brand`, `warehouse`, `tax_rate`, …) are deletable in principle — they are rows
precisely so they can change without a code change (G6) — but Part 1 wires no
delete route for them. They are edited through Settings. If a part adds one, the
category rule above is the precedent: refuse while anything still points at the
row.

---

## 4. Restoring

There is no undelete UI, deliberately — with one user (D-B), the recovery path is
a `deleted_at = NULL` update against the SQLite file, and the `activity_log` row
records what was deleted and when. If restoring ever becomes routine, that is the
signal to build it, not before.

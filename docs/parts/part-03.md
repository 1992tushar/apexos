# Part 3 - Procurement: pre-order -> PO depth

> Closed record. Tagged `part-03-done`. Not read during a session; the live handoff lives in PROGRESS.md.

## Part 3 — Procurement: pre-order → PO depth · **COMPLETE** · on `main` · tagged `part-03-done`

- [x] **C1** requisition (request → approve → convert) + RFQ + quote capture + comparison →
      commit `3d0162b`
- [x] **C2** PO revisions + partial receipt + back orders + receipt-against-revision →
      commit `e62f8bb`

**Every P0/P1 requirement in §5 (R4.1–R4.16) passes.** R4.14 is a "do not build" and was not built.

### ▶ Two defects found and fixed outside the part's scope

Both were things the register *claimed* were verified. Committed separately from C2 so the history
reads honestly.

1. **The R1.5 authz test asserted `[] == []`** (`64dde49`). It walked `build_web_router().routes`,
   but FastAPI ≥ 0.140 no longer flattens `include_router` into `.routes` — each inclusion is an
   `_IncludedRouter` holding the real router on `.original_router`. The walk saw 19 wrappers, none
   with `.methods`, matched nothing, and passed for free. **A dependency upgrade silently disarmed a
   P0 test and the suite stayed green.** Recursing properly finds 83 web routes / 48 POSTs, and all
   48 *do* carry the guard — so the claim was true, nothing was verifying it. Both walks now assert a
   floor on what they found, which is the actual lesson. `tests/test_web_smoke.py` also stopped
   hardcoding 17 paths: it discovers 22 plain GET routes plus the 9 registry slugs, so the nine
   `/masters/*` screens Part 2 shipped are covered by pytest instead of by clicking through uvicorn.
2. **`InventoryService.post_movement` does not exist** (`0a5af5c`). The real method is
   `record_movement`. The docs named the nonexistent one in **18 places across 5 files, including the
   G8, R4.8, R6.15, R7.6 and R9.4 acceptance criteria** — P0 gates specifying a method no session
   could call. Parts 5, 7 and 9 would each have hit it. Logged as `REQUIREMENTS.md` v1.2.

**Requirements passed at C2:**

| ID | How it was verified |
|---|---|
| R4.7 | `PurchaseOrderService.revise` appends a `purchase_order_revision` + `_line` snapshot with a required reason and one activity row; the live order lines carry current figures. Tests read version 1 back after revising and assert qty, unit price, subtotal, tax and total are all unchanged, that `revision_no` goes `[1, 2, 3]` across two revisions, and that reasons are `[None, "first cut", "second cut"]`. Revision 1 is written by `confirm`, not `create`. |
| R4.8 | Already passed from Part 1's `GoodsReceiptService.receive`; not rebuilt (G16). C2 only changed *where* it reads "outstanding" from — `PurchaseOrderService.open_qty`, one definition instead of two inline subtractions. |
| R4.9 | `open_qty` per line + `open_qty_total` on the order, derived on every read and clamped at zero. Shown as a "Back order" column and a badge. Tests: 100 ordered − 40 received = 60; it tracks two further receipts down to 0; a revision down to what arrived reads 0, never −n; and a test asserts no column named `open_qty`/`qty_open`/`back_order_qty`/`qty_outstanding` exists on `purchase_order_line` (G7). |
| R4.10 | `goods_receipt.purchase_order_revision_id`, set on every receipt and rendered as a `v2` tag beside the GRN. A receipt naming a superseded revision raises `ConflictError` quoting **both** versions and the PO number; a test asserts the refusal wrote no receipt and posted no stock. The web receive form carries a hidden `against_revision_no`, so a tab left open across a revision refuses instead of booking goods against a stale agreement — walked in the app. |
| R4.11 | `purchase_order.confirmed_at`, its own column because `updated_at` is overwritten by the first receipt. `GoodsReceipt.received_at` already existed. Part 4 has both ends of the interval it must measure. |
| R4.12 | `/purchase-orders/new` moved onto C1's `pre.line_grid` — one `<datalist>` (303 options total, down from ~1,900) and typed SKUs, and the buy price now defaults from the supplier's purchase price rather than being retyped. Verified in the booted app. |
| R4.15 | The requisition's own PO is confirmed, part-received 40 of 60, then revised to 50 — so `/purchase-orders` tells one story end to end and v1 stays readable at 60 with the receipt still stamped against it. Seed prints `PO-202607-00002 v2, back order 10`. |
| R4.16 | `tests/test_po_revisions.py` — 27 tests. **Mutation-checked:** making `revise` reuse the current revision instead of appending fails 10 of them, so they bite rather than pass vacuously. |

**Verify loop at Part 3 close:** **336 tests passing** (309 + 27); `ruff check app/ tests/` at **38**
findings — the standing baseline, **zero new**; every web route 200 (now asserted by pytest, not by
hand); the C2 web forms walked end to end: create → confirm → part-receive → revise → stale receipt
refused → cut-below-received refused → bill.

**New files at C2:** `tests/test_po_revisions.py`, `tests/_web_routes.py`.

**Decisions made at C2 (do not silently reverse):**
1. **A revision is a snapshot table; the live lines stay the current state.** Versioning the
   `purchase_order` row itself was the alternative — it would change `po_no` and break every FK from
   receipts, bills and `references.py`. One identity, an append-only history beside it.
2. **There is no `superseded_at`.** The next revision's `created_at` already says when a version
   stopped applying, and a column written *after* insert would mean the table is not append-only.
   Current = `max(revision_no)`, derived, so no pointer can drift. (The tax-slab precedent in R3.6
   does close a window, because a slab genuinely has a validity range; a revision does not.)
3. **Revision 1 is written by `confirm`, not `create`.** R4.7 is a statement about *confirmed*
   orders; a draft has no agreement to preserve. This is also why `confirmed_at` and revision 1 are
   written by the same verb.
4. **No new PO status.** Revisions are tracked by `revision_no`, so `REFERENCES.live_statuses` and
   `web/core.py:status_class` needed no change — the two gotchas C1 flagged simply don't fire.
5. **`revise` refuses a `received` order.** More goods after a complete delivery is a new order, not
   a revision. Cutting a *part*-delivered order down to what arrived is allowed and closes it.
6. **No line removal.** Cutting a quantity to what has arrived is the real-world equivalent; cutting
   below it is refused, because that would make the back order negative and contradict receipts that
   already posted stock.
7. **`_qty_text` lives in the service, not the web layer.** `Numeric(18, 4)` reads back as `40.0000`,
   which is right for arithmetic and wrong in a sentence. A service cannot import `app.web` (Part 2
   decision 10), so the rule is duplicated deliberately — and plain `.normalize()` is a trap, it
   turns 40 into `4E+1`.
8. **`_ADDITIVE_COLUMNS` DDL was checked against what `create_all` emits**, not guessed
   (`DATETIME`, `CHAR(32)`). `create_all` builds new tables but never ALTERs, so both new columns
   would be silently missing on any DB seeded before C2 — including the dev `apexos.db`.

**Verify loop at C1 close:** 293 tests passing (251 + 42); `ruff check app/ tests/` at **38** findings
(the standing baseline), **zero new**; app boots on `--port 8015` against a fresh seeded DB; all 21 web
routes 200 including the new `/requisitions`, `/requisitions/{id}`, `/rfqs`, `/rfqs/{id}`; the
approve → convert-to-PO walk done through the real POST routes; deleting a referenced warehouse now
refuses with a message naming the blockers instead of raising `AttributeError`.

**Requirements passed at C1:**

| ID | How it was verified |
|---|---|
| R4.1 | `RequisitionService` — `create` (status `requested`) → `approve`/`reject` → `convert_to_po` / `convert_to_rfq`. Walked in the booted app: an empty reason refuses, a reason approves, the approved screen offers both conversion paths, and a second conversion refuses with *"REQ-202607-00001 has already been converted"*. |
| R4.2 | `approve`/`reject` write `approved_by` / `approved_at` / `approval_reason` on the row **and** exactly one `activity_log` row. Tests assert the row count is exactly 1 for the verb and 2 in total for the requisition, and that a blank reason raises `ValidationError`. |
| R4.3 | `RfqService.issue` takes `supplier_ids` and writes one `rfq_supplier` row each (status `invited`); the same supplier listed twice is one invitation (tested). Reachable ad hoc from `/rfqs` or from a requisition via `convert_to_rfq`. |
| R4.4 | `capture_quote` prices lines in integer minor units with tax as bps off the line subtotal, defaults each qty to the RFQ line's so the comparison is like-for-like, marks the invitation `quoted`, and accepts a supplier who was never invited (adding them) rather than losing a real quote. A second quote from the same supplier refuses (D3 — a revised price is a new RFQ). |
| R4.5 | `comparison()` returns the grid: RFQ lines down, quoting suppliers across, with unit price + MOQ per cell and lead time + total + score per column. `is_cheapest` / `is_cheapest_total` / `is_fastest` are computed in the service, not the template, and mark **every** tied entry. Verified on the booted screen: ₹32.90 (cheapest, MOQ 1,000, 18 days) against ₹35.70 (fastest, 7 days, MOQ 500) — a real trade-off, not one dominant column. |
| R4.6 | `quotation_history(product_id, supplier_id=None)` + a "Quoted prices" panel on `/products/{id}` and `GET /products/{id}/quotations`. Tests: both suppliers' prices appear, the supplier filter narrows it, and a never-quoted product returns `[]`. |
| R4.13 | `REQUISITION_LIST` / `RFQ_LIST` in `app/modules/procurement/listing.py` + `view_from_request`. Tests assert markers only the shared macros emit (`list-toolbar`, `sort-arrow`, `pagination-count`) and that the CSV export row count equals the filtered on-screen total while an unfiltered export is strictly larger. |
| R4.14 | Not built, deliberately, and **visibly**: every comparison column's `score` is `None`, rendered "unknown", with a `score_note` naming part 4 and what to compare instead. A test asserts no column ever carries a score. This is G11 — a placeholder 0 or 50 would read as computed. |
| R4.15 | Partly: the seed leaves a requisition **awaiting approval**, one **approved and converted to a PO**, and an **RFQ with 2 quotes**. The revised PO and the partial receipt with an outstanding back order are C2's. |
| R4.16 | Partly: `tests/test_preorder.py` (42 tests) covers requisition→PO conversion, approval writing exactly one row, and the RFQ→quote comparison pick. Revision-preserves-history, back-order arithmetic and receipt-against-a-superseded-revision are C2's. |

**Requirements outstanding (all C2):** R4.7 (PO revisions, append-only), R4.9 (back-order qty derived),
R4.10 (receipt against a specific/superseded revision), R4.11 (**persist `confirmed_at` — part 4 must
measure lead time**; `GoodsReceipt.received_at` already exists), R4.12 (port `/purchase-orders/new` onto
C1's datalist picker), plus the C2 halves of R4.15 and R4.16. R4.8 already passes from Part 1's
`GoodsReceiptService.receive` — read it before rebuilding it.

### ▶ A pre-existing bug C1 found and fixed

`REFERENCES["warehouse"]` named `PurchaseOrder.warehouse_id` — **a column that does not exist.** A
purchase order carries no warehouse; the goods receipt chooses one. Because `Reference` names its column
by *string*, this failed at check time, not import time: from Part 2 C3 until now, deleting or
deactivating **any** warehouse raised `AttributeError` and 500'd rather than refusing. Part 2's C3 notes
claim R3.7 passes, and for the other twelve masters it does — the warehouse row of the R3.1 matrix
("movements, open POs") did not.

Fixed by reaching the warehouse through the receipt: `Reference(GoodsReceipt, "warehouse_id", …,
via=Via(PurchaseOrder, …, open_po))`. Now refuses with *"Cannot delete warehouse Pune Main — it is still
used by 274 stock movements (…, and 271 more)"*. **The lesson for C2: exercise a new `REFERENCES` entry
with `blocking_references(db, row)`; reading it is not enough.**

**New files at C1:** `app/modules/procurement/preorder.py` (the pre-order services),
`app/modules/procurement/listing.py`, `app/web/pages/preorder.py`,
`app/web/templates/_preorder.html`, `app/web/templates/requisitions/{list,detail}.html`,
`app/web/templates/rfqs/{list,detail}.html`, `tests/test_preorder.py`.

**Changed at C1:** `procurement/{models,repository,schemas,router,service}.py` ·
`db/references.py` · `web/core.py` (2 nav entries + pre-order statuses in `status_class`) ·
`web/pages/products.py` + `templates/products/detail.html` (the R4.6 panel) · `web/static/app.css`
(`.compare`, `.tag`, `.check-grid`) · `seed.py` (+~100, the pre-order section) ·
`docs/CODEBASE-MAP.md`.


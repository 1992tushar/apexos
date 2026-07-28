# ApexOS — Build Progress

> Working log so any session can pick up where the last one stopped.
> This file is the source of truth for status.

_Last updated: 2026-07-28_

---

# ▶ CURRENT WORK — read this first

A **session** is a token budget; a **part** is a group of sessions. Most parts take several sessions
with a checkpoint commit between each. See the *Session protocol* in `docs/ROADMAP.md` for the
checkpoint list per part.

**All work is on `main`** — no feature branches, no PRs. A part is "done" when every P0/P1 requirement
passes, the verify loop is green, this file is updated, and the part is tagged `part-0N-done`. Those
tags are the rollback points.

**Every session ends by updating the block below, before it runs out of room.** A session that dies
with an accurate resume block costs nothing; one that dies without it costs a re-derivation.

### Fresh clone — one-time setup

The build machine both writes and tests the code; there is no write-here/test-there split. The stack
is self-contained (SQLite file + one uvicorn process, no database server, no npm), so any machine with
**Python 3.11+** can do everything.

```bash
git clone https://github.com/1992tushar/apexos.git    # personal creds only, never org
cd apexos/apps/api
python -m venv .venv
# Windows: .venv\Scripts\Activate.ps1   ·   Linux/macOS: source .venv/bin/activate
pip install -e ".[dev]"
python -m app.seed          # creates apexos.db with demo data
```

Then verify the baseline before writing any code:

```bash
python -m pytest -q                  # count is in the CURRENT WORK block below (293 at Part 3 C1)
python -m ruff check app/ tests/     # expect exactly 38 pre-existing findings — 39 is a regression
python -m uvicorn app.main:app --port 8000   # http://localhost:8000/ — click through every nav page
```

If the baseline is not green, stop and report what failed — do not start feature work on top of it.

### ▶ How to start the next session

Open a fresh Claude Code session in your clone of the repo and type:

```
Start next part of development
```

That's the whole thing. `CLAUDE.md` at the repo root binds that phrase to "read the **▶ NEXT SESSION
PROMPT** below and follow it," so the state lives here in one maintained place rather than in whatever
you remember to type. Nothing to look up, nothing to keep in your head.

**The session that closes a checkpoint owns this prompt.** Updating it is part of the same duty as
updating the resume block — a starter that still names last part's baseline counts and edit set is worse
than none, because the next session will trust it. Keep it short: the binding lists live in the resume
block, and the prompt's job is to point at them and name the numbers.

#### ▶ NEXT SESSION PROMPT — Part 3, checkpoint C2 (the last one in Part 3)

```
Continue the ApexOS build. Do this in order:

1. git checkout main && git pull origin main && git fetch origin --tags

2. Read the "▶ CURRENT WORK" block at the top of PROGRESS.md — specifically the
   "Part 3 — Procurement" section. C1 is done and committed. That block names your edit set
   ("Read for C2"), carries verified signatures ("Call, don't read") so you don't open those
   modules, and lists what NOT to read. It is binding: C1 spent a third of its budget on
   context that is now written down there.

3. Read docs/REQUIREMENTS.md §1 (global invariants G1–G17) and §5 (R4.x). Your checkpoint is
   R4.7–R4.12 — the ones still open. NOT optional: the invariants you must not break —
   integer minor units, exactly one activity_log row per state change, derived-never-stored,
   append-only ledgers, InventoryService as the only writer of stock_movement — are not in
   the files you're editing.

4. `git show --stat HEAD` for C1's shape (one commit, ~20 files). Not a tree walk.

5. Verify the baseline before writing code (from apps/api, venv activated):
     python -m pytest -q                  # expect 293 passed
     python -m ruff check app/ tests/     # expect EXACTLY 38 findings — 39 is a regression
   If either is off, stop and report. 38 is the pre-existing count (32 E501, 4 F841, 1 B007,
   1 E402, all in untouched modules). C1 added ~2,600 lines with zero new findings; that's the bar.

6. C2 is PO DEPTH. Build, in this order:
     - R4.7 PO revisions: a confirmed PO is never mutated in place. A revision is a new
       version with a reason and one activity_log row; version 1 stays readable verbatim.
     - R4.11 timestamps FIRST if you touch confirm: PurchaseOrder has no `confirmed_at` and
       part 4 must MEASURE lead time, not have it typed in. GoodsReceipt.received_at already
       exists. This is a handoff requirement — do not defer it.
     - R4.9 back-order qty DERIVED as ordered − received (G7). `qty_received` already accrues
       on the line; the open quantity is a computed property, NEVER a stored counter.
     - R4.10 a receipt records which revision it was received against, and a receipt against a
       SUPERSEDED revision is handled explicitly — not silently accepted.
     - R4.12 port /purchase-orders/new onto the datalist picker C1 built (see "Call, don't
       read" for `product_datalist` / `line_grid` / `_lines`). It currently repeats a
       311-option <select> six times and cannot be typed into.
   R4.8 (partial receipt through InventoryService.post_movement) already works — read
   GoodsReceiptService.receive before adding a verb that exists (G16).

7. Two things C2 inherits and must not break:
     - Every new model owes app/db/references.py an entry, even an empty tuple (R3.7). If a
       revision is a new table, it owes one. And exercise it — `blocking_references(db, row)`
       — don't just read it: a Reference names its column by STRING, so a wrong one raises
       AttributeError at check time. C1 fixed exactly that bug in the warehouse entry.
     - If you add a status to the PO vocabulary, decide whether it counts as "open" in
       REFERENCES `open_po`. A new state that quietly stops blocking is R3.7 regressing.
   Extend app/seed.py (G14): R4.15 still needs "a revised PO, and a partial receipt with an
   outstanding back order". The pre-order section is already there; add to it or after it, but
   BEFORE the two trailing passes (master history backfill, tax-slab repair) that run last.

8. Work on main. No branches, no PRs. Commit when the checkpoint is done. When every P0/P1 in
   §5 passes, tag it: git tag part-03-done && git push origin part-03-done.

9. BEFORE you run low on context, update the "▶ CURRENT WORK" block: checkpoints with commit
   SHAs, requirement IDs passed and outstanding, gotchas, mid-part decisions, and the four
   delta lines — Changed since / Read for the next part / Call, don't read (copy signatures
   from source, never from memory) / Do NOT read. Then rewrite the "▶ NEXT SESSION PROMPT"
   above for Part 4, including its baseline test and ruff counts. Then commit and push.
   If the checkpoint changed the SHAPE of anything, amend docs/CODEBASE-MAP.md in the same
   session. A stale map is worse than none.

Use pytest -q, never verbose. Don't re-read files you just edited.
```

**If a session has drifted** and you want a hard reset on scope, ignore the above and paste the whole
```-fenced PROMPT for the part from `docs/ROADMAP.md` instead. More deterministic, more typing.

**Rules of thumb.** One checkpoint per session — don't push a session past its checkpoint to "just
finish the part". Start each session fresh (`/clear` or a new window) rather than continuing a long
one. And if a session ends messy, the recovery is `git log --oneline -5` plus the resume block, not
re-reading the design docs.

## Part 3 — Procurement: pre-order → PO depth · **IN FLIGHT** · on `main`

- [x] **C1** requisition (request → approve → convert) + RFQ + quote capture + comparison →
      commit `PENDING-C1`
- [ ] **C2** PO revisions + partial receipt + back orders + receipt-against-revision

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

**Read for C2 (PO revisions + receipts)** — these and nothing else:
- `docs/REQUIREMENTS.md` §5, rows R4.7–R4.12 only.
- **The edit set:** `app/modules/procurement/service.py` (452 lines — `PurchaseOrderService` +
  `GoodsReceiptService`, the whole of C2's domain work) · `app/modules/procurement/models.py`
  (`PurchaseOrder`, `PurchaseOrderLine`, `GoodsReceipt`) · `schemas.py` (the PO half, top ~110 lines) ·
  `app/web/pages/purchase_orders.py` (134 lines) + `templates/purchase_orders/{detail,new}.html` ·
  `app/db/references.py` if a revision is a new table · `seed.py`'s pre-order section (for the
  revised PO + partial receipt) · `tests/test_purchase_flow.py`.
- **Do NOT read `preorder.py`, `listing.py`, `web/pages/preorder.py` or the requisition/RFQ
  templates.** C1's half is finished and C2 does not touch it. The seam between `service.py` and
  `preorder.py` exists precisely so you can skip ~700 lines; the three functions you might want from
  it are in "Call, don't read" below.

**Call, don't read** — verified signatures from C1, copied from source:

```python
# app/modules/procurement/service.py — module level, already used by preorder.py
default_business_unit(db) -> uuid.UUID          # raises NotFoundError if none seeded
tax_bps_for(db, product) -> int                 # the product's default GST rate in bps, or 0
_round_minor(value: Decimal) -> int             # the one money rounding step (G1)

# app/modules/procurement/preorder.py — C2 needs only these
RequisitionService(db).convert_to_po(req_id, *, supplier_id, actor_id) -> PurchaseOrderDetail
RfqService(db).award(rfq_id, quotation_id, *, actor_id) -> PurchaseOrderDetail
#   BOTH build a PurchaseOrderCreate and call PurchaseOrderService.create. If C2 changes that
#   signature or what create() does with unit_price_minor, these two are the callers to check.
RfqService(db).quotation_history(product_id, *, supplier_id=None, limit=50)
#   -> list[QuotationHistoryRow]; a pure read (G15), already on /products/{id}

# app/modules/procurement/repository.py
PreorderRepository(db).products_by_id(ids) -> dict[uuid, Product]   # one query for a whole page
PreorderRepository(db).supplier_names(ids) -> dict[uuid, str]
#   ProcurementRepository is unchanged — .get/.add/.search/.receipts_for/.receipt_rows/.pending_count

# app/web/templates/_preorder.html — the R4.12 picker to port /purchase-orders/new onto
{% import "_preorder.html" as pre %}
pre.line_grid(products, rows, autofocus=false, title="Lines")
#   emits ONE <datalist id="product-options"> + N rows of
#   <input list="product-options" name="product_code"> + <input name="qty">
#   (a <select> per row is ~1,900 <option>s at 311 products and cannot be typed into)
pre.doc_lines(lines)               # a document's own lines, read-only: line_no/sku/name/qty
pre.supplier_checklist(suppliers)  # name="supplier_ids" checkboxes

# app/web/pages/preorder.py — the resolver that goes with line_grid
_lines(db, product_code: list[str], qty: list[str]) -> list[tuple[uuid.UUID, Decimal]]
#   skips blank rows; raises ValidationError NAMING an unknown SKU rather than dropping the row.
#   Copy it or import it — do not write a second SKU resolver.
```

Everything from Part 2's signature block below still holds (`ListSpec`, `view_from_request`,
`ensure_unreferenced`, `soft_delete`, `ensure_unique`, `ActivityService.history`).

**Gotchas C1 hit, for C2:**
- **`status_class` in `web/core.py` decides badge colour from a status *string*.** A status not in its
  `positive`/`warning`/`negative` sets renders grey, silently. Every pre-order badge was grey until C1
  added `requested`/`issued`/`invited` → warn and `approved`/`converted`/`awarded`/`quoted` → ok.
  **A new PO status needs a bucket, or the screen stops telling the founder anything.**
- **A list page with a bulk-entry form has TWO `<tbody>`s.** The Part 2 test idiom
  `assert html.count("<tbody>") == 1` is wrong on these pages. Assert markers only the shared macros
  emit (`sort-arrow`, `pagination-count`, `list-toolbar`) instead, and remember an **empty** list
  renders no table at all — so read the row total from the paginator (`Showing 1–25 of N`), not by
  counting `<tr>`.
- **`ListSpec.columns` read the projected row.** `RequisitionListRow.line_count` / `qty_total` /
  `outcome` exist only on the projection, so they carry no `sort=`. The projector fetches the
  aggregates for the **whole page in two queries** (`requisition_line_aggregates`,
  `requisition_outcomes`) — do not add a per-row query in a projector.
- **`APEXOS_DATABASE_URL` is NOT the env var.** It is `DATABASE_URL` (see `conftest.py`). Seeding with
  the wrong name silently writes to the real `apexos.db` and you will "verify" against stale data.
  Point both the seed and uvicorn at the same fresh file: `export DATABASE_URL="sqlite:///./fresh.db"`.
- **Deleting a scratch `.db` fails while uvicorn holds it** (Windows: *Device or resource busy*). Stop
  the process first — `pkill` does not exist in this shell; use PowerShell `Get-CimInstance
  Win32_Process | Where CommandLine -like '*<port>*' | Stop-Process -Force`.
- **`uuid.UUID` in a Pydantic response model serialises to a string**, so an API test comparing a
  `supplier_id` from JSON must compare against `str(supplier.id)`.
- **A `Body(..., embed=True)` param is how the JSON API takes a lone scalar** (`reason`,
  `supplier_id`, `quotation_id`) without inventing a one-field schema.
- Port 8000 may be occupied on this machine; C1 used `--port 8015`.

**Decisions made in C1 (do not silently reverse):**
1. **`procurement/` splits its services by flow, not by layer.** `service.py` = PO → confirm →
   receive → bill; `preorder.py` = requisition → RFQ → quotation. Same for the repository
   (`ProcurementRepository` / `PreorderRepository`). The justification is the reading diet, and it is
   the only one that counts: C2 works on the PO half and never opens the pre-order half, saving ~700
   lines of context. A shared primitive moves to **module level** in `service.py` rather than being
   reached across classes — hence `default_business_unit` / `tax_bps_for`, both called by `preorder.py`
   so a quotation and the PO it becomes cannot disagree about tax. **This is not licence to split a
   module with no such seam.**
2. **Conversion calls the target's service; it never rebuilds it (G16).** Requisition→PO and
   award→PO both assemble a `PurchaseOrderCreate` and call `PurchaseOrderService.create`. The
   requisition carries **no price** — it is a request, so `create` resolves the supplier price. An
   award passes the **quoted** `unit_price_minor` explicitly, which is the whole point of quoting.
3. **A conversion writes one row on the *source*; the target service writes its own on the target.**
   `convert_to_po` logs `purchase_requisition.converted` and `create` logs `purchase_order.created` —
   two entities, one row each, so G5 holds without either service knowing about the other's log.
4. **Losing quotations are left exactly as received.** Marking them "rejected" would be a state change
   per supplier with no decision behind it (and N rows to log). `Rfq.awarded_quotation_id` records
   which one won; the others stay `received` and readable. A test asserts the loser is untouched.
5. **A supplier cannot revise a quote in place** — `capture_quote` refuses a second quote from the same
   supplier and says *"A revised price is a new RFQ, not an edit (D3)."* Same reasoning as the tax-slab
   versioning in Part 2 C3.
6. **`lead_time_days` on a quotation is what the supplier *promised* and is never overwritten from a
   receipt.** Part 4 measures the actual lead time from `confirmed_at`/`received_at` (R4.11) and the
   gap between promise and delivery is the signal — writing the measurement back would destroy it.
7. **A requisition/RFQ is "open" while it can still change what it reads.** `open_req = ("requested",
   "approved")`, `open_rfq = ("issued",)` in `references.py`. A **converted** requisition no longer
   blocks retiring its product — same reasoning as R1.7 for a confirmed invoice; there is a test for
   each direction.
8. **The product picker submits a SKU, not an id.** A `<datalist>` is the only no-JS way to get
   search-as-you-type (R4.12), and it submits display text. `_lines()` resolves it in one query and
   **names an unknown SKU back to the user** — a free-text picker that silently drops a typo'd row is
   the one failure mode this must not have.

---

## Part 2 — Master data & shared machinery · **COMPLETE** · on `main` · tagged `part-02-done`

**Part 1 is COMPLETE and tagged `part-01-done`.** Its record is in the log below.

- [x] **C1** the machinery: list/table macros + generic query helper + CSV export + duplicate
      prevention + change history → commit `7419f67`
- [x] **C2** proven on products + customers, seed extended to 311/253 rows, R2.14 recorded →
      commit `5a1f89e`
- [x] **C3** rolled out to every remaining master + the special cases → commit `de73c23`

**Every P0/P1 requirement in §3 and §4 passes.** R2.6/R2.7 (CSV import) stay unbuilt — P2 by D-C.
R3.13 is a "do not build" and was not built.

### ▶ R3.1 — the capability matrix (no empty cells)

`S` search · `F` filters · `O` sort · `P` pagination · `X` CSV export · `A` audit trail (activity_log)
· `T` status · `D` soft delete · `H` change history · `V` validation · `I` relationship integrity
· `U` duplicate prevention

| Master | Screen | S | F | O | P | X | A | T | D | H | V | I | U |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Products | `/products` | ✅ | 3 | ✅ | 25 | ✅ | ✅ | 3-state | ✅ | ✅ | ✅ | open SO/PO | SKU + name/spec/brand |
| Customers | `/customers` | ✅ | 3 | ✅ | 25 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | open SO | code + name/city |
| Suppliers | `/suppliers` | ✅ | 3 | ✅ | 25 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | open PO | code + name/city |
| Categories | `/categories` | ✅ | 3 | ✅ | 25 | ✅ | ✅ | ✅ | ✅ | ✅ | cycle | products, children | code + name/parent |
| Business units | `/masters/business-units` | ✅ | 1 | ✅ | 25 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | cats, products, custs | code + name |
| Brands | `/masters/brands` | ✅ | 1 | ✅ | 25 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | products | code + name |
| Manufacturers | `/masters/manufacturers` | ✅ | 2 | ✅ | 25 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | none yet | code + name/city |
| Procurement models | `/masters/procurement-models` | ✅ | 1 | ✅ | 25 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | cats, products | code + name |
| Units of measure | `/masters/units` | ✅ | 1 | ✅ | 25 | ✅ | ✅ | ✅ | ✅ | ✅ | factor | products, conversions | code + name |
| Customer types | `/masters/customer-types` | ✅ | 1 | ✅ | 25 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | customers, leads | code + name |
| Supplier types | `/masters/supplier-types` | ✅ | 1 | ✅ | 25 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | suppliers | code + name |
| Warehouses | `/masters/warehouses` | ✅ | 2 | ✅ | 25 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | movements, open POs ¹ | code + name |
| Tax slabs | `/masters/tax-slabs` | ✅ | 1 | ✅ | 25 | ✅ | ✅ | ✅ | ⛔ versioned | ✅ | ✅ | products | n/a — code reuse **is** a version |

¹ **This cell was broken until Part 3 C1** — the reference named `PurchaseOrder.warehouse_id`, a column
that does not exist, so every warehouse deactivation raised `AttributeError` instead of refusing. See
"A pre-existing bug C1 found and fixed" in the Part 3 section above. The other twelve rows were fine.

Two deliberate non-✅s. **Tax slabs are not deletable** (`deletable=False` in the registry): a slab is a
version record, and R3.6 forbids editing history — a rate change appends. **Manufacturers have no
integrity guard** because nothing references them yet; their `references.py` entry is an explicit empty
tuple, so a later part that adds `product.manufacturer_id` finds the place to declare it.

**Requirements passed at C3:**

| ID | How it was verified |
|---|---|
| R3.1 | The matrix above; `tests/test_masters.py` parametrises the first five columns over every registry entry, so a master added without a spec, an export or a history panel fails. |
| R3.2 | One route set, one list template, one detail template for nine masters. Each list test asserts `html.count("<tbody>") == 1` and the presence of markers only the shared macros emit. |
| R3.3 | Applied three times rather than worked around: `model_options`/`distinct_options` (C2), then `kind="bool"` + `kind="bps"` + `active_options` + a `cell` that works with no `ListView`. Each is ~5 lines in the machinery and removes ~10 per master. |
| R3.4 | `CategoryService.reparent` (pre-existing) + `tree()` (new): depth-first, `sort_order` then code, carrying the business unit each row rolls up to. Rendered above the list. Tests: reparent to a descendant and to self both raise; the seeded tree is three levels deep and a child's BU equals its parent's. |
| R3.5 | `UomConversionService.upsert` rejects `from == to` and a non-positive factor; both asserted. |
| R3.6 | `TaxRateService.set_slab` appends and closes the prior window. Test: after a revision the prior row's code, name, `rate_bps` and `valid_from` are unchanged and only `valid_to` is set. The list shows every version with its window; `NATURAL_KEYS` deliberately has no `tax_rate` entry. |
| R3.7 | `app/db/references.py`. Refusals name the blockers: *"Cannot deactivate brand Apex — it is still used by 268 products (Black Garbage Bag 19x21, …, and 265 more)"*. Verified in the booted app, and by a test that puts a product on a draft PO and asserts the PO number appears in the refusal. Closed documents never block, so R1.7 still holds. |
| R3.8 | `NATURAL_KEYS` covers every master. Parametrised test posts a duplicate code per master and asserts a readable flash with no `IntegrityError` — including the tax-slab exception, where a reused code must *succeed*. |
| R3.9 | SKU generation untouched; `ProductService.set_status` makes Active/Draft/Discontinued a real verb with one activity row, a field-level diff and the R3.7 guard. Existing product tests still green. |
| R3.10 | 12 sub-categories + 3 sub-sub-categories, and GST_12 as two versions (12% from 2025-04-01, closed 2026-04-01; 5% from then). Seeded through `set_slab`, not hand-authored. |
| R3.11 | `tests/test_masters.py` — 65 tests. |
| R3.12 | `SupplierRepository.search` was the last old-path query; a test asserts none of the three repositories has a `search` attribute any more. Category deletion's two hand-rolled counts and four hand-rolled `code already exists` checks are gone. |
| R3.13 | Not built. |

**Verify loop at Part 2 close:** 251 tests passing; `ruff check app/ tests/` at 38 findings (the C2
baseline), zero new; app boots on `--port 8013`; all 26 web routes 200 including the nine new
`/masters/*` screens and `/products/{id}`; deactivating a referenced brand refuses with a message that
names the products; an unreferenced manufacturer deactivates and re-activates cleanly.

### ▶ R2.14 — what the second master cost (this is C3's gate)

**Customers, the second master: 82 lines added, 61 deleted, net +21.** It is net-positive-tiny because
the hand-rolled query and table markup left with it.

| Where | Added | What |
|---|---|---|
| `modules/customers/listing.py` | 41 | the whole spec — 7 columns, 3 filters, search, default sort (14 of the 41 are docstring + imports) |
| `web/pages/customers.py` | 16 | the CSV branch, `view_from_request`, the history call on detail |
| `modules/customers/service.py` | 12 | `to_read_many` + `list()` via `query_page` + 2 imports |
| `web/templates/customers/list.html` | 8 | four macro calls, replacing 28 lines of `<table>` |
| `modules/customers/repository.py` | 3 | a comment where `search()` was (−23) |
| `web/templates/customers/detail.html` | 2 | the history panel |

**A third master is ~60–80 lines** — the same rows minus the spec's docstring, or ~40 if it has no
detail page yet. Well inside R2.14's 100-line gate, so **C3 rolls out as-is; do not redesign.**
Products cost more (146 added) only because it had *no detail page at all* — 38 lines of new template
plus a route. That is a missing screen, not machinery friction.

**Where C3 should spend, if a master resists:** improve `app/db/listing.py`, never the page. C2 already
did this twice — `model_options` / `distinct_options` mean a filter dropdown needs no SQL of its own
(that alone took ~15 lines out of each spec), and `export_text` now normalises `Decimal`. If a master
needs a new *kind* of column or filter, add it there and every later master gets it (R3.3).

**Requirements passed at C1 (stage 1 machinery — built and tested, wired to pages in C2):**

| ID | How it was verified |
|---|---|
| R2.1 | `list_toolbar` / `list_table` / `pagination` / `list_empty` / `cell` / `history_panel` in `_macros.html` — search box, filter selects, chips, sortable headers, pagination controls. One definition; `tests/test_list_macros.py` renders each against a real `ListView`. |
| R2.2 | Driven by `ListSpec(columns=, filters=, sort=, page_size=)` in `app/db/listing.py`. `Column.kind` picks the renderer, so adding a column is a config line. Test asserts headers/cells/sortability all come from the spec. |
| R2.3 | `?q=&sort=&dir=&page=&<filter>=` only — no session, no cookie. `ListView.url/sort_url/page_url/clear_url` rebuild current state with one thing changed; tests assert sorting keeps the search, a new sort resets to page 1, and a stale filter value degrades instead of raising. |
| R2.4 | One helper: `query_page` / `query_rows` / `count_rows` over one `build_select`. No `LIMIT`/`OFFSET`/`ORDER BY` anywhere else. |
| R2.5 | `build_select` applies `deleted_at IS NULL` for any model with the column and `business_unit_id ==` for any model with the mixin. Tests: soft-deleting a row drops it from the count, the page and the search; another BU sees zero; a model without the column ignores the scope. |
| R2.8 | `csv_response` runs the same `build_select` with pagination removed. Tests: a filtered export's row count equals the on-screen count, and an unfiltered one is strictly larger. |
| R2.9 | `NATURAL_KEYS` + `ensure_unique` in `app/db/duplicates.py`; `DuplicateError` carries `.field` and `details={"field","value"}`. Wired into `ProductService.create`, `CustomerService.create` and `CustomerService.update`, replacing three hand-rolled checks. Tests assert the field, the message and that no `IntegrityError` ever reaches the caller. |
| R2.10 | Derived from `activity_log` — **no new table**, and `test_history_uses_the_activity_log_and_nothing_else` fails if one appears. `ActivityService.history()` reads it back with actor names; `field_changes()` records field-level before/after into the `data` JSON column that already existed. |
| R2.15 | `tests/test_listing.py` (29), `tests/test_duplicates.py` (17), `tests/test_change_history.py` (16), `tests/test_list_macros.py` (22) = 84 new tests. |

**Requirements passed at C2:**

| ID | How it was verified |
|---|---|
| R2.11 | `/products` and `/customers` are the machinery end to end. `tests/test_master_pages.py` (20 tests) goes through the real pages: page 2 shares no row ids with page 1, `?q=` narrows and survives a page link, a filter renders a removable chip, an unpublished `?sort=` degrades to the spec's default, `?export=csv` matches the on-screen count and carries *projected* columns, a duplicate POST comes back as a readable flash with no `IntegrityError`, and both detail pages render a history panel — the customer one showing a real before → after diff. Each test also asserts a marker only the shared macros emit, so a page that quietly grew its own table would fail. Confirmed in the booted app on `--port 8010`. |
| R2.13 | **311 products, 253 customers** from `bulk_products()` / `bulk_customers()` in `seed.py`. Deterministic index arithmetic, no randomness, `get_or_create`-idempotent. Uneven on purpose: draft/discontinued rows, zero-stock rows (no movement at all), a zero-credit-limit account, accounts with no credit policy. `/products` shows "Showing 1–25 of 311" with working Next/Prev. |
| R2.14 | The table above. 82 lines for the second master, net +21, a third at ~60–80. |

**Requirements outstanding:** all of §4 (R3.1–R3.13) is C3. R2.6/R2.7 are **P2** and deliberately not
built (D-C). Nothing from §3 is left.

**Verify loop at C2 close:** 186 tests passing (166 + 20); `ruff check app/ tests/` at **38** findings
(was 39 — the deleted `CustomerRepository.search` held one `E501`), zero new; app boots on `--port 8010`;
all 19 web routes 200 including the new `/products/{id}`; an unknown product id renders `error.html`.

**New files at C2:** `app/modules/products/listing.py`, `app/modules/customers/listing.py`,
`app/web/templates/products/detail.html`, `tests/test_master_pages.py`.

**New files at C3:** `app/db/references.py`, `app/modules/config/listing.py`,
`app/modules/suppliers/listing.py`, `app/web/pages/masters.py`,
`app/web/templates/masters/{list,detail}.html`, `app/web/templates/categories/detail.html`,
`tests/test_masters.py`.

**Changed at C2** (`git show --stat 5a1f89e` — 17 files, +755/−147; use
`git diff part-01-done..HEAD --stat` for the whole part):
`db/listing.py` (+41, the two options providers) · `web/listing.py` (+5, `Decimal` in the export) ·
`modules/products/{listing.py*,service.py,repository.py}` · `modules/customers/{listing.py*,service.py,repository.py}` ·
`web/pages/{products,customers}.py` · `web/templates/products/{list,detail*}.html` ·
`web/templates/customers/{list,detail}.html` · `seed.py` (+189) · `tests/test_master_pages.py`* ·
`tests/test_list_macros.py` (one seed-dependent assertion)
  *(`*` = new file)*

**Changed at C3** (`git show --stat de73c23` — 32 files, +1816/−252). Whole part:
`git diff part-01-done..HEAD --stat` — 52 files, +5634/−432.

**Read for the next part (Part 3 — Procurement: pre-order → PO depth)** — these and nothing else:
- `docs/REQUIREMENTS.md` §5 (R4.x) — the acceptance contract for Part 3.
- `docs/ROADMAP.md` → PROMPT for Part 3, and its SESSION PROTOCOL (2 checkpoints).
- `docs/08-module-breakdown.md` § Procurement.
- **The edit set:** `app/modules/procurement/{models,repository,service,schemas,router}.py` ·
  `app/web/pages/{procurement,purchase_orders}.py` and their templates · `seed.py`'s buy-loop section.
- **Reference only, and only if you add a list screen:** `app/modules/products/listing.py` +
  `app/web/pages/products.py` — the pattern for one, `app/web/pages/masters.py` — the pattern for many.
- **Already built, do not rewrite:** `PurchaseOrderService` covers create → confirm → receive → bill
  with the status vocabulary `draft / confirmed / partially_received / received`. Part 3 adds depth to
  it; read those methods before adding a verb that already exists (G16).

**Call, don't read** — verified signatures, so you don't have to open these files:

```python
# app/db/listing.py — declare the spec as a module-level constant beside the page
ListSpec(entity: str, model: type, columns: tuple[Column, ...], search=(), filters=(),
         sort="created_at", dir="desc", page_size=25, search_hint="Search")
Column(key: str, label: str, kind="text", sort=None, href=None, export=True)
#   kind: text | mono | money | number | date | datetime | badge | link
#   sort names the MODEL attribute; omit it and the header isn't clickable
#   key is read off the row the page renders (may be a projection, not the ORM row)
Filter(key: str, label: str, column: str, coerce="str", options=None, all_label="All")
#   coerce: str | uuid | int | bool     options: Callable[[Session], Sequence[tuple[str,str]]]
static_options(*pairs: tuple[str, str])                    # a fixed dropdown
model_options(model, *, label="name", value="id", order_by=None)   # another table's live rows
distinct_options(model, column: str)                       # the values a column actually holds
#   all three return a `Filter.options` provider; a filter needs no SQL of its own
ListParams(q="", sort="", dir="asc", page=1, filters: Mapping[str,str] = {})
query_page(db, spec, params, *, business_unit_id=None) -> ListPage
#   ListPage(.rows .total .page .page_size) — page_size comes from the SPEC, so a
#   caller wanting a different one passes replace(SPEC, page_size=n) (dataclasses.replace)

# app/web/listing.py
view_from_request(request, db, spec, *, business_unit_id=None, project=None) -> ListView
#   "the one call a GET list route makes". project: Callable[[Sequence[row]], list[row]]
#   — the WHOLE page of ORM rows at once, not one row at a time
wants_csv(request) -> bool                     # branch the GET route on this
csv_response_from_request(request, db, spec, *, business_unit_id=None, project=None) -> Response
#   pass the same `project` as the view, or projected columns export blank

# app/modules/{products,customers}/listing.py — the two worked specs
PRODUCT_LIST: ListSpec   ·   CUSTOMER_LIST: ListSpec
ProductService(db).to_read_many(rows) -> list[ProductRead]     # the projector
CustomerService(db).to_read_many(rows) -> list[CustomerRead]

# app/modules/activity/service.py
ActivityService(db).history(entity_type: str, entity_id: uuid.UUID, *, limit=50)
#   -> list[HistoryEntry(occurred_at, verb, summary, actor, changes)]; pass straight
#   to ui.history_panel(entries). A pure read (G15).

# app/seed.py
record_creation(db, activity, *, entity_type, entity_id, summary, actor_id) -> None
#   the `created` history line for a get_or_create'd master; idempotent, skips if the
#   row already has any activity

# app/db/references.py — relationship integrity (R3.7). ADD AN ENTRY PER NEW MODEL.
ensure_unreferenced(db, instance, *, action: str, label: str) -> None
#   raises ConflictError naming the live documents that block `action`
blocking_references(db, instance) -> list[str]      # the phrases, without raising
Reference(model, column, noun, plural, label="name", live_statuses=(), via=None)
Via(model, child_column, label, live_statuses=())   # a reference through a document LINE
REFERENCES: dict[tablename, tuple[Reference, ...]]  # the whole policy, as data

# app/modules/config/service.py — one creator/toggle/delete for nine masters
ConfigService(db).create_master(entity_type, *, code, name, extra=None, actor_id)
ConfigService(db).set_master_active(entity_type, row_id, *, active: bool, actor_id)
ConfigService(db).delete_master(entity_type, row_id, *, actor_id)
MASTER_LABELS: dict[entity_type, str]               # the label messages use
CategoryService(db).tree() -> list[(depth, Category, business_unit_name)]
CategoryService(db).get(category_id) -> CategoryRow
ProductService(db).set_status(product_id, status, *, actor_id)   # R3.9 lifecycle

# app/modules/config/listing.py
simple_master_spec(entity, model, *, plural, extra=(), search=(), filters=()) -> ListSpec
#   a code/name/is_active master's whole list, in one call

# app/db/duplicates.py
ensure_unique(db, model, values, *, exclude_id=None) -> None
#   raises DuplicateError(.field); pass exclude_id on update so a row isn't its own duplicate

# app/db/soft_delete.py
soft_delete(db, instance, *, actor_id, label=None) -> None
#   raises ConflictError for PROTECTED_TABLES or an already-deleted row
```

`build_select` applies `deleted_at IS NULL` and `business_unit_id` itself — do not re-add either.

**Do NOT read:**
- `docs/CODEBASE-MAP.md` covers the layout, the shared machinery, the patterns, `seed.py`'s section
  structure and the test inventory. **Read it instead of exploring the tree.** If it's wrong, fix it.
- `seed.py` end to end (750 lines). Jump to the `# --- section ---` blocks you need; the bulk
  generators are in the reference-data section at the top.
- The other 14 page modules "for an example" — `web/pages/products.py` + `modules/products/listing.py`
  are now *the* example, and they're in the read list above.
- `db/listing.py` / `web/listing.py` internals. C2 read them so C3 doesn't have to; everything a page
  calls is in the signature block above. Open them only to *add* a column kind or filter coerce.
- `db/soft_delete.py`, `web/security.py`, `activity/history.py`, `db/duplicates.py` internals — C1
  wired them and C2 didn't change them; the map's one-line contracts are enough.
- `_macros.html` — C2 changed nothing in it. Four calls (`list_toolbar`, `list_table`, `list_empty`,
  `pagination`) plus `history_panel`; copy them from `products/list.html`.
- The older `docs/` design files (`00`, `07`, `08` beyond §2.3/§2.4, `09`–`17`). Retired stack.
- Anything in this file below the `▶ CURRENT WORK` section — historical log.

**Gotchas for the next session:**
- **Do not build a second query helper or a second table macro.** R2.1/R2.4 are one definition each.
  All three repository `search()` methods are gone and `tests/test_masters.py` fails if one returns.
  A new list screen is a `ListSpec` + `view_from_request`; a new *set* of list screens is a
  `MasterPage` entry in `app/web/pages/masters.py`.
- **Every new model owes `app/db/references.py` an entry** — even an empty tuple. R3.7's guard reads
  that map, so a model missing from it silently permits deletion of something live points at. An
  explicit `(): nothing reads this live` is the difference between decided and forgotten.
- **A reference through a document line needs `via=`**, or the refusal quotes a line id instead of the
  document number the founder can act on.
- **`live_statuses` is what "open" means.** `("draft", "confirmed", "partially_received")` for a PO,
  `("draft", "confirmed", "partially_fulfilled")` for an SO. A part that adds a status to either
  vocabulary must decide whether it is open here too — otherwise a new state silently stops blocking.
- **One route set can serve many screens.** `/masters/{slug}` handles nine masters; `/settings` is the
  hub. Before adding a page module, check whether a registry entry does it.
- **`ListSpec.columns` read the *projected* row; `sort`/`filters`/`search` read the *model*.** On
  products, `category_name` and `stock_on_hand` exist only on `ProductRead`, so they are columns with
  no `sort=`. A `?sort=` naming a projection-only key silently falls back to the spec default — that's
  by design (C1 decision 2), so don't "fix" it by sorting in Python.
- **`page_size` lives on the spec, not in `query_page`.** A service `list()` that ignores its own
  `page_size` argument silently truncates its callers — `/sales`, `/purchase-orders` and `/warehouse`
  all ask `ProductService.list` for 300 rows to fill a `<select>`. Use `replace(SPEC, page_size=n)`.
- **Keep each service's `list()` signature.** C2 changed both implementations without touching a single
  caller (10 routers + 8 pages call these). Same for suppliers in C3.
- **A GET list route needs two branches** — `view_from_request` for HTML, `csv_response_from_request`
  when `wants_csv(request)` — and **both need the same `project=`**, or the CSV's projected columns
  come out blank. There's a test for that (`test_the_export_carries_projected_columns...`).
- **The CSV export leads with a UTF-8 BOM** (deliberate, so Excel opens it correctly). Read it back
  with `utf-8-sig` or the first header cell compares as `"﻿SKU"`.
- **Templates escape, so assert accordingly.** A filter chip for "Garbage Bags & Waste Management"
  renders `&amp;`. And a search term echoes into the toolbar's `value=`, so "the deleted row is gone"
  must be asserted against the `<tbody>`, not `in html`.
- **Multi-master screens need a query-string namespace.** `/settings` renders eight master lists on one
  page. `?q=` and `?page=` are per-`ListView`, so eight specs on one route would fight over them.
  Decide this before writing code — separate routes per master is the cheap answer.
- **The seed's masters bypass their services**, so `get_or_create` writes no `activity_log` row and the
  history panel would be empty on demo rows. `record_creation()` backfills the named rows and every
  config master, in a pass that runs **last** in `run()` — later sections create masters too (the
  Phase B warehouse), and a mid-file pass misses them. The generated hundreds are deliberately not
  logged; they would bury the activity feed.
- **A re-seed can't recover a real `occurred_at`.** `ActivityService.log` has no `occurred_at`
  parameter (it defaults to now), so a backfilled `created` line on an already-seeded DB reads
  "just now". A fresh DB is correct. Don't add the parameter to make demo data prettier.
- **Every web POST route carries `require_web_permission`.** A new mutation route added without one
  fails `tests/test_web_authz.py::test_every_web_post_route_carries_the_guard`. Add the guard, don't
  weaken the test. (A GET export route needs no guard — the test only walks POSTs.)
- **Port 8000 may be occupied** on the current build machine by an unrelated app. `uvicorn` logs the
  bind failure but the shell may still report success — check the log, or just use `--port 8010`.
- **Python is per-user installed** at `C:\Users\Administrator\AppData\Local\Programs\Python\Python312`
  and is not on `PATH` in a fresh shell; the venv at `apps/api/.venv` is what to activate.

**Decisions made mid-part (Part 2 — do not silently reverse):**
1. **`ListSpec` is shared by the query and the presentation**, not duplicated. `app/db/listing.py`
   owns the spec + the query; `app/web/listing.py` owns URL building and CSV over the same object.
   A column that can be sorted in SQL is therefore clickable in the header by construction — the two
   halves cannot drift into disagreeing.
2. **Sorting is whitelisted, filters degrade.** `?sort=` is honoured only if a column published it;
   anything else silently falls back to the spec's default. A filter value that no longer parses is
   dropped rather than raising, so a stale bookmark renders the list (R2.3) instead of an error page.
3. **Every order-by appends the primary key as a tiebreak.** Without it, rows sharing a sort value
   swap between pages and the same row shows twice — or never — while paging. Tested by walking every
   page and asserting the id set is exactly the total.
4. **The duplicate check matches the database constraint, not the read filter.** A soft-deleted row
   still occupies a `UNIQUE` column, so a `NaturalKey` marked `db_unique=True` counts deleted rows as
   collisions and says so ("a deleted product still holds this SKU"). Checking only live rows would
   pass and then hit the `IntegrityError` R2.9 exists to prevent. Keys with no DB constraint (the
   composite business identity) only consider live rows, which is all they promise.
5. **Code generators now count rows *ever* created, not live rows.** `repo.count_ever()` on products
   and customers. `count_all()` excludes deleted rows, so after one deletion the next generated code
   was one a deleted row still held — a latent duplicate that decision 4 would now surface as a user
   error. Fixed at the generator.
6. **Change history added no table (R2.10).** `activity_log` already answers all three questions;
   the only gap was field-level detail, and its `data` JSON column existed for exactly that. Services
   call `field_changes(instance, updates)` **before** applying the update and pass
   `data={CHANGES_KEY: changes}` to the *same* activity row — one row per verb still (G5), not a
   second row for the diff.
7. **An unresolvable actor says "Unknown user"; a null actor says "System".** No invented attribution
   (G11). Reading history writes nothing (G15), asserted by a test.
8. **`app/core/money.py:minor_to_text`** is the one minor-units→decimal-string conversion, integer
   arithmetic only (G1). Used by the CSV export and the history panel. `app/web/core.py:money` is
   left alone — it presents a figure with the ₹ symbol and Indian grouping, a different job.
9. **`number()` now normalises `Decimal`.** A `Numeric(18,4)` quantity was rendering as `20.0000`
   on screen. It now shows `20` and `1.25`; every quantity column benefits. **C2 extended the same
   normalisation to the CSV export** — a file carrying `40.0000` for a stock of 40 exports the column's
   scale rather than the number.
10. **A master's `ListSpec` lives in `app/modules/<feature>/listing.py`, not beside the page.** C1's
   note said "beside the page"; C2 moved it because R2.4 requires the *service* to run its `list()`
   through `query_page` too, and a service importing `app.web` would invert the layering. `app.db.listing`
   has no web dependency, so the module can own the spec and the page can import it. One spec means the
   JSON API's filters and the screen's headers cannot drift (this is decision 1, applied).
11. **The projector is a public service method** (`to_read_many`), not a lambda over a private one.
   Both the HTML and the CSV branch need the same projection, and `_to_read`-per-row in a page would
   have put N+1 query knowledge in the template layer.
12. **`/products/{id}` is new.** Products had no detail page, so the change-history panel R2.11 requires
   had nowhere to live. Its 38-line template is *not* counted as machinery cost in R2.14 — it is a
   screen that was missing.
13. **Filter dropdowns are three providers, not per-page SQL.** `model_options` (another table's live
   rows) and `distinct_options` (the values a column actually holds) joined `static_options` in
   `app/db/listing.py`. This is R3.3 applied before C3 rather than after: it took ~15 lines out of each
   spec, and every master C3 touches inherits it.
14. **The seed generates rather than lists.** 311 products and 253 customers come from
   `bulk_products()` / `bulk_customers()` — deterministic index arithmetic, no `random`, so re-seeding
   is idempotent, tests can name a row, and diffs stay readable. The named demo rows stay literal
   because later seed steps order and invoice them by code.
15. **Nine config masters are one route set, not nine page modules** (`/masters/{slug}` over the
   `MASTERS` registry). Eight lists on `/settings` could not each own `?q=`, `?sort=` and `?page=`, so
   the split was forced by R2.3 rather than chosen for tidiness. `/settings` kept the typed key/value
   settings and became the hub. The registry entry is the whole per-master cost: a spec plus a field
   list, ~6 lines.
16. **"Still referenced" is a question about *live* work, not about foreign keys** —
   `app/db/references.py`. A confirmed invoice snapshotted what it needed, so it never blocks (that is
   what keeps R1.7 true); an open purchase order will read the master again at receipt, so it does.
   Every refusal names the documents in the way, because "cannot delete: still referenced" is not
   something the founder can act on.
17. **Deactivation is guarded exactly like deletion.** Hiding a master from every picker breaks an open
   order as thoroughly as removing it, and two policies would drift. One question, one map.
18. **`tax_rate` has no `NATURAL_KEYS` entry, and slabs are not deletable.** Reusing a code *is* how a
   new version is expressed (R3.6), so a duplicate check there would forbid the feature; and deleting a
   slab would delete history. The registry's `deletable=False` keeps the button off the page.
19. **`create_master` grew an `extra` dict rather than a second creator.** Warehouses and manufacturers
   are the same master with extra text columns; `create_warehouse` is now a two-line wrapper kept for
   its callers. The four hand-rolled `code already exists` checks are gone — they each phrased the error
   differently and none of them noticed a soft-deleted row still holding the `UNIQUE` code.
20. **`kind="bool"` and `kind="bps"` are machinery, not per-page formatting.** Config masters carry
   `is_active` (a boolean, not a status string) and tax slabs carry integer basis points. Both now
   render in the shared `cell` macro and in the CSV export, so no page formats a value itself. The
   `bps` filter uses integer arithmetic — 1800 → "18%", never a float.
21. **`cell` works without a `ListView`.** A detail page renders the same spec columns as a `<dl>`
   (`masters/detail.html`), which means a new column appears on both screens. Duplicating the kind
   switch for detail pages was the alternative, and it would have drifted within a part.

**Decisions made mid-part (Part 1 — do not silently reverse):**
1. **Soft delete is one function, not a base-repository method** — `soft_delete()` in
   `app/db/soft_delete.py`. It owns the append-only guard, the already-deleted guard and the single
   `activity_log` row. `documents` was migrated off its own `repository.soft_delete` onto it, so
   there is one implementation rather than one plus a legacy.
2. **The non-deletable guard is table-level and unconditional**, keyed on `__tablename__` in
   `PROTECTED_TABLES`. Stricter than R1.3's "*posted* orders", which is fine because no delete path
   exists for drafts either. A part that wants draft deletion makes that entry status-aware **inside**
   the dict rather than adding a bypassing delete path.
3. **Categories refuse deletion while they have children or products**; customers do not refuse while
   they have invoices. The test is "does anything read this row *live*", not "does anything reference
   it" — an invoice snapshots what it needs, a product reads its category name now.
4. **A converted lead cannot be deleted** — it is the origin record of a real customer.
5. **Category web writes use `config.write`**, mirroring the JSON API (categories are a config-module
   master). Only `category.delete` uses the `<entity>.delete` shape, since deletion has no API twin.
6. **Web 404/422 rendering was widened beyond R1.10's letter** — `app/web/errors.py` now also handles
   `RequestValidationError` (a malformed id like `/customers/not-a-uuid` never reaches the service,
   so it needed its own path) and `StarletteHTTPException` (an unrouted web path). API, `/docs`,
   `/health` and `/static` keep their JSON.

**NEXT SESSION:** **Part 2 is complete and tagged `part-02-done`. Start Part 3** (Procurement:
pre-order → PO depth, Phase 2) using the Part 3 prompt in `docs/ROADMAP.md` — 2 checkpoints, one per
session. Read this block + `docs/REQUIREMENTS.md` §5 + the read list above, then the procurement module.
**Do not re-read the list machinery** — the signature block above is what C2 and C3 verified against
source, and Part 3 is domain work, not screen work.

Two things Part 3 inherits and must not break: every new model needs an `app/db/references.py` entry
(even an empty one), and if it adds a status to the PO vocabulary it must decide whether that status is
"open" in `REFERENCES` — a new state that silently stops blocking is R3.7 quietly regressing.

Do **not** re-read the older `docs/` design files, `docs/DELETION-POLICY.md`, or
`docs/MIGRATION-STRATEGY.md` — Part 1 resolved those. Do not re-read `docs/17-design-system.md` §6
either: it specifies the retired TanStack/React table, and its server-side-via-query-params rule is
already what the macros do.

---

## Resume-block template

Copy this at the start of a new part; update it at every checkpoint. Keep only the current part's
block in the `CURRENT WORK` section — move finished parts down into the chronological log below.

```
## Part <n> — <title> · on `main` · checkpoint <i> of <k> · tag when done: `part-0<n>-done`

- [x] **C1** <what it delivered> → commit `<sha>`
- [ ] **C2** <next chunk>

**Requirements passed:**      <IDs verified, e.g. R6.1–R6.6, R6.16>
**Requirements outstanding:** <IDs left>
**Gotchas for the next session:** <signature changes, migrations, half-finished refactors>
**Decisions made mid-part:**     <choices a later session must not silently reverse>

**Changed since last checkpoint:** <paths — paste from `git diff <last-tag>..HEAD --stat`>
**Read for the next checkpoint:**  <the 4–6 files it will actually modify. Be specific.>
**Call, don't read:**              <verified signatures of anything the next checkpoint calls but does
                                    not edit — copy them from the source so they're exact. Four lines
                                    here replaces a 250-line orientation read.>
**Do NOT read:**                   <what CODEBASE-MAP.md already covers; files listed above that
                                    the next checkpoint won't touch; docs already resolved>

**NEXT SESSION:** start at C<i+1>. Read this block + `docs/CODEBASE-MAP.md` + `docs/REQUIREMENTS.md` §<n>,
              then `git diff <last-tag>..HEAD --stat` for the delta. Nothing else.
```

Rules that make the block worth writing:

1. **Commit at every checkpoint**, not at part end. Uncommitted work dies with the session.
2. **Requirement IDs, not prose.** "Did the inventory stuff" is not resumable; "R6.1–R6.6 pass,
   R6.10 outstanding" is.
3. **Record decisions, not just progress.** A later session that silently reverses a mid-part
   decision is the expensive failure mode.
4. **Say what NOT to read.** Resuming sessions burn most of their budget re-establishing context they
   do not need.
5. **Name the files.** `Read for the next checkpoint` is the single highest-value line in the block.
   A session that has to *discover* which four files it needs will read twenty-five finding out.
6. **Keep `docs/CODEBASE-MAP.md` true.** If a checkpoint changes the *shape* of things — a new piece
   of shared machinery, a new pattern, a module that moved — amend the map in the same session. It is
   what lets the next session skip orientation entirely, and it is only worth reading if it's right.

---

## Part 1 — Foundation finish · COMPLETE · tagged `part-01-done` (2026-07-28)

Three checkpoints, three sessions. Delivered the two mechanisms every later part wires into (soft
delete, web authz) plus the migration strategy written down.

- [x] **C1** WS1 — test suite → commit `edf51ea`
- [x] **C2** WS2 — centralized web error handling → commit `edf51ea`
- [x] **C3** WS3 soft delete + WS4 web authz guard + WS5 migration strategy → commit `9670314`

**Requirements passed: R1.1–R1.10, all of them** (§2 of `docs/REQUIREMENTS.md`). R1.1–R1.10 were all
marked outstanding at the start of C3 because WS1/WS2 predated the register, so C3 verified the whole
section rather than just its own workstreams.

| ID | How it was verified |
|---|---|
| R1.1 | One definition: `soft_delete()` in `app/db/soft_delete.py`. `documents` migrated onto it and `DocumentRepository.soft_delete` deleted, so there is no second implementation. |
| R1.2 | Service verb + web POST route + `ui.delete_button` for customers, suppliers, products, tasks, leads, categories. Each POSTed against the booted app: 303, `ok=` flash, row count drops by one. |
| R1.3 | `PROTECTED_TABLES` (16 tables, reason each) + `docs/DELETION-POLICY.md` §3. Tests assert `ConflictError` with a readable message for invoices, bills, payments, sales orders, purchase orders, stock movements — and that a refusal writes no activity row. |
| R1.4 | `require_web_permission` in `app/web/security.py`. Tests drive a permission-less actor: GET → 403 `error.html`; POST → 303 with `err=` flash, and only the referer's *path* is used so an offsite referer cannot pick the redirect target. |
| R1.5 | All **36** web POST routes carry the guard, codes mirroring the API's. `test_every_web_post_route_carries_the_guard` walks the router and fails on any unguarded POST. |
| R1.6 | `soft_delete` writes exactly one `activity_log` row in the caller's transaction; tests assert the count goes 0→1 and that `entity_type`/`summary` are right. |
| R1.7 | Test deletes the seeded customer that has an invoice, then asserts `FinanceRepository.customer_name` still resolves and `/invoices/{id}` still 200s. |
| R1.8 | `docs/MIGRATION-STRATEGY.md` — dev SQLite `create_all` + the additive `_ensure_new_columns` shim (with its rules), prod Postgres via Alembic reintroduced behind `DATABASE_URL` (with the 6-step reintroduction and the "gate `create_all` to SQLite" step). |
| R1.9 | **Already clean on arrival** — longest line in `app/web/pages/settings.py` is 86 chars and `ruff check app/web/` passes. The "~3 E501" in the roadmap was stale; a previous checkpoint had cleared them. No change needed. |
| R1.10 | Verified in the booted app on five URLs. Two gaps found and fixed beyond the letter of the requirement: a **malformed** uuid returned a raw JSON 422 (FastAPI rejects it before the handler), and an **unrouted** web path returned raw JSON 404. Both now render `error.html`; API/docs/health/static keep JSON. |

**Verify loop at close:** 82 tests passing (43 baseline + 39 new); `ruff check app/ tests/` at exactly
the 39 pre-existing findings, zero new; app boots; all 17 nav pages 200.

**New files:** `app/db/soft_delete.py`, `app/web/security.py`, `tests/test_soft_delete.py`,
`tests/test_web_authz.py`, `docs/DELETION-POLICY.md`, `docs/MIGRATION-STRATEGY.md`.

**Scope held (G17):** no roles/permissions UI was built — D-B says the guard is a no-op with one user
and the mechanism existing is the whole point. No batch/lot, no FIFO, no notifications, no saved views.

---

## Stack Lightening — Postgres→SQLite + Next.js→Jinja (2026-07-23)

Goal: make ApexOS as light to run as the sister project **OrdeRR** — one command,
no database server, no frontend build. Delivery-layer only; **no business logic or
service behavior changed.** Done in two commits.

### Phase 1 — Postgres + Alembic → SQLite
- `database_url` default is now `sqlite:///./apexos.db` (still `DATABASE_URL`-overridable,
  so PostgreSQL remains a drop-in for production).
- Engine adds `connect_args={"check_same_thread": False}` conditionally for SQLite.
- All Postgres-only column types made dialect-agnostic: `PGUUID(as_uuid=True)` → `Uuid()`
  (17 model files), `JSONB` → `JSON` (activity, config), `ARRAY(String)` → `JSON` (identity
  `permission_codes`).
- **Alembic removed entirely** (`alembic/`, `alembic.ini`, the `alembic` dep, `db.ps1`).
  The schema now self-initializes: `app.main`'s lifespan imports every model and calls
  `Base.metadata.create_all(engine)` on startup (also still run by `app.seed`). A fresh
  `apexos.db` bootstraps itself.
- De-Postgres'd infra: `docker-compose.yml` (dropped the Postgres service), `Dockerfile`
  (dropped `libpq`/`psycopg` build deps), `.env.example`, `start.ps1`, run docs; removed
  `psycopg` from `pyproject.toml`.

### Phase 2 — Next.js SPA → server-rendered Jinja2
- New web layer at `apps/api/app/web/` (mirrors OrdeRR): `pages/*.py` route handlers call the
  existing domain **services directly** (never over HTTP) and render `templates/*.html`;
  shared plumbing in `core.py` (Jinja env + money/date/status filters + `render`/`redirect`
  helpers), `templates/base.html` app shell + sidebar nav, `_macros.html`, and `static/app.css`.
  Routers are auto-discovered by `app.web.build_web_router` and mounted at root by `app.main`;
  `/static` serves assets. Added `jinja2` to `pyproject.toml`.
- Recreated every former page for parity (17 page modules): dashboard, sales (list/new/detail
  + confirm/fulfill/invoice), customers (+detail), leads (+convert + opportunity pipeline),
  products, categories (+reparent), inventory, warehouse (transfer/adjust/count), procurement,
  purchase-orders (list/new/detail + confirm/receive/bill), suppliers (+detail + evaluate),
  finance (invoices/bills + payments + detail), reports (run + CSV export), analytics, tasks
  (+complete), documents (upload/download), settings (masters/warehouses/tax-rates/config).
  Forms POST to server routes → call service with the current actor → 303 redirect (PRG).
- **Deleted `apps/web/` entirely** (Next.js SPA, npm/TS build, and the hand-maintained TS DTO
  layer — the biggest source of drift bugs). No npm/node anywhere in the run path.

### Run it now — one command
```bash
cd apps/api
pip install -e ".[dev]"          # once
python -m app.seed               # optional: demo data (also self-creates apexos.db)
uvicorn app.main:app             # UI at http://localhost:8000/ , API docs at /docs
```
No Postgres, no `alembic upgrade`, no `npm`. See `RUNNING.md` / `QUICKSTART.md`.

> Note: the deeper design docs under `docs/` (deployment/backup strategy, ER migration order,
> build-phases) still describe the original Postgres+Alembic+Next.js design and are retained as
> historical design record; production can still target PostgreSQL via `DATABASE_URL`.

---

_Historical log below (pre-lightening; references to Alembic migrations, `apps/web`, and
`npm` predate the changes above)._

## Phase A (Buy side) — CODE REVIEWED, awaiting E2E verification (2026-07-22)

Reviewed the pre-existing, never-run buy-side code against the Phase A spec
(`docs/BUILD-PHASES.md`) and the architectural rules. **Verdict: complete and
correct as written; no code changes were needed.** It faithfully mirrors the
verified Sales spine. Detailed checks performed (all pass):

- **Backend modules** `suppliers`, `procurement`, `pricing` (buy), `finance` (bills)
  each have model/repository/service/router/schemas mirroring Sales. Buy loop:
  `PurchaseOrderService.create/confirm/bill` + `GoodsReceiptService.receive`
  (posts IN movement via the single `InventoryService.record_movement`; partial
  receipts accrue `qty_received`). `BillService.add_payment` writes a
  `direction="out"` payment allocated to the bill. One `activity_log` row per
  state change, in-transaction.
- **Migration** `0002_procurement_buy_side` chains `down_revision="0001_initial"`,
  creates the 9 buy-side tables via `metadata.create_all(checkfirst=True)`, and
  conditionally adds `payment.supplier_id` + `payment_allocation.bill_id`. Correct
  for both a fresh DB (0001 already creates the full metadata) and the existing
  33-table Phase-1 DB (0002 backfills). Idempotent.
- **Router wiring** (`app/api.py`) and **metadata registration** (`db/metadata.py`)
  include suppliers + procurement.
- **Seed** (`app/seed.py`) adds 3 demo suppliers, supplier-specific purchase
  prices for the paper SKUs, and a full completed buy loop (PO → confirm → receive
  → bill) with a half-payment to the supplier.
- **Web DTO contract** (`apps/web/src/lib/dto.ts`) matches the FastAPI
  `response_model` shapes field-for-field — incl. the envelope split: `/suppliers`
  and `/purchase-orders` return `{items,...}` (paginated) while `/bills`,
  `/invoices`, `/goods-receipts` return plain arrays; the pages consume each
  correctly. Feature dialogs/forms mirror verified spine components.
- **Nav** flips Suppliers / Purchase Orders / Procurement to `active:true`.

Still **UNVERIFIED** because this machine has no runtime — the test machine must
run migrate + seed, curl the new endpoints (incl. PO confirm→receive→bill and a
supplier payment), and confirm `npm run build` passes. See the test prompt handed
off with this session.

## Phase B (Operations & Config) — CODE WRITTEN, awaiting E2E (2026-07-22)

Migration **0003_operations_and_config** (down_revision 0002) creates `task` +
`document`; everything else reuses Phase-1 tables. Built:

- **Warehouse/Inventory widen** — `StockTransferService.transfer` (two ledger
  movements), `StockAdjustmentService.adjust` + `.count` (cycle count), all via
  the single `InventoryService.record_movement`; `GET /inventory/warehouse-stock`,
  `POST /inventory/transfers|adjustments|counts`.
- **Full Settings CRUD** in config — create/update for the code/name masters,
  warehouses, `CategoryService` (create/update/reparent, cycle-safe),
  `UomConversionService.upsert`, `TaxRateService.set_slab` (versioned),
  `SettingService.set`. All GET+POST/PATCH under the config router.
- **Tasks** module (create/complete/update, polymorphic link) and **Documents**
  module (`DocumentService.upload` → R2 when `R2_*` set, else local-disk fallback
  under gitignored `var/`; multipart upload + list + download). Added
  `python-multipart` dep.
- Frontend: `/warehouse`, `/categories`, `/settings`, `/tasks`, `/documents` with
  dialogs; DTOs added in parity; nav flipped for those five.

## Phase C (Intelligence & Growth) — CODE WRITTEN, awaiting E2E (2026-07-22)

Migration **0004_intelligence_and_growth** (down_revision 0003) creates
`pipeline_stage`, `lead`, `opportunity`, `competitor`, `notification`. Built:

- **CRM** module — leads (create/convert→customer), opportunities
  (create/advance through data-driven stages), competitors; pipeline stages seeded.
- **Notifications** module — push (emits `notification.sent`), list w/ unread
  count, mark read / read-all; a bell + slide-over inbox in the app shell.
- **Reports** (read-only, no entities) — `ReportService.run` with CSV/JSON over
  sales register, purchase register, stock ledger, AR/AP aging, GST summary.
- **Analytics** (read-only) — `AnalyticsService.board`: revenue/purchases, gross
  profit + margin, receivables/payables, DSO, fill rate, 6-month trends, top
  customers/suppliers/products; `/analytics` KPI board with a Recharts trend chart.
- **QuickBooks bridge** — `QuickBooksSyncService` behind `FLAG_QUICKBOOKS`,
  no-ops cleanly when off; manual sync endpoints. No core flow depends on it.
- Frontend: `/reports`, `/analytics`, `/leads` (pipeline board), notification
  inbox; DTOs in parity; nav flipped for Reports, Analytics, and a new Leads item.

**All of B and C are UNVERIFIED (no runtime here).** The test machine must run
`alembic upgrade head` (applies 0003 then 0004), `python -m app.seed`, curl the new
endpoints, and confirm `npm run build` passes. See the handoff test prompt.


## Where the build came from

- **2026-07-19 (session `1b3999ee`, run from `C:\Users\tthopte`):** Built ApexOS end-to-end in one
  autonomous run. Produced the full `docs/` design set (Phase 0), the base scaffold, the initial
  Alembic migration, then fanned out two parallel agents ("backend spine" + "frontend spine") that
  wrote all the code under `apps/api` and `apps/web`.
- **Where it stopped:** during **E2E run/verify**. No Docker on this machine; PostgreSQL 18 is
  installed but `initdb` refused because the shell ran under an **admin token**. The API stream then
  timed out and the session died. **Result: all code was written but never run or verified.**
- **2026-07-20 (this session, run from the project folder):** Recovered the history, resumed the
  unfinished E2E verification.

## Environment (this machine)

- Python 3.12.7, Node 24 — OK. **No Docker.** PostgreSQL 18 installed (binaries only, at
  `C:\Program Files\PostgreSQL\18`), no cluster, no service.
- **Admin-token gotcha:** Postgres refuses to run under an elevated token. Fix that works:
  run `initdb` / `pg_ctl start` via a **Windows Scheduled Task with `/RL LIMITED`** (forces the
  standard non-admin token). `runas /trustlevel` is NOT enough — the bootstrap child still sees admin.
- **Throwaway DB cluster:** initialized in the session scratchpad, **port 5433**, user `apex`,
  trust auth, db `apexos`. This is disposable — see "How to bring the DB back up" below.
- `apps/api/.env` and `apps/web/.env.local` are written pointing at port 5433 / API 8000.

## Status by area

- [x] Design docs (`docs/00`–`17`) — complete
- [x] Backend code (`apps/api`) — all modules written: identity, customers, products, pricing,
      inventory, sales, fulfillment, finance, dashboard, activity, config
- [x] Frontend code (`apps/web`) — app shell + spine pages (dashboard, customers, products,
      inventory, sales list/new/detail, finance)
- [x] Backend deps installed (venv + `pip install -e ".[dev]"`)
- [x] Web deps installed (`npm install`)
- [x] Postgres cluster up (5433) + `apexos` db created
- [x] Alembic migration applied (33 tables)
- [x] Seed data loaded (17 products, 3 customers, 1 order → invoice → part-payment)
- [x] API runs + endpoints verified (E2E backend) — reads, writes, and the full
      order→confirm→fulfill→invoice→payment workflow all return 200 with real data
- [x] Web builds/typechecks + runs — all 10 routes serve live API data, no runtime errors
- [x] Bugs found in audit fixed; **final smoke test green (every page HTTP 200)**

## ✅ E2E VERIFIED — 2026-07-20

The unfinished work from the 2026-07-19 session is complete. The whole stack runs and is verified.

### Bugs found & fixed during E2E (frontend/backend contract drift between the two build agents)

1. **`next.config.mjs`** — removed `experimental.typedRoutes`. It's incompatible with the
   data-driven nav (routes as data, `[module]` catch-all) and blocked the build on every shared
   component. (Confirmed by the frontend audit as the correct fix.)
2. **`apps/web/src/app/(app)/finance/page.tsx`** — `GET /invoices` returns a plain array, but the
   page treated it as a paginated `{items}` envelope → `.reduce` on `undefined` → 500. Now fetched
   as an array.
3. **`apps/web/src/app/(app)/sales/[id]/page.tsx` + `lib/dto.ts`** — backend `SalesOrderDetail`
   serves flat `customer_id`/`customer_name` and **arrays** `fulfillments`/`invoices`; the page
   expected a nested `customer` object and singular `fulfillment`/`invoice` → 500 on
   `order.customer.id`. DTO + page realigned to the real contract (uses `[0]` of each array; also
   `fulfilled_at` → `shipped_at`).
4. **`apps/web/src/features/products/products-table.tsx`** — removed `rowHref` to `/products/[id]`
   (no such route exists; it dead-ended at the `[module]` placeholder).

Backend audit was clean; only a non-blocking Dockerfile layer-ordering nit remains (see below).

## How to run it (verified working on this machine)

> ⚠️ **SUPERSEDED — do not follow these commands.** This section predates the stack lightening:
> Postgres, Alembic and the Next.js frontend are all gone. `alembic` is not installed and
> `apps/web/` no longer exists. For the current one-process SQLite setup see `RUNNING.md`, or the
> fresh-clone steps in the `▶ CURRENT WORK` section at the top of this file. Kept as historical record.

**1. Bring up Postgres** (only if `pg_isready -p 5433` fails — see recipe below).

**2. Backend** (from `apps/api`):
```
./.venv/Scripts/python.exe -m alembic upgrade head      # if DB is fresh
./.venv/Scripts/python.exe -m app.seed                  # if DB is empty
./.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```
Docs at http://localhost:8000/docs · OpenAPI at http://localhost:8000/api/v1/openapi.json

**3. Frontend** (from `apps/web`): `npm run dev` (or `npm run build && npx next start -p 3000`) →
http://localhost:3000

## Known non-blocking follow-ups (not needed to run)

- `apps/api/Dockerfile`: `pip install -e .` runs before `COPY . .`, so the editable package has no
  source at build time. Reorder for container builds. Local run is unaffected.
- `duration-[120ms]` Tailwind class is ambiguous → harmless build warning.
- Products have no detail page (`/products/[id]`) yet — by design (not in the spine).
- Nav modules marked `active: false` (Categories, Warehouse, Procurement, POs, Suppliers, Reports,
  Analytics, Tasks, Documents, Settings) render the "coming soon" placeholder — future work.

## How to bring the DB back up (new session)

The cluster lives in a session-scratchpad dir that may be cleaned up. If `pg_isready -p 5433` fails,
re-create it with the LIMITED-scheduled-task trick (init in a user-writable dir, `-U apex -A trust`,
set `port = 5433`, `pg_ctl start`, `createdb apexos`). See this session's commands for the exact recipe.

## Next steps

1. `alembic upgrade head` → `python -m app.seed`
2. `uvicorn app.main:app` → curl `/health` and `/api/v1/dashboard/summary`
3. `npm run build` (web) → `npm run dev`, verify pages load against the API

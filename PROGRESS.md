# ApexOS — Build Progress

> The source of truth for status. **This file is capped at ~400 lines and does not grow.**
> Closed parts live in `docs/parts/`. A new part's handoff **replaces** the previous one here — never appends.
> (It is 412 today because of the one-off `▶ Move 0` block, which gets archived when Part 4 closes.)

_Last updated: 2026-07-28_

### What belongs in this file

| Section | Rule |
|---|---|
| `▶ NEXT SESSION PROMPT` | Exactly one. The session that closes a checkpoint rewrites it. |
| `▶ Handoff` | Exactly one — the part just closed, pointing at the part about to start. |
| Anything else | Does not belong here. |

**Closing a part archives it.** Move its record to `docs/parts/part-0N.md`, then delete it from this
file, keeping only the `Read for the next part` and `Call, don't read` blocks the next session needs.
This is not tidiness. At Part 3 close this file was **1,212 lines / 90KB — about 22k tokens, re-read at
the start of every remaining session**, and it was growing ~300 lines per part. It was the single
largest avoidable cost in the build.

Where things live now:

- **Setup / how to run** → `RUNNING.md`. Do not restate it here.
- **Closed part records** → `docs/parts/`. Never read during a session; they exist for audit.
- **Resume-block template** → `docs/parts/_resume-block-template.md`.
- **Per-part prompt** → `docs/prompts/part-NN.md` (one file, self-contained).
- **Standing rules, session protocol, checkpoint table, reading diet, verify loop** → `docs/STANDING-RULES.md`.
- **Sequence, dependencies, prompt index** → `docs/ROADMAP.md`. Planning only — a session does not read it.
- **What exists and where** → `docs/CODEBASE-MAP.md`.

---

# ▶ CURRENT WORK — read this first

A **session** is a token budget; a **part** is a group of sessions. The checkpoint list per part is in
`docs/STANDING-RULES.md` → *Session protocol*.

**All work is on `main`** — no feature branches, no PRs. A part is "done" when every P0/P1 requirement
passes, the verify loop is green, this file is updated, and the part is tagged `part-0N-done`. Those
tags are the rollback points.

**Every session ends by updating the block below, before it runs out of room.** A session that dies
with an accurate resume block costs nothing; one that dies without it costs a re-derivation.

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

#### ▶ NEXT SESSION PROMPT — Part 4, checkpoint C1

```
Continue the ApexOS build. Do this in order:

1. git checkout main && git pull origin main && git fetch origin --tags
   (tags don't come down with a plain pull, and the delta command below needs part-03-done)

2. Read the "▶ CURRENT WORK" block at the top of PROGRESS.md. Part 3 is COMPLETE and tagged
   part-03-done. That block's job now is the handoff: "Read for the next part (Part 4)" names
   your edit set, "Call, don't read" carries verified signatures so you don't open those
   modules, and "Do NOT read" is binding. Part 3's two sessions each had this and it is why
   C2 fit in one.

3. Read docs/REQUIREMENTS.md §1 (global invariants G1–G17) and §6 (R5.x — Part 4's acceptance
   contract). NOT optional: the invariants you must not break — integer minor units, exactly
   one activity_log row per state change, derived-never-stored, append-only ledgers,
   InventoryService.record_movement as the only writer of stock_movement — are not in the
   files you're editing.
   Then docs/prompts/part-04.md (the full part brief, ~60 lines, self-contained) and
   docs/STANDING-RULES.md (binding: decisions D-A..D-D, session protocol, reading diet,
   verify loop). Do NOT open docs/ROADMAP.md — it is planning only and costs ~17k tokens.

4. `git diff part-03-done..HEAD --stat` for the delta (empty at session start). For Part 3's
   shape, `git show --stat 3d0162b` (C1) and `git show --stat e62f8bb` (C2). Not a tree walk.

5. Verify the baseline before writing code (from apps/api, venv activated):
     python -m pytest -q                  # expect 336 passed
     python -m ruff check app/ tests/     # expect EXACTLY 37 findings — 38 is a regression
   If either is off, stop and report. 37 is the pre-existing count (32 E501, 4 F841, 1 B007,
   all in untouched modules). It was 38 until Move 0 split app/seed.py into the app/seed/
   package, which removed the last E402. Parts 1–3 added ~10,000 lines with zero new findings.

6. Part 4 is INTELLIGENCE FROM PART 3's HISTORY — arithmetic and data, no ML and no runtime
   LLM call (G12). Two checkpoints; C1 is:
     - R5.1 product↔supplier mapping: a preferred vendor plus alternates.
     - R5.2 vendor score from the EXISTING `supplier_evaluation` plus on-time receipt history.
       `SupplierRepository.latest_score(supplier_id)` and `VendorEvaluationService.score`
       already exist — read them before building a second scorer (G16).
     - R5.3 lead time MEASURED from `PurchaseOrder.confirmed_at` → `GoodsReceipt.received_at`.
       C2 persisted both for exactly this. There must be NO editable lead-time input.
       Note `SupplierQuotation.lead_time_days` is what a supplier PROMISED — never overwrite
       it from a receipt; the promised-vs-measured gap is the point.
     - R5.4 on-time rate with the boundary stated: received exactly on the promised date is
       on time. Write the boundary test.
     - R5.5 MOQ per product+supplier, surfaced in R4.5's comparison grid.
     - R5.6 price history per product+supplier as a timeline.
   C1 also fills R4.5's `score` column, which C1-of-part-3 deliberately left as "unknown"
   with a SCORE_NOTE naming part 4. Replacing that placeholder is yours.

7. G11 is the hard one this part, and it is P0 on every output: every score, rate, lead time
   and recommendation MUST render its inputs, its formula, its data window, and links to the
   records it reasoned from. Where history is insufficient it MUST say "unknown" — never 0,
   never 50 (R5.11, and there is a required test for that path). Part 3 C1 set the pattern:
   a `score=None` plus a note explaining what to compare instead.

8. Three things Part 4 inherits and must not break:
     - R5.10: own FEW OR NO new mutable entities. The product↔supplier mapping and MOQ are
       legitimate new master data; scores, lead times and on-time rates are DERIVED (G7). Any
       stored derivation needs a measured performance problem written into PROGRESS.md.
     - Every new model owes app/db/references.py an entry, even an empty tuple (R3.7) — and
       EXERCISE it with `blocking_references(db, row)` in a test. A Reference names its column
       by STRING, so a wrong one raises AttributeError at check time, not import time. That
       bug hid in the warehouse entry for five checkpoints.
     - R5.9: the recommendation engine gets ONE service entry point. Parts 5 and 10 read it.
       Two implementations of "what should I buy" is the specific failure the ordering of this
       roadmap exists to prevent.
   Extend the seed (G14): R5.13 needs receipt history across ≥2 suppliers so lead time and
   on-time rate are non-trivial, plus one product below reorder level with an open PO and one
   without. app/seed.py is now the PACKAGE app/seed/ — write app/seed/vendor.py with
   `def seed_vendor(ctx: SeedContext)` and add ONE call in core.py's run(), before the
   master-change-history pass (which must stay last). Read app/seed/__init__.py's docstring
   and app/seed/preorder.py (the worked example); do NOT read core.py end to end.

9. Work on main. No branches, no PRs. Commit when the checkpoint is done.

10. BEFORE you run low on context, update the "▶ CURRENT WORK" block: checkpoints with commit
    SHAs, requirement IDs passed and outstanding, gotchas, mid-part decisions, and the four
    delta lines — Changed since / Read for the next checkpoint / Call, don't read (copy
    signatures from source, never from memory) / Do NOT read. Then rewrite the "▶ NEXT
    SESSION PROMPT" above for wherever the next session starts, with its baseline counts.
    Then commit and push. If the checkpoint changed the SHAPE of anything, amend
    docs/CODEBASE-MAP.md in the same session. A stale map is worse than none.

    PROGRESS.md IS CAPPED AT ~350 LINES AND DOES NOT GROW. When you CLOSE a part: move its
    record to docs/parts/part-0N.md and DELETE it from PROGRESS.md, keeping only the "Read for
    the next part" + "Call, don't read" blocks the next part needs. Do not append a new part's
    record below the old one — replace it.

    NAME EVERY NEW TEST AFTER THE REQUIREMENT IT PROVES —
    `def test_r5_3_lead_time_is_measured_from_confirmed_at_to_received_at(...)`. Then a
    requirement's evidence is `pytest -q -k r5_3`, a test node id, NOT a paragraph. Do not
    write per-requirement prose tables; Part 2's was 20 paragraphs restating its own
    assertions. See the naming rule in docs/STANDING-RULES.md.

Use pytest -q, never verbose. Don't re-read files you just edited.

One process note, learned the hard way on 2026-07-28: check `git status` before you start. A
second session was writing this tree mid-build and ~2,300 lines sat uncommitted. One writer
per working tree — parallelise the READING (several read-only scouts at once), never the
writing.
```

**If a session has drifted** and you want a hard reset on scope, ignore the above and paste the whole
```-fenced PROMPT for the part from `docs/prompts/part-NN.md` instead. More deterministic, more typing.

**Rules of thumb.** One checkpoint per session — don't push a session past its checkpoint to "just
finish the part". Start each session fresh (`/clear` or a new window) rather than continuing a long
one. And if a session ends messy, the recovery is `git log --oneline -5` plus the resume block, not
re-reading the design docs.


---

## ▶ Handoff — Part 3 closed · Part 4 starts here

Part 3 (Procurement: pre-order → PO depth) is **COMPLETE**, on `main`, tagged `part-03-done`.

Its full record — the two defects it fixed outside scope, the pre-existing `REFERENCES["warehouse"]`
bug, the requirement-by-requirement evidence, the C1/C2 file lists — is in **`docs/parts/part-03.md`**.
**Do not read it.** Everything a Part 4 session needs is below.

### ▶ Move 0 — the restructuring done between Part 3 and Part 4 (2026-07-28, no feature work)

Parts 1–3 spent a large and growing share of every session re-reading process documents. Measured at
Part 3 close: `PROGRESS.md` 1,212 lines / 90KB and growing ~300 lines per part; `ROADMAP.md` 1,056
lines, which every part prompt instructed the session to read in full; `seed.py` 1,075 lines, which
G14 makes every part extend. That was ~75k tokens of reading before the first edit, 19 sessions still
to go. Move 0 removed it. **Nothing about the product changed — no requirement was altered.**

| Before | After |
|---|---|
| `PROGRESS.md` 1,212 lines, append-only | **363 lines, capped** — closed parts in `docs/parts/` |
| `ROADMAP.md` 1,056 lines, read every session | **147 lines, planning only — do not read mid-part** |
| 12 prompts inside ROADMAP | one file each: **`docs/prompts/part-NN.md`** |
| Rules restated in ROADMAP + 12 prompts | one **`docs/STANDING-RULES.md`** (189 lines) |
| `app/seed.py` 1,075 lines, appended to per part | **`app/seed/`** package, one module per section |
| Requirement evidence = hand-written prose | test named `test_r5_3_...`; evidence is `-k r5_3` |

Three things to know before you start:

1. **All 12 prompts used to hardcode `c:\Imp Data\Personal\apexos`** — a path that does not exist on
   this machine. Fixed in every prompt.
2. **The ruff baseline is now 37, not 38.** Splitting the seed moved `import_all_models()` into
   `app/seed/__init__.py`, so `core.py`'s imports sit at the top of their file and the last `E402`
   is gone. 32 `E501` + 4 `F841` + 1 `B007`. **38 is now a regression.**
3. **Verified at Move 0 close:** 336 tests passing (unchanged), ruff 37, `python -m app.seed` seeds a
   fresh DB and the extracted `seed_preorder` still produces its 3 requisitions, RFQ with 2 quotes and
   the v2 revision with back order 10.

**Read for the next part (Part 4 — vendor intelligence + planning)** — these and nothing else:
- `docs/REQUIREMENTS.md` §6 (R5.x) — the acceptance contract for Part 4.
- `docs/prompts/part-04.md` → the whole prompt for Part 4, and its SESSION PROTOCOL (2 checkpoints).
  Self-contained; do **not** open `docs/ROADMAP.md`. Binding rules: `docs/STANDING-RULES.md`.
- `docs/08-module-breakdown.md` §§ Suppliers/Procurement and Pricing.
- **The edit set:** `app/modules/suppliers/{models,repository,service}.py` (the scorecard that
  already exists — extend it, do not add a second scorer) · `app/modules/pricing/` (MOQ + price
  history per product+supplier) · a new module or service for the recommendation entry point
  (R5.9) · `app/web/pages/{suppliers,products,procurement}.py` + their templates ·
  `app/db/references.py` for any new master · a NEW `app/seed/vendor.py` for R5.13's receipt
  history, plus one call in `app/seed/core.py` (never append to `run()`) ·
  `tests/` — a new file per flow, following `test_po_revisions.py`.
- **Already built, do not rebuild** (G16): `SupplierEvaluation` + `VendorEvaluationService.score`
  (the human scorecard, 1–5 per dimension, `overall_score` appended); `SupplierRepository.latest_score`
  / `evaluation_count`, already on `SupplierRead`; `RfqService.quotation_history`, already on
  `/products/{id}`; and the two timestamps R5.3 needs — `PurchaseOrder.confirmed_at` and
  `GoodsReceipt.received_at`.
- **Do NOT read `preorder.py` (814 lines), `procurement/listing.py`, `web/pages/preorder.py` or the
  requisition/RFQ templates.** Part 3 finished that half. The three functions you might want from it
  are in "Call, don't read" below. Same for `tests/test_preorder.py` and `tests/test_po_revisions.py` —
  they pass; read them only if you change what they cover.

**Call, don't read** — verified signatures from Part 3, copied from source:

```python
# app/modules/procurement/service.py — module level, already used by preorder.py
default_business_unit(db) -> uuid.UUID          # raises NotFoundError if none seeded
tax_bps_for(db, product) -> int                 # the product's default GST rate in bps, or 0
_round_minor(value: Decimal) -> int             # the one money rounding step (G1)

# app/modules/procurement/service.py — the PO chain (C2 added revise + open_qty)
PurchaseOrderService(db).create(payload: PurchaseOrderCreate, *, actor_id) -> PurchaseOrderDetail
PurchaseOrderService(db).confirm(order_id, *, actor_id) -> PurchaseOrderDetail
#   draft -> confirmed. ALSO stamps `confirmed_at` (R4.11) and writes revision 1. One activity row.
PurchaseOrderService(db).revise(order_id, payload: PurchaseOrderRevise, *, actor_id)
#   -> PurchaseOrderDetail. Appends a revision; needs confirmed|partially_received and a non-blank
#   reason. Lines matched BY PRODUCT; omitted lines unchanged; a new product is added. Cannot cut a
#   line below qty_received. Recomputes every line's money with _round_minor (G1).
PurchaseOrderService.open_qty(line) -> Decimal      # STATICMETHOD. ordered − received, clamped at 0.
#   THE definition of "open" (R4.9/G7). GoodsReceiptService.receive calls it too — do not inline a
#   second subtraction anywhere.
PurchaseOrderService(db).bill(order_id, *, actor_id) -> PurchaseOrderDetail
GoodsReceiptService(db).receive(order_id, payload: GoodsReceiptCreate | None, *, actor_id)
#   -> PurchaseOrderDetail. payload.lines=None receives everything outstanding.
#   payload.against_revision_no: if given and NOT current -> ConflictError naming both versions
#   (R4.10). Stamps goods_receipt.purchase_order_revision_id + received_at either way.
#   Posts stock IN via InventoryService.record_movement (the only writer, G8).
_qty_text(value: Decimal) -> str    # "40", not "40.0000" — for service-level messages only

# app/modules/procurement/models.py — C2's two new tables
PurchaseOrderRevision(purchase_order_id, revision_no, reason, subtotal/tax/total_minor)
PurchaseOrderRevisionLine(purchase_order_revision_id, product_id, qty, unit_price_minor, ...)
#   Append-only, NO superseded_at (see C2 decision 2). Current = max(revision_no), derived.
#   `order.revisions` is ordered by revision_no, so order.revisions[-1] is current.

# app/modules/procurement/preorder.py — Part 4 needs only these
RequisitionService(db).convert_to_po(req_id, *, supplier_id, actor_id) -> PurchaseOrderDetail
RfqService(db).award(rfq_id, quotation_id, *, actor_id) -> PurchaseOrderDetail
#   BOTH build a PurchaseOrderCreate and call PurchaseOrderService.create.
RfqService(db).quotation_history(product_id, *, supplier_id=None, limit=50)
#   -> list[QuotationHistoryRow]; a pure read (G15), already on /products/{id}

# app/modules/suppliers/ — the scorecard R5.2 must EXTEND, not replace
SupplierRepository(db).latest_score(supplier_id) -> int | None    # newest evaluation's overall
SupplierRepository(db).evaluation_count(supplier_id) -> int       # both already on SupplierRead
VendorEvaluationService(db).evaluations(supplier_id) -> list[SupplierEvaluationRead]
VendorEvaluationService(db).score(payload: SupplierEvaluationCreate, *, actor_id)
#   SupplierEvaluation carries quality/price/reliability (1–5) + overall = round(mean); append-only.
#   R4.5's comparison grid renders score=None with a SCORE_NOTE naming part 4 — replacing that
#   placeholder is R5.2's job. NOTE the types differ: QuoteComparisonColumn.score is str | None.

# app/modules/inventory/service.py — the ONLY writer of stock_movement (G8)
InventoryService(db).record_movement(*, product_id, warehouse_id, qty_delta: Decimal, reason: str,
    ref_type=None, ref_id=None, unit_cost_minor=None, actor_id=None) -> StockMovement
#   All keyword-only. NOT `post_movement` — that name never existed; the docs said so in 18 places
#   until 0a5af5c corrected them.

# app/modules/config/service.py — document numbers, one implementation
allocate_document_number(db, *, doc_type: str, business_unit_id, on_date: date) -> str
#   row-locked per (BU, doc_type, period) -> "PO-202607-00001". Types in use: PO, GRN, BILL, REQ,
#   RFQ, QUO, SO, INV.

# app/modules/procurement/repository.py
PreorderRepository(db).products_by_id(ids) -> dict[uuid, Product]   # one query for a whole page
PreorderRepository(db).supplier_names(ids) -> dict[uuid, str]
#   ProcurementRepository: .get/.add/.search/.receipts_for/.receipt_rows/.pending_count

# app/web/templates/_preorder.html — the typed SKU picker (both PO and pre-order forms use it)
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

**Gotchas from C2, for Part 4:**
- **`create_all` builds new TABLES but never ALTERs an existing one.** A new *column* on
  `purchase_order`, `supplier`, `product` … needs an `_ADDITIVE_COLUMNS` entry in `app/main.py`
  (~line 45) or it is silently missing on every DB seeded earlier — including the dev `apexos.db`
  carried since Part 1. Get the DDL from what `create_all` emits (`CreateTable(...).compile(sqlite)`),
  don't guess: `DateTime(timezone=True)` → `DATETIME`, `Uuid()` → `CHAR(32)`.
- **`Decimal` from `Numeric(18, 4)` reads back at full scale.** `40.0000` is right for arithmetic and
  wrong in a sentence. Screens have the `number` filter; a *service* message must use
  `_qty_text` — and note plain `.normalize()` is a trap, it turns 40 into `4E+1`.
- **A test can pass without testing anything.** C2 found the R1.5 walk asserting `[] == []` after a
  FastAPI upgrade. Two habits came out of it, both cheap: assert a **floor** on anything you
  enumerate (`assert len(found) > 40`), and **mutation-check** a new suite once — break the
  implementation deliberately and confirm the tests go red. C2's 27 tests fail 10-of-27 when `revise`
  stops appending. If breaking the code doesn't break a test, the test is decoration.
- **`db.get(Product, id)` in a loop is fine; a `select()` per row is not.** SQLAlchemy's identity map
  makes the repeat gets free within a session, which is why `_to_detail` can afford one per line and
  per revision line. A projector that runs a *query* per row is the thing to avoid.
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

**NEXT SESSION:** **Part 3 is complete and tagged `part-03-done`. Start Part 4** (Procurement: vendor
intelligence + planning, Phase 2 second half) using the prompt at the top of this file — 2 checkpoints,
one per session. Read this block + `docs/REQUIREMENTS.md` §6 + the "Read for the next part (Part 4)"
list above, then the suppliers module. **Do not re-read the pre-order half or the PO chain** — the
signature block above was copied from source at Part 3 close, and Part 4 is derivation work over data
that now exists, not document-flow work.

Three things Part 4 inherits and must not break: R5.10 (own few or no new mutable entities — scores,
lead times and on-time rates are **derived**, G7), R5.9 (**one** recommendation entry point, because
parts 5 and 10 read it rather than copy it), and G11 (every number renders its inputs, formula, window
and source records, or says "unknown" — R5.11 has a required test for the insufficient-history path).

Do **not** re-read the older `docs/` design files, `docs/DELETION-POLICY.md` or
`docs/MIGRATION-STRATEGY.md` — Part 1 resolved those. Note `docs/REQUIREMENTS.md` is at v1.2: the
stock writer is `InventoryService.record_movement`, and any older doc naming `post_movement` is wrong.

---



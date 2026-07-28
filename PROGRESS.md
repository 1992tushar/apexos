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

#### ▶ NEXT SESSION PROMPT — Part 4, finishing C1 then C2

```
Continue the ApexOS build. Do this in order:

1. git checkout main && git pull origin main && git fetch origin --tags
   (tags don't come down with a plain pull, and the delta command below needs part-03-done)

2. Read the "▶ CURRENT WORK" block at the top of PROGRESS.md, and in particular the
   "▶ Part 4 — IN FLIGHT" section. Part 4 is HALF BUILT: its engine landed in cf552e3 and
   is green. That section is your brief — the R-number table says what passes and what
   remains, "Call, don't read" carries verified signatures for the services you are about
   to render, and "Do NOT read" is binding.

3. Read docs/REQUIREMENTS.md §1 (global invariants G1–G17) and §6 (R5.x — Part 4's acceptance
   contract). NOT optional: the invariants you must not break — integer minor units, exactly
   one activity_log row per state change, derived-never-stored, append-only ledgers,
   InventoryService.record_movement as the only writer of stock_movement — are not in the
   files you're editing.
   Then docs/prompts/part-04.md (the full part brief, ~60 lines, self-contained) and
   docs/STANDING-RULES.md (binding: decisions D-A..D-D, session protocol, reading diet,
   verify loop). Do NOT open docs/ROADMAP.md — it is planning only and costs ~17k tokens.

4. `git show --stat cf552e3` for what Part 4's engine changed, and
   `git diff part-03-done..HEAD --stat` for everything since Part 3 (that includes Move 0,
   which restructured the docs and split app/seed.py — docs only plus the seed package).
   Not a tree walk.

5. Verify the baseline before writing code (from apps/api, venv activated):
     python -m pytest -q                  # expect 361 passed
     python -m ruff check app/ tests/     # expect EXACTLY 37 findings — 38 is a regression
   If either is off, stop and report. 37 is the pre-existing count (32 E501, 4 F841, 1 B007,
   all in untouched modules). It was 38 until Move 0 split app/seed.py into the app/seed/
   package, which removed the last E402. Parts 1–4 have added zero new findings.

   PART 4 IS ALREADY HALF DONE — the engine landed in cf552e3 and is green. Read the
   "▶ Part 4 — IN FLIGHT" block below FIRST: it lists exactly which R-numbers pass, which
   remain, and the signatures of the services you are about to render. Do NOT rebuild the
   scoring, lead-time, on-time or price-history logic; it exists, it is tested, and G16
   makes calling it mandatory. What is left is mostly TEMPLATES plus the C2 engine.

6. FINISH C1 FIRST — it is screens over services that already exist and are tested. In order:

   a. Add an `explain_panel` macro to app/web/templates/_macros.html that renders one
      `Explained` (app/db/explain.py): the value or "unknown", the formula, the data window,
      the inputs with their weights, and the linked records as <a href>. ONE macro used by
      every output — do not write per-screen markup, that is the duplication R13.1 is
      scheduled to clean up and the whole point of building the shape early.
      A missing input renders its `missing_reason`, not a blank or a zero.

   b. R5.12 supplier detail: score + lead time + on-time rate through that macro.
      R5.12 product detail: the vendor comparison (`ProductSupplierService.list_for_product`
      — preferred first, alternates after) and the price timeline
      (`VendorIntelService.price_history`). The row fields .score/.lead_time/.on_time_rate
      are ALREADY RENDERED STRINGS and may literally be "unknown" — print them, never
      format them as numbers.

   c. POST routes for the mapping: link, set-preferred, unlink. Reuse the part 2 macros and
      the existing page patterns; carry the R1.4 authz guard like the other POSTs (G10).

   d. R5.5 in R4.5's grid: app/modules/procurement/preorder.py builds QuoteComparisonColumn
      around lines 447-508 with `score=None`. Fill it from
      `VendorIntelService(db).score(supplier_id).display` and add the MOQ from
      `ProductSupplierService(db).moq(product_id, supplier_id)`. Then DELETE `SCORE_NOTE`
      (preorder.py:84) and the `score_note` plumbing — it exists only to say "part 4 will
      do this", and leaving it is a lie on the screen. rfqs/detail.html renders both.

7. THEN C2, in this order — R5.9's entry point before anything that calls it:

   a. R5.9 — ONE service entry point. Suggested: app/modules/procurement/recommend.py
        RecommendationService(db).recommend(*, product_id=None, limit=None)
            -> list[Recommendation]
      Parts 5 and 10 CALL this; R7.11 and R13.6 will check for a second implementation.
      Two implementations of "what should I buy" is the specific failure this prevents.

   b. R5.8 — each Recommendation carries a suggested qty and an `Explained` whose formula
      reads like the requirement's own example: "reorder 40 of X — stock 12, reorder level
      50, 0 on open PO, lead time 9 days measured over 6 receipts". Every recommendation
      needs a non-empty explanation and at least one linked record (G11), and the seed has
      both reorder cases waiting: APX-GB-004 is below reorder with nothing on order, and
      APX-GB-003 is below reorder WITH an open PO — the engine must subtract the open
      quantity and not double-order it.
      Reuse, do not rebuild (G16): InventoryService.on_hand(product_id),
      Product.reorder_level, PurchaseOrderService.open_qty(line) — a STATICMETHOD and THE
      definition of open (R4.9/G7) — and ProductSupplierService.preferred_supplier_id.

   c. R5.7 — the procurement calendar on /procurement. "Due to arrive" is confirmed and
      partially_received POs ordered by PurchaseOrder.expected_date (added in C1); "due to
      order" is (a)'s recommendations. A PO with no expected_date is listed as "no date
      promised", never bucketed under today.

8. Constraints that still bind:
     - R5.10: no new mutable entity beyond the mapping + MOQ already built. Scores, lead
       times, on-time rates and recommendations are DERIVED (G7) and stay computed.
     - Any new model owes app/db/references.py an entry, even an empty tuple (R3.7), and
       EXERCISE it with `blocking_references(db, row)` in a test. A Reference names its
       column by STRING, so a wrong one raises AttributeError at check time, not import
       time — that bug hid in the warehouse entry for five checkpoints.
     - G11 is P0 on every output C2 adds, and R5.11's "unknown" path needs its own test.
     - G12: arithmetic only. No ML dependency, no runtime LLM call.
   Seed (G14): the vendor history exists (app/seed/vendor.py). If C2 needs more demo data,
   add it THERE or in a new app/seed/<domain>.py — never by appending to core.py's run().

9. Work on main. No branches, no PRs. Commit when the checkpoint is done — commit after
   step 6 (C1 complete) and again after step 7 (C2), not once at the end. When every P0/P1
   in REQUIREMENTS.md §6 passes: git tag part-04-done && git push origin part-04-done.

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

### ▶ Part 4 — IN FLIGHT · engine done, screens and C2 outstanding

**Landed:** `cf552e3` — the derived half of Part 4. **361 tests passing, ruff 37.** Not tagged;
the part is not done.

| R | State | Where |
|---|---|---|
| R5.1 | ✅ mapping, preferred exclusive per product | `ProductSupplierService` |
| R5.2 | ✅ score 60/40, renormalises, arithmetic exposed | `VendorIntelService.score` |
| R5.3 | ✅ measured confirm→receipt, no editable field | `VendorIntelService.lead_time` |
| R5.4 | ✅ boundary `received <= promised` is ON TIME | `VendorIntelService.on_time_rate` |
| R5.5 | ⚠️ MOQ recorded + tested; **not yet in R4.5's grid** | `ProductSupplierService.moq` |
| R5.6 | ⚠️ timeline computed + tested; **no screen yet** | `VendorIntelService.price_history` |
| R5.10 R5.11 R5.13 R5.14 R3.7 | ✅ | tests + `app/seed/vendor.py` |
| **R5.7 R5.8 R5.9** | ❌ **not started — all of C2** | — |
| **R5.12** | ❌ **not started — the screens** | — |

**What is left, in the order to do it:**

1. **R5.12 screens.** Add an `explain_panel` macro to `_macros.html` rendering an `Explained`
   (what / value-or-"unknown" / formula / window / inputs with weights / linked records).
   One macro, used by every output — do not write per-screen markup. Then: supplier detail
   gets score + lead time + on-time; product detail gets the vendor comparison
   (`list_for_product`, preferred first) and the price timeline.
2. **R5.5 in R4.5's grid.** `preorder.py:447-508` builds `QuoteComparisonColumn`; fill its
   `score` from `VendorIntelService.score(...).display` and add MOQ from
   `ProductSupplierService.moq(...)`. **Delete `SCORE_NOTE` (preorder.py:84)** — it exists
   only to say "part 4 will do this", and it is now wrong.
3. **C2: R5.9's ONE entry point**, then R5.8 on top of it, then R5.7's calendar.
   Suggested shape — `app/modules/procurement/recommend.py`:
       RecommendationService(db).recommend(*, product_id=None, limit=None) -> list[Recommendation]
   Each `Recommendation` carries qty + an `Explained` whose formula reads like R5.8's example:
   "reorder 40 of X — stock 12, reorder level 50, 0 on open PO, lead time 9 days over 6
   receipts". Parts 5 and 10 CALL this; two implementations of "what should I buy" is the
   specific failure R5.9 exists to prevent.
   Reuse, do not rebuild: `InventoryService.on_hand(product_id)`,
   `Product.reorder_level`, `PurchaseOrderService.open_qty(line)` (a **staticmethod**, and
   THE definition of open — R4.9/G7), `ProductSupplierService.preferred_supplier_id`.
   The calendar's "due to arrive" is confirmed/partially_received POs by
   `PurchaseOrder.expected_date`; "due to order" is the recommendations.
4. Name new tests `test_r5_7_…` / `test_r5_8_…`; `pytest -q -k r5_` is the closeout evidence.

**Three decisions made in C1 that a later part must not undo:**

1. **`PurchaseOrder.expected_date` is an input, not a derivation.** It is the supplier's
   commitment for one order — the boundary R5.4 measures against and the date R5.7 reads.
   R5.3 is NOT violated: lead time is still measured from `confirmed_at` → `received_at` and
   there is a test asserting no lead-time field exists anywhere writable.
2. **`confirm(confirmed_at=…)` and `GoodsReceiptCreate.received_at` are deliberate.** Goods
   received Saturday and keyed in Monday arrived Saturday. This is also the only way the seed
   can fabricate history without UPDATE-ing `goods_receipt`, which G4 forbids.
3. **The vendor score renormalises over available inputs and says so.** A supplier with a
   scorecard but no receipts scores on the scorecard alone, with a caveat on screen. Only when
   BOTH inputs are absent is the score unknown. Inventing 0 or 50 is what R5.11 forbids; being
   transparent about a partial basis is not.

**Gotcha that cost a test:** `APX-GB-003` already carries opening stock from an earlier seed
section, so a hard-coded reorder level of 80 was not "below reorder" once stock was 100.
`REORDER_CASES` now sets the level relative to **measured** `on_hand`. If you add a seed
section that moves stock, that relationship still holds.

**Call, don't read** — Part 4's new signatures, copied from source:

```python
# app/db/explain.py — the ONE shape for every explained number (G11)
Explained(what, value: str | None, formula, window, inputs=(), records=(),
          unknown_reason=None, caveat=None)
#   .is_known  -> value is not None      .display -> value or "unknown"
Explained.unknown(*, what, formula, reason, window="no data", inputs=(), records=())
Input(label, value, weight=None, missing_reason=None)   # .is_missing
SourceRecord(label, href=None)

# app/modules/suppliers/vendor.py — READS ONLY, writes nothing (G15)
VendorIntelService(db).lead_time(supplier_id)    -> Explained   # R5.3, "7 days"
VendorIntelService(db).on_time_rate(supplier_id) -> Explained   # R5.4, "67%"
VendorIntelService(db).score(supplier_id)        -> Explained   # R5.2, "75"
VendorIntelService(db).price_history(product_id) -> list[PriceHistoryRow]
#   PriceHistoryRow(.supplier_id .supplier_name .price_minor .valid_from .valid_to
#                   .is_current .delta_minor)  — oldest first, delta vs that supplier's
#                   previous price, None on its first
VendorIntelService(db).receipts(supplier_id)     -> list[Receipt]
#   Receipt(.receipt_no .po_no .purchase_order_id .confirmed_on .received_on
#           .expected_on) · .lead_days · .is_on_time -> bool | None (None = unpromised)
LEAD_TIME_WINDOW = 12 · WEIGHT_SCORECARD = 60 · WEIGHT_ON_TIME = 40

# app/modules/suppliers/service.py — the WRITE half
ProductSupplierService(db).list_for_product(product_id) -> list[ProductSupplierRead]
#   preferred first, then supplier name. Each row's .score/.lead_time/.on_time_rate are
#   RENDERED strings and may be "unknown" — never format them as numbers.
ProductSupplierService(db).upsert(ProductSupplierUpsert, *, actor_id) -> ProductSupplierRead
ProductSupplierService(db).set_preferred(link_id, *, actor_id)
ProductSupplierService(db).delete(link_id, *, actor_id)
ProductSupplierService(db).moq(product_id, supplier_id) -> Decimal | None
ProductSupplierService(db).preferred_supplier_id(product_id) -> uuid.UUID | None
ProductSupplierUpsert(product_id, supplier_id, is_preferred=False, moq=None, note=None)
#   deliberately has NO lead-time field (R5.3) — a test asserts that

# app/modules/procurement/service.py — changed in C1, both optional
PurchaseOrderService(db).confirm(order_id, *, actor_id, confirmed_at=None, expected_date=None)
GoodsReceiptCreate(lines=None, against_revision_no=None, received_at=None)
```

**Do NOT read:** `app/seed/core.py` (707 lines — read `app/seed/__init__.py`'s docstring and
`app/seed/vendor.py` as the pattern), `tests/test_vendor_intel.py` unless you change what it
covers, `app/modules/procurement/preorder.py` except lines ~440–510 for item 2 above, and any
file in `docs/parts/`.

---

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



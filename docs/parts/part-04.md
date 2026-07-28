# Part 4 — Procurement: vendor intelligence + planning · CLOSED · `part-04-done`

> Archived from `PROGRESS.md` at part close. **Do not read this during a session** — it exists for
> audit. Everything a later part needs is in `PROGRESS.md`'s `▶ CURRENT WORK` block and
> `docs/CODEBASE-MAP.md`.

Phase 2, second half. Two checkpoints, both on `main`.

| Checkpoint | Commit | What landed |
|---|---|---|
| C1 engine | `cf552e3` | Mapping + MOQ, measured lead time, on-time rate, 60/40 vendor score, price history, `app/db/explain.py`, `app/seed/vendor.py` |
| C1 screens | `c98548a` | The `explain_panel` macro, R5.12's two detail pages, the three mapping POST verbs, score + agreed MOQ in R4.5's grid, `SCORE_NOTE` deleted |
| C2 | `6381ecd` | `app/modules/procurement/recommend.py` — R5.9's single entry point, R5.8's recommendations, R5.7's calendar |

**Verified at close:** 402 tests passing (336 at Part 3 close + 66 new), `ruff check app/ tests/`
**exactly 37** — zero new findings across the whole part. Fresh `python -m app.seed` + uvicorn: every
nav page 200s, a bad id renders `error.html`.

## Requirement evidence

Every new test is named after the requirement it proves, so the evidence is a node id rather than a
paragraph. `pytest -q -k r5_` runs the part.

| R | Evidence |
|---|---|
| R5.1 | `-k r5_1` — mapping, exclusive preferred, the three POST verbs end to end |
| R5.2 | `-k r5_2` — 60/40 against hand-computed values, renormalisation, the score in R4.5's grid with its arithmetic |
| R5.3 | `-k r5_3` — measured `confirmed_at`→`received_at`; no writable field in the schema, the table, or the UI |
| R5.4 | `-k r5_4` — `received <= promised` is on time; an unpromised receipt is excluded, not counted as met |
| R5.5 | `-k r5_5` — MOQ per product+supplier, on the product page, in the comparison grid, and raising a recommendation |
| R5.6 | `-k r5_6` — the price timeline, oldest first, delta against that supplier's own previous price |
| R5.7 | `-k r5_7` — five buckets, unpromised never bucketed as today, overdue, a fully received order leaving the calendar |
| R5.8 | `-k r5_8` — the shortfall arithmetic with every term non-zero, an open PO not double-ordered, a draft not counted, the sentence |
| R5.9 | `-k r5_9` — the signature, a source walk proving no second engine, and that the engine writes nothing |
| R5.10 | One new mutable entity in the whole part (`product_supplier`, which R5.10 names as legitimate). Everything else derived |
| R5.11 | `-k r5_11` — unknown on score, lead time, on-time rate, a recommendation's lead time, and a recommendation's supplier |
| R5.12 | `-k r5_12` — each figure on its page **with** formula, window and source records |
| R5.13 | `-k r5_13` — the seeded figures are non-trivial and both reorder cases are visible without paging |
| R5.14 | All five named cases have a test |

## Decisions a later part must not silently reverse

1. **`PurchaseOrder.expected_date` is an input, not a derivation.** The supplier's commitment for one
   order — the boundary R5.4 measures against and the date R5.7 reads. R5.3 is intact: lead time is
   still measured from `confirmed_at`→`received_at` and a test asserts no writable lead-time field
   exists anywhere.
2. **`confirm(confirmed_at=…)` and `GoodsReceiptCreate.received_at` are deliberate.** Goods received
   Saturday and keyed in Monday arrived Saturday. This is also the only way the seed can fabricate
   history without UPDATE-ing `goods_receipt`, which G4 forbids.
3. **The vendor score renormalises over available inputs and says so.** A supplier with a scorecard but
   no receipts scores on the scorecard alone, with the caveat on screen. Unknown only when BOTH are
   absent. Inventing 0 or 50 is what R5.11 forbids; being transparent about a partial basis is not.
4. **`SupplierQuotation.lead_time_days` stays the supplier's claim and is never overwritten from a
   receipt.** The gap between promised and measured is the signal; writing the measurement back would
   destroy it. It surfaces as a caveat on the lead-time panel.
5. **G11 has exactly one implementation.** `app/db/explain.py` holds the shape; `explain_panel` renders
   it; nothing else may render an explanation. R13.1 had scheduled this unification for Part 10 C1 —
   building it here means there is nothing left to unify. Parts 5/7/8/9/10 add outputs, not shapes.
6. **A rendered value is printed, never re-formatted.** `ProductSupplierRead.score` / `.lead_time` /
   `.on_time_rate` and `QuoteComparisonColumn.score` are strings that may literally read "unknown".
   Treating one as a number is the one mistake these screens must not make.
7. **"On open orders" excludes drafts.** `PurchaseOrderService.open_qty` is still THE definition of an
   outstanding quantity (R4.9) and is called rather than re-derived, but a draft is not a commitment to
   a supplier — counting it would suppress advice for goods nobody has ordered. Note this is
   deliberately *narrower* than `references.open_po`, which includes drafts because a draft still
   *reads* the product it names. Two different questions.
8. **A stated MOQ raises the suggested quantity and appears as its own term in the formula.** Ordering
   30 from a supplier whose minimum is 250 is a rejected order, not an order.
9. **A missing lead time does not suppress a recommendation.** Being short of stock is a fact about the
   ledger; how fast the supplier is, is a separate fact. The shortfall stands with the gap named.
   Withholding advice because one input is missing would be worse than advising with a caveat.
10. **An order with no promised date gets its own calendar column.** Never bucketed under today —
    treating "we do not know" as "arriving now" is how a calendar starts lying about the week ahead.
11. **`explain_panel` is a macro, not a component library.** One macro, five call sites, no per-screen
    variants. If a later part needs a different layout for the same data, it changes the macro.

## Gotchas the part hit

- **`APX-GB-003` already carried opening stock from an earlier seed section**, so a hard-coded reorder
  level of 80 stopped being "below reorder" once stock was 100. `REORDER_CASES` sets the level relative
  to **measured** `on_hand`. A seed section that moves stock still holds that relationship.
- **A recommendation list sorted worst-first buries the demo cases.** The catalogue gives ~99 products a
  reorder level of 20 against zero stock, so the two seeded cases needed margins well above that to be
  visible without paging. A demo case on page four demonstrates nothing (G14).
- **Three Part 3 tests asserted the placeholder** (`score is None`, `"part 4" in score_note`, `"unknown"
  in html`). Replacing a placeholder means rewriting its tests, including the API one — which now proves
  a client cannot get the number without the explanation.
- **`Explained` is a frozen dataclass inside a Pydantic response model** (`QuoteComparisonColumn.score_explained`).
  Pydantic v2 validates stdlib dataclasses natively, so it serialises over the API — but `.display` and
  `.is_known` are properties and do **not** appear in the JSON. An API test compares
  `col["score"] == (explained["value"] or "unknown")`.
- **27 new tests passing on the first run is not evidence.** Mutation-checked: dropping the open-order
  subtraction fails 5, counting drafts as on-order fails 1, bucketing unpromised orders under today
  fails 1. If breaking the code doesn't break a test, the test is decoration.
- **`fresh.db` cannot be deleted while uvicorn holds it** (Windows). Stop the process first:
  `Get-CimInstance Win32_Process | Where CommandLine -like '*<port>*' | Stop-Process -Force`.
- **`$pid` is a read-only PowerShell automatic variable** — a scratch script that assigns it dies.

## Scope

Nothing cut by D-A..D-D was built (G17). No ML dependency and no runtime model call (G12). The part
added **one** table (`product_supplier`), which R5.10 names as legitimate new master data; scores, lead
times, on-time rates, price deltas, arrival buckets and recommendations are all derived (G7) and
recomputed per read, so none of them can go stale behind a receipt.

## Handoff to Part 5

R7.11 and R7.13 are the live contract: Part 5 C3's reorder suggestions **call**
`RecommendationService(db).recommend(...)` and a test proves the two return identical output for the
same product. `test_r5_9_no_second_implementation_of_what_to_buy_exists_in_the_app` walks `app/` and
fails if a second `def recommend` appears — including one added by Part 5.

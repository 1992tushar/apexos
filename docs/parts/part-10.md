# Part 10 — Intelligence Layer · the part record

> Audit record. **Do not read this during a session** — `PROGRESS.md`'s `▶ CURRENT WORK`
> block carries what the next checkpoint needs, including the R13.1 audit list itself.

Requirements: `docs/REQUIREMENTS.md` §14 (R13.1–R13.14). Two checkpoints; nothing tagged
(waived for this run), so the SHA table in `PROGRESS.md` is the record.

---

## C1 — the R13.1 audit and the unification it found

**From `4c814b1` → `bdf384b`.** Tests 794 → 818. Ruff 35 → 35.

C1 built no screen, which is the point: the part prompt says *do not skip past C1 to the
visible screens*, because the audit is what stops Part 10 becoming a fourth copy of logic that
already exists three times.

### The finding

`MarginService.gp` is `(unit_price − buy_price) × qty` and reads a **missing** purchase price
as **zero**. So a product nothing has ever been bought for reports its whole selling value as
gross profit — a 100% margin, and the single most misleading number this codebase can produce.

Three places derive gross profit from it. Only `MarginAnalysisService` checked first. The rule
existed — written down in `FinanceRepository.purchase_prices_by_product`'s docstring, which
said in as many words that margin work *must* consult the map before trusting `gp` — and was
implemented once. That is precisely the shape R13.2 exists to catch: not two implementations of
an algorithm, but **one decision made in one place and skipped in two others**.

The decision is now `MarginService.gp_costed(line, *, buy_prices=None) -> int | None`. `None`
means "we do not know what this cost", which is a different fact from "it cost nothing".

### The two divergences were not equally bad

Worth separating, because writing them up as one story would have been its own overclaim.

**`CustomerHealthService.profitability` really was wrong.** An uncosted line was scored toward
a 100% margin, worth up to 30 of the score's 100 points (`WEIGHT_PROFITABILITY`) for a number
nobody measured. That is a G11 violation — a flattering default in place of an unknown — and it
was **recorded rather than fixed** at P8-C3's close, because margin was that part's scope and
this score was not. Part 10 is the part that owns it.

Now: uncosted lines are excluded and counted, and the score says so. A customer with *only*
uncosted lines gets a **missing** profitability input whose reason distinguishes "nothing
invoiced yet" from "none of their N order lines has a purchase price recorded" — because only
the second is something the founder can act on. A customer with a mix reports the margin it
could measure and appends *"excluding 1 line with no purchase price"*.

The seed cannot produce this case: `SKU-NOBUY-01` sits on invoices, and `profitability` reads
sales-order lines. So the test constructs it, on a customer it creates itself.

**`CashFlowService._cogs` was right by coincidence, and this nearly got overclaimed.** The
first draft of the docstring and the commit message said it understated COGS and therefore
inflated DIO. Driving the numbers side by side showed otherwise: an uncosted line's `gp` comes
out **equal to its own subtotal**, so `subtotal − gross` contributed exactly zero to cost —
which is also what excluding the line contributes.

| Over the seeded 90-day window | Before | After |
|---|---|---|
| Cost of goods sold | 14,691.95 | **14,691.95** |
| DIO | 8,283 days | **8,283 days** |
| Uncosted invoice lines disclosed on the DIO panel | — | **2** |

Routing it through `gp_costed` is still worth doing, for two reasons that are not about
today's figure: the answer stops depending on the coincidence that `gp` and the stored subtotal
agree (they diverge the moment a line is discounted after its unit price is set), and the count
now reaches the DIO panel, which is new information a reader of that figure needed (R13.10).
The docstrings and the test both say plainly that no number moved.

### The R13.1 audit list

The deliverable lives in `PROGRESS.md`'s `▶ CURRENT WORK` block, per the requirement. In
summary: **23 outputs across parts 4–9**, of which one was duplicated (above), four were
already unified, and one pair looks duplicated but is not.

**Already unified — recorded, not rebuilt.** R13.1 had some of these scheduled as Part 10
unifications; they were done earlier and the honest audit says so and moves on:

* **G11 is one `Explained`** in `app/db/explain.py`, rendered by one `explain_panel` macro,
  built in Part 4 and adopted by Parts 5–9.
* **R13.6's reorder engine is one `def recommend`.** `InventoryHealthService.reorder_suggestions`
  is a bare delegation, and Part 5's `test_r7_13_...` already proved identical output.
* **`recommend.py:_lead_time` is a memoising delegation** to `VendorIntelService.lead_time` —
  it *looks* like a duplication (two `-> Explained` lead-time methods) and is not. Telling
  those apart is the audit's job.
* **`InventoryRepository.consumption` is one definition of demand**, shared by ABC, dead stock
  and movement rates.
* **THE receivable and THE payable** are still the `outstanding_by_*` pair; nothing has crept
  back since Part 8 removed three second definitions.

**Deliberately NOT unified.** `InventoryHealthService.low_stock` fires on **available** (on
hand minus reserved) because stock committed to an order cannot cover a new one (R7.10).
`RecommendationService` computes a shortfall against **on hand plus on order** because a
purchase order already placed must not be placed twice (R5.9). They can legitimately disagree
about whether a product is short. Two different questions are not one question answered twice,
so R13.2 does not apply — and a test asserts each still carries the term the other does not, so
a later session reads the reasoning before "fixing" the discrepancy.

### Also moved

`purchase_prices_by_product` now lives on `PricingRepository`, which owns `PurchasePrice`;
Part 8 built it on `FinanceRepository` when finance was its only consumer, and the audit found
three consumers in three modules. Finance's method is a bare delegation, so Part 8's callers
and tests are untouched. `leakage` stopped making the costable-line decision inline
(`buy is not None`) and calling `gp` twice.

### The guards

All parsed with `ast`, never grepped — a text search cannot tell a call from a mention, and
this build has already had a source-walk test fail on its own docstring:

* only `MarginService` may call `gp`; everything else uses `gp_costed`,
* exactly one `def recommend` in `app/`,
* exactly one `Explained` and one `Input`,
* one `default_window` and one `month_starts`,
* **no table stores a DERIVED score.**

That last one found something worth keeping. `supplier_evaluation` holds `quality_score`,
`price_score`, `reliability_score` and `overall_score` — and that is **correct**: it is the
founder's own hand-entered 1–5 scorecard, which `VendorIntelService.score` consumes at 60%
weight. A score somebody **typed** is data; a score the system **worked out** is not, and only
the first may be stored. The exemption is named, and a second test pins the scorecard's shape
so the exemption cannot quietly become a loophole.

### Verification

* `pytest -q` → **818 passed** (794 + 24). `-k r13_` is Part 10's evidence.
* `ruff check app/ tests/` → **35**, unchanged. Ten parts, zero new findings.
* **Mutation check — seven mutations, all red:** `gp_costed` stopping refusing an uncosted
  line; customer health back on raw `gp`; `_cogs` back on raw `gp`; the margin report no longer
  excluding; an empty purchase-price map; a second `def recommend`; a derived score column.
* **Real app driven** on uvicorn: 42 links all 200, and the DIO panel's new excluded-lines row
  confirmed on screen rather than only in a test.

### Two things fixed in the tests themselves, worth carrying forward

**A fixture whose isolation depends on other tests is not isolated.** The first draft took the
last customer in code order on the theory nothing else touched them. It passed alone and failed
in the full suite, because `client.post` COMMITS and an earlier test had left sales orders on
that customer. It now creates its own customer through `CustomerService` and rolls back.

**`Path.relative_to` yields backslashes on Windows**, so three of the AST guards compared
against posix-form strings and matched nothing — a source walk that finds nothing looks exactly
like a pass. They use `.as_posix()` now, and the one with an allow-list says why in a comment.

### Left for C2

Everything visible: R13.4's radars (dead stock, margin leakage, customer churn risk), R13.5's
cockpits (working capital, category performance, business-unit performance), R13.7/R13.8's
forecasts (purchase, sales, cash requirement — trailing-window, window stated, confidence said
out loud) and R13.9's Founder Morning Brief, which must be a **view** over the other outputs
with no new business logic. R13.3 is satisfied by consolidation rather than new code: the three
scores exist and C2 surfaces them together.

**Churn risk is the one radar with no engine behind it yet.** Dead stock and margin leakage
both have owners (`InventoryHealthService.dead_stock`, `MarginAnalysisService.leakage`); churn
does not, and `CustomerHealthService.recency` is the nearest thing. C2 should build it in the
part that owns customers, not in the radar screen.

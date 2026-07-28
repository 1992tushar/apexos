# The Parts 5–7 E2E gate

**Result: clean.** 44 checks, all passing — 28 on the cross-part trail, 16 driving the real
POST forms. One check failed on the first run; it was a **miswritten assertion in the gate
script**, not a product defect, and the detail is recorded below rather than quietly fixed.

Run on a **fresh database** (`DATABASE_URL="sqlite:///./e2e.db"`, seeded from scratch) against
a live `uvicorn` on port 8025. Not to be read during a session.

## What this gate was for

Every requirement in Parts 5–7 already had passing tests. The gate exists to check the thing
no test checks: that the parts **join up** — that a receipt into a bin actually moves the
weighted-average cost the valuation screen shows, that confirming an order really reserves the
stock the inventory screen reports as unavailable, that a return leaves the invoice the
customer holds untouched while the receivable falls.

## How it was driven — and what that does and does not prove

| | What was done | What it proves |
|---|---|---|
| **Pass 1** (28 checks) | State changes through the **services**, figures read back through the same read paths the screens use, then every screen fetched over HTTP and checked for its sections | The trail joins up; the screens render what the services produce |
| **Pass 2** (16 checks) | The real **POST forms** submitted over HTTP — order entry, quotation send/revise/convert, count sheet open/record/close, adjustment, contact, credit terms | The buttons work, not just the markup |

**Stated plainly: this was driven over HTTP, not clicked in a browser.** Every assertion is
about a status code, a redirect, a rendered fragment or a database figure. Nobody looked at the
pixels. Layout, focus order as *experienced*, and whether the screens feel fast are not covered
— R9.12's acceptance is a manual walkthrough and that remains outstanding as a human task.

## The trail, with the numbers it produced

**Buy side.** R5.9's engine returned 5 recommendations, each with a plain-language sentence
("reorder 100 of Bin Liner Small — stock 100, reorder level 160, 0 on open PO, lead time …").
A receipt of 25 into bin `A-01` took on-hand **81 → 106**, moved the weighted-average cost
**94.29 → 106.07** (the receipt was deliberately dearer), landed in an age bucket, and rolled
up correctly bin **25** ≤ rack **25** ≤ warehouse **14,543**.

**Operations.** A dispatch of 4 left **total** on-hand unchanged at 198 while reporting 10 in
transit — R7.5's whole point, that stock in flight is never invisible. Receiving cleared 4 of
it. A count sheet with one varying line posted **exactly one** movement (−1); the seeded
zero-variance sheet posted **none** (R7.2).

**Sell side.** A quotation was raised at 900.00, sent, then revised to 850.00 — **v1 still
reads 900.00** and v2 reads 850.00, both on screen. Converting produced an order at **850.00**,
the latest quoted price, not the list price. Confirming reserved 6 (**reserved 8 → 14**) with
**on-hand unchanged at 198**. Fulfilment consumed the reservation *and* shipped the stock
(reserved → 8, on-hand → 192). A partial return of 2 raised credit note `CRN-202607-00002`,
left the invoice **identical column-for-column**, dropped the receivable **6,018.00 →
4,012.00**, and left **4** still returnable.

**Credit and health.** A deliberately tiny limit produced a refusal naming all four numbers
("limit 1.00, currently outstanding 590.00, this order 500.00 — short by …"). The health score
rendered at 76 with all four inputs and their weights.

**Errors.** A random UUID on a detail route returned **404** with `error.html`. All 14 nav
pages returned 200.

## The one failure, and why it is recorded rather than erased

The first run reported `R7.3 exactly one adjustment was posted — 0 posted`.

`CycleCountService.detail(count_id, *, adjustments_posted=0)` only carries that count when
`close()` passes it in. Calling `detail()` fresh therefore **always** reports zero. The gate
was asserting on a field that cannot answer the question.

A direct query settled it: the seeded variance count had 1 movement (−2), the seeded clean
count had 0, and the gate's own count had 1 (−1). **The behaviour was right; the check was
wrong.** It now asserts on the `stock_movement` ledger instead, which is where the answer
actually lives, and passes.

Worth keeping because it is the same species of error this build has hit repeatedly: a test
that reads a *convenience field* rather than the *source of truth* can be confidently wrong in
either direction.

## Outstanding after this gate

* **R9.12's manual walkthrough** — a human keyboarding a real order. The keystroke counts in
  `docs/parts/part-07.md` are measured against the rendered form, but "does it feel fast" is
  not something this gate can answer.
* **Nothing else.** Parts 1–7 are complete: 623 tests, `ruff` at exactly 37 findings — the
  pre-existing count, unchanged across all nine checkpoints of this run.

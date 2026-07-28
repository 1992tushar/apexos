# Part 7 — Sales: workflow completion + speed (Phase 4, second half)

**Status: COMPLETE.** Every P0/P1 in `docs/REQUIREMENTS.md` §10 (R9.x) passes. Not to be read
during a session — it exists for audit.

| Checkpoint | Commit | What landed |
|---|---|---|
| C1 | `eeae971` | Quotation: create / send / revise / expire / convert, append-only revisions |
| C2a | `27d1c49` | Reservation wiring (confirm / fulfil / cancel), returns, credit notes |
| C2b | `761e9aa` | Customer health score, R9.15's partial return |
| C2c | (this commit) | Fast order entry, and R9.13's keystroke measurement |

**No tags** — waived for Parts 5–7, so these SHAs are the record.

**Verified at close:** **623 tests passing**, `ruff check app/ tests/` **exactly 37** — zero new
findings across the whole part. Evidence: `pytest -q -k r9_` (**78 tests**). Fresh seed + uvicorn:
every nav page 200s, the quotation flow walks create → send → revise → convert, a return raises
its credit note without touching the invoice, and the order form prefills a repeat order.

---

## R9.13 — the keystroke measurement, as measured

**A 5-line repeat order, keyboard only, no mouse.** Counted against the rendered form, not
estimated from source.

| | Before | After |
|---|---|---|
| Reach the first field (19 focusable sidebar links + 1 header link, no `autofocus`) | **20** | **0** |
| Customer (type leading letters in the `<select>`) | 2 | 2 |
| Skip the order-date field | 2 | — |
| 5 lines × (SKU + qty + skip price) | **75** | — |
| Load their last order (Tab, Enter) | — | **2** |
| Submit (Enter in any field submits) | 1 | **1** |
| **Total** | **~100** | **5** |

Two things account for almost all of it, and neither is clever:

1. **`autofocus`.** Without it the caret starts outside the form and the founder tabs past
   nineteen sidebar links to reach the first field. That was a fifth of the whole cost.
2. **The product chooser was a `<select>` holding every product.** Part 3 identified this exact
   anti-pattern for requisitions and fixed it there with a `<datalist>`; the sales form never
   got the same treatment. Typing a SKU into a 268-option `<select>` means typing the full code
   because every option shares the `APX-` prefix — ~10 keystrokes per line, 50 of the 75.

**The honest caveat:** the 5 figure is the *repeat* path, which is what R9.13 specifies. A
**manual** 5-line order is **~100 → ~55**: `autofocus` saves the 20 tabs, and the datalist makes
each SKU ~6 keystrokes instead of 10 (type "GB-001", Down, Enter) — better, but not
transformative. The large win comes from not re-typing an order the customer has placed before,
not from making typing faster.

---

## Six decisions a later part must not reverse

1. **Quotation revisions mirror Part 3's append-only shape** (`revision_no`, no
   `superseded_at`), not Part 6's `valid_from`/`valid_to`. A credit policy is a *period*; a
   quotation is a *sequence of offers*. **Two versioning idioms is the limit.**
2. **`revision_no` 1 is written by `send`**, not `create`, and `revise` requires a *sent*
   quotation — a draft nobody has seen has no agreement to preserve (R4.7's reasoning).
3. **Conversion passes the quoted `unit_price_minor` explicitly** and calls
   `SalesOrderService.create`. Re-resolving would honour today's list price instead of what the
   customer agreed. The quotation's doc type is **`SQT`**, not `QUO` (Part 3's *supplier*
   quotation) — sharing it would interleave two unrelated number sequences.
4. **Reserve runs AFTER the credit gate**, and a refused confirm leaves NO reservation. On
   fulfilment, consume runs BEFORE the outbound movement: the other order would briefly show
   the units as both reserved and gone, and `available` (on-hand − reserved) would
   double-count them. Cancel refuses a fulfilled order — shipped stock is undone by a return.
5. **The invoice is never mutated by a return** (G4/R9.5). The receivable falls because
   `CustomerRepository.outstanding_minor` subtracts credit notes:
   `Σ invoice − Σ allocations − Σ credit_notes`. **Anything computing a receivable must call
   that method rather than re-deriving it.** A credit note carries no lines; the return holds
   them.
6. **"Never invoiced" is a MISSING health input, not perfect payment behaviour.** Collapsing
   the two made a brand-new customer score **100** — worse than the default R9.11 forbids,
   because it reads as praise for someone nobody has traded with.

## What the mutation checks found

Eleven mutations across the four checkpoints; every one was caught, and two of them found real
defects rather than merely confirming a test.

* **C2b's health score genuinely scored a new customer 100.** My own test caught it: "owes
  nothing" counted as full marks on payment, payment was then the only measurable input, and
  renormalisation handed it the entire weighting. Two of my own tests had to be corrected
  afterwards because they had been written against the wrong behaviour.
* **A source-walk test failed on its own docstring.** The "hints are bulk reads" test asserted
  `"resolve_selling_minor" not in src` and matched a *mention* in prose. Rewritten to count
  actual SQL statements with a SQLAlchemy event listener — which is what it was trying to
  measure all along. **A text match cannot tell a call from a comment.**

## Three traps this part hit, all worth carrying forward

1. **`uuid7()` is not monotonic within a millisecond.** It fills its low bits from
   `os.urandom`, so `ORDER BY (timestamp, id)` cannot break a same-millisecond tie — a
   tiebreaker this build had been treating as total since Part 5. Product code was fine, but
   two Part 6 tests read "the newest activity row" and were flaky; they now select by verb.
   Notes additionally stamp `created_at` explicitly at microsecond resolution, because the
   whole-second server default let the list flip order between page loads.
2. **Seeding or creating a document in an OPEN status breaks unrelated tests.** Part 6 did it
   with a *confirmed* order, C1 with a *draft* one (draft counts as open too), and C2c with
   test-created draft orders. All three broke the same two Part 1/3 tests that encode "the
   first customer's work is all closed".
3. **`client.post` commits; `db`-fixture writes roll back.** That is why C2c's own tests
   polluted the database where earlier service-level tests had not. Tests that POST need a
   subject no other test asserts about — see `test_fast_entry.py`'s `spare_customer` fixture.

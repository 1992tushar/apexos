# Part 9 — Founder Command Center · the part record

> Audit record. **Do not read this during a session** — `PROGRESS.md`'s `▶ CURRENT WORK`
> block carries what the next checkpoint needs. This exists so that block does not have to.

Requirements: `docs/REQUIREMENTS.md` §13 (R12.1–R12.15). Two checkpoints; nothing tagged
(waived for this run), so the SHA table in `PROGRESS.md` is the record.

---

## C1 — tiles · alerts · activity · quick actions

**From `c316861` → `45b8218`.** Tests 757 → 786. Ruff 35 → 35.

### What was built

`app/modules/command_center/` — a projection module that owns **no entity, no table and no
arithmetic**. `CommandCenterService.load(*, as_of=None)` makes thirteen calls to the parts
that own each number and arranges the answers into R12.1's three questions, in order.

| Section | Figures | Read from |
|---|---|---|
| **What happened** (R12.2) | revenue today · gross margin today · collections today | `MarginAnalysisService.by_dimension` over a one-day window (both money figures off ONE report, so they cannot disagree about which lines they counted) · `CashFlowService.cash_flow` |
| **Position** (R12.4) | net cash last 90 days · committed next 90 days · working capital | `CashFlowService.cash_flow` · `.committed` · `.working_capital` |
| **What needs attention** (R12.3) | receivables · payables · inventory value · POs pending · SOs pending · deliveries due | `AgeingService.ar_ageing`/`.ap_ageing` · the working-capital snapshot's inventory term · `ProcurementRepository.pending_count` · `SalesRepository.pending_count` · `ProcurementCalendarService.arrivals` |
| **Alerts** (R12.3, R12.8) | customers to chase · deliveries past promised date · products below reorder level · one per fired leakage indicator | `AgeingService.collections` · `.arrivals` · `InventoryHealthService.low_stock` · `MarginAnalysisService.leakage` |
| **What should I do now** (R12.6) | new sales order · new PO · record a payment · receive stock | four links, each with the reason it earned its place printed beside it |
| **Recent activity** (R12.5) | last 10 rows | `ActivityService.recent` |

Edit set: `app/modules/command_center/{__init__,schemas,service}.py` ·
`app/web/pages/command_center.py` · `app/web/templates/command_center/index.html` ·
`app/seed/command_center.py` + one call in `app/seed/core.py` · `tests/test_command_center.py`
· four lines of CSS · **deleted** `app/web/pages/dashboard.py` and
`app/web/templates/dashboard/`.

### Two requirements made structural rather than reviewable

Both are validators on the schema, so a tile or alert added in six months cannot forget:

* **R12.7** — `Figure` raises unless `href` starts with `/`. There is no unclickable number
  on the page, and the test asserts each href is *rendered* and *resolves*, because Part 8
  C1 shipped an href that was built and never rendered.
* **R12.8** — `Alert` raises on empty `records`, and raises again if `count` is smaller than
  the list it carries. "An alert with nothing to click MUST be removed" is therefore
  enforced by the constructor; a family that finds nothing is omitted and the page says
  "nothing needs attention", which is information, rather than showing confident zeros.

### The two defects this checkpoint found

Neither was visible in the tests. One came from measuring, one from driving the real app.

**1. `InventoryHealthService.low_stock` was reading the whole catalogue per row.** It called
`self.inventory.stock()` — a grouped read of all 311 products — *inside* its loop over
`states()`, then linearly scanned the result. 274 queries and 979 ms, out of a 344-query,
1,096 ms homepage. The reorder levels are now read once into a dict (`setdefault` keeps the
first row per product, exactly what the `next(...)` it replaced selected). The method is
**4 queries and 13 ms**, and `/inventory` had been paying the same bill since Part 5.
`test_r7_10_low_stock_reads_the_reorder_levels_once` counts statements so it cannot return.

**2. The committed-cash tile was labelled "next 90 days" over trailing data.**
`CashFlowReport.committed` covers the same window as its actuals — right on a cash-flow
report, wrong on a homepage, where money whose due date has already passed is not what the
label claims. It now calls `CashFlowService.committed` for `[today, today + 90]`. The test
asserts the figure equals the forward window **and differs from the trailing one**, because
an equality assertion between two code paths only tests what the current data distinguishes.

### Measurement (R12.12, R12.14 — C2 owns the write-up; these are C1's numbers)

Measured against **uvicorn over real HTTP**, seeded dataset, not a TestClient:

| | Before the `low_stock` fix | After |
|---|---|---|
| Queries for one page load | 344 | **81** |
| Warm render, median of 5 | 1,096 ms | **59 ms** |
| Cold first request | — | 190 ms |

81 is thirteen grouped projections of 1–14 queries each, **none of which grows with the row
count** — that is the property R12.12 is protecting, not the absolute number. The seed has
311 products, 273 stock states, 86 low-stock rows and 4 overdue customers, so any per-row
read lands in the hundreds. `QUERY_CEILING = 120` in the test is deliberately loose for
that reason: a ceiling tight enough to fail on one added figure gets re-litigated every
checkpoint and eventually raised without measuring, which is worse than one that still
catches what it is for.

**What the measurement does not cover:** it is one count on one dataset. It proves the page
does not read per row. It does not prove any individual query is fast, and it says nothing
about a dataset an order of magnitude larger.

### Seed (G14) — `app/seed/command_center.py`

One invoice **dated today, settled in full today**, on the customer at code-order offset 9
(nothing else asserts about them). Why it was needed: `Payment.paid_at` defaults to `now()`,
so every seeded receipt is already dated today and *collections today* had a real figure —
but every seeded invoice is placed by offset from its due date and the newest lands 30 days
ago, so *revenue today* and *gross margin today* were ₹0.00. A headline section of three
zeros cannot fail visibly when the arithmetic behind it is wrong.

Two lines, on purpose. The second is on `SKU-NOBUY-01`, the priced-but-never-purchased
product Part 8 C3 seeded, so the page's "1 line today has no purchase price and is excluded
from both revenue and margin" caveat appears on the demo rather than only in a test.

Settled in full so the addition touches nothing it has no business touching: it never
appears on an ageing screen, never joins the chase list, and leaves the receivable exactly
as it was. It is priced at list, so it adds no leakage offender — C3's two indicators must
keep firing on exactly the three lines seeded for them.

Reuses `_make_invoice` / `_pay_invoice` / `_totals` from `app/seed/finance.py` rather than
writing a second invoice path into the demo data; the tax rounding has to be identical
everywhere (G1).

### Verification

* `pytest -q` → **786 passed** (757 + 29 new, every one named after the requirement it
  proves; `-k r12_` is the evidence for Part 9).
* `ruff check app/ tests/` → **35**, unchanged. Nine parts, zero new findings.
* **Real app driven**: uvicorn on port 8040 against a freshly seeded scratch DB. 12 tiles
  rendered, 5 alert cards, **42 links on the page, all 200**, no empty table bodies, no
  `<svg>` / `<canvas>` / chart marker.
* **Mutation check — five mutations, all went red:** letting an alert fire with no records;
  reporting 0 where the margin is unknown; pointing the receivables tile at the payables
  list; swapping the AR and AP totals; restoring `low_stock`'s per-row read.

### One gap C1 closed that the seed could not reach

Today's margin *is* known on the seeded data, so G11's insufficient-data path would have
shipped untested — and it is the branch that matters most, since `MarginService.gp` reads a
missing purchase price as zero and reports a **100% margin**.
`test_g11_a_day_with_no_costed_line_reports_unknown_not_zero` drives `_what_happened`
directly with a stub whose `margin_bps` is `None` and asserts the tile renders the word
"unknown" as text, never a money-formatted zero.

### Left for C2

R12.11's remaining half (`app/modules/dashboard/` — `repository.py` 58, `router.py` 16,
`schemas.py` 38, `service.py` 89 — plus the `app.modules.dashboard.router` line in
`app/api.py`; the JSON route `/dashboard/summary` has no test referencing it), R12.12's and
R12.14's write-up in `PROGRESS.md` (the numbers above are what it writes), and R12.15's
fresh-DB empty state. The web half of R12.11 could not wait for C2: `app/web/pages/dashboard.py`
owned `/`, and two handlers cannot both own it.

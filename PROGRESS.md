# ApexOS — Build Progress

> The source of truth for status. **This file is capped at ~350 lines and does not grow.**
> Closed parts live in `docs/parts/`. A new part's handoff **replaces** the previous one here.

_Last updated: 2026-07-29_

### What belongs in this file

Exactly one `▶ NEXT SESSION PROMPT` and exactly one `▶ Handoff`, both rewritten — never appended
to — by the session that closes a checkpoint. Anything else belongs in `docs/parts/`.

**This is a hard cap, not a preference.** At Part 3 close this file was **1,212 lines / 90KB ≈ 22k
tokens, re-read at the start of every remaining session**, growing ~300 lines per part — the single
largest avoidable cost in the build. What keeps it down: each finished checkpoint's record moves to
`docs/parts/part-0N.md` as it closes, and the signature block carries what the NEXT part needs
rather than everything ever built. Where everything else lives is in `CLAUDE.md`.

---

# ▶ CURRENT WORK — read this first

**Parts 1–7 are COMPLETE. Part 8's three checkpoints are all DELIVERED, but Part 8 is NOT formally
closed** — R11.7 is open, by the user's decision on 2026-07-29 to leave it open rather than settle it
now (see below). The build continues at **Part 9 — the Founder Command Center**, two checkpoints;
nothing in Part 9 depends on the open item. **All work is on `main`**; nothing in this run is tagged
(waived), so the SHA table is the record.

| Part 8 checkpoint | From | Commit | Tests | Ruff |
|---|---|---|---|---|
| **C1** ledgers · AR/AP ageing · collections · allocation | `3aede6e` | `ec8a573` | 623 → 688 | 37 → 37 |
| **C2** cash flow · working capital · CCC | `ec8a573` | `30b3cc1` | 688 → 721 | 37 → 37 |
| **C3** margin ×4 · leakage · GST | `30b3cc1` | `0ce6931` | 721 → **757** | 37 → **35** |

**The one open item: R11.7 is PARTIALLY MET (P0).** Its "freight not recovered" indicator cannot be
built — there is **no freight, shipping, carriage or delivery-charge field anywhere in the schema** —
so nothing can be computed, and R11.8 forbids shipping an indicator with nothing to click. It is
named on screen under *Not measured*.

**Asked and answered on 2026-07-29: the user chose to LEAVE IT OPEN and proceed to Part 9.** So it is
neither built nor struck, and **Part 8 must not be described as closed or tagged** until it is
settled. The two ways to settle it remain: capture freight on the invoice/bill (a slice of work in
its own right), or strike the indicator from R11.7 with a reason — the register's rule being that a
dropped requirement is struck through, never deleted. **Do not quietly resolve this inside another
part.** Full reasoning in `docs/parts/part-08.md`.

### ▶ How to start the next session

Type **`Start next part of development`** in a fresh session; `CLAUDE.md` binds that phrase to the
prompt below. **The session that closes a checkpoint owns it** — one still naming the previous
baseline is worse than none, because the next session will trust it.

#### ▶ NEXT SESSION PROMPT — Part 9, C1 (Command Center: tiles, alerts, activity, quick actions)

```
Continue the ApexOS build. Do this in order:

1. git checkout main && git pull origin main, then git status — one writer per working tree;
   if it is dirty, STOP and report. Nothing is tagged (waived), so the SHA table in the
   CURRENT WORK block is the record and keeping it accurate replaces the tag.

2. Read the "▶ CURRENT WORK" block below — PARTS 1–8 COMPLETE, with R11.7 partially met and a
   decision pending (that is finance's problem, not Part 9's). The block carries what Part 8
   settled, and verified signatures to CALL without opening the source. Its "Do NOT read"
   list is binding.

3. Read docs/REQUIREMENTS.md §1 (G1–G17) + §13 (R12.x). §11 and §12 are Part 8's and CLOSED.
   Then docs/prompts/part-09.md, docs/STANDING-RULES.md (binding), and
   docs/08-module-breakdown.md § Dashboard. Do NOT open docs/ROADMAP.md (~17k tokens).
   `git show --stat 0ce6931` for C3's shape — not a tree walk.

4. Verify the baseline before writing code (from apps/api, venv activated):
     python -m pytest -q                  # expect 757 passed
     python -m ruff check app/ tests/     # expect EXACTLY 35 — 36 is a regression
   NOTE 35, not 37: C3 rewrote `_gst_summary` and dropped two over-long lines. All 35 are
   pre-existing (E501/F841/B007 in modules this run never touched); tests/ contributes zero.
   NINE PARTS HAVE ADDED ZERO NEW FINDINGS. If a single unrelated test fails and passes on
   re-run, do NOT shrug — C2 found a real uuid7 ordering defect exactly that way.

5. C1 is the Command Center itself: R12.1–R12.11. C2 is the measurement, the empty state and
   deleting the placeholder. Five things decide whether this checkpoint is any good:

   **PART 9 COMPUTES ALMOST NOTHING (R12.10).** It is a read-only projection that CONSUMES
   Part 8's finance projections, Part 5's inventory health and Part 4's vendor intelligence.
   Every signature you need is in "Call, don't read" below, with explicit period parameters
   because R11.13 exists for exactly this. **If a number you want is not exposed, add it in
   THAT part and read it here** — a figure computed in the dashboard is a second definition,
   and Part 8 spent three checkpoints removing those.

   **THE PAGE ANSWERS THREE QUESTIONS IN ORDER (R12.1):** what happened · what needs
   attention · what should I do now. That ordering is the requirement, not a layout
   preference. R12.2 fixes the first (today's revenue, today's gross margin, collections
   today), R12.3 the second (a long list — read it), R12.6 the fourth-most-frequent four
   actions: new order, new PO, record payment, receive stock.

   **EVERY ALERT STATES TRIGGER, THRESHOLD AND RECORDS, AND LINKS TO THEM (R12.8). An alert
   with nothing to click MUST BE REMOVED.** This is the same rule R11.8 applied to leakage,
   and C3 is the worked example: two indicators were built, the third was named as a
   *stated gap* rather than shipped empty. Use `Explained` + `explain_panel` — G11 has
   exactly ONE implementation and R13.1 had this unification scheduled for Part 10, where it
   will simply be recorded as already done. A boundary test per alert.

   **EVERY NUMBER DRILLS THROUGH (R12.7).** Click every tile. C1 of Part 8 shipped a href
   that was built and never rendered, and only driving the real app found it — so build the
   figure and render its link in the same pass.

   **NO DECORATIVE CHARTS, NO DONUTS, NO GRADIENT HERO TILES, NO VANITY METRICS (R12.9).**
   A tile that does not change a decision must be deleted. `test_finance_margin.py` has a
   test asserting no <svg>/<canvas>/chart.js reaches the page; copy it.

6. Constraints that bind:
     - G15/R12.10: a read-only projection writes NO activity_log rows. Assert it.
     - G7: derived, never stored. No cached tile values, no snapshot table.
     - G1: money is integer minor units through `app.core.money.round_minor` only. A ratio
       (a margin %, a rate) rounds ONCE, states where, and never round-trips a float into a
       money figure. `margin.py:_bps` and `cash.py:_days` are the two worked examples.
     - G11: every score, alert and rate explains itself; insufficient data is
       `Explained.unknown(...)`, NEVER 0 or a flattering default. Part 8's hardest-won
       instance: an unpriced product has UNKNOWN margin, not 100%.
     - G10: any new POST carries the R1.4 authz guard — the authz walk enforces it
       automatically, so a quick action that mutates will fail the walk if you forget.
     - G12: no ML, no runtime LLM call. G17: nothing cut by D-A..D-D.
     - A new plain GET route must 200 with NO query parameters — `test_web_smoke.py` walks
       them blind. Every new screen needs a real empty state, and R12.15 asks for exactly
       that on a FRESH DB, with no fake zeros-as-alerts.
     - Any new model owes app/db/references.py an entry, even an empty tuple (R3.7). All
       three Part 8 checkpoints added NO new model; Part 9 should need none either.

7. Work on main. No branches, no PRs, NO TAGS. Commit at the END OF C1 and push. Personal
   credentials only (github.com/1992tushar/apexos).

8. NAME EVERY NEW TEST AFTER THE REQUIREMENT IT PROVES — `pytest -q -k r12_` becomes the
   evidence. MUTATION-CHECK the new suite once. Good mutations here: make an alert fire with
   an empty record list, return 0 where a figure is unknown, and point one tile's
   drill-through at the wrong list.

   R12.12/R12.13 are C2's but affect how you build C1: the query count for one page load
   gets MEASURED and ASSERTED IN A TEST. Use a SQLAlchemy `before_cursor_execute` listener —
   `tests/test_fast_entry.py` has a working example — because a source walk cannot tell a
   call from a comment. So while building C1, prefer Part 8's GROUPED reads (the `*_by_*`
   dicts) over per-row calls, or C2 will have a fan-out to unpick rather than a number to
   report.

   The lesson to re-read before writing an assertion — it has now cost four sessions, most
   recently C3: AN EQUALITY ASSERTION BETWEEN TWO CODE PATHS ONLY TESTS WHAT THE CURRENT
   DATA DISTINGUISHES. C3 swapped one margin dimension's group-by key for another's and
   every test still passed, because the totals reconcile whatever the key. Choose data that
   can tell the two apart, and ASSERT that it does. The rest are in "Gotchas" below.
   DRIVE THE REAL APP before calling it done — that has found a defect in all three of
   Part 8's checkpoints, each time something the tests were happy with.

9. BEFORE you run low, update the "▶ CURRENT WORK" block: the SHA table, R-numbers passed
   and outstanding, gotchas, decisions a later checkpoint must not reverse, and the four
   delta lines — Changed since / Read for the next checkpoint / Call, don't read (copy
   signatures FROM SOURCE) / Do NOT read. Then rewrite this prompt for P9-C2 with MEASURED
   baselines. Start docs/parts/part-09.md with C1's record. Amend docs/CODEBASE-MAP.md if
   the SHAPE changed. Commit and push.
   PROGRESS.md IS CAPPED AT ~350 LINES — replace, never append.

Use pytest -q, never verbose. Don't re-read files you just edited.
```

#### ▶ What Part 8 settled that Part 9 must not reverse

**Baseline measured at `0ce6931`: 757 passed, ruff 35.** `-k r10_` is 58, `-k r11_` is 62.

1. **ONE receivable, ONE payable, and a bulk sibling of each** —
   `CustomerRepository.outstanding_by_customer()` / `SupplierRepository.outstanding_by_supplier()`.
   The receivables and payables tiles must CALL these. Part 8 removed three second definitions
   (`_ar_aging`, `_ap_aging`, `InvoiceService.balance_minor`); do not add a fourth.
2. **`MarginService.gp` reads a missing purchase price as ZERO**, i.e. reports a **100% margin**.
   `margin.py` excludes and counts those lines. **Part 7's `CustomerHealthService.profitability`
   has the same blind spot** — known, recorded, not silently changed. R12.2's "today's gross
   margin" must go through `MarginAnalysisService`, which handles it.
3. **Flows take `date_from`/`date_to`; balances take `as_of`** (R11.13). That split is what lets
   Part 9 ask for "today" without recomputing anything.
4. **A ratio with a thin denominator says so.** DIO is ~10,000 days on the seed — correct and
   useless as a precise figure — so `_thin_window_caveat` marks any day count longer than its own
   window. **"Today's margin" off one invoice has the same problem**; treat it the same way.
5. **`Explained.unknown` is the answer for a missing input, never 0.**
6. **Leakage/alert totals that measure different things are NOT added together.** C3 removed a
   tile that summed a loss and a give-away into one figure reading as a loss nobody made.
7. **An indicator or alert that can never produce a clickable record is NOT built** (R11.8/R12.8).
   Name the gap instead — C3's freight note is the pattern.
8. **The seed's finance section is `app/seed/finance.py`**: 9 invoices (spread across every ageing
   bucket, plus due-today, no-due-date and settled-in-full), 3 bills, and three deliberate leakage
   offenders including a product listed but never purchased. Invoices are written DIRECTLY
   (`sales_order_id` is nullable) because the sell loop needs stock and reservations and would
   leave OPEN sales orders on customers other tests assert are quiet; subjects come from the
   middle and end of the code order for the same reason.

---

## ▶ Handoff — Part 8's three checkpoints are DELIVERED · R11.7 left open by decision

Full records in `docs/parts/part-08.md`; **do not read it.** Parts 1–7 in `part-01.md`…`part-07.md`
and `e2e-gate.md`; do not read those either. The Parts 5–7 E2E gate passed 44 checks but over
**HTTP, not clicked in a browser** — so layout and whether the screens *feel* fast are uncovered,
and **R9.12's manual walkthrough remains a human task.**

Part 8 delivered operational finance in three checkpoints: party statements and AR/AP ageing with a
collections list and multi-document payment allocation (C1); cash flow, working capital and the cash
conversion cycle (C2); margin across four dimensions, leakage indicators and a GST summary by period
(C3). **No new table and no new column in any of the three** — every figure is derived from the
append-only ledgers at read time (G7/R10.10), and none of the projections writes an `activity_log`
row (G15).

**What Part 8 actually fixed, beyond building screens.** Three places already disagreed about money
and now do not: `ReportService._ar_aging` never subtracted credit notes (so it had disagreed with the
receivable since Part 7 shipped returns) and aged nothing despite its name; `_ap_aging` the same;
`InvoiceService.balance_minor` was `total − paid`, so an invoice reduced by a return showed a balance
the customer did not owe **and `add_payment` would have collected it**. C2 also found a real uuid7
ordering defect in Part 6's `CreditPolicyService.history` via an intermittently red baseline.

### Read for P9-C1 — these and nothing else

- `docs/REQUIREMENTS.md` §1 + **§13 (R12.x)**. §11/§12 are Part 8's and closed.
- `docs/prompts/part-09.md` · `docs/STANDING-RULES.md` (binding) · `docs/08-module-breakdown.md`
  § Dashboard · `docs/CODEBASE-MAP.md`'s **Finance** section for what Part 8 exposes.
- **The likely edit set:** `app/web/pages/dashboard.py` (replaced) · a new
  `app/modules/dashboard/service.py` **or**, better, a thin `app/web/pages/command_center.py` that
  calls the existing services · `app/web/templates/dashboard/index.html` ·
  `tests/test_command_center.py`.
- **R12.11's deletion set, named so C2 does not have to find it:** `app/web/pages/dashboard.py`
  (22 lines), `app/modules/dashboard/` (`repository.py` 58, `router.py` 16, `schemas.py` 38,
  `service.py` 89) and `app/web/templates/dashboard/`. The JSON route `/dashboard/summary` has **no
  test referencing it**, so it can go with the rest. Two dashboards must not remain.

### Call, don't read — verified signatures, copied from source at P8-C3 close

```python
# app/core/money.py — G1
round_minor(value: Decimal) -> int   # THE one money rounding step
minor_to_text(minor) -> str          # 123456 -> "1234.56" · qty_text(Decimal) -> "40"

# app/db/explain.py — the ONE shape for every explained number (G11)
Explained(what, value: str | None, formula, window, inputs=(), records=(),
          unknown_reason=None, caveat=None)      # .is_known · .display
Explained.unknown(*, what, formula, reason, window="no data", inputs=(), records=())
Input(label, value, weight=None, missing_reason=None) · SourceRecord(label, href=None)
# Rendered by ONE macro:  {{ ui.explain_panel(explained, "Optional title") }}

# app/modules/finance/ — Part 8. Projections; they write NOTHING (G15).
# FLOWS take date_from/date_to, BALANCES take as_of (R11.13). This is what R12.10 consumes.
AgeingService(db).ar_ageing/.ap_ageing(*, as_of=None) -> AgeingReport
#   .rows[AgeingPartyRow] .total_minor .due_minor .overdue_minor .unaged_minor
AgeingService(db).collections(*, as_of=None) -> list[CollectionsEntry]   # .explained, .reason
AgeingService(db).payments_due(*, as_of=None) -> list[PaymentsDueEntry]
PartyLedgerService(db).customer_statement/.vendor_statement(party_id, *, as_of=None)
open_invoices(db, *, customer_id=None, as_of=None) / open_bills(...) -> list[OpenDocument]
AllocationService(db).allocate_receipt/.allocate_payment(party_id, AllocationCreate, *, actor_id)
CashFlowService(db).cash_flow(*, date_from, date_to) -> CashFlowReport
#   .actual_in_minor .actual_out_minor .actual_net_minor .projected_net_minor .committed .rows
CashFlowService(db).committed(*, date_from, date_to) -> CommittedCash   # .terms is R11.2's prose
CashFlowService(db).working_capital(*, as_of=None) -> WorkingCapitalSnapshot
#   .receivables_minor .inventory_minor .payables_minor .working_capital_minor .caveat
CashFlowService(db).cash_conversion_cycle(*, date_from, date_to) -> CashCycleReport
#   .dso/.dio/.dpo/.ccc are Explained · .*_days are int|None (None => unknown)
MarginAnalysisService(db).by_dimension(dimension, *, date_from, date_to) -> MarginReport
#   dimension in MARGIN_DIMENSIONS: product | customer | category | business_unit
#   .revenue_minor .cost_minor .gp_minor .margin_bps (int|None) .unknown_cost_lines .explained
MarginAnalysisService(db).leakage(*, date_from, date_to) -> LeakageReport
#   .indicators[LeakageIndicator: .records .impact_minor .rule .explained] .not_measured
GstService(db).summary(*, date_from, date_to) -> GstSummary   # .rows are per MONTH
GstService.position_text(net_minor) -> str
default_window(*, as_of=None) -> tuple[date, date]   # 90 days ending today
month_starts(date_from, date_to) -> list[date] · today() -> date
bps_text(bps: int | None) -> str      # 1850 -> "18.5%", None -> "unknown"

# app/modules/customers/ + suppliers/ — THE receivable and THE payable
CustomerRepository(db).outstanding_minor(id) -> int · .outstanding_by_customer() -> dict
SupplierRepository(db).outstanding_minor(id) -> int · .outstanding_by_supplier() -> dict
CustomerHealthService(db).score(customer_id, *, as_of=None) -> Explained   # R12.3's alerts

# app/modules/inventory/ + suppliers/vendor.py — R12.3's other alert sources
InventoryHealthService(db).low_stock() -> list[LowStockRow] · .low_stock_explained(row)
InventoryHealthService(db).dead_stock(...) · .dead_stock_explained(row) · .abc(...)
InventoryHealthService(db).reorder_suggestions(...)   # delegates to R5.9's ONE engine
ValuationService(db).stock_value()    # StockValueRow.value_minor is None where cost unknown
VendorIntelService(db).score(supplier_id) -> Explained · .lead_time / .on_time_rate

# app/modules/activity/service.py — R12.5
ActivityService(db).recent(limit: int = 20) -> list[ActivityLog]

# app/web/listing.py + app/modules/config/service.py
csv_rows_response(spec: ListSpec, rows) -> Response     # Part 2's ONE export path
default_business_unit(db) -> uuid.UUID
allocate_document_number(db, *, doc_type, business_unit_id, on_date) -> "INV-202607-00001"
```

Part 2's machinery still holds: `ListSpec` + `view_from_request`, `ensure_unreferenced` /
`soft_delete` / `ensure_unique`, and the `page_header` / `stat` / `badge` / `list_*` /
`history_panel` / `explain_panel` macros.

### Gotchas that will bite Part 9

- **`client.post` COMMITS; `db`-fixture writes roll back.** A POSTing test leaves rows behind, and
  three checkpoints broke the same two Part 1/3 tests by leaving an OPEN document on the first
  customer. It needs a subject no other test asserts about — `test_fast_entry.py`'s
  `spare_customer` and `test_finance_allocation.py`'s `quiet_customer` are the two patterns.
- **A source-walk test cannot tell a call from a comment.** C3 searched for "portal" and failed on
  its own docstring. Assert on imports and public surface, or count queries with a SQLAlchemy
  `before_cursor_execute` listener.
- **Assert on HTML phrases that do NOT straddle a template line break** — five runs and counting.
  If a claim matters, put it on one line in the template.
- **A test can pass without testing anything.** Assert a **floor** on anything you enumerate.
  A test reading a **convenience field** instead of the source of truth can be confidently wrong.
- **Never order by `uuid7()` as a tiebreak** — its low bits are `os.urandom`, so it is not monotonic
  within a millisecond. Sort on something that cannot tie.
- **A `select()` per row is the thing to avoid**; `db.get(Model, id)` in a loop is free (identity
  map). Part 8's grouped `*_by_*` dicts are the pattern — and R12.12 will measure this.
- **`create_all` never ALTERs an existing table.** A new column needs an `_ADDITIVE_COLUMNS` entry
  in `app/main.py` (~line 45); get the DDL from `CreateTable(...).compile(sqlite)`.
- **The env var is `DATABASE_URL`, not `APEXOS_DATABASE_URL`.** Stop uvicorn before deleting a
  scratch `.db` (`Get-CimInstance Win32_Process | Where CommandLine -like '*<port>*' |
  Stop-Process -Force`; `pkill` does not exist here). Ports 8015–8036 used; pick above that.
- **PowerShell has no heredocs** — a multi-line commit message needs the Bash tool
  (`git commit -F - <<'EOF'`). **Never edit a source file with `Set-Content`**: it round-trips
  UTF-8 through cp1252 and mojibakes every em dash.
- **A script reading the DB without booting the app skips `_ensure_new_columns`.** Use a
  `TestClient(app)` context if the shim must have run.

### Do NOT read

`app/seed/core.py` (740 lines — read `app/seed/__init__.py`'s docstring, and `app/seed/finance.py`
as the pattern for a new section) · `app/modules/finance/{ledger,ageing,allocation,cash,margin,
gst}.py` (Part 8 finished them; signatures above) · `app/modules/procurement/preorder.py` ·
`app/modules/suppliers/vendor.py` · `app/modules/inventory/{valuation,health}.py` ·
`app/modules/customers/{credit,timeline,health}.py` · `app/modules/sales/{quotation,returns,
fast_entry}.py` · `tests/test_finance_*.py`, `test_inventory_*.py`, `test_customer_*.py`,
`test_quotations.py`, `test_returns_and_reservations.py`, `test_fast_entry.py`, `test_preorder.py`,
`test_po_revisions.py`, `test_vendor_*.py`, `test_procurement_planning.py` (they pass; read one only
if you change what it covers) · anything in `docs/parts/` · `docs/ROADMAP.md` (~17k tokens,
planning only) · the older `docs/` design files, `docs/DELETION-POLICY.md`,
`docs/MIGRATION-STRATEGY.md`.

Note `docs/REQUIREMENTS.md` is at v1.2: the stock writer is `InventoryService.record_movement`, and
any older doc naming `post_movement` is wrong.

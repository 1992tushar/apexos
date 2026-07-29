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

**Parts 1–7 COMPLETE. Part 8 DELIVERED but not formally closed** — R11.7 is open by the user's
decision on 2026-07-29 (below). **Part 9's C1 is done**; the build continues at **P9-C2**, which
closes Part 9. **All work is on `main`**; nothing in this run is tagged (waived), so the SHA
table is the record.

| Checkpoint | From | Commit | Tests | Ruff |
|---|---|---|---|---|
| **P8-C1** ledgers · AR/AP ageing · collections · allocation | `3aede6e` | `ec8a573` | 623 → 688 | 37 → 37 |
| **P8-C2** cash flow · working capital · CCC | `ec8a573` | `30b3cc1` | 688 → 721 | 37 → 37 |
| **P8-C3** margin ×4 · leakage · GST | `30b3cc1` | `0ce6931` | 721 → 757 | 37 → **35** |
| **P9-C1** tiles · alerts · activity · quick actions | `c316861` | `45b8218` | 757 → **786** | 35 → 35 |

**The one open item: R11.7 is PARTIALLY MET (P0).** Its "freight not recovered" indicator cannot be
built — there is **no freight, shipping, carriage or delivery-charge field anywhere in the schema** —
so nothing can be computed, and R11.8 forbids shipping an indicator with nothing to click. It is
named on screen under *Not measured*. **Asked and answered on 2026-07-29: the user chose to LEAVE IT
OPEN and proceed.** So it is neither built nor struck, and **Part 8 must not be described as closed
or tagged** until it is settled — either capture freight on the invoice/bill, or strike the indicator
from R11.7 with a reason (the register strikes through, never deletes). **Do not quietly resolve this
inside another part.** Reasoning in `docs/parts/part-08.md`.

### ▶ How to start the next session

Type **`Start next part of development`** in a fresh session; `CLAUDE.md` binds that phrase to the
prompt below. **The session that closes a checkpoint owns it** — one still naming the previous
baseline is worse than none, because the next session will trust it.

#### ▶ NEXT SESSION PROMPT — Part 9, C2 (measurement write-up · empty state · delete the placeholder)

```
Continue the ApexOS build. Do this in order:

1. git checkout main && git pull origin main, then git status — one writer per working tree;
   if it is dirty, STOP and report. Nothing is tagged (waived); the SHA table above is the
   record and keeping it accurate replaces the tag.

2. Read the "▶ CURRENT WORK" block below. C1 built the Command Center and MEASURED it —
   the numbers are here, already measured, and C2's job is to WRITE THEM DOWN plus the two
   things C1 could not do. Do NOT re-measure to a different method and report a different
   number; if you re-measure, say which method produced which figure.

3. Read docs/REQUIREMENTS.md §1 (G1–G17) + §13 (R12.x) — specifically R12.11, R12.12,
   R12.14 and R12.15, which are the four still open. Then docs/STANDING-RULES.md (binding).
   `git show --stat 45b8218` for C1's shape — not a tree walk. Do NOT open docs/ROADMAP.md
   (~17k tokens) and do NOT open docs/parts/part-09.md.

4. Verify the baseline before writing code (from apps/api, venv activated):
     python -m pytest -q                  # expect 786 passed
     python -m ruff check app/ tests/     # expect EXACTLY 35 — 36 is a regression
   All 35 are pre-existing (E501/F841/B007 in modules this run never touched); tests/
   contributes zero. NINE PARTS HAVE ADDED ZERO NEW FINDINGS. If a single unrelated test
   fails and passes on re-run, do NOT shrug — P8-C2 found a real uuid7 ordering defect
   exactly that way.

5. C2 is four requirements and it CLOSES Part 9. In rough order of risk:

   **R12.11 — DELETE THE REST OF THE PLACEHOLDER. Two dashboards must not remain.**
   C1 deleted `app/web/pages/dashboard.py` and `app/web/templates/dashboard/` because
   they owned `/`. Still there, and yours: `app/modules/dashboard/` (`repository.py` 58,
   `router.py` 16, `schemas.py` 38, `service.py` 89, `__init__.py` 1) and the line
   `"app.modules.dashboard.router",` in `app/api.py` (~line 30). The JSON route
   `/dashboard/summary` has **NO test referencing it** — grep to confirm, then it goes with
   the rest. `test_api_contract.py` may count routers; check before you delete, not after.
   Deleting `app/modules/dashboard/` also removes the LAST caller of some things — if a
   helper becomes dead, delete it too rather than leaving it.

   **R12.15 — the empty state, ON A FRESH DB, with no fake zeros-as-alerts.**
   This is the one genuinely new piece of work. A fresh DB has no invoice, no payment, no
   product, no activity. The page must render 200 and must NOT show four alerts reading
   zero — `Alert` already refuses to be constructed without records, so the families should
   simply be absent and the "Nothing needs attention right now" empty state should show.
   VERIFY IT, do not assume it: create the schema WITHOUT seeding (a TestClient against a
   scratch DATABASE_URL, so `_ensure_new_columns` runs) and load `/`. Expect to find at
   least one figure whose formatting assumes data — a margin over zero lines, a hint doing
   integer division on an empty total, `entries[0].explained` on an empty list. Each one
   fixed in the SERVICE, and each one a named test.

   **R12.12 + R12.14 — write the numbers down.** They are already measured (below). What
   R12.12 asks for is the figure IN PROGRESS.md, which is this file, plus the honest
   statement of what the measurement does not cover. R12.13's test already exists
   (`test_r12_13_one_page_load_stays_inside_its_query_budget`, ceiling 120).

6. Constraints that bind:
     - G15/R12.10: the page is a read-only projection. It writes NO activity_log row and
       there is NO `select()` in `app/modules/command_center/service.py` — a namespace-walk
       test enforces the second. If the empty state needs a figure that does not exist, add
       it to the OWNING service, not to the projection.
     - G7 derived-never-stored · G1 money is integer minor units through `round_minor` · G11
       insufficient data is `Explained.unknown(...)`, NEVER 0 or a flattering default.
     - G12 no ML, no runtime LLM call. G17 nothing cut by D-A..D-D.
     - A new plain GET route must 200 with NO query parameters (`test_web_smoke.py` walks
       them blind). `/` takes no parameters at all — keep it that way.

7. Work on main. No branches, no PRs, NO TAGS. Commit at the END OF C2 and push. Personal
   credentials only (github.com/1992tushar/apexos).

8. NAME EVERY NEW TEST AFTER THE REQUIREMENT IT PROVES — `pytest -q -k r12_` is the
   evidence (29 tests today). MUTATION-CHECK the new suite once. Good mutations here: let
   an alert fire with an empty record list on the fresh DB, and make the empty state render
   a zero where the figure is unknown.

   The lesson to re-read before writing an assertion — it has cost five sessions, most
   recently C1's committed-cash tile: AN EQUALITY ASSERTION BETWEEN TWO CODE PATHS ONLY
   TESTS WHAT THE CURRENT DATA DISTINGUISHES. C1's tile read the TRAILING window under a
   "next 90 days" label and every test passed, because nothing compared it to the forward
   figure. Choose data that can tell the two apart, and ASSERT that it does.
   DRIVE THE REAL APP before calling it done — that has now found a defect in all four
   checkpoints of Parts 8 and 9, each time something the tests were happy with.

9. BEFORE you run low, update the "▶ CURRENT WORK" block: the SHA table, R-numbers passed
   and outstanding, gotchas, decisions a later checkpoint must not reverse, and the four
   delta lines — Changed since / Read for the next checkpoint / Call, don't read (copy
   signatures FROM SOURCE) / Do NOT read. Append C2's record to docs/parts/part-09.md
   (C1's is already there). Then rewrite this prompt for P10-C1 (the R13.1 audit + the
   unifications — the real work of Part 10) with MEASURED baselines. Amend
   docs/CODEBASE-MAP.md if the SHAPE changed.
   PROGRESS.md IS CAPPED AT ~350 LINES — replace, never append.

Use pytest -q, never verbose. Don't re-read files you just edited.
```

#### ▶ P9-C1's measurements, for C2 to write up (R12.12, R12.14)

Measured against **uvicorn over real HTTP** on the seeded dataset — not a TestClient.

| | Before C1's `low_stock` fix | After |
|---|---|---|
| Queries, one `/` page load | 344 | **81** |
| Warm render, median of 5 | 1,096 ms | **59 ms** |
| Cold first request | — | 190 ms |

81 is **thirteen grouped projections of 1–14 queries each, none of which grows with the row
count** — that property, not the absolute number, is what R12.12 protects. The seed holds 311
products, 273 stock states, 86 low-stock rows and 4 overdue customers, so any per-row read lands
in the hundreds. **What it does not cover:** one count on one dataset; it proves the page does not
read per row, not that any individual query is fast, and it says nothing about a 10× dataset.

#### ▶ What C1 settled that C2 must not reverse

1. **R12.7 and R12.8 are enforced by schema validators, not by review.** `Figure` raises without
   an `href`; `Alert` raises on empty `records` and on a `count` below the list it carries. Do not
   relax either to make an empty state easier — **omit the alert instead.** That is the point.
2. **The projection computes nothing.** No `select()`, no ORM model, no `sum()` over rows in
   `app/modules/command_center/service.py`, and
   `test_r12_10_the_projection_module_holds_no_query_and_no_model` walks the module's NAMESPACE
   (not its text — C3's source walk failed on its own docstring) to keep it true.
3. **The inventory tile reads the working-capital snapshot's inventory term**, not
   `ValuationService.stock_value()`. Both would be right; reading one means the tile and the
   position figure cannot disagree, and it costs one fewer valuation pass.
4. **Committed cash looks FORWARD** (`CashFlowService.committed` over `[today, today+90]`).
   `CashFlowReport.committed` covers the same trailing window as its actuals — correct on a
   cash-flow report, wrong under a "next 90 days" label. A test asserts the forward and trailing
   figures **differ**, so it cannot pass on data that cannot tell them apart.
5. **`InventoryHealthService.low_stock` reads the reorder levels ONCE.** It used to call
   `stock()` — a grouped read of all 311 products — inside its loop over `states()`: 274 queries,
   979 ms. `test_r7_10_low_stock_reads_the_reorder_levels_once` counts statements. `/inventory`
   had been paying this since Part 5.
6. **Arrivals, not `calendar()`.** `ProcurementCalendarService.calendar()` also runs the
   recommendation engine, which this page does not show. `.arrivals()` is the half that answers
   "deliveries due", and its `overdue` bucket is the vendor alert.
7. **An unpromised arrival is NOT due** (R5.7). `DUE_BUCKETS` excludes it deliberately.
8. **Leakage indicators are one alert each, never summed.** C3 removed a tile that added a loss
   to a give-away; do not re-merge them.

---

## ▶ Handoff — P9-C1 delivered · Part 9 closes at C2

Full records in `docs/parts/part-09.md` (C1) and `part-08.md`; **do not read either.** Parts 1–7
in `part-01.md`…`part-07.md` and `e2e-gate.md`; do not read those either. The Parts 5–7 E2E gate
passed 44 checks but over **HTTP, not clicked in a browser** — layout and whether the screens
*feel* fast are uncovered, and **R9.12's manual walkthrough remains a human task.**

### Read for P9-C2 — these and nothing else

- `docs/REQUIREMENTS.md` §1 + **§13 (R12.x)**, especially R12.11/R12.12/R12.14/R12.15.
- `docs/STANDING-RULES.md` (binding) · `docs/CODEBASE-MAP.md`'s **Command Center** section.
- **The likely edit set:** `app/modules/command_center/service.py` (the empty-state fixes) ·
  `app/api.py` (drop the dashboard router line) · `tests/test_command_center.py` ·
  **deletions**: `app/modules/dashboard/` entire.
- `app/web/templates/command_center/index.html` only if the empty state needs markup — it
  already has `ui.empty(...)` fallbacks for the alert list and the activity feed.

### Call, don't read — verified signatures, copied from source at P9-C1 close

```python
# app/modules/command_center/ — Part 9. Writes NOTHING (G15).
CommandCenterService(db).load(*, as_of: date | None = None) -> CommandCenter
#   .as_of .window_from .window_to
#   .happened[Figure] .happened_caveat  .position[Figure] .position_caveat
#   .attention[Figure] .alerts[Alert] .actions[QuickAction] .activity[ActivityEntry]
#   .alert_count
Figure(key, label, kind, value, href, hint=None, explained=None)   # kind: money|count|text
#   raises unless href startswith "/"  (R12.7)
Alert(key, label, trigger, threshold, count, records, href, impact_minor=None,
      explained=None, source="")       # raises on empty records / count < len(records)
#   .hidden_count = count - len(records)
AlertRecord(label, href, detail=None) · QuickAction(label, href, why)
ActivityEntry(verb, entity_type, summary, occurred_at)
RECORD_LIMIT = 5 · ACTIVITY_LIMIT = 10 · THIN_SAMPLE_LINES = 3 · AHEAD_DAYS = 90
DUE_BUCKETS = ("overdue", "today", "this_week") · QUICK_ACTIONS  # tuple of 4

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
# FLOWS take date_from/date_to, BALANCES take as_of (R11.13).
AgeingService(db).ar_ageing/.ap_ageing(*, as_of=None) -> AgeingReport
#   .rows[AgeingPartyRow] .total_minor .due_minor .overdue_minor .unaged_minor .buckets
AgeingService(db).collections(*, as_of=None) -> list[CollectionsEntry]
#   .customer_id .customer_name .href .ledger_href .outstanding_minor .overdue_minor
#   .oldest_days_overdue .oldest_doc_no .oldest_doc_href .open_count .reason .explained
AgeingService(db).payments_due(*, as_of=None) -> list[PaymentsDueEntry]
CashFlowService(db).cash_flow(*, date_from, date_to) -> CashFlowReport
#   .actual_in_minor .actual_out_minor .actual_net_minor .projected_net_minor .committed .rows
CashFlowService(db).committed(*, date_from, date_to) -> CommittedCash
#   .in_minor .out_minor .net_minor .invoice_count .bill_count .terms (R11.2's prose)
CashFlowService(db).working_capital(*, as_of=None) -> WorkingCapitalSnapshot
#   .receivables_minor .inventory_minor .payables_minor .working_capital_minor
#   .inventory_known .products_without_cost .caveat
CashFlowService(db).cash_conversion_cycle(*, date_from, date_to) -> CashCycleReport
MarginAnalysisService(db).by_dimension(dimension, *, date_from, date_to) -> MarginReport
#   .revenue_minor .cost_minor .gp_minor .margin_bps (int|None) .line_count
#   .unknown_cost_lines .explained .rows   # product|customer|category|business_unit
MarginAnalysisService(db).leakage(*, date_from, date_to) -> LeakageReport
#   .indicators / .fired [LeakageIndicator: .key .label .rule .records .impact_minor
#     .explained .fired] · .not_measured · LeakageRecord: .doc_no .href .detail …
GstService(db).summary(*, date_from, date_to) -> GstSummary   # rows are per MONTH
default_window(*, as_of=None) -> tuple[date, date]   # 90 days ending today
today() -> date · bps_text(bps: int | None) -> str   # 1850 -> "18.5%", None -> "unknown"

# THE receivable and THE payable — do not re-derive
CustomerRepository(db).outstanding_minor(id) -> int · .outstanding_by_customer() -> dict
SupplierRepository(db).outstanding_minor(id) -> int · .outstanding_by_supplier() -> dict
CustomerHealthService(db).score(customer_id, *, as_of=None) -> Explained   # per-customer

# Parts 3/4/5/7 — the rest of what the homepage consumes
InventoryHealthService(db).low_stock() -> list[LowStockRow]  # .product_id .sku_code
#   .product_name .warehouse_name .available .on_hand .reserved .reorder_level .shortfall
InventoryHealthService(db).low_stock_explained(row) -> Explained · .dead_stock(...) · .abc(...)
InventoryHealthService(db).reorder_suggestions(...)   # delegates to R5.9's ONE engine
ValuationService(db).stock_value() -> list[StockValueRow] · .total_value_minor(rows=None)
#   .unknown_basis_count(rows=None)      # value_minor is None where cost unknown
ProcurementCalendarService(db).arrivals() -> list[Arrival]
#   .purchase_order_id .po_no .supplier_name .expected_date .open_qty .bucket .days_away
#   ARRIVAL_BUCKETS = overdue|today|this_week|later|unpromised
ProcurementRepository(db).pending_count() -> int · SalesRepository(db).pending_count() -> int
VendorIntelService(db).score(supplier_id) -> Explained · .lead_time / .on_time_rate
ActivityService(db).recent(limit: int = 20) -> list[ActivityLog]

# app/web/listing.py + app/modules/config/service.py
csv_rows_response(spec: ListSpec, rows) -> Response     # Part 2's ONE export path
default_business_unit(db) -> uuid.UUID
allocate_document_number(db, *, doc_type, business_unit_id, on_date) -> "INV-202607-00001"
```

Part 2's machinery still holds: `ListSpec` + `view_from_request`, `ensure_unreferenced` /
`soft_delete` / `ensure_unique`, and the `page_header` / `stat` / `badge` / `list_*` /
`history_panel` / `explain_panel` macros.

### Gotchas that will bite P9-C2

- **Asserting a rendered link needs Jinja's escaper.** `href="…?a=1&b=2"` lands as `&amp;`, and an
  alert saying "purchase order's" lands with `&#39;`. `tests/test_command_center.py` has `_rendered`
  (escape the CONTENT) and `_linked` (escape the URL, not the attribute quotes) — use them. Escaping
  `href="…"` as a whole turns the quotes into `&#34;` and matches nothing.
- **`client.post` COMMITS; `db`-fixture writes roll back.** A POSTing test leaves rows behind, and
  three checkpoints broke the same two Part 1/3 tests by leaving an OPEN document on the first
  customer. Use a subject nothing else asserts about — `test_fast_entry.py`'s `spare_customer`,
  `test_finance_allocation.py`'s `quiet_customer`, and the Part 9 seed's offset-9 customer.
- **A source-walk test cannot tell a call from a comment.** C3 searched for "portal" and failed on
  its own docstring. Walk the module's namespace, or count queries with a SQLAlchemy
  `before_cursor_execute` listener (`tests/test_command_center.py:_count_queries`).
- **Assert on HTML phrases that do NOT straddle a template line break** — six runs and counting.
- **A test can pass without testing anything.** Assert a **floor** on anything you enumerate; the
  Command Center tests assert both the equality AND that the figure is non-zero on the seed.
- **Never order by `uuid7()` as a tiebreak** — its low bits are `os.urandom`, so it is not monotonic
  within a millisecond. Sort on something that cannot tie.
- **A `select()` per row is the thing to avoid**, and it hides inside an *invariant* call in a loop —
  that is exactly what `low_stock` did. `db.get(Model, id)` in a loop is free (identity map).
- **`create_all` never ALTERs an existing table.** A new column needs an `_ADDITIVE_COLUMNS` entry
  in `app/main.py` (~line 45); get the DDL from `CreateTable(...).compile(sqlite)`.
- **The env var is `DATABASE_URL`, not `APEXOS_DATABASE_URL`.** Stop uvicorn before deleting a
  scratch `.db` (`Get-CimInstance Win32_Process | Where CommandLine -like '*<port>*' |
  Stop-Process -Force`; `pkill` does not exist here). Ports 8015–8040 used; pick above that.
- **PowerShell has no heredocs** — a multi-line commit message needs the Bash tool
  (`git commit -F - <<'EOF'`). **Never edit a source file with `Set-Content`**: it round-trips
  UTF-8 through cp1252 and mojibakes every em dash.
- **A script reading the DB without booting the app skips `_ensure_new_columns`.** Use a
  `TestClient(app)` context if the shim must have run — which R12.15's fresh-DB test needs.

### Do NOT read

`app/seed/core.py` (760 lines — read `app/seed/__init__.py`'s docstring, and
`app/seed/command_center.py` as the smallest section) · `app/modules/finance/{ledger,ageing,
allocation,cash,margin,gst}.py` (Part 8 finished them; signatures above) ·
`app/modules/procurement/{preorder,recommend}.py` · `app/modules/suppliers/vendor.py` ·
`app/modules/inventory/{valuation,health}.py` · `app/modules/customers/{credit,timeline,health}.py` ·
`app/modules/sales/{quotation,returns,fast_entry}.py` · `tests/test_finance_*.py`,
`test_inventory_*.py`, `test_customer_*.py`, `test_quotations.py`,
`test_returns_and_reservations.py`, `test_fast_entry.py`, `test_preorder.py`,
`test_po_revisions.py`, `test_vendor_*.py`, `test_procurement_planning.py` (they pass; read one
only if you change what it covers) · anything in `docs/parts/` · `docs/ROADMAP.md` (~17k tokens,
planning only) · the older `docs/` design files, `docs/DELETION-POLICY.md`,
`docs/MIGRATION-STRATEGY.md`.

Note `docs/REQUIREMENTS.md` is at v1.2: the stock writer is `InventoryService.record_movement`, and
any older doc naming `post_movement` is wrong.

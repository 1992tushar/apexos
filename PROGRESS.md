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

**Parts 1–7 and 9 are COMPLETE. Part 8 is DELIVERED but not formally closed** — R11.7 is open by
the user's decision on 2026-07-29 (below). The build continues at **Part 10 — the Intelligence
Layer**, two checkpoints, starting with **P10-C1: the R13.1 audit and the unifications**. **All
work is on `main`**; nothing in this run is tagged (waived), so the SHA table is the record.

| Checkpoint | From | Commit | Tests | Ruff |
|---|---|---|---|---|
| **P8-C1** ledgers · AR/AP ageing · collections · allocation | `3aede6e` | `ec8a573` | 623 → 688 | 37 → 37 |
| **P8-C2** cash flow · working capital · CCC | `ec8a573` | `30b3cc1` | 688 → 721 | 37 → 37 |
| **P8-C3** margin ×4 · leakage · GST | `30b3cc1` | `0ce6931` | 721 → 757 | 37 → **35** |
| **P9-C1** tiles · alerts · activity · quick actions | `c316861` | `45b8218` | 757 → 786 | 35 → 35 |
| **P9-C2** empty state · placeholder deleted · measured — **PART 9 COMPLETE** | `8c87f52` | `42b4392` | 786 → **794** | 35 → 35 |

**Part 9 measured (R12.12, R12.14) — the figure this file is required to state.** One `/` page
load: **81 queries, 51 ms median warm render** (184 ms cold), measured on uvicorn over real HTTP
against the seeded dataset. Down from 344 queries / 1,096 ms, which is what it cost before C1
fixed a per-row read in `InventoryHealthService.low_stock`. 81 is thirteen grouped projections of
1–14 queries each, **none growing with the row count** — that property, not the number, is what
R12.12 protects. **What it does not cover:** one count and one timing, one dataset, SQLite, this
machine. It proves the page does not read per row. It does not prove any single query is fast, says
nothing about a 10× dataset, and is not a browser measurement. Full record in `docs/parts/part-09.md`.

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

#### ▶ NEXT SESSION PROMPT — Part 10, C1 (the R13.1 audit + the unifications · the real work)

```
Continue the ApexOS build. Do this in order:

1. git checkout main && git pull origin main, then git status — one writer per working tree;
   if it is dirty, STOP and report. Nothing is tagged (waived); the SHA table above is the
   record and keeping it accurate replaces the tag.

2. Read the "▶ CURRENT WORK" block below. Parts 1–7 and 9 are complete; Part 8 is delivered
   with R11.7 open (finance's problem, not Part 10's — do NOT resolve it here).

3. Read docs/REQUIREMENTS.md §1 (G1–G17) + §14 (R13.x — your acceptance contract). §13 is
   Part 9's and CLOSED. Then docs/prompts/part-10.md and docs/STANDING-RULES.md (binding),
   and docs/CODEBASE-MAP.md — this is the ONE part where the map earns its keep, because
   the R13.1 audit is a question about what exists everywhere. Do NOT open docs/ROADMAP.md
   (~17k tokens). `git show --stat 45b8218 42b4392` for Part 9's shape.

4. Verify the baseline before writing code (from apps/api, venv activated):
     python -m pytest -q                  # expect 794 passed
     python -m ruff check app/ tests/     # expect EXACTLY 35 — 36 is a regression
   All 35 are pre-existing (E501/F841/B007 in modules this run never touched); tests/
   contributes zero. NINE PARTS HAVE ADDED ZERO NEW FINDINGS. If a single unrelated test
   fails and passes on re-run, do NOT shrug — P8-C2 found a real uuid7 ordering defect
   exactly that way.

5. **C1 IS THE AUDIT, AND THE AUDIT IS THE DELIVERABLE (R13.1, R13.2, R13.6).** Not a
   warm-up for the screens — C2 builds those. This part CONSOLIDATES; it does not
   duplicate, and the way it fails is by building a tenth score instead of finding the two
   that disagree.

   **R13.1 — list every score, radar, suggestion and alert parts 4–9 produce, and where
   each lives. That list goes in PROGRESS.md.** Start from "Call, don't read" below, which
   already names most of them, then go looking for what it misses. Expect ~20 outputs
   across vendor intel, inventory health, customer health, pricing, procurement
   recommendations, finance ageing/leakage/cash, and Part 9's Command Center.

   **R13.2 — anything computed in two places becomes ONE engine, each unification
   recorded.** Three things are ALREADY DONE and the audit should say so and move on
   rather than rebuilding them:
     - **G11 has exactly one implementation** — `Explained` + `explain_panel`, built in
       Part 4, used by Parts 5–9. R13.1 had this unification scheduled here; it is done.
     - **R13.6 is largely done.** `InventoryHealthService.reorder_suggestions` is a bare
       delegation to `RecommendationService.recommend`, and
       `test_r7_13_the_reorder_suggestion_is_identical_to_part_4s_engine` already proves
       identical output. Part 4 also left a source walk that FAILS if a second
       `def recommend` appears anywhere in `app/`. VERIFY and RECORD this; do not rebuild.
     - **THE receivable and THE payable** are `CustomerRepository.outstanding_by_customer`
       / `SupplierRepository.outstanding_by_supplier`. Part 8 removed three second
       definitions (`_ar_aging`, `_ap_aging`, `InvoiceService.balance_minor`). Part 9 reads
       the first pair. Confirm nothing has crept back.
   So the audit's real job is finding what genuinely IS still duplicated. Two known
   candidates worth checking first: **`CustomerHealthService.profitability` and
   `MarginAnalysisService` both derive gross profit**, and only the second handles the
   missing-purchase-price case (the first reports a 100% margin — recorded, not silently
   changed, at P8-C3 close). And **`cash.py:_cogs` is a cost-of-goods definition** that
   nothing else shares yet — check whether Part 10's cockpits would need a second.

   **R13.13 — for each unification, a test proving both screens return identical output for
   the same input.** The trap, which has cost five sessions: AN EQUALITY ASSERTION BETWEEN
   TWO CODE PATHS ONLY TESTS WHAT THE CURRENT DATA DISTINGUISHES. A no-op filter once
   passed an "identical output" test because the seed could not tell the difference, and
   P9-C1's committed-cash tile read the wrong window under the right label with every test
   green. So **assert the STRUCTURE too**, not just equality of totals, and choose data
   that can tell the two paths apart.

6. Constraints that bind:
     - G16/R13.2: call the earlier service, never reimplement it. A unification DELETES
       code; if your diff only adds, you have built a tenth engine.
     - G12/R13.12: no ML dependency, no runtime LLM call. Transparent arithmetic only —
       weighted ratios, trailing averages, simple linear projections.
     - G11/R13.10/R13.11: every output states definition, formula, window and linked
       records, through `Explained` + `explain_panel`. Insufficient history says so —
       NEVER 0, never 50.
     - G7 derived-never-stored · G1 money is integer minor units through `round_minor`; a
       ratio rounds ONCE and states where (`margin.py:_bps`, `cash.py:_days` are the two
       worked examples).
     - G15: a projection writes no activity_log row. Part 9's page asserts this; anything
        C2 adds should too.
     - Any new model owes app/db/references.py an entry, even an empty tuple (R3.7).
       Part 9 added none and Part 10 probably needs none — it consolidates.
     - A new plain GET route must 200 with NO query parameters (test_web_smoke.py walks
       them blind), and needs a real empty state (Part 9's `is_empty` is the pattern).

7. Work on main. No branches, no PRs, NO TAGS. Commit at the END OF C1 and push. Personal
   credentials only (github.com/1992tushar/apexos).

8. NAME EVERY NEW TEST AFTER THE REQUIREMENT IT PROVES — `pytest -q -k r13_` becomes the
   evidence. MUTATION-CHECK the new suite once: break each unification so the two paths
   disagree, and confirm the R13.13 test goes red. Over Parts 8 and 9 this found four real
   defects.
   DRIVE THE REAL APP before calling it done — it has found a defect in all five
   checkpoints of Parts 8 and 9, each time something the tests were happy with.

9. BEFORE you run low, update the "▶ CURRENT WORK" block: the SHA table, R-numbers passed
   and outstanding, gotchas, decisions a later checkpoint must not reverse, and the four
   delta lines — Changed since / Read for the next checkpoint / Call, don't read (copy
   signatures FROM SOURCE) / Do NOT read. **The R13.1 audit list belongs in that block —
   it is the deliverable.** Start docs/parts/part-10.md with C1's record. Then rewrite this
   prompt for P10-C2 (radars · cockpits · forecasts · Morning Brief). Amend
   docs/CODEBASE-MAP.md if the SHAPE changed.
   PROGRESS.md IS CAPPED AT ~350 LINES — replace, never append.

Use pytest -q, never verbose. Don't re-read files you just edited.
```

#### ▶ What Part 9 settled that Part 10 must not reverse

1. **A projection computes NOTHING.** `app/modules/command_center/service.py` has no `select()`,
   no ORM model and no arithmetic; `test_r12_10_the_projection_module_holds_no_query_and_no_model`
   walks the module's NAMESPACE (not its text — C3's source walk failed on its own docstring).
   **R13.9's Morning Brief is the same shape** and the requirement says so explicitly: a VIEW over
   other outputs, no new business logic. Copy this module's structure.
2. **R12.7 and R12.8 are schema validators, not review notes.** `Figure` raises without an `href`;
   `Alert` raises on empty `records` and on a `count` below the list it carries. Radars and
   cockpits should reuse `Figure`/`Alert` rather than inventing parallel shapes.
3. **An empty state distinguishes a measured zero from no measurement.** `CommandCenter.is_empty`
   is empty `activity_log` + no alerts + no figure with a value. A business with a hundred invoices
   and nothing due today sees its zeros; a fresh install is told the figures will fill in.
4. **Committed cash looks FORWARD.** `CashFlowService.committed` over `[today, today+90]`.
   `CashFlowReport.committed` covers the trailing window — right on a report, wrong under a "next
   90 days" label.
5. **`InventoryHealthService.low_stock` reads the reorder levels ONCE.** It used to call `stock()`
   inside its loop over `states()`: 274 queries, 979 ms. A statement-counting test holds it.
   **The generalised lesson: a per-row read hides inside a loop-invariant CALL, not only inside an
   obvious `select()`.**
6. **Arrivals, not `calendar()`,** when you want deliveries — `calendar()` also runs the
   recommendation engine. An **unpromised** arrival is NOT due (R5.7).
7. **Leakage indicators are one alert each, never summed.** C3 removed a tile that added a loss to
   a give-away. Do not re-merge them.
8. **`MarginService.gp` reads a missing purchase price as ZERO — a 100% margin.**
   `MarginAnalysisService` excludes and counts those lines; **`CustomerHealthService.profitability`
   still has the blind spot** — known, recorded, and a live R13.2 candidate.

---

## ▶ Handoff — Part 9 COMPLETE · Part 10 next

Full records in `docs/parts/part-09.md` (both checkpoints) and `part-08.md`; **do not read
either.** Parts 1–7 in `part-01.md`…`part-07.md` and `e2e-gate.md`; do not read those either. The
Parts 5–7 E2E gate passed 44 checks but over **HTTP, not clicked in a browser** — layout and
whether the screens *feel* fast are uncovered, and **R9.12's manual walkthrough remains a human
task.** Part 9's 51 ms figure is a server render, not a paint.

### Read for P10-C1 — these and nothing else

- `docs/REQUIREMENTS.md` §1 + **§14 (R13.x)**. §13 is Part 9's and closed.
- `docs/prompts/part-10.md` · `docs/STANDING-RULES.md` (binding) · **`docs/CODEBASE-MAP.md` in
  full** — R13.1's audit is a question about what exists everywhere, and this is the one
  checkpoint where reading the map beats reading the tree.
- **The likely edit set is mostly DELETIONS plus one or two engines.** It cannot be named in
  advance — that is what the audit decides, and an exploratory checkpoint is exactly when the map
  earns its keep. Expect `tests/test_intelligence.py` to be new.

### Call, don't read — verified signatures, copied from source at P9-C2 close

```python
# app/modules/command_center/ — Part 9. A projection: writes NOTHING, computes NOTHING.
CommandCenterService(db).load(*, as_of: date | None = None) -> CommandCenter
#   .happened[Figure] .happened_caveat · .position[Figure] .position_caveat
#   .attention[Figure] .alerts[Alert] .actions[QuickAction] .activity[ActivityEntry]
#   .alert_count · .is_empty     # R12.15: no activity + no alerts + no figure with a value
Figure(key, label, kind, value, href, hint=None, explained=None)   # kind: money|count|text
#   raises unless href startswith "/"  (R12.7)
Alert(key, label, trigger, threshold, count, records, href, impact_minor=None,
      explained=None, source="")   # raises on empty records / count < len(records)
#   .hidden_count = count - len(records)
AlertRecord(label, href, detail=None) · QuickAction(label, href, why)

# app/db/explain.py — the ONE shape for every explained number (G11). ONE implementation.
Explained(what, value: str | None, formula, window, inputs=(), records=(),
          unknown_reason=None, caveat=None)      # .is_known · .display
Explained.unknown(*, what, formula, reason, window="no data", inputs=(), records=())
Input(label, value, weight=None, missing_reason=None) · SourceRecord(label, href=None)
ExplainedSet().add(e) · .known · .all_unknown
# Rendered by ONE macro:  {{ ui.explain_panel(explained, "Optional title") }}

# app/core/money.py — G1
round_minor(value: Decimal) -> int   # THE one money rounding step
minor_to_text(minor) -> str          # 123456 -> "1234.56" · qty_text(Decimal) -> "40"

# THE SCORES R13.3 consolidates — three, each already the only one of its kind
CustomerHealthService(db).score(customer_id, *, as_of=None) -> Explained
#   also .frequency / .profitability / .payment / .recency — profitability has the
#   missing-purchase-price blind spot (reports 100%); an R13.2 candidate
VendorIntelService(db).score(supplier_id) -> Explained · .lead_time · .on_time_rate
#   .price_history(product_id) · .receipts(supplier_id)
InventoryHealthService(db).abc(...) · .abc_explained(row, *, total_minor)
#   .dead_stock(...) · .dead_stock_explained(row) · .movement_rates(...)
#   .low_stock() -> list[LowStockRow] · .low_stock_explained(row)
#   .reorder_suggestions(*, product_id=None, limit=None)   # R13.6: bare delegation

# R13.6's ONE engine — a second `def recommend` in app/ fails a Part 4 source walk
RecommendationService(db).recommend(*, product_id=None, limit=None) -> list[Recommendation]
#   Recommendation.sentence() is R5.8's prose
ProcurementCalendarService(db).arrivals() -> list[Arrival]   # .bucket .days_away .open_qty
ProcurementCalendarService(db).calendar(*, limit=DEFAULT_LIMIT) -> ProcurementCalendar
#   ARRIVAL_BUCKETS = overdue|today|this_week|later|unpromised

# app/modules/finance/ — Part 8. FLOWS take date_from/date_to, BALANCES take as_of (R11.13).
AgeingService(db).ar_ageing/.ap_ageing(*, as_of=None) -> AgeingReport
#   .rows .buckets .total_minor .due_minor .overdue_minor .unaged_minor
AgeingService(db).collections(*, as_of=None) -> list[CollectionsEntry]   # .explained .reason
AgeingService(db).payments_due(*, as_of=None) -> list[PaymentsDueEntry]
PartyLedgerService(db).customer_statement/.vendor_statement(party_id, *, as_of=None)
open_invoices(db, *, customer_id=None, as_of=None) / open_bills(...) -> list[OpenDocument]
AllocationService(db).allocate_receipt/.allocate_payment(party_id, AllocationCreate, *, actor_id)
CashFlowService(db).cash_flow(*, date_from, date_to) -> CashFlowReport
#   .actual_in_minor .actual_out_minor .actual_net_minor .projected_net_minor .committed .rows
CashFlowService(db).committed(*, date_from, date_to) -> CommittedCash
#   .in_minor .out_minor .net_minor .invoice_count .bill_count .terms (R11.2's prose)
CashFlowService(db).working_capital(*, as_of=None) -> WorkingCapitalSnapshot
#   .receivables_minor .inventory_minor .payables_minor .working_capital_minor
#   .inventory_known .products_without_cost .caveat
CashFlowService(db).cash_conversion_cycle(*, date_from, date_to) -> CashCycleReport
#   .dso/.dio/.dpo/.ccc are Explained · .*_days are int|None (None => unknown)
MarginAnalysisService(db).by_dimension(dimension, *, date_from, date_to) -> MarginReport
#   product|customer|category|business_unit · .revenue_minor .cost_minor .gp_minor
#   .margin_bps (int|None) .line_count .unknown_cost_lines .explained .rows
MarginAnalysisService(db).leakage(*, date_from, date_to) -> LeakageReport
#   .indicators / .fired [.key .label .rule .records .impact_minor .explained .fired]
#   .not_measured · .total_impact_minor (NOT shown as one figure) · .flagged_line_count
GstService(db).summary(*, date_from, date_to) -> GstSummary   # rows are per MONTH
default_window(*, as_of=None) -> tuple[date, date]   # 90 days ending today
today() -> date · month_starts(date_from, date_to) · bps_text(bps) -> "18.5%" | "unknown"

# THE receivable and THE payable — three second definitions were removed; add no fourth
CustomerRepository(db).outstanding_minor(id) -> int · .outstanding_by_customer() -> dict
SupplierRepository(db).outstanding_minor(id) -> int · .outstanding_by_supplier() -> dict

# The rest
ValuationService(db).stock_value() -> list[StockValueRow] · .total_value_minor(rows=None)
#   .unknown_basis_count(rows=None) · .cost_basis(product_id) -> Explained · .ageing(...)
InventoryService(db).states() / .stock() / .bin_stock() / .location_rollup() / .available()
ProcurementRepository(db).pending_count() -> int · SalesRepository(db).pending_count() -> int
ActivityService(db).recent(limit: int = 20) -> list[ActivityLog] · .history(type, id)
csv_rows_response(spec: ListSpec, rows) -> Response     # Part 2's ONE export path
default_business_unit(db) -> uuid.UUID
allocate_document_number(db, *, doc_type, business_unit_id, on_date) -> "INV-202607-00001"
```

Part 2's machinery still holds: `ListSpec` + `view_from_request`, `ensure_unreferenced` /
`soft_delete` / `ensure_unique`, and the `page_header` / `stat` / `badge` / `list_*` /
`history_panel` / `explain_panel` macros.

### Gotchas that will bite P10-C1

- **An "identical output" test only tests what the data distinguishes.** A no-op filter once passed
  one because the seed could not tell the difference. **R13.13 asks for exactly this kind of test —
  so assert the STRUCTURE too**, and pick data that separates the paths.
- **A per-row read hides inside a loop-invariant CALL**, not only inside an obvious `select()` —
  that is what `low_stock` did. Count statements with a `before_cursor_execute` listener
  (`tests/test_command_center.py:_count_queries`); `db.get(Model, id)` in a loop is free.
- **A source-walk test cannot tell a call from a comment.** C3 searched for "portal" and failed on
  its own docstring. Walk the module's NAMESPACE, or count queries.
- **Asserting a rendered link needs Jinja's escaper.** `href="…?a=1&b=2"` lands as `&amp;`; an
  apostrophe lands as `&#39;`. `tests/test_command_center.py` has `_rendered` (escape the CONTENT)
  and `_linked` (escape the URL, not the attribute quotes).
- **`git rm -r` leaves `__pycache__` behind**, so a "deleted" module's directory still exists and
  can still import. Assert the directory's absence AND that the import raises.
- **A fresh-DB test needs its own engine** — the suite's `db` fixture is seeded once, session-wide,
  and cannot be un-seeded. `tests/test_command_center.py:fresh_db` + `fresh_client` (a `get_db`
  dependency override, so the real route and template are exercised) is the pattern.
- **`client.post` COMMITS; `db`-fixture writes roll back.** A POSTing test leaves rows behind, and
  three checkpoints broke the same two Part 1/3 tests by leaving an OPEN document on the first
  customer. Use a subject nothing else asserts about — `spare_customer`, `quiet_customer`, or the
  Part 9 seed's offset-9 customer.
- **Assert on HTML phrases that do NOT straddle a template line break** — six runs and counting.
- **A test can pass without testing anything.** Assert a **floor** on anything you enumerate, and
  assert both directions of a boolean (Part 9's `is_empty` needed a not-empty test to mean anything).
- **Never order by `uuid7()` as a tiebreak** — its low bits are `os.urandom`, so it is not monotonic
  within a millisecond. Sort on something that cannot tie.
- **Environment, unchanged every part:** `create_all` never ALTERs — a new column needs an
  `_ADDITIVE_COLUMNS` entry in `app/main.py` (~line 45). The env var is `DATABASE_URL`, never
  `APEXOS_DATABASE_URL`; stop uvicorn before deleting a scratch `.db` (`Get-CimInstance
  Win32_Process | Where CommandLine -like '*<port>*' | Stop-Process -Force` — no `pkill` here);
  ports 8015–8040 used. PowerShell has no heredocs, so a multi-line commit message needs the Bash
  tool (`git commit -F - <<'EOF'`), and **never edit a source file with `Set-Content`** — it
  round-trips UTF-8 through cp1252 and mojibakes every em dash.

### Do NOT read

`app/seed/core.py` (760 lines — read `app/seed/__init__.py`'s docstring, and
`app/seed/command_center.py` as the smallest section) · `app/modules/finance/{ledger,ageing,
allocation,cash,margin,gst}.py` and `app/modules/command_center/` (finished; signatures above —
open one only if the audit finds a duplication inside it) · every `tests/test_*.py` that already
passes (`test_finance_*`, `test_command_center`, `test_inventory_*`, `test_customer_*`,
`test_quotations`, `test_returns_and_reservations`, `test_fast_entry`, `test_preorder`,
`test_po_revisions`, `test_vendor_*`, `test_procurement_planning`) — read one only if you change
what it covers · anything in `docs/parts/` · `docs/ROADMAP.md` (~17k tokens, planning only) · the
older `docs/` design files, `docs/DELETION-POLICY.md`, `docs/MIGRATION-STRATEGY.md`.

Note `docs/REQUIREMENTS.md` is at v1.2: the stock writer is `InventoryService.record_movement`, and
any older doc naming `post_movement` is wrong.

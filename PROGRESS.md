# ApexOS — Build Progress

> The source of truth for status. **This file is capped at ~350 lines and does not grow.**
> Closed parts live in `docs/parts/`. A new part's handoff **replaces** the previous one here.

_Last updated: 2026-07-29_

### What belongs in this file

Exactly one `▶ NEXT SESSION PROMPT` and exactly one `▶ Handoff`, both rewritten — never appended
to — by the session that closes a checkpoint. Anything else belongs in `docs/parts/`. **A hard
cap, not a preference:** at Part 3 close this file was 1,212 lines ≈ 22k tokens, re-read every
session. Each finished checkpoint's record moves to `docs/parts/part-0N.md` as it closes.

---

# ▶ CURRENT WORK — read this first

**Parts 1–7 and 9 COMPLETE. Part 8 DELIVERED but not formally closed** (R11.7 open, below).
**Part 10's C1 is done**; the build continues at **P10-C2**, which closes Part 10. **All work is
on `main`**; nothing in this run is tagged (waived), so the SHA table is the record.

| Checkpoint | From | Commit | Tests | Ruff |
|---|---|---|---|---|
| **P8-C3** margin ×4 · leakage · GST | `30b3cc1` | `0ce6931` | 721 → 757 | 37 → **35** |
| **P9-C1** tiles · alerts · activity · quick actions | `c316861` | `45b8218` | 757 → 786 | 35 → 35 |
| **P9-C2** empty state · placeholder deleted — **PART 9 COMPLETE** | `8c87f52` | `42b4392` | 786 → 794 | 35 → 35 |
| **P10-C1** the R13.1 audit + the costed-line unification | `4c814b1` | `bdf384b` | 794 → **818** | 35 → 35 |
| **baseline fix** the two flaky R9.12 tests — no product change | `642896c` | `db33e38` | 818 → 818 | 35 → 35 |

**P10-C2's features are NOT built.** That firing went entirely on making the baseline
trustworthy: two `test_fast_entry.py` R9.12 tests were failing together about one session in
three, and building radars on a suite that fails at random means you cannot tell your own
regressions from noise. **The C2 prompt below is unchanged and still the next thing to do.**

**Part 9 measured (R12.12/R12.14):** one `/` page load is **81 queries, 51 ms median warm render**
(184 ms cold), uvicorn over real HTTP — down from 344 / 1,096 ms. Thirteen grouped projections,
none growing with row count. Not a browser measurement. Detail in `docs/parts/part-09.md`.

**R11.7 is PARTIALLY MET (P0) and OPEN by the user's decision on 2026-07-29.** Its "freight not
recovered" indicator cannot be built — no freight/shipping/carriage field exists anywhere in the
schema — and R11.8 forbids an indicator with nothing to click, so it is named on screen under
*Not measured*. **Part 8 must not be called closed or tagged** until it is settled: capture
freight on the invoice/bill, or strike the indicator with a reason (the register strikes through,
never deletes). **Do not resolve it inside another part.**

---

## ▶ THE R13.1 AUDIT — the deliverable. Do not redo this survey.

Every score, radar, suggestion and alert parts 4–9 produce. **23 outputs.** One was duplicated
and is now unified; four were already unified; one pair looks duplicated and is not.

| # | Output | Lives in | Notes |
|---|---|---|---|
| 1 | `VendorIntelService.score` | `suppliers/vendor.py` | 60% hand-entered scorecard + 40% measured on-time, renormalised over what exists |
| 2 | `.lead_time` | " | measured `confirmed_at`→`received_at`, last 12 receipts |
| 3 | `.on_time_rate` | " | `received <= promised` is on time (R5.4's boundary) |
| 4 | `.price_history` | " | per product, not a score but an explained series |
| 5 | `RecommendationService.recommend` | `procurement/recommend.py` | **R13.6's ONE reorder engine.** Shortfall vs on hand + **on order** |
| 6 | `.reorder_suggestions` | `inventory/health.py` | **bare delegation to #5** — already unified |
| 7 | `ProcurementCalendarService.arrivals` | `procurement/recommend.py` | 5 buckets; **unpromised ≠ due** (R5.7) |
| 8 | `InventoryHealthService.abc` | `inventory/health.py` | consumption **value**, cumulative-share bands |
| 9 | `.dead_stock` | " | no consumption in N days |
| 10 | `.movement_rates` | " | per-month velocity, fast/slow |
| 11 | `.low_stock` | " | on **available** = on hand − reserved (R7.10) |
| 12 | `ValuationService.cost_basis` | `inventory/valuation.py` | weighted average (D-A: no FIFO) |
| 13 | `.ageing` | " | receipt-date derived, **approximate — says so** |
| 14 | `CustomerHealthService.score` | `customers/health.py` | 25/30/25/20 frequency/profitability/payment/recency |
| 15 | `CreditPolicyService.explain` | `customers/credit.py` | the credit-gate decision |
| 16 | `AgeingService.ar_ageing` / `.ap_ageing` | `finance/ageing.py` | `bucket_for()` is the one rule; due **today** is not overdue |
| 17 | `.collections` | " | the chase list, `.explained` per entry |
| 18 | `.payments_due` | " | oldest due first |
| 19 | `CashFlowService.cash_flow` / `.committed` / `.working_capital` | `finance/cash.py` | flows take `date_from`/`date_to`, balances `as_of` (R11.13) |
| 20 | `.cash_conversion_cycle` | " | DSO/DIO/DPO/CCC, four `Explained` |
| 21 | `MarginAnalysisService.by_dimension` | `finance/margin.py` | product / customer / category / business_unit |
| 22 | `.leakage` | " | 2 indicators + 1 **stated gap** (R11.7) |
| 23 | Command Center's 4 alert families | `command_center/service.py` | a **view** over #11, #17, #22 and arrivals — computes nothing |

**The one duplication, now unified (R13.2/R13.13).** `MarginService.gp` reads a missing purchase
price as **zero** → a 100% margin. Three consumers; only `MarginAnalysisService` checked first.
The decision is now **`MarginService.gp_costed(line, *, buy_prices=None) -> int | None`**.
`CustomerHealthService.profitability` **really was wrong** (up to 30 of 100 points for an
unmeasured number — a G11 violation recorded at P8-C3 rather than fixed); `CashFlowService._cogs`
was **right by coincidence** and no figure moved — COGS 14,691.95 and DIO 8,283 days before and
after, measured, and the docstrings say so rather than claiming a fix.

**Already unified — record, do not rebuild:** G11 is one `Explained` (`db/explain.py`); #6
delegates to #5; `recommend.py:_lead_time` is a *memoising delegation* to #2, not a second
measurement; `InventoryRepository.consumption` is one definition of demand behind #8/#9/#10; and
the `outstanding_by_*` pair is still THE receivable and THE payable.

**Deliberately NOT unified:** #11 fires on **available** (reserved stock cannot cover a new order,
R7.10); #5 works from **on hand + on order** (a placed PO must not be placed twice, R5.9). Two
questions, not one asked twice. A test asserts each still carries the term the other does not.

**Guards, all `ast`-parsed (a text search cannot tell a call from a mention):** only
`MarginService` may call `gp`; one `def recommend`; one `Explained`/`Input`; one `default_window`
and one `month_starts`; **no table stores a DERIVED score** — `supplier_evaluation` is exempt and
its exemption is pinned, because a score somebody **typed** is data and one the system **worked
out** is not.

### ▶ How to start the next session

Type **`Start next part of development`** in a fresh session; `CLAUDE.md` binds that phrase to the
prompt below. **The session that closes a checkpoint owns it.**

#### ▶ NEXT SESSION PROMPT — Part 10, C2 (radars · cockpits · forecasts · Morning Brief)

```
Continue the ApexOS build. Do this in order:

1. git checkout main && git pull origin main, then git status — one writer per working tree;
   if it is dirty, STOP and report. Nothing is tagged (waived); the SHA table above is the
   record.

2. Read the "▶ CURRENT WORK" block below, INCLUDING THE R13.1 AUDIT TABLE. That table is a
   deliverable C1 produced and you must not redo the survey — it names every output you are
   about to assemble and where each lives. Part 8's R11.7 stays open; not your problem.

3. Read docs/REQUIREMENTS.md §1 (G1–G17) + §14 (R13.x). Then docs/prompts/part-10.md and
   docs/STANDING-RULES.md (binding). `git show --stat bdf384b` for C1's shape. Do NOT open
   docs/ROADMAP.md (~17k tokens) or anything in docs/parts/.

4. Verify the baseline before writing code (from apps/api, venv activated):
     python -m pytest -q                  # expect 818 passed — RELIABLY, 16 runs verified
     python -m ruff check app/ tests/     # expect EXACTLY 35 — 36 is a regression
   TEN PARTS HAVE ADDED ZERO NEW FINDINGS. If a test fails and passes on re-run, do NOT
   shrug — but DO capture the assertion text before theorising. See the open-flake note.

5. C2 is the visible half: R13.3, R13.4, R13.5, R13.7, R13.8, R13.9, R13.10, R13.11, R13.14.

   **ASSEMBLE, DO NOT COMPUTE.** Every radar and cockpit is a view over the audit table's
   23 outputs. `app/modules/command_center/` is the shape to copy — no `select()`, no ORM
   model, no arithmetic, and a namespace-walk test that keeps it that way. R13.9 says the
   Morning Brief MUST NOT contain new business logic, and the same discipline belongs in
   the radars.

   **THE ONE THING WITH NO ENGINE YET IS CHURN RISK (R13.4).** Dead stock has
   `InventoryHealthService.dead_stock`; margin leakage has `MarginAnalysisService.leakage`;
   churn has nothing, and `CustomerHealthService.recency` is the nearest thing. BUILD IT IN
   `app/modules/customers/`, the part that owns customers, and READ it from the radar — a
   churn score computed in a radar screen is exactly the second definition C1 spent a
   checkpoint removing.

   **FORECASTS (R13.7/R13.8): trailing-window, window STATED, confidence SAID OUT LOUD.**
   Purchase, sales and cash requirement. Transparent arithmetic only (R13.12) — trailing
   averages and simple linear projections, nothing a founder cannot redo by hand. NO ML
   dependency, NO runtime LLM (G12); a test asserts the dependency list.
   R13.14 wants each forecast tested AGAINST A KNOWN SERIES, not just against the seed.

   **REUSE `Figure` AND `Alert` from `command_center/schemas.py`.** They already enforce
   R12.7 (an href or it will not construct) and R12.8 (records or it will not construct),
   which are R13.10's requirements under different numbers. Do not invent parallel shapes.

6. Constraints that bind:
     - G11/R13.10/R13.11: definition, formula, window and linked records on screen, via
       `Explained` + `explain_panel`. Insufficient history says so — NEVER 0, never 50.
       C1's precedent: distinguish "no data yet" from "the data cannot be costed", because
       only the second is actionable.
     - G7: derived, never stored. A `*_score` column fails an existing test.
     - G1: money is integer minor units through `round_minor`; a ratio rounds ONCE and says
       where (`margin.py:_bps`, `cash.py:_days`).
     - G15: a projection writes no activity_log row. G16: call the earlier service.
     - New plain GET routes must 200 with NO query parameters, and need a real empty state —
       `CommandCenter.is_empty` is the pattern, and R12.15's fresh-DB test is where three
       lying hints were found. Add the same fresh-DB pass here.
     - Any new model owes app/db/references.py an entry, even an empty tuple (R3.7).

7. Work on main. No branches, no PRs, NO TAGS. Commit at the END OF C2 and push. Personal
   credentials only (github.com/1992tushar/apexos).

8. NAME EVERY NEW TEST AFTER THE REQUIREMENT IT PROVES — `pytest -q -k r13_` is the
   evidence (24 tests today). MUTATION-CHECK the new suite once: make a forecast return a
   default where history is insufficient, and make the Morning Brief rank something it has
   no record for.
   DRIVE THE REAL APP before calling it done — it has found a defect in all six checkpoints
   of Parts 8–10, most recently a DIO claim that measurement did not support.

9. BEFORE you run low, update the "▶ CURRENT WORK" block: the SHA table, R-numbers passed
   and outstanding, gotchas, decisions a later checkpoint must not reverse, and the four
   delta lines. **KEEP THE R13.1 AUDIT TABLE — it is a deliverable, and a test asserts it is
   still in this file.** Append C2's record to docs/parts/part-10.md. Then rewrite this
   prompt for P11-C1 (measure everything, write the findings down, NO FIXES — R14.7/R14.8
   forbid optimising without a baseline). Amend docs/CODEBASE-MAP.md if the SHAPE changed.
   PROGRESS.md IS CAPPED AT ~350 LINES — replace, never append.

Use pytest -q, never verbose. Don't re-read files you just edited.
```

#### ▶ What C1 settled that C2 must not reverse

1. **`MarginService.gp_costed` is the ONE costable-line decision.** Only `MarginService` may call
   `gp` — an `ast` guard fails otherwise. If a forecast or cockpit needs gross profit, it uses
   `gp_costed` and discloses what it excluded.
2. **A projection computes nothing.** `command_center/service.py` is the shape; its namespace-walk
   test is the enforcement. R13.9's Morning Brief is the same shape by requirement.
3. **`Figure` and `Alert` enforce R12.7/R12.8 structurally.** Reuse them; do not relax them to
   make an empty state easier — omit the alert instead.
4. **`is_empty` distinguishes a measured zero from no measurement.** A fresh install is told the
   figures will fill in; a quiet day still shows its zeros.
5. **Do not merge `low_stock` with the reorder engine.** Different bases, on purpose (#11 vs #5).
6. **`supplier_evaluation` is the only table that may hold score columns** — it is hand-entered.
7. **Overclaiming a fix is a defect.** C1's first draft said the `_cogs` change fixed DIO;
   measurement showed no number moved, and the record now says so. Measure before claiming.

---

## ▶ Handoff — P10-C1 delivered · Part 10 closes at C2

Full records in `docs/parts/part-10.md` (C1) and `part-09.md`; **do not read either.** Parts 1–7
in `part-01.md`…`part-07.md` and `e2e-gate.md`. The Parts 5–7 E2E gate passed 44 checks but over
**HTTP, not clicked in a browser**, so layout and whether screens *feel* fast are uncovered, and
**R9.12's manual walkthrough remains a human task.**

### Read for P10-C2 — these and nothing else

- `docs/REQUIREMENTS.md` §1 + **§14 (R13.x)** · `docs/prompts/part-10.md` ·
  `docs/STANDING-RULES.md` (binding) · the audit table above instead of `CODEBASE-MAP.md`'s
  survey sections.
- `app/modules/command_center/{schemas,service}.py` **in full** — the shape every new projection
  copies, and the source of `Figure`/`Alert`.
- **The likely edit set:** a new `app/modules/intelligence/` (radars, cockpits, forecasts, the
  Brief) · a churn engine in `app/modules/customers/` · `app/web/pages/intelligence.py` +
  templates · `tests/test_intelligence.py` (exists — 24 tests) and a new screens test.

### Call, don't read — the signatures C2 needs, from source at P10-C1 close

The **audit table above** names where every output lives; these are the exact call shapes.

```python
# THE costable-line decision (Part 10 C1). Only MarginService may call `gp`.
MarginService(db).gp_costed(line, *, buy_prices=None) -> int | None   # None => cost UNKNOWN
MarginService(db).purchase_price_map() -> dict[uuid, int]   # hoist out of loops; ONE query
MarginService(db).gp(line) -> int                          # raw; reads missing cost as ZERO

# app/db/explain.py — the ONE explained-number shape (G11, R13.10/R13.11)
Explained(what, value: str | None, formula, window, inputs=(), records=(),
          unknown_reason=None, caveat=None)      # .is_known · .display
Explained.unknown(*, what, formula, reason, window="no data", inputs=(), records=())
Input(label, value, weight=None, missing_reason=None) · SourceRecord(label, href=None)
ExplainedSet().add(e) · .known · .all_unknown     # {{ ui.explain_panel(e, "Title") }}

# app/modules/command_center/schemas.py — REUSE these, do not re-invent
Figure(key, label, kind, value, href, hint=None, explained=None)  # kind: money|count|text
#   raises unless href startswith "/"   (R12.7 == R13.10's linked records)
Alert(key, label, trigger, threshold, count, records, href, impact_minor=None,
      explained=None, source="")   # raises on empty records / count < len(records)
#   .hidden_count · AlertRecord(label, href, detail=None) · QuickAction(label, href, why)
CommandCenterService(db).load(*, as_of=None) -> CommandCenter    # .is_empty is the pattern

# Scores (R13.3) — consolidate, do not rebuild
CustomerHealthService(db).score(customer_id, *, as_of=None) -> Explained
#   .frequency / .payment / .recency(customer_id, *, as_of) · WINDOW_DAYS = 365
#   .profitability(...) -> (margin_pct|None, revenue_minor, gp_minor, uncosted_line_count)
VendorIntelService(db).score(supplier_id) -> Explained · .lead_time · .on_time_rate
#   .price_history(product_id) · .receipts(supplier_id)
InventoryHealthService(db).abc(...) · .abc_explained(row, *, total_minor)
#   .dead_stock(...) · .dead_stock_explained(row) · .movement_rates(...)
#   .low_stock() · .low_stock_explained(row) · .reorder_suggestions(*, product_id, limit)
ValuationService(db).cost_basis(product_id) -> Explained · .stock_value()
#   .total_value_minor(rows=None) · .unknown_basis_count(rows=None) · .ageing(...)

# Finance (Part 8) — flows take date_from/date_to, balances take as_of (R11.13)
AgeingService(db).ar_ageing/.ap_ageing(*, as_of=None) · .collections(...) · .payments_due(...)
CashFlowService(db).cash_flow(*, date_from, date_to) -> CashFlowReport
#   .actual_in_minor .actual_out_minor .actual_net_minor .projected_net_minor .committed .rows
CashFlowService(db).committed(*, date_from, date_to) -> CommittedCash   # .net_minor .terms
CashFlowService(db).working_capital(*, as_of=None) -> WorkingCapitalSnapshot
#   .receivables_minor .inventory_minor .payables_minor .working_capital_minor .caveat
CashFlowService(db).cash_conversion_cycle(*, date_from, date_to) -> CashCycleReport
MarginAnalysisService(db).by_dimension(dim, *, date_from, date_to) -> MarginReport
#   .revenue_minor .cost_minor .gp_minor .margin_bps .line_count .unknown_cost_lines .explained
MarginAnalysisService(db).leakage(*, date_from, date_to) -> LeakageReport   # .fired .not_measured
default_window(*, as_of=None) -> tuple[date, date]  # 90 days ending today · today()
month_starts(date_from, date_to) · bps_text(bps) -> "18.5%" | "unknown"

# The rest
RecommendationService(db).recommend(*, product_id=None, limit=None)   # .sentence is a PROPERTY
ProcurementCalendarService(db).arrivals() · .calendar(*, limit=DEFAULT_LIMIT)
CustomerRepository(db).outstanding_by_customer() -> dict   # THE receivable · supplier pair too
ActivityService(db).recent(limit=20) · .history(entity_type, entity_id)
csv_rows_response(spec: ListSpec, rows) · default_business_unit(db)
round_minor(Decimal) -> int · minor_to_text(minor) · qty_text(Decimal)
```

#### ▶ ONE FLAKE IS STILL OPEN — do not re-chase the disproven theory

`test_r8_5_notes_are_recordable_against_a_customer` **failed once** and has not recurred in
**16 consecutive full runs**. It is recorded here rather than guessed at. If you see it, capture
the assertion text before theorising — that mistake is what made the first attempt useless.

**Already disproven, with the measurement:** the tie theory. `notes()` sorts on
`(created_at DESC, id DESC)` and `id` is a `uuid7` whose low bits are random, so a `created_at`
tie *would* order by coin flip — but `add_note`'s stamps do not tie. Measured: consecutive
`add_note` calls land **~0.5 ms apart at microsecond resolution**. A fix for that
non-existent defect was written, measured, disproven and reverted rather than shipped.

**The trap that produced the wrong theory, worth remembering:**
`time.get_clock_info("time").resolution` reports **0.015625 s** on this machine, and two
back-to-back `datetime.now(UTC)` calls with nothing between them return the same value ~100%
of the time. Neither fact describes `datetime.now()` under real work — it resolves to
microseconds there. **Do not reason about `datetime.now()` from `time.time()`'s clock info.**

### Gotchas that will bite P10-C2

- **A `set` of UUIDs iterates by hash — arbitrarily, and differently every session**, because
  the ids are regenerated with the throwaway DB. `next(iter(some_id_set))` is not a choice, it
  is a dice roll, and it made both R9.12 tests fail one session in three. Sort, or pick from a
  query's order.
- **`/sales/new` renders only `PICKER_PAGE_SIZE` (200) customers and the seed has 250+.** A
  founder with a longer list cannot select everyone from that screen. Recorded as debt, not
  fixed with a bigger number — the fix is Part 2's list machinery plus a search, in Part 11.
  Any test comparing a rendered page against an **unbounded** service result has this bug.
- **A fixture whose isolation depends on other tests is not isolated.** `client.post` COMMITS.
  C1's first fixture took "the last customer in code order", passed alone and failed in the suite
  because an earlier test had left orders there. **Create your own subject** —
  `tests/test_intelligence.py:lonely_customer` is the pattern.
- **`Path.relative_to` yields backslashes on Windows.** Three AST guards compared against
  posix strings and matched nothing; a source walk that finds nothing looks exactly like a pass.
  Use `.as_posix()`, and assert a floor on whatever you enumerate.
- **Parse, don't grep.** A text search cannot tell a call from a comment — a Part 8 walk failed on
  its own docstring. `ast` for structure, a `before_cursor_execute` listener for query counts.
- **An equality between two code paths only tests what the data distinguishes.** R13.13's whole
  risk. Assert the structure too, and assert the discriminating case EXISTS (C1's uncosted-line
  count is asserted non-zero for exactly this reason).
- **Measure before claiming.** C1 nearly shipped "this fixed DIO" when the number had not moved,
  and the flake hunt nearly shipped a fix for a tie that does not happen.
- **A per-row read hides inside a loop-invariant CALL** — Part 9 found `stock()` inside a loop
  (274 queries). `gp` resolves a price per call: hoist `purchase_price_map()`.
- **Assert on HTML phrases that do NOT straddle a template line break** — six runs and counting.
  Escaping: `_rendered` (content) / `_linked` (URL) in `tests/test_command_center.py`.
- **Never order by `uuid7()` as a tiebreak** — low bits are `os.urandom`, not monotonic within a
  millisecond. `CreditPolicyService.history` shows the fix: sort on a discriminating column.
- **A fresh-DB test needs its own engine**; the suite's `db` is seeded session-wide.
  `test_command_center.py:fresh_db` / `fresh_client` (a `get_db` override) is the pattern.
- **Orphaned pytest processes lock the scratch DB on Windows** (`PermissionError WinError 32`).
  Stop them by PID; do not touch the unrelated `featurelens` process.
- **Environment, unchanged every part:** `create_all` never ALTERs — a new column needs an
  `_ADDITIVE_COLUMNS` entry in `app/main.py` (~line 45). The env var is `DATABASE_URL`, never
  `APEXOS_DATABASE_URL`; ports 8015–8040 used. PowerShell has no heredocs, so a multi-line commit
  message needs the Bash tool (`git commit -F - <<'EOF'`), and **never edit a source file with
  `Set-Content`** — it mojibakes every em dash.

### Do NOT read

`app/seed/core.py` (760 lines — read `app/seed/__init__.py`'s docstring, and
`app/seed/command_center.py` as the smallest section) · `app/modules/finance/{ledger,ageing,
allocation,cash,margin,gst}.py`, `app/modules/suppliers/vendor.py`,
`app/modules/inventory/{valuation,health}.py`, `app/modules/customers/{credit,timeline,health}.py`,
`app/modules/procurement/{preorder,recommend}.py` — **the audit table above is what you needed
them for**; open one only when you change it · every `tests/test_*.py` that already passes ·
anything in `docs/parts/` · `docs/ROADMAP.md` (~17k tokens) · the older `docs/` design files,
`docs/DELETION-POLICY.md`, `docs/MIGRATION-STRATEGY.md`.

Note `docs/REQUIREMENTS.md` is at v1.2: the stock writer is `InventoryService.record_movement`.

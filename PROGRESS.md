# ApexOS — Build Progress

> The source of truth for status. **This file is capped at ~350 lines and does not grow.**
> Closed parts live in `docs/parts/`. A new part's handoff **replaces** the previous one here.

_Last updated: 2026-07-29 (P10-C2)_

### What belongs in this file

Exactly one `▶ NEXT SESSION PROMPT` and exactly one `▶ Handoff`, both rewritten — never appended
to — by the session that closes a checkpoint. Anything else belongs in `docs/parts/`. **A hard
cap, not a preference:** at Part 3 close this file was 1,212 lines ≈ 22k tokens, re-read every
session. Each finished checkpoint's record moves to `docs/parts/part-0N.md` as it closes.

---

# ▶ CURRENT WORK — read this first

**Parts 1–7, 9 and 10 FEATURE-COMPLETE. Part 8 DELIVERED but not formally closed** (R11.7
open, below). **Part 10 is built but carries one recorded gap** (R13.14, below) — not tagged
on that account, same as Part 8's R11.7. The build continues at **Part 11, C1** (measurement
only — see the NEXT SESSION PROMPT). **All work is on `main`**; nothing in this run is tagged
(waived), so the SHA table is the record.

| Checkpoint | From | Commit | Tests | Ruff |
|---|---|---|---|---|
| **P9-C1** tiles · alerts · activity · quick actions | `c316861` | `45b8218` | 757 → 786 | 35 → 35 |
| **P9-C2** empty state · placeholder deleted — **PART 9 COMPLETE** | `8c87f52` | `42b4392` | 786 → 794 | 35 → 35 |
| **P10-C1** the R13.1 audit + the costed-line unification | `4c814b1` | `bdf384b` | 794 → **818** | 35 → 35 |
| **baseline fix** the two flaky R9.12 tests — no product change | `642896c` | `db33e38` | 818 → 818 | 35 → 35 |
| **P10-C2** radars · cockpits · forecasts · churn · Brief — **built thin** | `a281160` | `6060937` | 818 → **819** | 35 → 35 |

**P10-C2 was built thin, at the user's explicit request, trading away one P0 requirement —
recorded rather than left implicit:**

* **R13.14 is UNMET.** No test asserts a score or forecast against a hand-computed/known
  series. The five new figures (3 forecasts + churn's two arithmetic paths) were checked by
  hand against the rendered `/intelligence` page this session, not pinned in a suite.
* No mutation check was run against the two new engines (`ChurnRiskService`, `ForecastService`).
* No fresh-DB empty-state pass exercises `Intelligence.is_empty` — the property exists,
  untested.
* `pytest -q` → **819** (the route walk absorbed `/intelligence` as one parametrised case; zero
  tests were hand-written). `ruff` unchanged at **35**. The real app WAS driven on uvicorn —
  every drill-through resolved; the two radars that render nothing (churn, leakage) were
  checked against the Command Center's own identical window and found consistent, not broken.

Full record, including what each new file does and why: `docs/parts/part-10.md`'s **C2**
section (added this session — the C1 section above it is still the survey, unchanged).
**Whichever session next touches Part 10 or the Intelligence Layer should backfill R13.14 or
explicitly accept it as debt** — same treatment as R11.7 below. Do not build a THIRD forecast
or score engine while it's unmet; the R13.2 guards would fail before you got far.

**Part 9 measured (R12.12/R12.14):** one `/` page load is **81 queries, 51 ms median warm render**
(184 ms cold), uvicorn over real HTTP — down from 344 / 1,096 ms. Thirteen grouped projections,
none growing with row count. Not a browser measurement. Detail in `docs/parts/part-09.md`.
**`/intelligence` has not been query-counted or timed** — Part 11 C1's measurement pass is
where that number belongs; do not guess at it.

**R11.7 is PARTIALLY MET (P0) and OPEN by the user's decision on 2026-07-29.** Its "freight not
recovered" indicator cannot be built — no freight/shipping/carriage field exists anywhere in the
schema — and R11.8 forbids an indicator with nothing to click, so it is named on screen under
*Not measured*. **Part 8 must not be called closed or tagged** until it is settled: capture
freight on the invoice/bill, or strike the indicator with a reason (the register strikes through,
never deletes). **Do not resolve it inside another part** — Part 11 is UI/perf/security only
(GOAL: "Add NO new features").

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

#### ▶ NEXT SESSION PROMPT — Part 11, C1 (measure everything — NO FIXES)

```
Continue the ApexOS build. Do this in order:

1. git checkout main && git pull origin main, then git status — one writer per working tree;
   if it is dirty, STOP and report. Nothing is tagged (waived); the SHA table above is the
   record.

2. Read the "▶ CURRENT WORK" block below in full, including the R13.14 debt note on P10-C2
   and the still-open R11.7 note. Neither is yours to fix in this part — R11.7 belongs to
   whichever session settles Part 8, and Part 11's own GOAL line forbids new features, which
   is what fixing R13.14 (writing the missing tests is fine; changing behaviour is not) or
   R11.7 (a new freight field) would be.

3. Read docs/STANDING-RULES.md (binding) + docs/REQUIREMENTS.md §15 (R14.x — your acceptance
   contract) + docs/prompts/part-11.md + docs/17-design-system.md. Do NOT open docs/ROADMAP.md
   (~17k tokens) or anything in docs/parts/.

4. Verify the baseline before measuring anything (from apps/api, venv activated):
     python -m pytest -q                  # expect 819 passed
     python -m ruff check app/ tests/     # expect EXACTLY 35 — 36 is a regression
   TEN PARTS HAVE ADDED ZERO NEW RUFF FINDINGS; Part 11 (R14.x) is where those 35 finally
   get cleared, but NOT in C1 — C1 measures, it does not fix.

5. C1 IS MEASUREMENT-ONLY. NO FIXES THIS SESSION (R14.7/R14.8) — a session that measures
   and fixes in one pass loses the baseline C3 is graded against. If you find yourself
   editing app/ code to make a number look better, STOP.

   Measure and WRITE DOWN, with evidence, in the PROGRESS.md resume block C1 leaves behind:
     - Page timings and query counts for the heaviest screens — `/`, `/intelligence`,
       `/inventory`, `/warehouse`, `/finance`. Command Center's own numbers (81 queries,
       ~51ms warm) are the template; `/intelligence` has NEVER been measured — do it fresh.
     - N+1s and missing indexes, the same way Part 9 found `low_stock` calling `stock()`
       inside a loop — profile, don't guess.
     - Which list screens do NOT go through app/db/listing.py's ListSpec machinery yet.
       Known suspects from CODEBASE-MAP's "Known debt": `/analytics` (div-height fake
       charts), `/warehouse` and `/inventory` (page_size=300, no pagination), `/categories`
       (full parent dropdown per row), `/sales/new` (200-customer cap against a 250+ seed).
       Confirm each, and look for others.
     - Click counts on the top-10 most frequent tasks (report the number, don't reduce it
       yet).
     - UI consistency gaps — spacing/type/colour drift across the ~21 screens.
     - Security: input validation gaps, file-upload handling (if any), error messages that
       leak internals, a dependency audit for known CVEs.
     - Static asset size, template render cost.

6. Constraints that bind:
     - D-B resizes this part: the founder is the only user. Accessibility narrows to form
       labels and contrast — no screen-reader table work. The per-route authz audit and
       "every POST is guarded" test are SHOULD, not MUST (R14.13/R14.14) — the Part 1 guard
       mechanism is what matters with one user.
     - D-D: saved views are CUT. Do not measure toward building them.
     - Add NO new features. A new screen belongs nowhere in this part — say so and stop.

7. Work on main. No branches, no PRs, NO TAGS (this checkpoint doesn't close the part).
   Commit at the END OF C1. Personal credentials only (github.com/1992tushar/apexos).

8. BEFORE you run low, update the "▶ CURRENT WORK" block: the SHA table, and a full
   MEASUREMENTS section with every number above, in enough detail that C3 can be graded
   against it without re-measuring. Rewrite this prompt for P11-C2 (fix batch 1 — UI
   consistency, de-duplication, global search + Ctrl+K palette; the highest-value items for
   a solo founder per docs/prompts/part-11.md). PROGRESS.md IS CAPPED AT ~350 LINES —
   replace, never append. Amend docs/CODEBASE-MAP.md only if you found the shape was
   already wrong, not to record measurements (those belong here, not there).

Use pytest -q, never verbose. Don't re-read files you just edited.
```

#### ▶ What P10 built that P11 must not rebuild or re-measure into fixing

1. **The Intelligence Layer exists at `/intelligence`.** `app/modules/intelligence/` (forecast,
   schemas, service — no model, no repository) + `app/modules/customers/churn.py` (the one new
   engine). Full shape in `docs/parts/part-10.md`'s C2 section. **R13.14 is unmet** — C1 may
   measure `/intelligence` freely but writing its missing tests is R14.x/general-quality work
   for a later checkpoint to decide on, not something to silently patch mid-measurement.
2. **`MarginService.gp_costed` is still the ONE costable-line decision** — an `ast` guard fails
   if anything but `MarginService` calls raw `gp`.
3. **`Figure` and `Alert` (command_center/schemas.py) enforce R12.7/R12.8 structurally** and are
   reused, not reinvented, by `/intelligence` too. Do not relax them to make measurement easier.
4. **`is_empty` distinguishes a measured zero from no measurement** on both `/` and
   `/intelligence`. Any UI-consistency pass touching either template must preserve it.
5. **`supplier_evaluation` is the only table that may hold score columns** — hand-entered, not
   derived. Don't let a de-duplication pass "simplify" that exemption away.

---

## ▶ Handoff — P10-C2 delivered thin · Part 11 begins at C1

Full records in `docs/parts/part-10.md` (both C1 and C2) and `part-09.md`; **do not read
these — the notes above and here are what C1 needs.** Parts 1–7 in `part-01.md`…`part-07.md`
and `e2e-gate.md`. The Parts 5–7 E2E gate passed 44 checks but over **HTTP, not clicked in a
browser**, so layout and whether screens *feel* fast are uncovered, and **R9.12's manual
walkthrough remains a human task** — no session has done it yet, across ten parts.

### Read for P11-C1 — these and nothing else

- `docs/STANDING-RULES.md` (binding) · `docs/REQUIREMENTS.md` §15 (R14.x) ·
  `docs/prompts/part-11.md` · `docs/17-design-system.md`.
- **Do NOT** re-open `docs/REQUIREMENTS.md` §14 or the R13.1 audit table above for this
  checkpoint — Part 11 doesn't touch business logic, so C1 has no need of where each score
  lives, only of which *screens* exist. The nav list in `app/web/core.py:NAV_ITEMS` (19 routes,
  including `/intelligence` now) is the actual screen inventory to measure against.

### Where things are, without re-deriving them

- **Query-count / timing pattern:** `tests/test_command_center.py` has a `before_cursor_execute`
  listener that counts statements per page load — copy that technique to measure `/intelligence`,
  `/inventory`, `/warehouse`, rather than eyeballing.
- **List machinery:** `app/db/listing.py` (`ListSpec`/`build_select`) + `app/web/listing.py`
  (`view_from_request`). A screen NOT going through these is doing its own pagination/sort/filter
  — that's what C1 is checking for.
- **The UI vocabulary:** `templates/_macros.html` (`stat`, `badge`, `list_table`, `explain_panel`,
  …) — a screen with markup that doesn't call these macros is a UI-consistency finding.
- **Known suspects already on record** (`docs/CODEBASE-MAP.md`'s "Known debt" section):
  `/analytics` fake div-height charts, `/warehouse` + `/inventory` unpaginated at
  `page_size=300`, `/categories`' per-row parent dropdown, `/sales/new`'s 200-customer cap
  against 250+ seeded. Confirm each with a real measurement rather than re-describing them.

#### ▶ ONE FLAKE, LONG QUIET — do not re-chase it

`test_r8_5_notes_are_recordable_against_a_customer` failed once, long ago, and has not recurred
in **17+ consecutive full runs** (including this session's). The tie theory was chased and
disproven (`add_note`'s timestamps land ~0.5ms apart at microsecond resolution, so they don't
actually tie) — a fix for that non-existent defect was written, measured, and reverted rather
than shipped. If it reappears, capture the assertion text before theorising; don't re-derive the
tie theory from `time.get_clock_info()`'s 15.6ms resolution, which does not describe
`datetime.now()` under real work.

### Gotchas that will bite P11

- **`Path.relative_to` yields backslashes on Windows** — any new source-walk/AST check must use
  `.as_posix()`, or it silently matches nothing and looks like a pass.
- **Orphaned pytest processes lock the scratch DB on Windows** (`PermissionError WinError 32`).
  Stop them by PID; do not touch the unrelated `featurelens` process.
- **A per-row read hides inside a loop-invariant CALL, not just an obvious `select()`.** Part 9
  found `stock()` called inside a loop over `states()` — 274 queries. Profile calls, not just
  queries, when measuring.
- **A `set` of UUIDs iterates by hash, differently every session** — never pick from one with
  `next(iter(...))`; sort, or take from a query's own order. This is what made two R9.12 tests
  flaky one session in three, fixed at `db33e38`.
- **Assert on HTML phrases that do NOT straddle a template line break.** Escaping helpers
  `_rendered` (content) / `_linked` (URL) live in `tests/test_command_center.py` if a
  UI-consistency test needs the same pattern.
- **Environment, unchanged every part:** `create_all` never ALTERs — a new column needs an
  `_ADDITIVE_COLUMNS` entry in `app/main.py` (~line 45). The env var is `DATABASE_URL`, never
  `APEXOS_DATABASE_URL`; ports 8015–8040 used. PowerShell has no heredocs, so a multi-line commit
  message needs the Bash tool (`git commit -F - <<'EOF'`), and **never edit a source file with
  `Set-Content`** — it mojibakes every em dash.

### Do NOT read

`app/seed/core.py` (760 lines — read `app/seed/__init__.py`'s docstring instead) ·
`app/modules/finance/{ledger,ageing,allocation,cash,margin,gst}.py`,
`app/modules/suppliers/vendor.py`, `app/modules/inventory/{valuation,health}.py`,
`app/modules/customers/{credit,timeline,health,churn}.py`,
`app/modules/procurement/{preorder,recommend}.py`, `app/modules/intelligence/*.py` — C1 is
measuring screens, not reading business logic; open one only if a screen it renders looks
actually broken · every `tests/test_*.py` that already passes · anything in `docs/parts/` ·
`docs/ROADMAP.md` (~17k tokens) · `docs/REQUIREMENTS.md` §14 (the R13.x you don't need this
part) · the older `docs/` design files, `docs/DELETION-POLICY.md`, `docs/MIGRATION-STRATEGY.md`.

Note `docs/REQUIREMENTS.md` is at v1.2: the stock writer is `InventoryService.record_movement`.

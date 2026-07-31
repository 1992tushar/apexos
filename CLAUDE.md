# ApexOS — instructions for Claude Code

## Continuing the build

`docs/REQUIREMENTS.md` is the acceptance contract (§1 = global invariants G1–G17, binding on every
change; per-part sections after that) — check `git log`/`git tag` for what's actually landed against
it. `docs/CODEBASE-MAP.md` is what exists and where — read it instead of exploring the tree. Don't
re-read files you already have open in this session, and don't survey the wider codebase before an
edit — go to the relevant file(s) directly.

## Status (2026-07-31)

Parts 1–7, 9 and 10 feature-complete. Part 8 delivered but not formally closed. Part 13 — GST Tax
Invoice (Print/Download), `docs/REQUIREMENTS.md` §16a, R16.x — landed this session: a company
profile (`CompanyProfileService`, single row, seeded with placeholder GSTIN/PAN since the company
isn't registered yet), `Product.hsn_code`, and `/invoices/{id}/print` (`InvoicePrintService` derives
the CGST/SGST/IGST split from GSTIN state-code prefixes at print time; "download" is the browser's
own print-to-PDF, no new dependency). All work is on `main`; nothing in this run is tagged/waived.
Next up: **Part 11 — Polish & Optimization** (`docs/REQUIREMENTS.md` §15, R14.x) — measure first
(page timings, query counts, N+1s, UI-consistency gaps, security review), then fix in batches. No new
features. `docs/CODEBASE-MAP.md`'s "Known debt" section has suspects already on record.

**Two open items, not yet settled:**
- **R11.7 (P0):** margin-leakage's "freight not recovered" indicator can't be built — no
  freight/shipping field exists in the schema, and R11.8 forbids an indicator with nothing to click.
  Named on screen as *Not measured*. Part 8 isn't closed until this is settled: capture freight on
  the invoice/bill, or strike the indicator with a reason.
- **R13.14 (P0, unmet, accepted as debt for now):** no test asserts a score or forecast against a
  hand-computed/known series for the Intelligence Layer's 5 new figures. Checked by hand against the
  running app, not pinned in a suite. Backfill when next touching Part 10, or explicitly re-accept.

**Gotchas:** `Path.relative_to` yields backslashes on Windows — use `.as_posix()`. Orphaned pytest
processes lock the scratch DB on Windows — kill by PID. Don't pick from a `set` of UUIDs with
`next(iter(...))` — sort, or take from a query's own order. A new column needs an
`_ADDITIVE_COLUMNS` entry in `app/main.py` — `create_all` never ALTERs. Env var is `DATABASE_URL`.
PowerShell has no heredocs — use the Bash tool for multi-line commit messages; never edit a source
file with `Set-Content` (mojibakes em dashes).

## Product decisions (settled 2026-07-28 — binding, not aspirational)

- **D-A**: no batch/lot tracking, no expiry, no FIFO — simple weighted-average cost.
- **D-B**: single user (the founder) — no roles/permissions UI; keyboard-first order entry matters more, not less.
- **D-C**: no data migration — CSV import is P2 everywhere; export stays P1.
- **D-D**: cut, not deferred — QuickBooks bridge, notifications/inbox, saved views, ADR log, SOP index.

## Non-negotiables

- **All work is on `main`.** No feature branches, no PRs. Commit at every checkpoint; tag
  `part-0N-done` when a part completes.
- **Personal GitHub credentials only** — `github.com/1992tushar/apexos`, never org credentials.
- **Verify loop, every session, from `apps/api` with the venv active:**
  ```bash
  python -m pytest -q                 # all green, never verbose
  python -m ruff check app/ tests/    # zero new findings
  python -m uvicorn app.main:app --port 8000
  # then: every nav page 200s; a bad id (e.g. /customers/<random-uuid>) renders error.html
  ```
- **Do not add abstractions that aren't earned, and do not rebuild what exists.** One soft-delete
  helper, one query helper, one table macro, one duplicate check, one reference map. If you are about
  to write a second, you have misread the requirement.
- **Every new model owes `app/db/references.py` an entry**, even an empty tuple (R3.7).
- **Scope discipline:** no batch/lot tracking, no expiry, no FIFO layers, no roles/permissions UI, no
  QuickBooks bridge, no notifications, no saved views. CSV import is P2 everywhere. Finding yourself
  building one of these means the session has drifted — stop and say so (G17).

## Stack & architecture (established — follow, don't redesign)

FastAPI + SQLAlchemy + SQLite (`DATABASE_URL`-swappable to Postgres for prod), server-rendered
Jinja2 at `apps/api/app/web/`, no Alembic, no npm/node in the run path. Domain logic lives in
`apps/api/app/modules/<feature>/` (model / repository / service / router / schemas). Web pages call
services directly, never over HTTP. Feature-based modules, repository pattern, thin routers +
services, DI, 12-factor config, typed `AppError` envelope, structlog + correlation-id, Pydantic v2,
`ActivityService` audit log, `EntityMixin` (soft-delete read filter) + `BusinessUnitMixin`.

**Data rules:** money = integer minor units; keys = UUID v7; every table has audit + soft-delete +
`business_unit_id`; ledgers (`stock_movement`, `payment`, invoices, bills) are append-only, never
mutated; every state-changing service verb writes exactly one `activity_log` row in the same
transaction; nouns are data, never hardcoded (`customer_type`, `supplier_type`, … are rows).

**Explainability:** every score, alert, recommendation and forecast states its inputs, formula, data
window, and the records it reasoned from, on screen. Where it can't be computed, say "unknown" —
never a misleading default like 0 or 50. No decorative charts, no vanity metrics, no ML dependency,
no runtime LLM call for any number the product displays.

**Name a test after the requirement it proves** — `def test_r5_3_lead_time_is_measured_from_confirmed_at_to_received_at(...)`.
`pytest -q -k r5_` is then the evidence for that requirement group; a test node id is the evidence,
not hand-written prose in `PROGRESS.md`.

Use plain `python` with the venv active rather than a hardcoded interpreter path — the build machine
isn't guaranteed to be Windows.

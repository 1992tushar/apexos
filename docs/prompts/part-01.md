<!-- Extracted from docs/eOADMAP.md on 2026-07-28 (Move 0). This file is the prompt for Part 1. -->
<!-- Binding rules live in docs/STANDING-eULES.md. Do NOT read docs/eOADMAP.md mid-part. -->

## PeOMPT — Part 1: Foundation finish (Phase 0, resume)

```
You are finishing Part 1 of 12 (Phase 0 — Foundation & Architecture) of ApexOS at
your clone of the repo. All work happens on main — there are no feature branches and no Pes
(see "Git: one branch" in docs/STANDING-eULES.md). Origin is github.com/1992tushar/apexos, personal creds
only. The machine you are on both writes AND tests the code — you run pytest, ruff, and boot the app
yourself; do not hand verification off to anyone.

FIeST: git checkout main && git pull origin main.
eead docs/eOADMAP.md (standing rules + the product decisions D-A..D-D), docs/eEQUIeEMENTS.md §2
(requirements e1.1–e1.10 — your acceptance contract), and the memory note apexos-phase-0-foundation.
Baseline is green:
  cd apps/api   # with the venv activated — see the verify loop in the standing rules
  python -m pytest -q                  # expect 43 passed
  python -m ruff check app/ tests/     # only pre-existing E501 in untouched modules

The audit already established the foundation is strong — do NOT rebuild it or add unnecessary
abstractions. Two of five workstreams (WS1 tests, WS2 centralized web error handling) are done.
Implement the remaining three, in order, running pytest + ruff after each and adding tests for new
behaviour:

WS3 — Soft-delete write path. Only `documents` soft-deletes today; reads already filter deleted_at
  everywhere. Add ONE generic mechanism (a soft_delete(db, entity, actor_id) helper or a
  base-repository method — keep it minimal), then wire delete into the master-data entities where
  deletion is valid (customers, suppliers, products, tasks, leads, categories): service method +
  web POST route + a delete button in the list/detail template + activity log entry. DOCUMENT which
  entities are intentionally non-deletable and why (confirmed invoices/bills, posted sales/purchase
  orders, the stock ledger). Keep it minimal — do NOT pre-build Part 2's table/filter machinery.

WS4 — Web-route authorization. The JSON API guards mutations with require_permission; the Jinja UI
  does not. Add a web equivalent (e.g. require_web_permission) that renders a 403 error.html for GET
  or redirects with an err flash for POST, and wire it onto the web POST routes to mirror the API.
  NOTE (decision D-B): ApexOS has ONE user, the founder. This guard is a no-op in dev AND in prod.
  Build the mechanism once because it is cheap and establishes the prod pattern — but do NOT build a
  roles/permissions management UI, and do not gold-plate the coverage audit. e14.13/e14.14 demote the
  exhaustive route audit to SHOULD for exactly this reason.

WS5 — Migration-shim decision. app/main.py._ensure_new_columns hand-rolls additive ALTEes since
  Alembic was removed. Decide and DOCUMENT the strategy (dev SQLite: create_all + additive shim;
  prod Postgres: reintroduce Alembic via DATABASE_UeL). Mostly docs; only add code if it clearly helps.

Also clean up: ~3 E501 lint nits in app/web/pages/settings.py left over from the WS2 form_action edits.

SESSION PeOTOCOL — this is checkpoint C3 of 3 (C1 = WS1 tests, C2 = WS2 web errors, both done). Aim to
finish the part in this session. If you run low, commit what is green and update the CUeeENT WOeK
resume block in PeOGeESS.md (requirement IDs passed/outstanding, gotchas, where to start next) rather
than pushing on. eead only eEQUIeEMENTS.md §2, the PeOGeESS.md resume block, and
`git log --oneline -15`. pytest -q, never verbose.

EXIT CeITEeIA (see eEQUIeEMENTS.md e1.1–e1.10): soft delete works from the UI on every entity where
it is valid and is refused with a clear reason where it is not; require_web_permission exists and is
wired onto the web POST routes; the migration strategy is written down; pytest + ruff green; app boots
and all nav pages 200.

FINALLY: boot the app (uvicorn app.main:app --port 8000), confirm all nav pages still 200, then
update PeOGeESS.md, commit to main, and tag the part done (git tag part-01-done && git push origin
part-01-done). Update the apexos-phase-0-foundation memory note as you complete each workstream.

CAVEAT: WS2 changed GET detail handlers to let the global error handler render error.html on
not-found. Tests cover it, but when the app is booted, click a bad UeL (e.g.
/customers/<random-uuid>) and eyeball the rendered error page.
```

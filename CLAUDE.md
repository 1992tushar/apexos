# ApexOS — instructions for Claude Code

## "Start next part of development"

When the user says **"Start next part of development"** (or any close variant — "continue the build",
"next part", "resume ApexOS"), that is a request to follow the **▶ NEXT SESSION PROMPT** block inside
the `▶ CURRENT WORK` section at the top of `PROGRESS.md`. Read that block and execute it in order.
Do not ask which part — the prompt names it, and it is maintained by the session that closed the last
checkpoint.

Treat that prompt as if the user had pasted it verbatim, including its read lists and its
"do NOT read" list.

## The four documents that carry state

- **`PROGRESS.md`** — the source of truth for status. Its `▶ CURRENT WORK` block names the part in
  flight, the checkpoint to start at, the exact edit set, verified signatures for things you should
  call without opening, and what not to read. **Ending a session by updating it is not optional.**
  **It is capped at ~350 lines and does not grow** — closing a part means moving its record to
  `docs/parts/part-0N.md` and deleting it from here, not appending below the previous one.
- **`docs/REQUIREMENTS.md`** — the acceptance contract. §1 is the global invariants (G1–G17); every
  part has its own § of R-numbers. A change that violates an invariant is not done, regardless of
  whether the part's own requirements pass.
- **`docs/STANDING-RULES.md`** — the binding rules: decisions D-A..D-D, the session protocol and
  checkpoint table, the "Reading diet" that explains which reading is irreducible and which is waste,
  and the verify loop. **This is the rules document you read — not `ROADMAP.md`.**
- **`docs/prompts/part-NN.md`** — one self-contained prompt per part. Open only the part in flight.

`docs/CODEBASE-MAP.md` is what exists and where — read it instead of exploring the tree.
`docs/ROADMAP.md` is planning only (sequence, dependencies, prompt index); **do not read it mid-part.**
`docs/parts/` holds closed part records for audit; never read them during a session.

## Non-negotiables

- **All work is on `main`.** No feature branches, no PRs. Commit at every checkpoint; tag
  `part-0N-done` when a part completes.
- **Personal GitHub credentials only** — `github.com/1992tushar/apexos`, never org credentials.
- **The verify loop runs in the same session that writes the code**: from `apps/api` with the venv
  active, `python -m pytest -q` (never verbose) and `python -m ruff check app/ tests/`. The expected
  counts are in the `PROGRESS.md` starter prompt. **New work adds zero ruff findings** — that is the
  bar, not "roughly the same".
- **Do not add abstractions that aren't earned, and do not rebuild what exists.** One soft-delete
  helper, one query helper, one table macro, one duplicate check, one reference map. If you are about
  to write a second, you have misread the requirement.
- **Every new model owes `app/db/references.py` an entry**, even an empty tuple (R3.7).
- **Scope discipline:** no batch/lot tracking, no expiry, no FIFO layers, no roles/permissions UI, no
  QuickBooks bridge, no notifications, no saved views. CSV import is P2 everywhere. Finding yourself
  building one of these means the session has drifted — stop and say so (G17).

<!-- Extracted from docs/ROADMAP.md on 2026-07-28 (Move 0). This file is the prompt for Part 11. -->
<!-- Binding rules live in docs/STANDING-RULES.md. Do NOT read docs/ROADMAP.md mid-part. -->

## PROMPT — Part 11: Polish & Optimization (Phase 8)

```
You are starting Part 11 of 12 (Phase 8 — Polish & Optimization) of ApexOS at
your clone of the repo. Parts 1–10 are complete and merged — the product is feature-complete.
Read docs/STANDING-RULES.md first — it is binding: decisions D-A..D-D plus the standing rules. Then read
docs/REQUIREMENTS.md §15 (R14.x — your acceptance contract). Also read PROGRESS.md and
docs/17-design-system.md. Work on main — no branch, no PR: git checkout main && git pull origin main.

SESSION PROTOCOL — 3 checkpoints, ONE PER SESSION, each ending in a commit:
  C1 MEASURE EVERYTHING and write the findings down — NO FIXES IN THIS SESSION
  C2 fix batch 1 — UI consistency, de-duplication, global search + Ctrl+K palette
  C3 fix batch 2 — perf against C1's baselines, security review, the written summary
C1 is measurement-only on purpose: R14.7/R14.8 forbid optimising without a baseline, and a session that
measures and fixes in one pass invariably loses the baseline. Put every number from C1 into the
PROGRESS.md resume block — C3 is graded against them. Read only REQUIREMENTS.md §15, the PROGRESS.md
resume block, and the design system. pytest -q.

GOAL: make ApexOS feel like a premium internal operating system. Add NO new features. If you find
yourself designing a new screen, stop — that belongs nowhere.

READ DECISION D-B, IT RESIZES THIS PART: the founder is the only user. Accessibility narrows to form
labels and contrast — the screen-reader table work is cut. The exhaustive per-route authz audit and
the "every POST route is guarded" test are demoted to SHOULD (R14.13, R14.14): the guard mechanism
from part 1 exists and that is what matters with one user. Saved views are CUT (decision D-D).

IMPROVE:
  Experience — UI consistency (one spacing/type/colour system actually applied everywhere), UX flow,
    form labels and contrast, full keyboard navigation, responsive layout down to a tablet.
  Findability — global search across every entity, and a command palette (Ctrl+K) for
    navigate-and-act without the mouse. For a solo operator who lives in this app daily, these two
    are the highest-value items in the part.
  Speed — MEASURE FIRST, then fix: page timings, N+1 queries, missing indexes, template render cost,
    static asset size, all baselined BEFORE any change. Report before/after numbers; do not
    "optimise" without a measurement.
  Code — de-duplicate: by now EVERY list screen should be going through part 2's macros. Find the ones
    that are not and migrate them. Simplify workflows, count and reduce clicks on the top-10 most
    frequent tasks (report both numbers), delete unnecessary screens, tighten developer experience
    (one-command run, fast tests).
  Security — input validation, file-upload handling, error messages that don't leak internals,
    dependency audit for known vulnerabilities.

Method: audit → write down the findings with evidence → fix in reviewable batches → prove it with
measurements. Deliver a short written summary of what changed and what was measured.

The full test suite must stay green throughout — this part must not change behaviour, only its
quality. Add tests where refactors created risk, especially the de-duplication work.

Follow the verify loop in docs/STANDING-RULES.md, update PROGRESS.md, and commit directly to main — no branch, no PR
(see "Git: one branch" in docs/STANDING-RULES.md). When every P0/P1 requirement for the part passes, tag it
(git tag part-0N-done && git push origin part-0N-done). Update memory.
```

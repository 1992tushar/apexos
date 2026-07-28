<!-- Extracted from docs/ROADMAP.md on 2026-07-28 (Move 0). This file is the prompt for Part 12. -->
<!-- Binding rules live in docs/STANDING-RULES.md. Do NOT read docs/ROADMAP.md mid-part. -->

## PROMPT — Part 12: Product Challenge (Phase X)

```
You are running Part 12 of 12 (Phase X — Product Challenge) on ApexOS at
your clone of the repo. Parts 1–11 are complete. Read docs/STANDING-RULES.md, docs/REQUIREMENTS.md §16
(R15.x) and PROGRESS.md.

SESSION PROTOCOL — 1 checkpoint, and it produces no code. Budget your room for READING the product and
WRITING the report; if you run low, commit the report as far as it goes with a note on which screens
are still unreviewed. Read the app itself (nav + templates + services) rather than the design docs —
this review is about what exists, not what was intended.

Forget that this codebase was built with your help. Pretend a different company hired you to REPLACE
it, and you are being paid to be right, not agreeable.

Review every screen and every feature. For each one, answer:
  - Should this exist at all?
  - Can it be merged into another screen?
  - Can it be simplified?
  - Can it be removed outright?
  - Would a FOUNDER actually use it? How often?
  - Would an OPERATIONS executive use it?
  - Would a PROCUREMENT executive use it?
  - Would a WAREHOUSE employee understand it without training?

NOTE on those last three seats: decision D-B means only the founder uses ApexOS today. Keep asking
the other three questions anyway — they are the test of whether a screen could survive the business
growing — but be honest that today they are hypothetical, and do not justify a screen's existence by
a user who does not exist yet.

Challenge every decision, including the architectural ones, and including decisions D-A..D-D
themselves — if dropping FIFO or batch tracking turned out to be wrong, say so with evidence. Name
the things that exist because they were on a roadmap rather than because someone needs them. Be
specific: cite the file and the screen, say what you would cut, and say what breaks if you cut it.

The goal is NOT more features. The goal is the simplest, most powerful operating system for a
procurement company. Fewer, sharper screens beat comprehensive ones.

START BY WRITING THE REVIEW ONLY — no code changes. Deliver a prioritised report:
  1. Cut (with the blast radius of each cut)
  2. Merge (which screens collapse into which)
  3. Simplify (the specific reduction)
  4. Keep as-is (and why it earns its place)
Then STOP and wait for a decision on what to act on. Do not start deleting.
```

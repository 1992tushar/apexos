<!-- Extracted from docs/ROADMAP.md on 2026-07-28 (Move 0). This file is the prompt for Part 2. -->
<!-- Binding rules live in docs/STANDING-RULES.md. Do NOT read docs/ROADMAP.md mid-part. -->

## PROMPT — Part 2: Master data & shared machinery (Phase 1)

```
You are starting Part 2 of 12 (Phase 1 — Master data & shared machinery) of ApexOS at
your clone of the repo. Part 1 (Foundation) is complete and merged to main. Read
docs/STANDING-RULES.md first — "Standing rules" and the product decisions D-A..D-D are binding (docs/STANDING-RULES.md). Then read
docs/REQUIREMENTS.md §3 and §4 (requirements R2.x and R3.x — your acceptance contract). Also read
PROGRESS.md, docs/08-module-breakdown.md (§2.1 Org/Config, §2.3 Products, §2.4 Customers,
§2.5 Suppliers), docs/12-coding-standards.md, docs/17-design-system.md.
Work on main — no branch, no PR. Start with: git checkout main && git pull origin main.

SESSION PROTOCOL — 3 checkpoints, ONE PER SESSION, each ending in a commit:
  C1 macros + query helper + dup prevention + change history
  C2 prove on products + customers, and RECORD the R2.14 line count
  C3 roll out to the remaining 8 masters + their special cases
Before you run low on room, update the CURRENT WORK resume block in PROGRESS.md: checkpoints done with
SHAs, requirement IDs passed and outstanding, gotchas, mid-part decisions, where the next session
starts. Read only REQUIREMENTS.md §3–§4, the PROGRESS.md resume block, and the module-breakdown §§
named above — the standing rules are reproduced in this prompt. Use pytest -q, never verbose.

GOAL: build ONCE the list/table machinery that parts 3–8 will all reuse, then apply it to every
master so they are complete, consistent and safe to grow on. Most masters ALREADY EXIST (see
app/modules/config, products, customers, suppliers) — this adds depth and uniformity, it is NOT a
rewrite. Audit what each master already has before adding code.

THIS PART HAS TWO STAGES AND THE ORDER IS THE POINT. Do not roll out first and generalise later —
that path ends in copy-paste, and five later parts inherit it.

STAGE 1 — the machinery (build, then prove on exactly TWO masters):
1. A reusable list/table pattern as macros in app/web/templates/_macros.html: search box, filter
   chips, sortable headers, pagination controls. Driven by declarative per-page config (columns,
   filters, default sort), NOT copy-pasted markup. Query-string driven (?q=&sort=&dir=&page=&<filter>=)
   so links and the back button behave.
2. One generic paginated/filtered/sorted query helper in the repository layer, composing with the
   EntityMixin soft-delete read filter and business_unit scoping. Pages must not hand-roll
   LIMIT/OFFSET or ORDER BY.
3. One generic CSV EXPORT path over that helper, so an export respects the filters on screen.
4. One duplicate-prevention approach: natural-key uniqueness plus a pre-save check surfacing a clean
   field-level error, not an IntegrityError or a 500. Applied per entity via configuration.
5. Change history: derive from the existing activity_log wherever possible. Only add a table if
   activity_log provably cannot answer "what changed on this record, when, by whom" — and if you do,
   say in PROGRESS.md why it was insufficient.

CSV IMPORT IS P2, NOT P0 (decision D-C: there is no data to migrate, we start fresh). Build it only
if stages 1 and 2 are fully done and green, and keep it minimal if you do. Do NOT let import shape
the design of the machinery.

Prove stage 1 on TWO masters (suggest products and customers) end to end: list with search + filter
+ sort + pagination, export, duplicate rejection, change-history panel. Then RECORD IN PROGRESS.md
how many lines of new code the SECOND master needed — a third master must be achievable in well
under 100 lines. That number is the gate for stage 2.

STAGE 2 — roll out to every master:
  business units, categories + subcategories (self-referencing tree), products, brands,
  manufacturers, warehouses, units of measure (+ conversions), tax masters (versioned slabs),
  customers, suppliers.

Each must uniformly support: search, filters, sorting, pagination, CSV export, audit trail, status
(active/inactive), soft delete (the part 1 mechanism), change history, validation, relationship
integrity, duplicate prevention. Via the stage-1 machinery — NOT bespoke code. If a master needs
substantially more code than your recorded figure, STOP and improve the machinery rather than working
around it, then say so in PROGRESS.md.

Where a master needs more than the generic treatment, build only that:
  - categories: reparent with cycle prevention, tree rendering, business-unit rollup.
  - uom_conversion: non-zero and non-cyclic factor validation.
  - tax_rate: versioned slabs — a new slab appends, never edits history.
  - relationship integrity: block or clearly explain deletion/deactivation of a master still
    referenced by live transactions (e.g. a product on an open PO). Never silently cascade.

DO NOT BUILD (decision D-B — ApexOS has one user, the founder): roles and permissions management
screens. Features 16.12 and 16.13 in docs/06-feature-list.md are cut.

Extend app/seed.py so each master has enough rows to exercise search/filter/pagination (hundreds for
products and customers, not five), including a multi-level category tree and at least two tax slab
versions.

Add tests: the query helper (filter + sort + pagination boundaries, soft-deleted rows excluded),
export respects active filters, duplicate rejection returns a field error not a 500, per-master list
filtering, category reparent rejects a cycle, uom conversion rejects zero/cyclic factors, tax slab
append preserves the prior version, soft delete then absent-from-list, blocked deletion of a
referenced master explains why.

Follow the verify loop in docs/STANDING-RULES.md, update PROGRESS.md, and commit directly to main — no branch, no PR
(see "Git: one branch" in docs/STANDING-RULES.md). When every P0/P1 requirement for the part passes, tag it
(git tag part-0N-done && git push origin part-0N-done). Update memory.
```

# Part 6 — Sales: customer depth (Phase 4, first half)

**Status: COMPLETE.** Every P0/P1 in `docs/REQUIREMENTS.md` §9 (R8.x) passes. Not to be read
during a session — it exists for audit.

| Checkpoint | Commit | What landed |
|---|---|---|
| C1 (whole part) | `a8c9bde` | Profile depth, versioned credit terms, the credit gate, the unified timeline |

**No tags** — waived for Parts 5–7, so this SHA is the record.

**Verified at close:** **541 tests passing** (505 at Part 5 close + 36), `ruff check app/ tests/`
**exactly 37** — zero new findings. Evidence: `pytest -q -k r8_` (**35 tests**) in
`tests/test_customer_depth.py`. Fresh seed + uvicorn: every nav page 200s, the depth page renders
contacts, branches, versioned terms with their reasons, notes, documents and the timeline; the
overridden customer shows its override; a bad id renders `error.html` at 404.

**Relaxed by D-B:** R8.13's plain labels remain house style rather than a MUST.

---

## What already existed, and what that changed

`CustomerContact`, `CustomerAddress` and `CustomerCreditPolicy` were already modelled — and the
policy already carried `valid_from` / `valid_to`. So most of this part was services, enforcement
and screens rather than schema. **`Document` already keys on `(entity_type, entity_id)`**, so R8.4
needed no second upload path at all.

**The defect that hid behind that.** `CustomerService.update` **mutated the current credit policy
in place**. The columns said "versioned"; the behaviour was not. R8.3's "prior version readable"
was therefore untrue despite the schema looking correct — the kind of gap that a schema review
passes and only a behavioural test catches.

## Six decisions a later part must not reverse

1. **Credit terms version; they are never edited.** `set_policy` appends a row and stamps
   `valid_to` on the one it replaces. `CustomerService.update` delegates to it rather than
   assigning fields. A mutation reintroducing the in-place edit fails `test_r8_3`.
2. **A version carries forward what the caller did not name.** Setting a limit must not silently
   reset the payment terms to zero.
3. **A credit limit of ZERO means no limit recorded, not "refuse everything".** A customer with no
   terms is cash-and-carry; blocking every order for them would be a worse failure than allowing it.
4. **The boundary is integer arithmetic on minor units** (G1/R8.9): `outstanding + order <= limit`.
   At the limit is allowed, one minor unit over is blocked. No float goes near it.
5. **An override is logged against the CUSTOMER, not only the order.** "We went over their limit"
   is a fact about the relationship — which is also how it reaches the timeline. Exactly one
   activity row (G5), naming who, when, by how much and why. A passing check logs nothing.
6. **The timeline is a projection with a deterministic sort.** Six sources, six queries, no events
   table. Several sources default to `func.now()` and tie, so the sort key carries a per-kind
   **causal rank** — you cannot be paid for an invoice you have not raised — with `id` last.

## Two things worth remembering

**R2.10 needed care, not a shrug.** Versioning moved *where* the field-level before/after diff
lives, and a Part 2 test asserted it sat on the customer's `updated` row. The diff must not
disappear, so `set_policy` carries it — together with the reason, which is strictly better history.
The Part 2 test now reads across the customer's entries rather than only the newest, and says why.
**When a change relocates a fact, move the assertion; do not delete it.**

**The seed's breaching order goes on a DIFFERENT customer from the depth one.** Better demo — a
healthy account and an overridden one — and it preserves an invariant two older tests encode: the
first customer's work is all *closed*, so nothing live references it. A confirmed order is "open"
per `references.py`, which had made that customer undeletable and broke both tests. The order is
also sized off the *current* limit rather than a hard-coded quantity, so it stays a breach if the
seeded terms are ever edited.

**Mutation check:** two run, both caught — the credit boundary off by one minor unit, and editing
the policy in place.

## The note left for Part 7

`SalesOrderService.confirm` now runs the credit check. Its docstring records that **R9.8 must
reserve stock AFTER the check passes** — reserving against an order the credit gate is about to
refuse would leave a reservation holding stock for an order that never confirmed.

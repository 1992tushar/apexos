"""Idempotent seed of real Apex data + one completed spine sales order.

Run with:  python -m app.seed

Safe to re-run: every row is get-or-created by its natural key, prices/opening
stock are only written when a product is first created, and the demo documents
are only generated once (when none exist yet).

LAYOUT (Move 0, 2026-07-28). This was one 1,076-line module, and because G14 makes
every part extend the seed, every part had to read all of it. It is now one module
per concern:

    helpers.py    SeedContext + get_or_create + record_creation
    catalogue.py  the static data tables + the deterministic bulk generators
    core.py       run() — the orchestrator, and the sections not yet extracted
    preorder.py   seed_preorder(ctx) — Part 3's section, the worked example

ADDING A SECTION — do this, and do not append to `run()`:

    1. Write `app/seed/<domain>.py` with
       `def seed_<domain>(ctx: SeedContext) -> dict | None`.
    2. Guard it on its own emptiness check so a re-seed stays idempotent.
    3. Call it from `run()` in `core.py`, BEFORE the master-change-history pass —
       that pass must stay last, since it backfills every master created above it.

You then read your own module plus `run()`'s call order, not the whole seed.
"""
from __future__ import annotations

from app.db.metadata import import_all_models

# Complete Base.metadata before the submodules below import any model, so mapper
# configuration never sees a half-registered relationship. Importing app.seed (or
# any submodule of it) always runs this first.
import_all_models()

from app.seed.catalogue import bulk_customers, bulk_products  # noqa: E402
from app.seed.core import run  # noqa: E402
from app.seed.helpers import SeedContext, get_or_create, record_creation  # noqa: E402

__all__ = [
    "SeedContext",
    "bulk_customers",
    "bulk_products",
    "get_or_create",
    "record_creation",
    "run",
]

"""operations & config (Phase B): task + document tables

Revision ID: 0003_operations_and_config
Revises: 0002_procurement_buy_side
Create Date: 2026-07-22

Phase B adds two owned entities — `task` (actionable to-dos, polymorphically
linked) and `document` (stored-file metadata). Everything else in Phase B
(multi-warehouse transfers/adjustments/counts, full Settings CRUD, category
reparent, uom conversions, tax slabs, settings) operates on tables that already
exist from the 0001 baseline (`stock_movement`, `warehouse`, `category` incl.
`parent_category_id`, `uom_conversion`, `setting`), so no column changes are
needed here.

New tables are created from `Base.metadata` with `checkfirst=True` (only the
missing ones), matching the 0002 style — correct on both a fresh DB and the
existing migrated DB.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

from app.db.metadata import Base  # importing populates metadata with all models

revision: str = "0003_operations_and_config"
down_revision: str | None = "0002_procurement_buy_side"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


NEW_TABLES = ["task", "document"]


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(
        bind=bind,
        tables=[Base.metadata.tables[name] for name in NEW_TABLES],
        checkfirst=True,
    )


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(
        bind=bind,
        tables=[Base.metadata.tables[name] for name in reversed(NEW_TABLES)],
        checkfirst=True,
    )

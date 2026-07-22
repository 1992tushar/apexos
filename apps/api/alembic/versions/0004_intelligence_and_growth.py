"""intelligence & growth (Phase C): CRM + notification tables

Revision ID: 0004_intelligence_and_growth
Revises: 0003_operations_and_config
Create Date: 2026-07-22

Phase C adds the pre-sale funnel and the notification inbox:
`pipeline_stage`, `lead`, `opportunity`, `competitor`, `notification`. Reports and
Analytics are read-only projections and own no tables. QuickBooks is a
feature-flagged bridge and owns no tables.

Created from `Base.metadata` with `checkfirst=True` (matching 0002/0003) —
correct on both a fresh DB and the existing migrated DB.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

from app.db.metadata import Base  # importing populates metadata with all models

revision: str = "0004_intelligence_and_growth"
down_revision: str | None = "0003_operations_and_config"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


NEW_TABLES = ["pipeline_stage", "lead", "opportunity", "competitor", "notification"]


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

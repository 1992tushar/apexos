"""initial schema — built from model metadata (drift-free baseline)

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-19

This baseline creates every table directly from `Base.metadata`, which is fully
populated by importing all model modules. Subsequent migrations use ordinary
Alembic autogenerate/ops. Derived read models (stock balance, receivables) are
computed in the service layer, not as DB views, so this baseline is sufficient.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

from app.db.metadata import Base  # importing populates metadata with all models

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())

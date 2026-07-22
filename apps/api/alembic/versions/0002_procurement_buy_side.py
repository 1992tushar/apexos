"""procurement + buy-side finance (suppliers, POs, goods receipts, bills)

Revision ID: 0002_procurement_buy_side
Revises: 0001_initial
Create Date: 2026-07-21

Adds the buy side: supplier / supplier_contact / supplier_evaluation,
purchase_order / purchase_order_line, goods_receipt / goods_receipt_line, and
bill / bill_line, plus two columns on the existing finance ledger
(`payment.supplier_id`, `payment_allocation.bill_id`).

New tables are created from `Base.metadata` (checkfirst — only the missing ones),
matching the 0001 baseline style. The two new columns are added conditionally so
this migration is correct whether the payment/allocation tables were created by
0001 before those columns existed (existing DB) or with them (fresh DB).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.db.metadata import Base  # importing populates metadata with all models

revision: str = "0002_procurement_buy_side"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


NEW_TABLES = [
    "supplier",
    "supplier_contact",
    "supplier_evaluation",
    "purchase_order",
    "purchase_order_line",
    "goods_receipt",
    "goods_receipt_line",
    "bill",
    "bill_line",
]


def _has_column(inspector, table: str, column: str) -> bool:
    if table not in inspector.get_table_names():
        return False
    return any(c["name"] == column for c in inspector.get_columns(table))


def upgrade() -> None:
    bind = op.get_bind()
    # Create only the buy-side tables that don't yet exist.
    Base.metadata.create_all(
        bind=bind,
        tables=[Base.metadata.tables[name] for name in NEW_TABLES],
        checkfirst=True,
    )

    inspector = sa.inspect(bind)
    if not _has_column(inspector, "payment", "supplier_id"):
        op.add_column(
            "payment",
            sa.Column(
                "supplier_id",
                sa.dialects.postgresql.UUID(as_uuid=True),
                sa.ForeignKey("supplier.id"),
                nullable=True,
            ),
        )
    if not _has_column(inspector, "payment_allocation", "bill_id"):
        op.add_column(
            "payment_allocation",
            sa.Column(
                "bill_id",
                sa.dialects.postgresql.UUID(as_uuid=True),
                sa.ForeignKey("bill.id"),
                nullable=True,
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _has_column(inspector, "payment_allocation", "bill_id"):
        op.drop_column("payment_allocation", "bill_id")
    if _has_column(inspector, "payment", "supplier_id"):
        op.drop_column("payment", "supplier_id")
    Base.metadata.drop_all(
        bind=bind,
        tables=[Base.metadata.tables[name] for name in reversed(NEW_TABLES)],
        checkfirst=True,
    )

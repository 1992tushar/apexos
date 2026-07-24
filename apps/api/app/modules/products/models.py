"""Product (SKU) model. Reorder level as a quantity numeric(18,4)."""
from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, BusinessUnitMixin, EntityMixin


class Product(Base, EntityMixin, BusinessUnitMixin):
    __tablename__ = "product"

    sku_code: Mapped[str] = mapped_column(String(24), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("category.id"), nullable=False
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("brand.id"), nullable=False
    )
    uom_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("uom.id"), nullable=False
    )
    procurement_model_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(), ForeignKey("procurement_model.id"), nullable=True
    )
    default_tax_rate_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(), ForeignKey("tax_rate.id"), nullable=True
    )
    specification: Mapped[str | None] = mapped_column(String(200), nullable=True)
    launch_phase: Mapped[str | None] = mapped_column(String(24), nullable=True)
    reorder_level: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0")
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")

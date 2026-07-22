"""Config service — read-through over the type masters + document numbering."""
from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.config.models import NumberSequence
from app.modules.config.repository import ConfigRepository


def allocate_document_number(
    db: Session,
    *,
    doc_type: str,
    business_unit_id: uuid.UUID | None,
    on_date: date,
) -> str:
    """Atomically allocate the next `<PREFIX>-YYYYMM-#####` number (§7 naming).

    Uses a row-locked per-(BU, doc_type, month) counter (`SELECT ... FOR UPDATE`),
    creating the row on first use. Prefix is derived from `doc_type` (e.g. 'SO').
    """
    period = on_date.strftime("%Y%m")
    seq = db.scalar(
        select(NumberSequence)
        .where(
            NumberSequence.doc_type == doc_type,
            NumberSequence.period == period,
            NumberSequence.business_unit_id == business_unit_id,
            NumberSequence.deleted_at.is_(None),
        )
        .with_for_update()
    )
    if seq is None:
        seq = NumberSequence(
            doc_type=doc_type, period=period, business_unit_id=business_unit_id, counter=0
        )
        db.add(seq)
        db.flush()
    seq.counter += 1
    db.flush()
    return f"{doc_type}-{period}-{seq.counter:05d}"


class ConfigService:
    def __init__(self, db: Session) -> None:
        self.repo = ConfigRepository(db)

    def business_units(self):
        return self.repo.business_units()

    def brands(self):
        return self.repo.brands()

    def procurement_models(self):
        return self.repo.procurement_models()

    def categories(self):
        return self.repo.categories()

    def uoms(self):
        return self.repo.uoms()

    def customer_types(self):
        return self.repo.customer_types()

    def supplier_types(self):
        return self.repo.supplier_types()

    def warehouses(self):
        return self.repo.warehouses()

    def tax_rates(self):
        return self.repo.tax_rates()

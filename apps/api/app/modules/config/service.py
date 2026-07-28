"""Config service — read-through over the type masters + document numbering +
full Settings CRUD (Phase B).

Reads stay data-driven (D2); writes are the state-changing verbs and each emit
one `activity_log` row (D10). `tax_rate` slabs are versioned (append, never edit
history — D3 spirit); `uom_conversion` factors are validated non-zero/non-cyclic.
"""
from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationError
from app.db.duplicates import ensure_unique
from app.db.listing import ListParams, query_page
from app.db.references import ensure_unreferenced
from app.db.soft_delete import soft_delete
from app.modules.activity.service import ActivityService
from app.modules.config.listing import CATEGORY_LIST
from app.modules.config.models import (
    Brand,
    BusinessUnit,
    Category,
    CustomerType,
    Manufacturer,
    NumberSequence,
    ProcurementModel,
    Setting,
    SupplierType,
    TaxRate,
    Uom,
    UomConversion,
    Warehouse,
)
from app.modules.config.repository import ConfigRepository


def default_business_unit(db: Session) -> uuid.UUID:
    """The BU a document falls back to when neither the payload nor the party names one.

    Lived in `procurement/service.py` until Part 5 C3, when inventory needed it to number
    transfer and count documents — and inventory cannot import procurement (procurement
    imports `InventoryService`, so it would be circular). It belongs here anyway:
    `BusinessUnit` is a config master and `allocate_document_number` below is its
    neighbour. Procurement re-exports it under the same name, so its callers are unchanged.
    """
    bu = db.scalar(select(BusinessUnit.id).where(BusinessUnit.deleted_at.is_(None)).limit(1))
    if bu is None:
        raise NotFoundError("No business unit configured; run the seed first.")
    return bu


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


# Model map for the code/name/is_active masters (entity_type -> model). Warehouse and
# manufacturer are here too: they are the same master with two extra text columns, and
# one creator with an `extra` dict beats a second create path per master (R3.12).
_SIMPLE_MASTERS: dict[str, type] = {
    "business_unit": BusinessUnit,
    "brand": Brand,
    "manufacturer": Manufacturer,
    "procurement_model": ProcurementModel,
    "uom": Uom,
    "customer_type": CustomerType,
    "supplier_type": SupplierType,
    "warehouse": Warehouse,
}

# The label the messages and the activity log use for each.
MASTER_LABELS: dict[str, str] = {
    "business_unit": "Business unit",
    "brand": "Brand",
    "manufacturer": "Manufacturer",
    "procurement_model": "Procurement model",
    "uom": "Unit of measure",
    "customer_type": "Customer type",
    "supplier_type": "Supplier type",
    "warehouse": "Warehouse",
    "tax_rate": "Tax slab",
    "category": "Category",
}


class ConfigService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = ConfigRepository(db)
        self.activity = ActivityService(db)

    # --- reads ----------------------------------------------------------
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

    def uom_conversions(self):
        return self.repo.uom_conversions()

    def settings(self):
        return self.repo.settings()

    # --- simple master writes ------------------------------------------
    def _master_model(self, entity_type: str) -> type:
        model = _SIMPLE_MASTERS.get(entity_type)
        if model is None:
            raise NotFoundError(f"Unknown master '{entity_type}'")
        return model

    def _master_row(self, entity_type: str, row_id: uuid.UUID):
        model = self._master_model(entity_type)
        row = self.db.scalar(
            select(model).where(model.id == row_id, model.deleted_at.is_(None))
        )
        if row is None:
            raise NotFoundError(f"{MASTER_LABELS.get(entity_type, entity_type)} not found")
        return row

    def create_master(
        self, entity_type: str, *, code: str, name: str, extra: dict | None = None, actor_id
    ):
        """Create a code/name master row (brand, uom, warehouse, …).

        Duplicates go through `ensure_unique`, the one pre-save check (R2.9, R3.8) —
        the hand-rolled `code already exists` query this used to run reported a
        different message per master and missed soft-deleted rows still holding the
        `UNIQUE` code.
        """
        model = self._master_model(entity_type)
        # `extra` joins the values so a composite key that includes one of those columns
        # (a manufacturer's name + city) is actually checked rather than skipped.
        ensure_unique(self.db, model, {"code": code, "name": name, **(extra or {})})
        row = model(code=code, name=name, is_active=True, created_by=actor_id)
        for field, value in (extra or {}).items():
            if value is not None and hasattr(model, field):
                setattr(row, field, value)
        self.db.add(row)
        self.db.flush()
        self.activity.log(
            actor_id=actor_id,
            verb="created",
            entity_type=entity_type,
            entity_id=row.id,
            summary=f"{MASTER_LABELS.get(entity_type, entity_type)} {name} ({code}) created",
        )
        return row

    def set_master_active(self, entity_type: str, row_id: uuid.UUID, *, active: bool, actor_id):
        """Activate or deactivate a master (R3.1 status, R3.7 integrity).

        Deactivating is guarded exactly as deleting is: a master that live work still
        reads cannot be hidden from every dropdown either, and the refusal names the
        documents in the way (R3.7).
        """
        row = self._master_row(entity_type, row_id)
        label = MASTER_LABELS.get(entity_type, entity_type)
        if row.is_active == active:
            return row
        if not active:
            ensure_unreferenced(self.db, row, action="deactivate", label=label)
        row.is_active = active
        row.updated_by = actor_id
        self.db.flush()
        self.activity.log(
            actor_id=actor_id,
            verb="activated" if active else "deactivated",
            entity_type=entity_type,
            entity_id=row.id,
            summary=f"{label} {row.name} {'activated' if active else 'deactivated'}",
        )
        return row

    def delete_master(self, entity_type: str, row_id: uuid.UUID, *, actor_id) -> None:
        """Soft-delete a master, refusing while live work still reads it (R3.7)."""
        row = self._master_row(entity_type, row_id)
        label = MASTER_LABELS.get(entity_type, entity_type)
        ensure_unreferenced(self.db, row, action="delete", label=label)
        soft_delete(self.db, row, actor_id=actor_id, label=label)

    def update_master(self, entity_type: str, row_id: uuid.UUID, *, data: dict, actor_id):
        model = _SIMPLE_MASTERS.get(entity_type)
        if model is None:
            raise NotFoundError(f"Unknown master '{entity_type}'")
        row = self.db.scalar(
            select(model).where(model.id == row_id, model.deleted_at.is_(None))
        )
        if row is None:
            raise NotFoundError(f"{entity_type} {row_id} not found")
        for field in ("name", "is_active"):
            if field in data and data[field] is not None:
                setattr(row, field, data[field])
        row.updated_by = actor_id
        self.db.flush()
        self.activity.log(
            actor_id=actor_id,
            verb="updated",
            entity_type=entity_type,
            entity_id=row.id,
            summary=f"{entity_type.replace('_', ' ').title()} {row.name} updated",
        )
        return row

    # --- warehouse writes ----------------------------------------------
    def create_warehouse(self, *, code, name, city, state_code, actor_id) -> Warehouse:
        """Kept for its callers; the work is `create_master`'s (R3.12)."""
        return self.create_master(
            "warehouse", code=code, name=name,
            extra={"city": city, "state_code": state_code}, actor_id=actor_id,
        )

    def update_warehouse(self, warehouse_id: uuid.UUID, *, data: dict, actor_id) -> Warehouse:
        wh = self.db.scalar(
            select(Warehouse).where(
                Warehouse.id == warehouse_id, Warehouse.deleted_at.is_(None)
            )
        )
        if wh is None:
            raise NotFoundError(f"Warehouse {warehouse_id} not found")
        for field in ("name", "city", "state_code", "is_active"):
            if field in data and data[field] is not None:
                setattr(wh, field, data[field])
        wh.updated_by = actor_id
        self.db.flush()
        self.activity.log(
            actor_id=actor_id,
            verb="updated",
            entity_type="warehouse",
            entity_id=wh.id,
            summary=f"Warehouse {wh.name} updated",
        )
        return wh


@dataclass(frozen=True)
class CategoryRow:
    """A category as the list screen and its CSV need it (R3.1).

    `parent_name`, `procurement_model_name` and `product_count` are projected, so they
    are columns without a `sort=` — see `config/listing.py`.
    """

    id: uuid.UUID
    code: str
    name: str
    parent_name: str | None
    procurement_model_name: str | None
    product_count: int
    is_active: bool
    sort_order: int


class CategoryService:
    """Category create/update + reparent, enforcing the `→business_unit` rollup."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.activity = ActivityService(db)

    def to_read_many(self, rows: Sequence[Category]) -> list[CategoryRow]:
        """Project a page of categories — three queries for the page, not per row."""
        if not rows:
            return []
        names = dict(
            self.db.execute(select(Category.id, Category.name)).all()
        )
        models = dict(
            self.db.execute(select(ProcurementModel.id, ProcurementModel.name)).all()
        )
        from app.modules.products.models import Product

        ids = [row.id for row in rows]
        counts = dict(
            self.db.execute(
                select(Product.category_id, func.count())
                .where(Product.category_id.in_(ids), Product.deleted_at.is_(None))
                .group_by(Product.category_id)
            ).all()
        )
        return [
            CategoryRow(
                id=row.id,
                code=row.code,
                name=row.name,
                parent_name=names.get(row.parent_category_id),
                procurement_model_name=models.get(row.procurement_model_id),
                product_count=counts.get(row.id, 0),
                is_active=row.is_active,
                sort_order=row.sort_order,
            )
            for row in rows
        ]

    def get(self, category_id: uuid.UUID) -> CategoryRow:
        """One category, projected the same way the list projects it."""
        return self.to_read_many([self._require(category_id)])[0]

    def tree(self) -> list[tuple[int, Category, str | None]]:
        """The whole category tree as `(depth, category, business_unit_name)` (R3.4).

        Depth-first in each parent's `sort_order` then `code`, so the indentation on
        screen matches the order the founder set. The business unit comes along because
        a child rolls up to its parent's BU — seeing the rollup is the point of the tree
        rather than the flat list.
        """
        rows = list(
            self.db.scalars(
                select(Category)
                .where(Category.deleted_at.is_(None))
                .order_by(Category.sort_order, Category.code)
            )
        )
        bu_names = dict(self.db.execute(select(BusinessUnit.id, BusinessUnit.name)).all())
        children: dict[uuid.UUID | None, list[Category]] = {}
        for row in rows:
            children.setdefault(row.parent_category_id, []).append(row)

        out: list[tuple[int, Category, str | None]] = []

        def walk(parent_id: uuid.UUID | None, depth: int) -> None:
            for row in children.get(parent_id, ()):
                out.append((depth, row, bu_names.get(row.business_unit_id)))
                walk(row.id, depth + 1)

        walk(None, 0)
        return out

    def list(self, *, search: str | None = None, page: int = 1, page_size: int = 25):
        """One page of categories through the one query helper (R2.4)."""
        result = query_page(
            self.db,
            replace(CATEGORY_LIST, page_size=page_size),
            ListParams(q=search or "", page=page),
        )
        return self.to_read_many(result.rows), result.total

    def _default_bu(self) -> uuid.UUID:
        bu = self.db.scalar(
            select(BusinessUnit.id).where(BusinessUnit.deleted_at.is_(None)).limit(1)
        )
        if bu is None:
            raise NotFoundError("No business unit configured; run the seed first.")
        return bu

    def _require(self, category_id: uuid.UUID) -> Category:
        cat = self.db.scalar(
            select(Category).where(Category.id == category_id, Category.deleted_at.is_(None))
        )
        if cat is None:
            raise NotFoundError(f"Category {category_id} not found")
        return cat

    def delete(self, category_id: uuid.UUID, *, actor_id) -> None:
        """Soft-delete a category (R1.2).

        Refused while anything still hangs off it. Unlike a customer — whose
        invoices stay readable because they snapshot what they need — a category
        is a live classification: hiding one with children would orphan a subtree,
        and hiding one with products would blank the category column on rows that
        are still for sale. Reparent or reassign first.
        """
        cat = self._require(category_id)
        # The two hand-rolled counts this used to run are now the `category` entry in
        # `app/db/references.py`, which every master shares (R3.7, R3.12).
        ensure_unreferenced(self.db, cat, action="delete", label="Category")
        soft_delete(self.db, cat, actor_id=actor_id, label="Category")

    def create(self, payload, *, actor_id) -> Category:
        # One duplicate check, configured in `app.db.duplicates` (R2.9, R3.8).
        ensure_unique(
            self.db,
            Category,
            {
                "code": payload.code,
                "name": payload.name,
                "parent_category_id": payload.parent_category_id,
            },
        )
        bu = payload.business_unit_id or self._default_bu()
        parent = None
        if payload.parent_category_id is not None:
            parent = self._require(payload.parent_category_id)
            bu = parent.business_unit_id  # child rolls up to the parent's BU
        cat = Category(
            code=payload.code,
            name=payload.name,
            business_unit_id=bu,
            procurement_model_id=payload.procurement_model_id,
            parent_category_id=parent.id if parent else None,
            sort_order=payload.sort_order,
            is_active=True,
            created_by=actor_id,
        )
        self.db.add(cat)
        self.db.flush()
        self.activity.log(
            actor_id=actor_id,
            verb="created",
            entity_type="category",
            entity_id=cat.id,
            summary=f"Category {cat.name} ({cat.code}) created",
        )
        return cat

    def update(self, category_id: uuid.UUID, payload, *, actor_id) -> Category:
        cat = self._require(category_id)
        data = payload.model_dump(exclude_unset=True)
        for field in ("name", "procurement_model_id", "business_unit_id", "sort_order", "is_active"):
            if field in data and data[field] is not None:
                setattr(cat, field, data[field])
        cat.updated_by = actor_id
        self.db.flush()
        self.activity.log(
            actor_id=actor_id,
            verb="updated",
            entity_type="category",
            entity_id=cat.id,
            summary=f"Category {cat.name} updated",
        )
        return cat

    def reparent(self, category_id: uuid.UUID, parent_id: uuid.UUID | None, *, actor_id) -> Category:
        """Move a category under a new parent (or to top level when null). Rejects
        self-parenting and cycles; the child inherits the parent's business unit."""
        cat = self._require(category_id)
        if parent_id is None:
            cat.parent_category_id = None
            cat.updated_by = actor_id
            self.db.flush()
            self.activity.log(
                actor_id=actor_id,
                verb="reparented",
                entity_type="category",
                entity_id=cat.id,
                summary=f"Category {cat.name} moved to top level",
            )
            return cat
        if parent_id == category_id:
            raise ValidationError("A category cannot be its own parent")
        parent = self._require(parent_id)
        # Walk up from the proposed parent to ensure we don't create a cycle.
        cursor: Category | None = parent
        seen: set[uuid.UUID] = set()
        while cursor is not None:
            if cursor.id == category_id:
                raise ValidationError("Reparenting would create a cycle")
            if cursor.id in seen or cursor.parent_category_id is None:
                break
            seen.add(cursor.id)
            cursor = self.db.scalar(
                select(Category).where(Category.id == cursor.parent_category_id)
            )
        cat.parent_category_id = parent.id
        cat.business_unit_id = parent.business_unit_id
        cat.updated_by = actor_id
        self.db.flush()
        self.activity.log(
            actor_id=actor_id,
            verb="reparented",
            entity_type="category",
            entity_id=cat.id,
            summary=f"Category {cat.name} moved under {parent.name}",
        )
        return cat


class UomConversionService:
    """Upsert UOM conversion factors (e.g. Case→Pack). Validates non-zero,
    non-cyclic (from ≠ to) factors; one row per (from, to) pair."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.activity = ActivityService(db)

    def upsert(self, payload, *, actor_id) -> UomConversion:
        if payload.from_uom_id == payload.to_uom_id:
            raise ValidationError("from_uom and to_uom must differ")
        if payload.factor <= 0:
            raise ValidationError("Conversion factor must be positive")
        existing = self.db.scalar(
            select(UomConversion).where(
                UomConversion.from_uom_id == payload.from_uom_id,
                UomConversion.to_uom_id == payload.to_uom_id,
                UomConversion.deleted_at.is_(None),
            )
        )
        if existing is not None:
            existing.factor = payload.factor
            existing.updated_by = actor_id
            row = existing
        else:
            row = UomConversion(
                from_uom_id=payload.from_uom_id,
                to_uom_id=payload.to_uom_id,
                factor=payload.factor,
                created_by=actor_id,
            )
            self.db.add(row)
        self.db.flush()
        self.activity.log(
            actor_id=actor_id,
            verb="set",
            entity_type="uom_conversion",
            entity_id=row.id,
            summary=f"UOM conversion factor set to {payload.factor}",
        )
        return row


class TaxRateService:
    """Versioned GST slabs. `set_slab` closes any open row for the same code and
    appends a new one (history is never edited — D3 spirit)."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.activity = ActivityService(db)

    def set_slab(self, payload, *, actor_id) -> TaxRate:
        on_date = payload.valid_from or datetime.now(UTC).date()
        # Close the currently-open slab(s) for this code.
        open_rows = list(
            self.db.scalars(
                select(TaxRate).where(
                    TaxRate.code == payload.code,
                    TaxRate.valid_to.is_(None),
                    TaxRate.deleted_at.is_(None),
                )
            )
        )
        for row in open_rows:
            row.valid_to = on_date
            row.is_active = False
            row.updated_by = actor_id
        slab = TaxRate(
            code=payload.code,
            name=payload.name,
            rate_bps=payload.rate_bps,
            valid_from=on_date,
            is_active=True,
            created_by=actor_id,
        )
        self.db.add(slab)
        self.db.flush()
        self.activity.log(
            actor_id=actor_id,
            verb="changed",
            entity_type="tax_rate",
            entity_id=slab.id,
            summary=f"Tax slab {payload.code} set to {payload.rate_bps} bps",
            data={"rate_bps": payload.rate_bps},
        )
        return slab


class SettingService:
    """Typed key/value settings. `get` returns a default when absent; `set`
    upserts the value and records the change."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.activity = ActivityService(db)

    def _find(self, key: str, business_unit_id: uuid.UUID | None) -> Setting | None:
        return self.db.scalar(
            select(Setting).where(
                Setting.key == key,
                Setting.business_unit_id == business_unit_id,
                Setting.deleted_at.is_(None),
            )
        )

    def get(self, key: str, *, business_unit_id: uuid.UUID | None = None, default: Any = None) -> Any:
        row = self._find(key, business_unit_id)
        return row.value if row is not None else default

    def set(self, payload, *, actor_id) -> Setting:
        row = self._find(payload.key, payload.business_unit_id)
        if row is not None:
            row.value = payload.value
            row.value_type = payload.value_type
            row.description = payload.description
            row.updated_by = actor_id
        else:
            row = Setting(
                key=payload.key,
                value=payload.value,
                value_type=payload.value_type,
                description=payload.description,
                business_unit_id=payload.business_unit_id,
                created_by=actor_id,
            )
            self.db.add(row)
        self.db.flush()
        self.activity.log(
            actor_id=actor_id,
            verb="changed",
            entity_type="setting",
            entity_id=row.id,
            summary=f"Setting {payload.key} changed",
        )
        return row

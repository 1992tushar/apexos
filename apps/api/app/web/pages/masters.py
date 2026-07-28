"""One screen for every config master (R3.1, R3.2, R3.12).

Eight masters used to be eight cards on `/settings`, each with its own `<dl>` and its
own add-form, and none of them had search, filters, sorting, pagination, export, delete
or history. Rather than eight page modules, this is **one** set of routes over a
registry: `MASTERS` says what a master is called, which `ListSpec` drives it, and which
fields its create form collects. Everything else — the list, the export, the detail page
with its change history, the delete and the activate/deactivate — is generic.

That is why `/settings` needed splitting: each `ListView` owns `?q=`, `?sort=` and
`?page=`, so eight lists on one URL would fight over them. `/masters/<slug>` gives each
one its own query string (R2.3) and `/settings` keeps the typed key/value settings plus
links here.

Adding the ninth master is a `MasterPage(...)` entry — a spec and a field list.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import NotFoundError
from app.core.security import Actor
from app.db.listing import ListSpec
from app.modules.activity.service import ActivityService
from app.modules.config.listing import (
    BRAND_LIST,
    BUSINESS_UNIT_LIST,
    CUSTOMER_TYPE_LIST,
    MANUFACTURER_LIST,
    PROCUREMENT_MODEL_LIST,
    SUPPLIER_TYPE_LIST,
    TAX_RATE_LIST,
    UOM_LIST,
    WAREHOUSE_LIST,
)
from app.modules.config.schemas import TaxRateSlabCreate
from app.modules.config.service import ConfigService, TaxRateService
from app.web.core import form_action, render
from app.web.listing import csv_response_from_request, view_from_request, wants_csv
from app.web.security import require_web_permission

router = APIRouter()


@dataclass(frozen=True)
class Field:
    """One input on a master's create form."""

    name: str
    label: str
    required: bool = True
    kind: str = "text"  # text | number
    step: str | None = None


@dataclass(frozen=True)
class MasterPage:
    """A master's whole screen, as configuration."""

    slug: str
    title: str
    label: str  # singular, for buttons and messages
    entity_type: str  # the `activity_log` / service entity name
    spec: ListSpec
    fields: tuple[Field, ...] = ()
    blurb: str = ""
    # Tax slabs append versions rather than being edited or removed (R3.6).
    deletable: bool = True
    toggleable: bool = True


_CODE_NAME = (Field("code", "Code"), Field("name", "Name"))

MASTERS: tuple[MasterPage, ...] = (
    MasterPage("business-units", "Business Units", "Business unit", "business_unit",
               BUSINESS_UNIT_LIST, _CODE_NAME,
               "Every operational row rolls up to one of these."),
    MasterPage("brands", "Brands", "Brand", "brand", BRAND_LIST, _CODE_NAME,
               "The brand half of a SKU code."),
    MasterPage("manufacturers", "Manufacturers", "Manufacturer", "manufacturer",
               MANUFACTURER_LIST, (*_CODE_NAME, Field("city", "City", required=False)),
               "Who physically makes the goods. Nothing references these yet."),
    MasterPage("procurement-models", "Procurement Models", "Procurement model",
               "procurement_model", PROCUREMENT_MODEL_LIST, _CODE_NAME,
               "How a category is sourced — private label, master distribution, contract."),
    MasterPage("units", "Units of Measure", "Unit of measure", "uom", UOM_LIST, _CODE_NAME,
               "Pack, roll, case. Conversions between them live on this page's list."),
    MasterPage("customer-types", "Customer Types", "Customer type", "customer_type",
               CUSTOMER_TYPE_LIST, _CODE_NAME, "Hotel, restaurant, hospital — data, never an enum."),
    MasterPage("supplier-types", "Supplier Types", "Supplier type", "supplier_type",
               SUPPLIER_TYPE_LIST, _CODE_NAME, "Manufacturer, distributor."),
    MasterPage("warehouses", "Warehouses", "Warehouse", "warehouse", WAREHOUSE_LIST,
               (*_CODE_NAME, Field("city", "City", required=False),
                Field("state_code", "State code", required=False)),
               "Stock lives in one of these; movements name it."),
    MasterPage("tax-slabs", "Tax Slabs", "Tax slab", "tax_rate", TAX_RATE_LIST,
               (*_CODE_NAME, Field("rate_percent", "Rate (%)", kind="number", step="0.01")),
               "Adding a slab for an existing code closes the old one and appends a new "
               "version — history is never edited (R3.6).",
               deletable=False, toggleable=False),
)

BY_SLUG: dict[str, MasterPage] = {m.slug: m for m in MASTERS}


def _master(slug: str) -> MasterPage:
    page = BY_SLUG.get(slug)
    if page is None:
        raise NotFoundError(f"No master called '{slug}'")
    return page


@router.get("/masters/{slug}")
def master_list(slug: str, request: Request, db: Session = Depends(get_db)):
    page = _master(slug)
    if wants_csv(request):
        return csv_response_from_request(request, db, page.spec)
    return render(
        request,
        "masters/list.html",
        master=page,
        masters=MASTERS,
        view=view_from_request(request, db, page.spec),
    )


@router.get("/masters/{slug}/{row_id}")
def master_detail(
    slug: str, row_id: uuid.UUID, request: Request, db: Session = Depends(get_db)
):
    page = _master(slug)
    row = db.get(page.spec.model, row_id)
    if row is None or getattr(row, "deleted_at", None) is not None:
        raise NotFoundError(f"{page.label} {row_id} not found")
    return render(
        request,
        "masters/detail.html",
        master=page,
        row=row,
        history=ActivityService(db).history(page.entity_type, row_id),
    )


@router.post("/masters/{slug}")
async def master_create(
    slug: str,
    request: Request,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("config.write")),
):
    """Create a row from the master's declared fields.

    The form is generated from `MasterPage.fields`, so it is read back the same way
    rather than as a signature per master.
    """
    page = _master(slug)
    form = await request.form()
    values = {f.name: (form.get(f.name) or "").strip() for f in page.fields}

    def work():
        if page.entity_type == "tax_rate":
            return TaxRateService(db).set_slab(
                TaxRateSlabCreate(
                    code=values["code"], name=values["name"],
                    # Percent in, integer basis points stored — no float in the column.
                    rate_bps=int(round(float(values["rate_percent"] or 0) * 100)),
                ),
                actor_id=actor.id,
            )
        extra = {k: v or None for k, v in values.items() if k not in ("code", "name")}
        return ConfigService(db).create_master(
            page.entity_type, code=values["code"], name=values["name"],
            extra=extra, actor_id=actor.id,
        )

    return form_action(
        db, work, back=f"/masters/{slug}",
        success=(f"/masters/{slug}", f"{page.label} added"),
        err=f"Could not add {page.label.lower()}",
    )


@router.post("/masters/{slug}/{row_id}/status")
def master_set_status(
    slug: str,
    row_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("config.write")),
):
    """Activate or deactivate. `?active=0` deactivates; the guard is in the service."""
    page = _master(slug)
    active = (request.query_params.get("active") or "").lower() in ("1", "true", "yes", "on")
    return form_action(
        db,
        lambda: ConfigService(db).set_master_active(
            page.entity_type, row_id, active=active, actor_id=actor.id
        ),
        back=f"/masters/{slug}",
        success=(f"/masters/{slug}", f"{page.label} {'activated' if active else 'deactivated'}"),
        err=f"Could not update {page.label.lower()}",
    )


@router.post("/masters/{slug}/{row_id}/delete")
def master_delete(
    slug: str,
    row_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("config.delete")),
):
    page = _master(slug)
    return form_action(
        db,
        lambda: ConfigService(db).delete_master(page.entity_type, row_id, actor_id=actor.id),
        back=f"/masters/{slug}",
        success=(f"/masters/{slug}", f"{page.label} deleted"),
        err=f"Could not delete {page.label.lower()}",
    )

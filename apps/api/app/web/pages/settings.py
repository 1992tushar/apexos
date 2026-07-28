"""Settings pages: masters, warehouses, tax rates, and typed settings CRUD."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import Actor
from app.modules.config.schemas import SettingUpsert, TaxRateSlabCreate
from app.modules.config.service import ConfigService, SettingService, TaxRateService
from app.web.core import form_action, redirect, render
from app.web.security import require_web_permission

router = APIRouter()

_MASTER_TYPES = {"business_unit", "brand", "uom", "customer_type", "supplier_type"}


@router.get("/settings")
def settings_index(request: Request, db: Session = Depends(get_db)):
    cfg = ConfigService(db)
    return render(
        request,
        "settings/index.html",
        business_units=cfg.business_units(),
        brands=cfg.brands(),
        uoms=cfg.uoms(),
        customer_types=cfg.customer_types(),
        supplier_types=cfg.supplier_types(),
        warehouses=cfg.warehouses(),
        tax_rates=cfg.tax_rates(),
        settings=cfg.settings(),
    )


@router.post("/settings/masters/{entity_type}")
def create_master(
    request: Request,
    entity_type: str,
    code: str = Form(...),
    name: str = Form(...),
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("config.write")),
):
    if entity_type not in _MASTER_TYPES:
        return redirect("/settings", err=f"Unknown master '{entity_type}'")
    return form_action(
        db,
        lambda: ConfigService(db).create_master(
            entity_type, code=code, name=name, actor_id=actor.id
        ),
        back="/settings", success=("/settings", "Added"), err="Could not add",
    )


@router.post("/settings/warehouses")
def create_warehouse(
    request: Request,
    code: str = Form(...),
    name: str = Form(...),
    city: str = Form(""),
    state_code: str = Form(""),
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("config.write")),
):
    return form_action(
        db,
        lambda: ConfigService(db).create_warehouse(
            code=code, name=name, city=city or None,
            state_code=state_code or None, actor_id=actor.id
        ),
        back="/settings", success=("/settings", "Warehouse added"),
        err="Could not add warehouse",
    )


@router.post("/settings/tax-rates")
def create_tax_rate(
    request: Request,
    code: str = Form(...),
    name: str = Form(...),
    rate_percent: str = Form(...),
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("config.write")),
):
    def work():
        payload = TaxRateSlabCreate(
            code=code, name=name, rate_bps=int(round(float(rate_percent) * 100))
        )
        return TaxRateService(db).set_slab(payload, actor_id=actor.id)

    return form_action(
        db, work, back="/settings", success=("/settings", "Tax rate added"),
        err="Could not add tax rate",
    )


@router.post("/settings/settings")
def create_setting(
    request: Request,
    key: str = Form(...),
    value: str = Form(...),
    description: str = Form(""),
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("config.write")),
):
    def work():
        payload = SettingUpsert(key=key, value=value, description=description or None)
        return SettingService(db).set(payload, actor_id=actor.id)

    return form_action(
        db, work, back="/settings", success=("/settings", "Setting saved"),
        err="Could not save setting",
    )

"""Integrations router — QuickBooks Online bridge (feature-flagged, non-blocking)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import Actor, require_permission
from app.modules.integrations.quickbooks import QuickBooksSyncService

router = APIRouter(tags=["integrations"])


@router.get("/integrations/quickbooks/status")
def quickbooks_status(db: Session = Depends(get_db)):
    """Whether the QBO bridge is enabled (feature flag)."""
    return QuickBooksSyncService(db).status()


@router.post("/integrations/quickbooks/invoices/{invoice_id}")
def sync_invoice(
    invoice_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_permission("qbo.sync")),
):
    return QuickBooksSyncService(db).push_invoice(invoice_id, actor_id=actor.id)


@router.post("/integrations/quickbooks/bills/{bill_id}")
def sync_bill(
    bill_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_permission("qbo.sync")),
):
    return QuickBooksSyncService(db).push_bill(bill_id, actor_id=actor.id)


@router.post("/integrations/quickbooks/payments/{payment_id}")
def sync_payment(
    payment_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_permission("qbo.sync")),
):
    return QuickBooksSyncService(db).push_payment(payment_id, actor_id=actor.id)

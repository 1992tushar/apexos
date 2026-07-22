"""CRM router — pipeline stages, leads, opportunities, competitors."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import Actor, require_permission
from app.modules.crm.schemas import (
    CompetitorCreate,
    CompetitorRead,
    LeadConvert,
    LeadCreate,
    LeadPage,
    LeadRead,
    OpportunityAdvance,
    OpportunityCreate,
    OpportunityListRow,
    OpportunityRead,
    PipelineStageRead,
)
from app.modules.crm.service import CrmService

router = APIRouter(tags=["crm"])


@router.get("/pipeline-stages", response_model=list[PipelineStageRead])
def list_pipeline_stages(db: Session = Depends(get_db)):
    return CrmService(db).stages()


@router.get("/leads", response_model=LeadPage)
def list_leads(
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
):
    items, total = CrmService(db).leads(status=status, page=page, page_size=page_size)
    return LeadPage(items=items, total=total, page=page, page_size=page_size)


@router.post("/leads", response_model=LeadRead, status_code=201)
def create_lead(
    payload: LeadCreate,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_permission("lead.create")),
):
    return CrmService(db).create_lead(payload, actor_id=actor.id)


@router.post("/leads/{lead_id}/convert", response_model=LeadRead)
def convert_lead(
    lead_id: uuid.UUID,
    payload: LeadConvert,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_permission("lead.convert")),
):
    return CrmService(db).convert_lead(lead_id, payload, actor_id=actor.id)


@router.get("/opportunities", response_model=list[OpportunityListRow])
def list_opportunities(db: Session = Depends(get_db)):
    return CrmService(db).opportunities()


@router.post("/opportunities", response_model=OpportunityRead, status_code=201)
def create_opportunity(
    payload: OpportunityCreate,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_permission("opportunity.create")),
):
    return CrmService(db).create_opportunity(payload, actor_id=actor.id)


@router.post("/opportunities/{opp_id}/advance", response_model=OpportunityRead)
def advance_opportunity(
    opp_id: uuid.UUID,
    payload: OpportunityAdvance,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_permission("opportunity.advance")),
):
    return CrmService(db).advance_opportunity(opp_id, payload, actor_id=actor.id)


@router.get("/competitors", response_model=list[CompetitorRead])
def list_competitors(db: Session = Depends(get_db)):
    return CrmService(db).competitors()


@router.post("/competitors", response_model=CompetitorRead, status_code=201)
def create_competitor(
    payload: CompetitorCreate,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_permission("competitor.create")),
):
    return CrmService(db).create_competitor(payload, actor_id=actor.id)

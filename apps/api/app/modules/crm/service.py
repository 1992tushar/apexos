"""CRM services — leads (create/convert), opportunities (create/advance),
competitors. Each state change writes one activity_log row (D10)."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.modules.activity.service import ActivityService
from app.modules.config.models import BusinessUnit
from app.modules.crm.models import Competitor, Lead, Opportunity
from app.modules.crm.repository import CrmRepository
from app.modules.crm.schemas import (
    CompetitorCreate,
    CompetitorRead,
    LeadConvert,
    LeadCreate,
    LeadRead,
    OpportunityAdvance,
    OpportunityCreate,
    OpportunityListRow,
    OpportunityRead,
    PipelineStageRead,
)
from app.modules.customers.schemas import CustomerCreate
from app.modules.customers.service import CustomerService


class CrmService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = CrmRepository(db)
        self.activity = ActivityService(db)

    def _default_bu(self) -> uuid.UUID:
        bu = self.db.scalar(
            select(BusinessUnit.id).where(BusinessUnit.deleted_at.is_(None)).limit(1)
        )
        if bu is None:
            raise NotFoundError("No business unit configured; run the seed first.")
        return bu

    # --- reads ----------------------------------------------------------
    def stages(self) -> list[PipelineStageRead]:
        return [PipelineStageRead.model_validate(s) for s in self.repo.stages()]

    def leads(self, *, status: str | None, page: int, page_size: int):
        rows, total = self.repo.leads(status=status, page=page, page_size=page_size)
        return [LeadRead.model_validate(row) for row in rows], total

    def opportunities(self) -> list[OpportunityListRow]:
        rows: list[OpportunityListRow] = []
        for o in self.repo.opportunities():
            rows.append(
                OpportunityListRow(
                    id=o.id,
                    name=o.name,
                    pipeline_stage_id=o.pipeline_stage_id,
                    stage_name=self.repo.stage_name(o.pipeline_stage_id),
                    estimated_value_minor=int(o.estimated_value_minor),
                    status=o.status,
                    expected_close_date=o.expected_close_date,
                    customer_id=o.customer_id,
                    lead_id=o.lead_id,
                )
            )
        return rows

    def competitors(self) -> list[CompetitorRead]:
        return [CompetitorRead.model_validate(c) for c in self.repo.competitors()]

    # --- leads ----------------------------------------------------------
    def create_lead(self, payload: LeadCreate, *, actor_id: uuid.UUID | None) -> LeadRead:
        lead = Lead(
            company_name=payload.company_name,
            contact_name=payload.contact_name,
            email=payload.email,
            phone=payload.phone,
            city=payload.city,
            source=payload.source,
            customer_type_id=payload.customer_type_id,
            notes=payload.notes,
            status="open",
            business_unit_id=payload.business_unit_id or self._default_bu(),
            created_by=actor_id,
        )
        self.repo.add_lead(lead)
        self.activity.log(
            actor_id=actor_id,
            verb="created",
            entity_type="lead",
            entity_id=lead.id,
            summary=f"Lead {lead.company_name} created",
        )
        return LeadRead.model_validate(lead)

    def convert_lead(
        self, lead_id: uuid.UUID, payload: LeadConvert, *, actor_id: uuid.UUID | None
    ) -> LeadRead:
        """Convert a lead into a customer, close its open opportunities as won,
        and mark the lead converted. Requires a customer_type (on the lead or in
        the payload)."""
        lead = self.repo.lead(lead_id)
        if lead is None:
            raise NotFoundError(f"Lead {lead_id} not found")
        if lead.status == "converted":
            raise ConflictError(f"Lead {lead.company_name} is already converted")
        customer_type_id = payload.customer_type_id or lead.customer_type_id
        if customer_type_id is None:
            raise ValidationError("A customer_type_id is required to convert this lead")

        customer = CustomerService(self.db).create(
            CustomerCreate(
                name=lead.company_name,
                customer_type_id=customer_type_id,
                phone=lead.phone,
                email=lead.email,
                city=lead.city,
                credit_limit_minor=payload.credit_limit_minor,
                payment_terms_days=payload.payment_terms_days,
                business_unit_id=lead.business_unit_id,
            ),
            actor_id=actor_id,
        )

        # Attach any open opportunities on this lead to the new customer, won.
        for opp in self.repo.opportunities_for_lead(lead.id):
            opp.customer_id = customer.id
            if opp.status == "open":
                opp.status = "won"
            opp.updated_by = actor_id

        lead.status = "converted"
        lead.converted_customer_id = customer.id
        lead.updated_by = actor_id
        self.db.flush()

        self.activity.log(
            actor_id=actor_id,
            verb="converted",
            entity_type="lead",
            entity_id=lead.id,
            summary=f"Lead {lead.company_name} converted to customer {customer.code}",
            data={"customer_id": str(customer.id)},
        )
        return LeadRead.model_validate(lead)

    # --- opportunities --------------------------------------------------
    def create_opportunity(
        self, payload: OpportunityCreate, *, actor_id: uuid.UUID | None
    ) -> OpportunityRead:
        stage_id = payload.pipeline_stage_id
        if stage_id is None:
            default = self.repo.default_stage()
            if default is None:
                raise NotFoundError("No pipeline stages configured; run the seed first.")
            stage_id = default.id
        elif self.repo.stage(stage_id) is None:
            raise NotFoundError(f"Pipeline stage {stage_id} not found")

        opp = Opportunity(
            name=payload.name,
            lead_id=payload.lead_id,
            customer_id=payload.customer_id,
            pipeline_stage_id=stage_id,
            estimated_value_minor=payload.estimated_value_minor,
            expected_close_date=payload.expected_close_date,
            status="open",
            business_unit_id=payload.business_unit_id or self._default_bu(),
            created_by=actor_id,
        )
        self.repo.add_opportunity(opp)
        self.activity.log(
            actor_id=actor_id,
            verb="created",
            entity_type="opportunity",
            entity_id=opp.id,
            summary=f"Opportunity {opp.name} created",
        )
        return OpportunityRead.model_validate(opp)

    def advance_opportunity(
        self, opp_id: uuid.UUID, payload: OpportunityAdvance, *, actor_id: uuid.UUID | None
    ) -> OpportunityRead:
        opp = self.repo.opportunity(opp_id)
        if opp is None:
            raise NotFoundError(f"Opportunity {opp_id} not found")
        stage = self.repo.stage(payload.pipeline_stage_id)
        if stage is None:
            raise NotFoundError(f"Pipeline stage {payload.pipeline_stage_id} not found")
        opp.pipeline_stage_id = stage.id
        if stage.is_won:
            opp.status = "won"
        elif stage.is_lost:
            opp.status = "lost"
        else:
            opp.status = "open"
        opp.updated_by = actor_id
        self.db.flush()
        self.activity.log(
            actor_id=actor_id,
            verb="stage_changed",
            entity_type="opportunity",
            entity_id=opp.id,
            summary=f"Opportunity {opp.name} moved to {stage.name}",
            data={"stage": stage.code, "status": opp.status},
        )
        return OpportunityRead.model_validate(opp)

    # --- competitors ----------------------------------------------------
    def create_competitor(
        self, payload: CompetitorCreate, *, actor_id: uuid.UUID | None
    ) -> CompetitorRead:
        competitor = Competitor(
            name=payload.name,
            strength=payload.strength,
            notes=payload.notes,
            business_unit_id=payload.business_unit_id or self._default_bu(),
            created_by=actor_id,
        )
        self.repo.add_competitor(competitor)
        self.activity.log(
            actor_id=actor_id,
            verb="created",
            entity_type="competitor",
            entity_id=competitor.id,
            summary=f"Competitor {competitor.name} added",
        )
        return CompetitorRead.model_validate(competitor)

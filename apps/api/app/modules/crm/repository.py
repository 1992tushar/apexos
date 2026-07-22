"""CRM repository — leads, opportunities, stages, competitors."""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.crm.models import Competitor, Lead, Opportunity, PipelineStage


class CrmRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # --- pipeline stages -----------------------------------------------
    def stages(self) -> list[PipelineStage]:
        return list(
            self.db.scalars(
                select(PipelineStage)
                .where(PipelineStage.deleted_at.is_(None))
                .order_by(PipelineStage.sort_order)
            )
        )

    def stage(self, stage_id: uuid.UUID) -> PipelineStage | None:
        return self.db.scalar(
            select(PipelineStage).where(
                PipelineStage.id == stage_id, PipelineStage.deleted_at.is_(None)
            )
        )

    def default_stage(self) -> PipelineStage | None:
        return self.db.scalar(
            select(PipelineStage)
            .where(
                PipelineStage.deleted_at.is_(None),
                PipelineStage.is_won.is_(False),
                PipelineStage.is_lost.is_(False),
            )
            .order_by(PipelineStage.sort_order)
            .limit(1)
        )

    def stage_name(self, stage_id: uuid.UUID) -> str | None:
        return self.db.scalar(select(PipelineStage.name).where(PipelineStage.id == stage_id))

    # --- leads ----------------------------------------------------------
    def add_lead(self, lead: Lead) -> Lead:
        self.db.add(lead)
        self.db.flush()
        return lead

    def lead(self, lead_id: uuid.UUID) -> Lead | None:
        return self.db.scalar(
            select(Lead).where(Lead.id == lead_id, Lead.deleted_at.is_(None))
        )

    def leads(self, *, status: str | None, page: int, page_size: int) -> tuple[list[Lead], int]:
        base = select(Lead).where(Lead.deleted_at.is_(None))
        if status:
            base = base.where(Lead.status == status)
        total = self.db.scalar(select(func.count()).select_from(base.subquery())) or 0
        rows = list(
            self.db.scalars(
                base.order_by(Lead.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        return rows, total

    # --- opportunities --------------------------------------------------
    def add_opportunity(self, opp: Opportunity) -> Opportunity:
        self.db.add(opp)
        self.db.flush()
        return opp

    def opportunity(self, opp_id: uuid.UUID) -> Opportunity | None:
        return self.db.scalar(
            select(Opportunity).where(
                Opportunity.id == opp_id, Opportunity.deleted_at.is_(None)
            )
        )

    def opportunities(self) -> list[Opportunity]:
        return list(
            self.db.scalars(
                select(Opportunity)
                .where(Opportunity.deleted_at.is_(None))
                .order_by(Opportunity.created_at.desc())
            )
        )

    def opportunities_for_lead(self, lead_id: uuid.UUID) -> list[Opportunity]:
        return list(
            self.db.scalars(
                select(Opportunity).where(
                    Opportunity.lead_id == lead_id, Opportunity.deleted_at.is_(None)
                )
            )
        )

    # --- competitors ----------------------------------------------------
    def add_competitor(self, competitor: Competitor) -> Competitor:
        self.db.add(competitor)
        self.db.flush()
        return competitor

    def competitors(self) -> list[Competitor]:
        return list(
            self.db.scalars(
                select(Competitor)
                .where(Competitor.deleted_at.is_(None))
                .order_by(Competitor.name)
            )
        )

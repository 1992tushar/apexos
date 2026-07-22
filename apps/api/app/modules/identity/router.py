"""Identity router — GET /me (current actor)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.security import Actor, get_current_actor
from app.modules.identity.schemas import MeRead

router = APIRouter(tags=["identity"])


@router.get("/me", response_model=MeRead)
def me(actor: Actor = Depends(get_current_actor)) -> MeRead:
    return MeRead(
        id=actor.id,
        email=actor.email,
        role=actor.role,
        permissions=sorted(actor.permissions),
    )

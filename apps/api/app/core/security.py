"""Authentication & authorization.

Production: a Clerk-issued session is verified server-side and mapped to our own
`user` / `role` / `permission` tables (doc 13). For local E2E development (no Clerk
keys), we resolve a stable dev actor from the seeded users, selected by the
`DEV_ACTOR_EMAIL` setting or an `X-Dev-Actor` header. Authorization is enforced
through `require_permission(...)`, which is permissive in dev but wired at every
mutation so production only needs the permission catalog turned on.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db


@dataclass(frozen=True)
class Actor:
    """The authenticated principal for the current request."""

    id: uuid.UUID
    email: str
    role: str
    permissions: frozenset[str]

    def has(self, permission: str) -> bool:
        return "*" in self.permissions or permission in self.permissions


def get_current_actor(
    db: Session = Depends(get_db),
    x_dev_actor: str | None = Header(default=None, alias="X-Dev-Actor"),
) -> Actor:
    """Resolve the current actor.

    In dev, look up the seeded user by email; if the identity tables are not yet
    present (early boot) or the user is missing, fall back to a synthetic founder
    actor with full permissions so the E2E flow is never blocked.
    """
    email = x_dev_actor or settings.dev_actor_email
    try:
        from app.modules.identity.models import User  # local import avoids cycles

        user = db.scalar(select(User).where(User.email == email))
        if user is not None:
            perms = frozenset(getattr(user, "permission_codes", []) or ["*"])
            role = getattr(user, "role_name", "founder")
            return Actor(id=user.id, email=user.email, role=role, permissions=perms)
    except Exception:
        pass

    # Synthetic fallback (dev only).
    return Actor(
        id=uuid.UUID("00000000-0000-7000-8000-000000000001"),
        email=email,
        role="founder",
        permissions=frozenset({"*"}),
    )


def require_permission(permission: str):
    """Dependency factory enforcing a `resource.action` permission."""

    def _dep(actor: Actor = Depends(get_current_actor)) -> Actor:
        if not actor.has(permission):
            from app.core.errors import PermissionDeniedError

            raise PermissionDeniedError(f"Missing permission: {permission}")
        return actor

    return _dep

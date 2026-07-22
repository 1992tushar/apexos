"""Identity service."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.modules.identity.repository import IdentityRepository


class IdentityService:
    def __init__(self, db: Session) -> None:
        self.repo = IdentityRepository(db)

    def get_by_email(self, email: str):
        return self.repo.get_by_email(email)

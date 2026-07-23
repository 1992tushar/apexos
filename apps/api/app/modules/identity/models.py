"""Identity & access models (minimal spine).

`user` denormalizes `role_name` + `permission_codes` (JSON list) so the dev auth
in `app.core.security` can resolve an Actor without joining the RBAC junctions.
"""
from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy import JSON
from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, EntityMixin


class User(Base, EntityMixin):
    __tablename__ = "user"

    email: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    business_unit_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(), ForeignKey("business_unit.id"), nullable=True
    )
    role_name: Mapped[str] = mapped_column(String(60), nullable=False, default="viewer")
    permission_codes: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Role(Base, EntityMixin):
    __tablename__ = "role"

    code: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(String(300), nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Permission(Base, EntityMixin):
    __tablename__ = "permission"

    code: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(String(300), nullable=True)

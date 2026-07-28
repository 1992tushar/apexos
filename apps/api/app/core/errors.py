"""Typed application errors and the standard error envelope (doc 09 & 12).

All API errors serialize to:  {"error": {"code": str, "message": str, "details": ...}}
"""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Base class for expected, typed application errors."""

    status_code: int = 400
    code: str = "app_error"

    def __init__(self, message: str, *, details: Any = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ValidationError(AppError):
    status_code = 422
    code = "validation_error"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class PermissionDeniedError(AppError):
    status_code = 403
    code = "permission_denied"


class DuplicateError(ConflictError):
    """A natural-key collision, blamed on the field the user can fix (R2.9).

    A `ConflictError` (409) like any other duplicate, but it carries the offending
    field so a form can mark it rather than only showing a sentence. Raised by
    `app.db.duplicates.ensure_unique` — never by a hand-rolled check, and never as
    a bare `IntegrityError` reaching the user as a 500.
    """

    code = "duplicate"

    def __init__(self, message: str, *, field: str, value: Any = None) -> None:
        super().__init__(message, details={"field": field, "value": value})
        self.field = field
        self.value = value


def _envelope(code: str, message: str, details: Any = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details}}


def register_error_handlers(app: FastAPI) -> None:
    """Attach exception handlers that emit the standard error envelope."""

    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=_envelope("validation_error", "Request validation failed", exc.errors()),
        )

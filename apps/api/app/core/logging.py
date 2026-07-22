"""Structured logging (structlog) with a per-request correlation id."""
from __future__ import annotations

import logging
import uuid
from contextvars import ContextVar

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="-")


def configure_logging() -> None:
    """Configure structlog to emit JSON logs with the correlation id bound."""
    logging.basicConfig(format="%(message)s", level=logging.INFO)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    )


logger = structlog.get_logger("apexos")


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Bind a correlation id to every request for traceable logs."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        cid = request.headers.get("x-correlation-id") or str(uuid.uuid4())
        token = _correlation_id.set(cid)
        structlog.contextvars.bind_contextvars(correlation_id=cid, path=request.url.path)
        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.clear_contextvars()
            _correlation_id.reset(token)
        response.headers["x-correlation-id"] = cid
        return response

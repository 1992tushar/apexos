"""App-level error handling for the web UI.

`app.core.errors` serializes every `AppError` to the JSON envelope — correct for
the `/api/v1` surface. The server-rendered UI needs the same errors to come back
as an HTML page instead. This handler is registered *after* the core one (so it
wins) and branches on the request path: API paths keep the JSON envelope, web
paths render `error.html`. It is a safety net — page handlers still surface
expected form errors inline via `form_action`; this catches anything uncaught.

One exception to "render the page": a permission denial on a *mutating* web
request redirects instead (R1.4). See `app.web.security` for why.
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings
from app.core.errors import AppError, NotFoundError, PermissionDeniedError, ValidationError
from app.web.core import redirect, render_error
from app.web.security import SAFE_METHODS

# Prefixes that belong to a machine-readable surface and must keep their JSON
# bodies: the versioned API, the OpenAPI docs, the health probe, and static files
# (a browser asking for a missing stylesheet should not be handed a web page).
_MACHINE_PREFIXES = ("/static", "/docs", "/redoc", "/openapi.json", "/health")


def _wants_html(request: Request) -> bool:
    path = request.url.path
    return not (
        path.startswith(settings.api_v1_prefix) or path.startswith(_MACHINE_PREFIXES)
    )


def _back_to(request: Request) -> str:
    """Where to send a denied form submit — the page it was submitted from.

    Prefer the referer, but only its path+query: an absolute URL from the header
    would let a foreign site choose our redirect target. Falls back to the
    dashboard when there is no usable referer.
    """
    referer = request.headers.get("referer") or ""
    if referer:
        from urllib.parse import urlparse

        parsed = urlparse(referer)
        if parsed.path.startswith("/"):
            return parsed.path + (f"?{parsed.query}" if parsed.query else "")
    return "/"


def register_web_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> Response:
        if not _wants_html(request):
            return JSONResponse(
                status_code=exc.status_code,
                content={
                    "error": {"code": exc.code, "message": exc.message, "details": exc.details}
                },
            )
        # A denied mutation must not strand the user on a URL they cannot reload:
        # 303 back to the form with an `err` flash instead of a 403 body (R1.4).
        if isinstance(exc, PermissionDeniedError) and request.method not in SAFE_METHODS:
            return redirect(_back_to(request), err=exc.message)
        return render_error(request, exc)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> Response:
        """A malformed path/query value on a web route is still a bad URL (R1.10).

        FastAPI coerces `/customers/{customer_id}` to a UUID before the handler
        runs, so `/customers/not-a-uuid` never reaches the service that would have
        raised `NotFoundError` — it fails validation first. Without this, that URL
        returns a raw JSON validation envelope in the middle of the UI.
        """
        if not _wants_html(request):
            return JSONResponse(
                status_code=422,
                content={
                    "error": {
                        "code": "validation_error",
                        "message": "Request validation failed",
                        "details": exc.errors(),
                    }
                },
            )
        return render_error(
            request,
            ValidationError("That address is not valid. Check the link and try again."),
            code="Bad Request",
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> Response:
        """Render `error.html` for a plain HTTP error on a web path — chiefly the
        404 for a URL that matches no route at all."""
        if not _wants_html(request):
            # Nothing overrode this before, so keep FastAPI's own JSON for the API,
            # docs and static surfaces rather than inventing a second shape.
            return await http_exception_handler(request, exc)
        message = str(exc.detail) if exc.detail else "Something went wrong."
        if exc.status_code == 404:
            message = "That page does not exist. It may have been deleted or the link is wrong."
        wrapped: AppError = (
            NotFoundError(message) if exc.status_code == 404 else AppError(message)
        )
        wrapped.status_code = exc.status_code
        return render_error(request, wrapped)

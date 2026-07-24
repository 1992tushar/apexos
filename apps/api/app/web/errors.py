"""App-level error handling for the web UI.

`app.core.errors` serializes every `AppError` to the JSON envelope — correct for
the `/api/v1` surface. The server-rendered UI needs the same errors to come back
as an HTML page instead. This handler is registered *after* the core one (so it
wins) and branches on the request path: API paths keep the JSON envelope, web
paths render `error.html`. It is a safety net — page handlers still surface
expected form errors inline via `form_action`; this catches anything uncaught.
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

from app.core.config import settings
from app.core.errors import AppError
from app.web.core import render_error


def register_web_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> Response:
        if request.url.path.startswith(settings.api_v1_prefix):
            return JSONResponse(
                status_code=exc.status_code,
                content={
                    "error": {"code": exc.code, "message": exc.message, "details": exc.details}
                },
            )
        return render_error(request, exc)

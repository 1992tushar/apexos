"""Server-rendered web UI (Jinja2).

Mirrors OrdeRR's model: FastAPI routes render HTML templates by calling the
existing domain services directly (never over HTTP), so there is no separate
SPA build and no hand-maintained DTO layer to keep in sync with the API.

Page routers live under `app.web.pages.*` and are auto-discovered here, so a new
page is just a new file — no central registration list to edit.
"""
from __future__ import annotations

import importlib
import pkgutil

from fastapi import APIRouter

from app.core.logging import logger
from app.web import pages


def build_web_router() -> APIRouter:
    """Discover and mount every page router under `app.web.pages`.

    Resilient like `app.api`: a module that fails to import is logged and
    skipped so the rest of the UI still boots.
    """
    router = APIRouter(include_in_schema=False)
    for mod in pkgutil.iter_modules(pages.__path__):
        dotted = f"{pages.__name__}.{mod.name}"
        try:
            module = importlib.import_module(dotted)
        except Exception as exc:  # noqa: BLE001 - never let one page break the app
            logger.warning("web_page_import_failed", module=dotted, error=str(exc))
            continue
        page_router = getattr(module, "router", None)
        if page_router is None:
            continue
        router.include_router(page_router)
        logger.info("web_page_loaded", module=dotted)
    return router

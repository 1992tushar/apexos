"""API v1 router aggregation.

Each feature module exposes `router: APIRouter`. We import them resiliently so the
app still boots (health check + whatever modules exist) while modules are being
built out. Missing modules are logged, not fatal.
"""
from __future__ import annotations

import importlib

from fastapi import APIRouter

from app.core.logging import logger

api_router = APIRouter()

# Order controls the OpenAPI/tag ordering, not runtime behavior.
MODULE_ROUTERS: list[str] = [
    "app.modules.config.router",
    "app.modules.identity.router",
    "app.modules.customers.router",
    "app.modules.suppliers.router",
    "app.modules.products.router",
    "app.modules.pricing.router",
    "app.modules.sales.router",
    "app.modules.fulfillment.router",
    "app.modules.procurement.router",
    "app.modules.inventory.router",
    "app.modules.finance.router",
    "app.modules.dashboard.router",
    "app.modules.activity.router",
    "app.modules.tasks.router",
    "app.modules.documents.router",
]


def load_module_routers() -> None:
    for dotted in MODULE_ROUTERS:
        try:
            module = importlib.import_module(dotted)
        except ModuleNotFoundError:
            logger.info("router_not_found", module=dotted)
            continue
        router = getattr(module, "router", None)
        if router is None:
            logger.warning("router_missing_attr", module=dotted)
            continue
        api_router.include_router(router)
        logger.info("router_loaded", module=dotted)


load_module_routers()

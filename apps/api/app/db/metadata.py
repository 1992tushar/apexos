"""Import every model module so `Base.metadata` is fully populated.

Alembic imports this to autogenerate/target the full schema. Imports are resilient
so migration tooling works even while some modules are still being authored.
"""
from __future__ import annotations

import importlib

from app.db.base import Base  # re-exported for Alembic's target_metadata

MODEL_MODULES: list[str] = [
    "app.modules.config.models",
    "app.modules.identity.models",
    "app.modules.customers.models",
    "app.modules.suppliers.models",
    "app.modules.products.models",
    "app.modules.pricing.models",
    "app.modules.sales.models",
    "app.modules.fulfillment.models",
    "app.modules.procurement.models",
    "app.modules.inventory.models",
    "app.modules.finance.models",
    "app.modules.activity.models",
]


def import_all_models() -> None:
    for dotted in MODEL_MODULES:
        try:
            importlib.import_module(dotted)
        except ModuleNotFoundError:
            continue


import_all_models()

__all__ = ["Base"]

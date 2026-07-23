"""Import every model module so `Base.metadata` is fully populated.

The app startup (`app.main.lifespan`) and the seed script call `import_all_models`
before `Base.metadata.create_all`, so the SQLite schema is created directly from
the models — no migration tool involved. Imports are resilient so the metadata
still assembles even while some modules are being authored.
"""
from __future__ import annotations

import importlib

from app.db.base import Base  # re-exported so callers get the full metadata

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
    "app.modules.tasks.models",
    "app.modules.documents.models",
    "app.modules.crm.models",
    "app.modules.notifications.models",
]


def import_all_models() -> None:
    for dotted in MODEL_MODULES:
        try:
            importlib.import_module(dotted)
        except ModuleNotFoundError:
            continue


import_all_models()

__all__ = ["Base"]

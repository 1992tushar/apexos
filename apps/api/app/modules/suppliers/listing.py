"""The supplier list, as configuration (R3.1). See `products/listing.py` for the shape."""
from __future__ import annotations

from app.db.listing import (
    Column,
    Filter,
    ListSpec,
    distinct_options,
    model_options,
    static_options,
)
from app.modules.config.models import SupplierType
from app.modules.suppliers.models import Supplier

SUPPLIER_LIST = ListSpec(
    entity="supplier",
    model=Supplier,
    columns=(
        Column("code", "Code", kind="mono", sort="code"),
        Column("name", "Name", kind="link", sort="name", href="/suppliers/{id}"),
        Column("supplier_type_name", "Type"),
        Column("city", "City", sort="city"),
        Column("outstanding_minor", "Payable", kind="money"),
        Column("latest_score", "Latest score", kind="number"),
        Column("status", "Status", kind="badge", sort="status"),
    ),
    search=("name", "code", "city", "gstin"),
    filters=(
        Filter("type", "Type", "supplier_type_id", coerce="uuid",
               options=model_options(SupplierType)),
        Filter("city", "City", "city", options=distinct_options(Supplier, "city")),
        Filter("status", "Status", "status",
               options=static_options(("active", "Active"), ("inactive", "Inactive"))),
    ),
    sort="code",
    dir="asc",
    page_size=25,
    search_hint="Search suppliers by name, code, city or GSTIN",
)

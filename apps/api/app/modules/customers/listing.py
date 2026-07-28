"""The customer list, as configuration (R2.2). See `products/listing.py` for why
the spec lives in the module and not beside the page.
"""
from __future__ import annotations

from app.db.listing import (
    Column,
    Filter,
    ListSpec,
    distinct_options,
    model_options,
    static_options,
)
from app.modules.config.models import CustomerType
from app.modules.customers.models import Customer

CUSTOMER_LIST = ListSpec(
    entity="customer",
    model=Customer,
    columns=(
        Column("code", "Code", kind="mono", sort="code"),
        Column("name", "Name", kind="link", sort="name", href="/customers/{id}"),
        Column("customer_type_name", "Type"),
        Column("city", "City", sort="city"),
        Column("outstanding_minor", "Outstanding", kind="money"),
        Column("status", "Status", kind="badge", sort="status"),
        Column("created_at", "Added", kind="datetime", sort="created_at"),
    ),
    search=("name", "code", "city", "email"),
    filters=(
        Filter("type", "Type", "customer_type_id", coerce="uuid",
               options=model_options(CustomerType)),
        Filter("city", "City", "city", options=distinct_options(Customer, "city")),
        Filter("status", "Status", "status",
               options=static_options(("active", "Active"), ("inactive", "Inactive"))),
    ),
    sort="created_at",
    dir="desc",
    page_size=25,
    search_hint="Search customers by name, code, city or email",
)

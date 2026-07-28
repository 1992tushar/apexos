"""Every config master's list, as configuration (R3.1, R3.2).

The eight code/name masters differ only in their table and their label, so they share
one builder rather than eight near-identical specs — `simple_master_spec` is the
"substantially more code" escape hatch R3.3 asks for, applied once. Warehouses,
manufacturers, tax slabs and categories add their own columns on top of it.

`is_active` is the status on every config master (a boolean, not a status string), so
the status column is `kind="bool"` and its filter is `coerce="bool"` + `active_options`.
"""
from __future__ import annotations

from app.db.listing import (
    Column,
    Filter,
    ListSpec,
    active_options,
    distinct_options,
    model_options,
)
from app.modules.config.models import (
    Brand,
    BusinessUnit,
    Category,
    CustomerType,
    Manufacturer,
    ProcurementModel,
    SupplierType,
    TaxRate,
    Uom,
    Warehouse,
)

STATUS_FILTER = Filter(
    "active", "Status", "is_active", coerce="bool", options=active_options()
)


def simple_master_spec(
    entity: str,
    model: type,
    *,
    plural: str,
    extra: tuple[Column, ...] = (),
    search: tuple[str, ...] = (),
    filters: tuple[Filter, ...] = (),
) -> ListSpec:
    """A `code` / `name` / `is_active` master's list, which is most of them."""
    return ListSpec(
        entity=entity,
        model=model,
        columns=(
            Column("code", "Code", kind="mono", sort="code"),
            Column("name", "Name", sort="name"),
            *extra,
            Column("is_active", "Status", kind="bool", sort="is_active"),
        ),
        search=("code", "name", *search),
        filters=(STATUS_FILTER, *filters),
        sort="code",
        dir="asc",
        page_size=25,
        search_hint=f"Search {plural} by code or name",
    )


BUSINESS_UNIT_LIST = simple_master_spec(
    "business_unit", BusinessUnit, plural="business units"
)
BRAND_LIST = simple_master_spec("brand", Brand, plural="brands")
PROCUREMENT_MODEL_LIST = simple_master_spec(
    "procurement_model", ProcurementModel, plural="procurement models"
)
UOM_LIST = simple_master_spec("uom", Uom, plural="units of measure")
CUSTOMER_TYPE_LIST = simple_master_spec(
    "customer_type", CustomerType, plural="customer types"
)
SUPPLIER_TYPE_LIST = simple_master_spec(
    "supplier_type", SupplierType, plural="supplier types"
)

MANUFACTURER_LIST = simple_master_spec(
    "manufacturer", Manufacturer, plural="manufacturers",
    extra=(Column("city", "City", sort="city"),),
    search=("city",),
    filters=(Filter("city", "City", "city", options=distinct_options(Manufacturer, "city")),),
)

WAREHOUSE_LIST = simple_master_spec(
    "warehouse", Warehouse, plural="warehouses",
    extra=(
        Column("city", "City", sort="city"),
        Column("state_code", "State", kind="mono", sort="state_code"),
    ),
    search=("city",),
    filters=(Filter("city", "City", "city", options=distinct_options(Warehouse, "city")),),
)

# Tax slabs are versioned (R3.6): every row of a code is a version, so the list shows
# the validity window and defaults to newest-first rather than by code.
TAX_RATE_LIST = ListSpec(
    entity="tax_rate",
    model=TaxRate,
    columns=(
        Column("code", "Code", kind="mono", sort="code"),
        Column("name", "Name", sort="name"),
        Column("rate_bps", "Rate", kind="bps", sort="rate_bps"),
        Column("valid_from", "In force from", kind="date", sort="valid_from"),
        Column("valid_to", "Until", kind="date", sort="valid_to"),
        Column("is_active", "Status", kind="bool", sort="is_active"),
    ),
    search=("code", "name"),
    filters=(STATUS_FILTER,),
    sort="valid_from",
    dir="desc",
    page_size=25,
    search_hint="Search tax slabs by code or name",
)

# `parent_name` is projected (see `CategoryService.to_read_many`), so it is a column
# without a `sort=`; the tree itself is rendered separately on the same page (R3.4).
CATEGORY_LIST = ListSpec(
    entity="category",
    model=Category,
    columns=(
        Column("code", "Code", kind="mono", sort="code"),
        Column("name", "Name", sort="name"),
        Column("parent_name", "Parent"),
        Column("procurement_model_name", "Procurement model"),
        Column("product_count", "Products", kind="number"),
        Column("is_active", "Status", kind="bool", sort="is_active"),
    ),
    search=("code", "name"),
    filters=(
        STATUS_FILTER,
        Filter("parent", "Parent", "parent_category_id", coerce="uuid",
               options=model_options(Category)),
        Filter("model", "Procurement model", "procurement_model_id", coerce="uuid",
               options=model_options(ProcurementModel)),
    ),
    sort="code",
    dir="asc",
    page_size=25,
    search_hint="Search categories by code or name",
)

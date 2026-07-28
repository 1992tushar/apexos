"""The product list, as configuration (R2.2).

Declared in the module rather than beside the page because both halves need it:
`ProductService.list` runs the query through `query_page`, and `/products` renders
the same spec's columns. One spec, so the API's filters and the screen's headers
cannot drift apart.

`Column.key` reads the *projected* row (`ProductRead`), which is why
`category_name`, `selling_price_minor` and `stock_on_hand` can be columns; only
`Column.sort` and `Filter.column` name real `Product` attributes.
"""
from __future__ import annotations

from app.db.listing import Column, Filter, ListSpec, model_options, static_options
from app.modules.config.models import Brand, Category
from app.modules.products.models import Product

# The status lifecycle (R3.9). One definition: the filter's options and the set the
# service will accept come from the same place.
PRODUCT_STATUS_CHOICES: tuple[tuple[str, str], ...] = (
    ("active", "Active"),
    ("draft", "Draft"),
    ("discontinued", "Discontinued"),
)
PRODUCT_STATUSES_ALLOWED = frozenset(value for value, _ in PRODUCT_STATUS_CHOICES)
PRODUCT_STATUSES = static_options(*PRODUCT_STATUS_CHOICES)

PRODUCT_LIST = ListSpec(
    entity="product",
    model=Product,
    columns=(
        Column("sku_code", "SKU", kind="mono", sort="sku_code"),
        Column("name", "Name", kind="link", sort="name", href="/products/{id}"),
        Column("category_name", "Category"),
        Column("brand_name", "Brand"),
        Column("specification", "Specification", sort="specification"),
        Column("selling_price_minor", "Selling price", kind="money"),
        Column("stock_on_hand", "Stock", kind="number"),
        Column("status", "Status", kind="badge", sort="status"),
    ),
    search=("name", "sku_code", "specification"),
    filters=(
        Filter("category", "Category", "category_id", coerce="uuid",
               options=model_options(Category)),
        Filter("brand", "Brand", "brand_id", coerce="uuid", options=model_options(Brand)),
        Filter("status", "Status", "status", options=PRODUCT_STATUSES),
    ),
    sort="sku_code",
    dir="asc",
    page_size=25,
    search_hint="Search products by name, SKU or spec",
)

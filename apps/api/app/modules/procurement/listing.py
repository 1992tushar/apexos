"""The requisition and RFQ lists, as configuration (R2.2, R4.13).

No hand-rolled table markup and no query: `query_page` runs these specs and the
part 2 macros render them. `Column.key` reads the *projected* row
(`RequisitionListRow` / `RfqListRow`), which is why `line_count`, `qty_total` and
`quote_count` can be columns — only `Column.sort` and `Filter.column` name real
model attributes, so those columns publish no `sort=`.
"""
from __future__ import annotations

from app.db.listing import Column, Filter, ListSpec, static_options
from app.modules.procurement.models import PurchaseRequisition, Rfq
from app.modules.procurement.preorder import REQUISITION_STATUSES, RFQ_STATUSES

REQUISITION_LIST = ListSpec(
    entity="purchase_requisition",
    model=PurchaseRequisition,
    columns=(
        Column("requisition_no", "Requisition", kind="link", sort="requisition_no",
               href="/requisitions/{id}"),
        Column("status", "Status", kind="badge", sort="status"),
        Column("line_count", "Lines", kind="number"),
        Column("qty_total", "Total qty", kind="number"),
        Column("needed_by", "Needed by", kind="date", sort="needed_by"),
        Column("outcome", "Became"),
        Column("created_at", "Raised", kind="datetime", sort="created_at"),
    ),
    search=("requisition_no", "note"),
    filters=(
        Filter("status", "Status", "status", options=static_options(*REQUISITION_STATUSES)),
    ),
    sort="created_at",
    dir="desc",
    page_size=25,
    search_hint="Search requisitions by number or note",
)

RFQ_LIST = ListSpec(
    entity="rfq",
    model=Rfq,
    columns=(
        Column("rfq_no", "RFQ", kind="link", sort="rfq_no", href="/rfqs/{id}"),
        Column("status", "Status", kind="badge", sort="status"),
        Column("line_count", "Lines", kind="number"),
        Column("supplier_count", "Asked", kind="number"),
        Column("quote_count", "Quoted", kind="number"),
        Column("due_date", "Quotes due", kind="date", sort="due_date"),
        Column("created_at", "Issued", kind="datetime", sort="created_at"),
    ),
    search=("rfq_no", "note"),
    filters=(Filter("status", "Status", "status", options=static_options(*RFQ_STATUSES)),),
    sort="created_at",
    dir="desc",
    page_size=25,
    search_hint="Search RFQs by number or note",
)

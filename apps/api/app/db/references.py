"""Relationship integrity: what still points at this row, and does it matter (R3.7).

A master that is referenced by *live* work cannot be quietly retired. The rule this
module enforces is the one Part 1 settled on for deletion (`docs/DELETION-POLICY.md`):
**does anything read this row live?** — not "does anything reference it". A confirmed
invoice snapshotted the product's name and price, so deleting the product leaves the
invoice intact (R1.7). An *open* purchase order has not been received yet; it will read
the product again at receipt, so retiring the product underneath it breaks work in
progress.

The map at the bottom lists, per table, the references that block. Each one names the
documents it found, because "cannot delete: still referenced" tells the founder nothing
they can act on:

    Cannot deactivate product Toilet Roll — it is still used by 2 open purchase orders
    (PO-202607-00001, PO-202607-00003). Close, cancel or reassign those first.

A reference reached through a document *line* declares `via`, so the message quotes the
document rather than a line id, and `live_statuses` on the `via` is what "open" means for
that document type. Anything closed, cancelled or historical is not a reference for this
purpose — that distinction is the whole point, and it is data here, not a rule buried in
a service.

Deactivation and deletion ask the same question. A master unsafe to delete is unsafe to
hide from every dropdown, and two answers would mean two policies to keep in step.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError

# How many blocking documents to quote before saying "and N more".
_QUOTE_LIMIT = 3


@dataclass(frozen=True)
class Via:
    """The parent document a referring line belongs to."""

    model: type[Any]
    child_column: str  # the line's FK to this document
    label: str  # the document's human identifier, e.g. "po_no"
    live_statuses: tuple[str, ...] = ()  # empty = every row of it counts


@dataclass(frozen=True)
class Reference:
    """One table that points at a master, and what makes that pointer live."""

    model: type[Any]
    column: str
    noun: str
    plural: str
    label: str = "name"
    live_statuses: tuple[str, ...] = ()
    via: Via | None = None


def _direct(db: Session, ref: Reference, row_id: Any) -> tuple[int, list[str]]:
    model = ref.model
    where = [getattr(model, ref.column) == row_id]
    deleted = getattr(model, "deleted_at", None)
    if deleted is not None:
        where.append(deleted.is_(None))
    if ref.live_statuses:
        where.append(model.status.in_(ref.live_statuses))
    total = db.scalar(select(func.count()).select_from(model).where(*where)) or 0
    if not total:
        return 0, []
    labels = [
        str(v)
        for (v,) in db.execute(
            select(getattr(model, ref.label)).where(*where).limit(_QUOTE_LIMIT)
        )
    ]
    return total, labels


def _through(db: Session, ref: Reference, row_id: Any) -> tuple[int, list[str]]:
    """Count the *documents* whose lines point here, not the lines."""
    via, child = ref.via, ref.model
    parent = via.model
    where = [
        getattr(child, ref.column) == row_id,
        getattr(child, via.child_column) == parent.id,
    ]
    for model in (child, parent):
        deleted = getattr(model, "deleted_at", None)
        if deleted is not None:
            where.append(deleted.is_(None))
    if via.live_statuses:
        where.append(parent.status.in_(via.live_statuses))
    total = db.scalar(
        select(func.count(func.distinct(parent.id))).select_from(child, parent).where(*where)
    ) or 0
    if not total:
        return 0, []
    labels = [
        str(v)
        for (v,) in db.execute(
            select(getattr(parent, via.label))
            .select_from(child, parent)
            .where(*where)
            .distinct()
            .limit(_QUOTE_LIMIT)
        )
    ]
    return total, labels


def _phrase(ref: Reference, count: int, labels: Sequence[str]) -> str:
    noun = ref.noun if count == 1 else ref.plural
    quoted = ", ".join(labels)
    if count > len(labels):
        quoted += f", and {count - len(labels)} more"
    return f"{count} {noun} ({quoted})"


def blocking_references(db: Session, instance: Any) -> list[str]:
    """Human-readable phrases for everything live that points at `instance`."""
    found: list[str] = []
    for ref in REFERENCES.get(type(instance).__tablename__, ()):
        count, labels = (_through if ref.via else _direct)(db, ref, instance.id)
        if count:
            found.append(_phrase(ref, count, labels))
    return found


def ensure_unreferenced(db: Session, instance: Any, *, action: str, label: str) -> None:
    """Raise `ConflictError` naming the live work that blocks `action` (R3.7).

    Never cascades and never silently succeeds: either nothing live points here, or the
    caller gets a sentence listing what does.
    """
    found = blocking_references(db, instance)
    if not found:
        return
    name = getattr(instance, "name", None) or getattr(instance, "code", "")
    raise ConflictError(
        f"Cannot {action} {label.lower()} {name} — it is still used by "
        + "; ".join(found)
        + ". Close, cancel or reassign those first."
    )


def _build_map() -> dict[str, tuple[Reference, ...]]:
    # Imported here rather than at module scope: `app.db` sits under the modules in the
    # import order, and this map is the one place that needs to know all of them.
    from app.modules.config.models import Category, UomConversion
    from app.modules.crm.models import Lead
    from app.modules.customers.models import Customer
    from app.modules.inventory.models import StockMovement
    from app.modules.procurement.models import (
        GoodsReceipt,
        PurchaseOrder,
        PurchaseOrderLine,
        PurchaseRequisition,
        PurchaseRequisitionLine,
        Rfq,
        RfqLine,
        RfqSupplier,
        SupplierQuotation,
    )
    from app.modules.products.models import Product
    from app.modules.sales.models import SalesOrder, SalesOrderLine
    from app.modules.suppliers.models import Supplier

    # A document is open while it can still change what it reads from a master.
    open_po = ("draft", "confirmed", "partially_received")
    open_so = ("draft", "confirmed", "partially_fulfilled")
    # A requisition is open until it has been converted or rejected; an RFQ until it
    # is awarded or closed. Both still read the product they name (R4.1/R4.3).
    open_req = ("requested", "approved")
    open_rfq = ("issued",)
    via_po = Via(PurchaseOrder, "purchase_order_id", "po_no", open_po)
    via_so = Via(SalesOrder, "sales_order_id", "order_no", open_so)
    via_req = Via(PurchaseRequisition, "purchase_requisition_id", "requisition_no", open_req)
    via_rfq = Via(Rfq, "rfq_id", "rfq_no", open_rfq)

    def on_product(column: str) -> Reference:
        return Reference(Product, column, "product", "products")

    return {
        # --- config masters: a product or a party reads these live ------------
        "brand": (on_product("brand_id"),),
        "uom": (
            on_product("uom_id"),
            Reference(UomConversion, "from_uom_id", "conversion", "conversions", label="id"),
            Reference(UomConversion, "to_uom_id", "conversion", "conversions", label="id"),
        ),
        "customer_type": (
            Reference(Customer, "customer_type_id", "customer", "customers"),
            Reference(Lead, "customer_type_id", "lead", "leads"),
        ),
        "supplier_type": (Reference(Supplier, "supplier_type_id", "supplier", "suppliers"),),
        "tax_rate": (on_product("default_tax_rate_id"),),
        "warehouse": (
            Reference(StockMovement, "warehouse_id", "stock movement", "stock movements",
                      label="id"),
            # A goods receipt names the warehouse the stock landed in, so a warehouse
            # is live while any PO it received against is still open. Reached through
            # the receipt, not the PO: a purchase order carries no warehouse of its
            # own (the receipt chooses one), and naming a column the model does not
            # have is an AttributeError the moment someone retires a warehouse.
            Reference(GoodsReceipt, "warehouse_id", "open purchase order",
                      "open purchase orders", via=via_po),
        ),
        "business_unit": (
            Reference(Category, "business_unit_id", "category", "categories"),
            on_product("business_unit_id"),
            Reference(Customer, "business_unit_id", "customer", "customers"),
        ),
        "category": (
            on_product("category_id"),
            Reference(Category, "parent_category_id", "sub-category", "sub-categories"),
        ),
        "procurement_model": (
            Reference(Category, "procurement_model_id", "category", "categories"),
            on_product("procurement_model_id"),
        ),
        # --- operational masters: only OPEN documents block -------------------
        # An invoice or a bill snapshotted what it needed, so it is not a reference
        # (R1.7 requires a deleted customer's invoice to keep rendering).
        "product": (
            Reference(PurchaseOrderLine, "product_id", "open purchase order",
                      "open purchase orders", via=via_po),
            Reference(SalesOrderLine, "product_id", "open sales order",
                      "open sales orders", via=via_so),
            # Pre-order work reads the product again when it converts (R4.1/R4.3), so
            # retiring it underneath an unconverted requisition or a live RFQ would
            # break the conversion. A converted requisition is history and does not.
            Reference(PurchaseRequisitionLine, "product_id", "open requisition",
                      "open requisitions", via=via_req),
            Reference(RfqLine, "product_id", "open RFQ", "open RFQs", via=via_rfq),
        ),
        "customer": (
            Reference(SalesOrder, "customer_id", "open sales order", "open sales orders",
                      label="order_no", live_statuses=open_so),
        ),
        "supplier": (
            Reference(PurchaseOrder, "supplier_id", "open purchase order",
                      "open purchase orders", label="po_no", live_statuses=open_po),
            # An invited supplier on a live RFQ is still being waited on. A quotation
            # already received is history — it snapshotted its own prices (R1.7).
            Reference(RfqSupplier, "supplier_id", "open RFQ", "open RFQs", via=via_rfq),
        ),
        # --- pre-order documents ---------------------------------------------
        # A requisition or RFQ is itself referenced only by what it produced, and a
        # produced PO is the record — deleting the request does not unmake the order.
        # Declared explicitly so the next part finds the decision, not a gap (R3.7).
        "purchase_requisition": (
            Reference(Rfq, "purchase_requisition_id", "open RFQ", "open RFQs",
                      label="rfq_no", live_statuses=open_rfq),
        ),
        "rfq": (
            Reference(SupplierQuotation, "rfq_id", "quotation", "quotations",
                      label="quotation_no"),
        ),
        # Part 4 (R5.1). A product↔supplier link is a *preference*, not a live
        # document, so it deliberately does NOT appear under "product" or "supplier"
        # above: retiring a supplier you no longer buy from must not be blocked by
        # the fact that you once recorded you could. The link soft-deletes with the
        # one helper and the mapping screen simply stops offering it.
        #
        # Nothing points AT a link, hence the empty tuple — and it is declared rather
        # than omitted, because R3.7 treats a missing entry as "not yet considered".
        "product_supplier": (),
        # Deliberately empty — nothing reads these live. Present so a missing entry
        # reads as "not yet considered" rather than "considered, nothing to guard".
        "manufacturer": (),
        "setting": (),
        "uom_conversion": (),
        "purchase_requisition_line": (),
        "rfq_line": (),
        "rfq_supplier": (),
        "supplier_quotation": (),
        "supplier_quotation_line": (),
        # A revision is history, not a master (R3.7 / R4.7). Goods receipts point at
        # one, but a revision is never deleted or deactivated — `purchase_order` is
        # in PROTECTED_TABLES and revisions cascade with it — so there is no action
        # for a guard to block. Present, and deliberately empty.
        "purchase_order_revision": (),
        "purchase_order_revision_line": (),
    }


REFERENCES: dict[str, tuple[Reference, ...]] = _build_map()

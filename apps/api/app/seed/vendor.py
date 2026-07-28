"""Part 4's seed section: vendor intelligence history (R5.13).

R5.13 asks for receipt history across at least two suppliers making lead time and
on-time rate non-trivial, plus one product below reorder level with an open PO and
one without. "Non-trivial" is the point — a seed where every delivery lands the same
day it was ordered makes lead time 0 and on-time meaningless.

What this section ADDS: leads of 5, 7 and 9 days for PaperWings and 12 and 16 for
Baroda, each with a promised date to judge against. What the demo database then
SHOWS is not those numbers alone, because the earlier buy-loop and pre-order sections
already gave PaperWings two same-day receipts with nothing promised:

    PaperWings (SUPP-0001)  leads 0, 0, 5, 7, 9 → mean 4    on time 2 of 3 → 67%
                            (the two 0-day receipts have no promised date, so they
                             are excluded from on-time rather than counted as met)
    Baroda     (SUPP-0002)  leads 12, 16        → mean 14   on time 1 of 2 → 50%
    K K Sales  (SUPP-0003)  no confirmed receipt → all three unknown (R5.11 on screen)

That messiness is deliberate and realistic, and it is why the arithmetic tests in
`tests/test_vendor_intel.py` build their **own** supplier with a known history rather
than asserting against these totals — a later part adding one more PO must not break
a formula test. The seeded figures above are asserted separately, as R5.13's own
"the demo data is non-trivial" check.

One of PaperWings' added receipts lands **exactly on the promised date**, which is
R5.4's boundary case: it must count as ON TIME.

Timestamps are passed to `confirm(confirmed_at=…)` and `receive(received_at=…)` so
history is fabricated at INSERT time. The seed never UPDATEs `goods_receipt` or
`purchase_order.confirmed_at` after the fact — those are ledger rows and G4 makes
them append-only.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select

from app.modules.inventory.service import InventoryService
from app.modules.pricing.models import PurchasePrice
from app.modules.procurement.schemas import (
    GoodsReceiptCreate,
    PurchaseOrderCreate,
    PurchaseOrderLineCreate,
)
from app.modules.procurement.service import GoodsReceiptService, PurchaseOrderService
from app.modules.products.models import Product
from app.modules.suppliers.models import ProductSupplier
from app.modules.suppliers.schemas import (
    ProductSupplierUpsert,
    SupplierEvaluationCreate,
)
from app.modules.suppliers.service import ProductSupplierService, VendorEvaluationService
from app.seed.helpers import SeedContext

#: (supplier code, confirm offset, receive offset, promised offset) in days before
#: today. `receive − confirm` is the measured lead time; `receive <= promised` is
#: on time, and equality counts as on time (R5.4).
RECEIPT_HISTORY: tuple[tuple[str, int, int, int], ...] = (
    # PaperWings: 5 days, landed exactly on the promised date — R5.4's boundary.
    ("SUPP-0001", 40, 35, 35),
    # PaperWings: 7 days, a day early.
    ("SUPP-0001", 30, 23, 22),
    # PaperWings: 9 days, two days late.
    ("SUPP-0001", 20, 11, 13),
    # Baroda: 12 days, two days late.
    ("SUPP-0002", 40, 28, 30),
    # Baroda: 16 days, four days early — slow but honest about it.
    ("SUPP-0002", 25, 9, 5),
)

#: (product SKU, supplier code, is_preferred, moq)
#:
#: The last two are the reorder cases below, mapped on purpose: a recommendation for
#: a product with no preferred supplier can say nothing about lead time, and R5.8's
#: whole point is a sentence that ends "lead time 9 days measured over 6 receipts".
#: SUPP-0001 measures 4 days and SUPP-0002 measures 14, so the two recommendations
#: differ in urgency for a visible reason. APX-GB-004's MOQ of 100 is deliberately
#: ABOVE its shortfall, which is the case that exercises the MOQ step on screen.
#: The ~99 other products below their reorder level have no mapping, so the
#: "no preferred supplier" path is on the same screen.
MAPPING: tuple[tuple[str, str, bool, str | None], ...] = (
    ("APX-GB-001", "SUPP-0001", True, "500"),
    ("APX-GB-001", "SUPP-0002", False, "1000"),
    ("AUR-TIS-003", "SUPP-0001", True, "100"),
    ("APX-GB-002", "SUPP-0002", True, "250"),
    ("APX-GB-002", "SUPP-0001", False, "300"),
    ("APX-GB-003", "SUPP-0001", True, "25"),
    ("APX-GB-004", "SUPP-0002", True, "100"),
)

#: The SKU each receipt-history order is placed for — one line, so the arithmetic
#: on screen is easy to follow back to the record.
HISTORY_SKU = "AUR-TIS-001"

#: R5.13's two reorder cases: (SKU, how far ABOVE current stock to set the reorder
#: level, whether it also gets an open PO).
#:
#: The level is set relative to measured stock rather than to a fixed number,
#: because these SKUs already carry opening stock from an earlier seed section — a
#: hard-coded 80 silently stopped being "below reorder" the moment stock was 100,
#: and the requirement is the *relationship*, not the number.
#: The margins are set well above the 20-unit gap most of the catalogue carries so
#: that these two sort to the TOP of "due to order" — the recommendation list is
#: worst-shortfall-first, and a demo case buried on page four demonstrates nothing.
REORDER_CASES: tuple[tuple[str, str, bool], ...] = (
    # Below reorder level AND already on order — the recommendation must NOT
    # double-order this one; part 4's engine subtracts the open quantity. Margin 90
    # against an open 40 leaves a shortfall of 50, so the subtraction is visible on
    # screen rather than being the difference between 10 and 0.
    ("APX-GB-003", "90", True),
    # Below reorder level with nothing on order — the genuine "buy this" case.
    ("APX-GB-004", "60", False),
)

#: R5.7's other column: one order that is already late. A calendar that never shows
#: an overdue row hides the one thing a founder most needs from it. Confirmed, past
#: its promised date, never received. (supplier code, confirmed days ago, promised
#: days ago.)
LATE_ARRIVAL: tuple[str, int, int] = ("SUPP-0002", 12, 3)


def seed_vendor(ctx: SeedContext) -> dict | None:
    """Mapping + MOQ, receipt history, scorecards, price history, reorder cases.

    Returns the summary `run()` files under `"vendor"`, or None when the section is
    skipped because the mapping already exists (idempotence).
    """
    db = ctx.db
    actor_id = ctx.actor_id
    suppliers = ctx.suppliers

    if (db.scalar(select(func.count()).select_from(ProductSupplier)) or 0) > 0:
        return None

    def product(sku: str) -> Product:
        return db.scalar(select(Product).where(Product.sku_code == sku))

    links = ProductSupplierService(db)
    po_service = PurchaseOrderService(db)
    grn_service = GoodsReceiptService(db)
    today = datetime.now(UTC).date()

    # --- R5.1 / R5.5: which suppliers each product can be bought from ------
    for sku, supplier_code, preferred, moq in MAPPING:
        links.upsert(
            ProductSupplierUpsert(
                product_id=product(sku).id,
                supplier_id=suppliers[supplier_code].id,
                is_preferred=preferred,
                moq=Decimal(moq) if moq else None,
                note=None,
            ),
            actor_id=actor_id,
        )

    # --- R5.13: receipt history, so lead time and on-time rate are real ----
    history_product = product(HISTORY_SKU)
    receipts: list[str] = []
    for supplier_code, confirm_ago, receive_ago, promised_ago in RECEIPT_HISTORY:
        order = po_service.create(
            PurchaseOrderCreate(
                supplier_id=suppliers[supplier_code].id,
                order_date=today - timedelta(days=confirm_ago),
                lines=[
                    PurchaseOrderLineCreate(
                        product_id=history_product.id, qty=Decimal("25")
                    )
                ],
            ),
            actor_id=actor_id,
        )
        confirmed_at = datetime.now(UTC) - timedelta(days=confirm_ago)
        po_service.confirm(
            order.id,
            actor_id=actor_id,
            confirmed_at=confirmed_at,
            expected_date=today - timedelta(days=promised_ago),
        )
        grn_service.receive(
            order.id,
            GoodsReceiptCreate(
                received_at=datetime.now(UTC) - timedelta(days=receive_ago)
            ),
            actor_id=actor_id,
        )
        receipts.append(f"{order.po_no} {confirm_ago - receive_ago}d")

    # --- R5.2's other input: a scorecard for one supplier only -------------
    # PaperWings gets one, so its score uses both inputs at the full 60/40 weight.
    # Baroda deliberately gets none, so the screen shows the renormalised single-input
    # case; K K Sales gets neither, so it shows "unknown" (R5.11).
    VendorEvaluationService(db).score(
        SupplierEvaluationCreate(
            supplier_id=suppliers["SUPP-0001"].id,
            quality_score=4,
            price_score=4,
            reliability_score=5,
            notes="Consistent quality, occasionally slips on the promised date.",
        ),
        actor_id=actor_id,
    )

    # --- R5.6: a price timeline with a real change to show ----------------
    # `purchase_price` already carries supplier_id + valid_from/valid_to, so the
    # timeline needs no new table — it needs more than one row.
    base = db.scalar(
        select(PurchasePrice.price_minor).where(
            PurchasePrice.product_id == history_product.id,
            PurchasePrice.supplier_id.is_(None),
        )
    ) or 8400
    for supplier_code, months_ago, factor in (
        ("SUPP-0001", 8, Decimal("0.94")),
        ("SUPP-0001", 3, Decimal("1.00")),
        ("SUPP-0002", 5, Decimal("0.97")),
    ):
        start = datetime.now(UTC) - timedelta(days=30 * months_ago)
        closes = months_ago == 8  # the older PaperWings price is superseded
        db.add(
            PurchasePrice(
                product_id=history_product.id,
                supplier_id=suppliers[supplier_code].id,
                price_minor=int(Decimal(base) * factor),
                valid_from=start,
                valid_to=(start + timedelta(days=150)) if closes else None,
                created_by=actor_id,
            )
        )
    db.flush()

    # --- R5.13: one product below reorder WITH an open PO, one WITHOUT -----
    reorder_summary: dict[str, str] = {}
    inventory = InventoryService(db)
    for sku, margin, wants_open_po in REORDER_CASES:
        prod = product(sku)
        # `reorder_level` is ordinary product master data, not a derived figure.
        # Set above measured stock so the row really is below its reorder level.
        on_hand = inventory.on_hand(prod.id)
        level = on_hand + Decimal(margin)
        prod.reorder_level = level
        prod.updated_by = actor_id
        db.flush()
        if wants_open_po:
            order = po_service.create(
                PurchaseOrderCreate(
                    supplier_id=suppliers["SUPP-0001"].id,
                    lines=[PurchaseOrderLineCreate(product_id=prod.id, qty=Decimal("40"))],
                ),
                actor_id=actor_id,
            )
            # Confirmed but NOT received: this is what "on open PO" means (R4.9).
            po_service.confirm(
                order.id,
                actor_id=actor_id,
                expected_date=today + timedelta(days=7),
            )
            reorder_summary[sku] = (
                f"stock {on_hand}, reorder level {level}, {order.po_no} open"
            )
        else:
            reorder_summary[sku] = (
                f"stock {on_hand}, reorder level {level}, nothing on order"
            )

    # --- R5.7: one overdue arrival, so the calendar's worst column is not empty --
    late_code, late_confirm_ago, late_promised_ago = LATE_ARRIVAL
    late = po_service.create(
        PurchaseOrderCreate(
            supplier_id=suppliers[late_code].id,
            order_date=today - timedelta(days=late_confirm_ago),
            lines=[
                PurchaseOrderLineCreate(product_id=history_product.id, qty=Decimal("30"))
            ],
        ),
        actor_id=actor_id,
    )
    # Confirmed and promised, never received: this is what "overdue" means (R5.7).
    po_service.confirm(
        late.id,
        actor_id=actor_id,
        confirmed_at=datetime.now(UTC) - timedelta(days=late_confirm_ago),
        expected_date=today - timedelta(days=late_promised_ago),
    )

    return {
        "mapping": f"{len(MAPPING)} product-supplier links",
        "receipts": receipts,
        "reorder_cases": reorder_summary,
        "overdue_arrival": f"{late.po_no} promised {late_promised_ago} days ago",
    }

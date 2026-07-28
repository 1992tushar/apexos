"""Idempotent seed of real Apex data + one completed spine sales order.

Run with:  python -m app.seed

Safe to re-run: every row is get-or-created by its natural key, prices/opening
stock are only written when a product is first created, and the demo sales order
+ payment are only generated once (when none exist yet).
"""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, engine
from app.db.metadata import Base, import_all_models

# Ensure every model is imported so Base.metadata is complete, then make sure the
# tables physically exist (create_all runs below in run(); this just completes the
# metadata for the model imports that follow).
import_all_models()

from app.modules.activity.models import ActivityLog  # noqa: E402
from app.modules.activity.service import ActivityService  # noqa: E402
from app.modules.config.models import (  # noqa: E402
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
from app.modules.config.schemas import TaxRateSlabCreate  # noqa: E402
from app.modules.config.service import MASTER_LABELS, TaxRateService  # noqa: E402
from app.modules.crm.models import (  # noqa: E402
    Lead,
    Opportunity,
    PipelineStage,
)
from app.modules.crm.schemas import (  # noqa: E402
    CompetitorCreate,
    LeadCreate,
    OpportunityCreate,
)
from app.modules.crm.service import CrmService  # noqa: E402
from app.modules.customers.models import Customer, CustomerCreditPolicy  # noqa: E402
from app.modules.customers.schemas import CustomerUpdate  # noqa: E402
from app.modules.customers.service import CustomerService  # noqa: E402
from app.modules.documents.models import Document  # noqa: E402
from app.modules.documents.service import DocumentService  # noqa: E402
from app.modules.finance.models import Bill, Invoice  # noqa: E402
from app.modules.finance.schemas import BillPaymentCreate, PaymentCreate  # noqa: E402
from app.modules.finance.service import BillService, InvoiceService  # noqa: E402
from app.modules.identity.models import User  # noqa: E402
from app.modules.inventory.schemas import StockTransferCreate  # noqa: E402
from app.modules.inventory.service import (
    InventoryService,  # noqa: E402
    StockTransferService,  # noqa: E402
)
from app.modules.notifications.models import Notification  # noqa: E402
from app.modules.notifications.schemas import NotificationCreate  # noqa: E402
from app.modules.notifications.service import NotificationService  # noqa: E402
from app.modules.pricing.models import PurchasePrice, SellingPrice  # noqa: E402
from app.modules.procurement.models import (  # noqa: E402
    PurchaseOrder,
    PurchaseRequisition,
    Rfq,
)
from app.modules.procurement.preorder import (  # noqa: E402
    RequisitionService,
    RfqService,
)
from app.modules.procurement.schemas import (  # noqa: E402
    GoodsReceiptCreate,
    GoodsReceiptLineInput,
    PurchaseOrderCreate,
    PurchaseOrderLineCreate,
    PurchaseOrderRevise,
    PurchaseOrderReviseLine,
    QuotationCreate,
    QuotationLineInput,
    RequisitionCreate,
    RequisitionLineCreate,
)
from app.modules.procurement.service import (  # noqa: E402
    GoodsReceiptService,
    PurchaseOrderService,
)
from app.modules.products.models import Product  # noqa: E402
from app.modules.sales.models import SalesOrder  # noqa: E402
from app.modules.sales.schemas import SalesOrderCreate, SalesOrderLineCreate  # noqa: E402
from app.modules.sales.service import SalesOrderService  # noqa: E402
from app.modules.suppliers.models import Supplier  # noqa: E402
from app.modules.tasks.models import Task  # noqa: E402
from app.modules.tasks.schemas import TaskCreate  # noqa: E402
from app.modules.tasks.service import TaskService  # noqa: E402


def get_or_create(db: Session, model, *, defaults: dict | None = None, **filters):
    """Return (instance, created)."""
    stmt = select(model)
    for key, val in filters.items():
        stmt = stmt.where(getattr(model, key) == val)
    instance = db.scalar(stmt)
    if instance is not None:
        return instance, False
    params = {**filters, **(defaults or {})}
    instance = model(**params)
    db.add(instance)
    db.flush()
    return instance, True


# --- reference data ------------------------------------------------------

CATEGORIES = [
    ("TIS", "Tissue & Paper Consumables", "AUR", "PRIVATE_LABEL"),
    ("GB", "Garbage Bags & Waste Management", "APX", "MASTER_DIST"),
    ("FP", "Food Packaging", "APX", "MASTER_DIST"),
    ("FSD", "Food Service Disposables", "APX", "MASTER_DIST"),
    ("CC", "Cleaning Chemicals", "APX", "CONTRACT_MFR"),
    ("CT", "Cleaning Tools", "APX", "MASTER_DIST"),
    ("WS", "Washroom Solutions", "APX", "PRIVATE_LABEL"),
    ("GLV", "Gloves & Safety Consumables", "APX", "MASTER_DIST"),
    ("GA", "Guest Amenities", "APX", "PRIVATE_LABEL"),
]

# (sku, name, spec, uom_code, sell_minor, buy_minor, category_code, brand_code)
PRODUCTS = [
    ("AUR-TIS-001", "Toilet Roll", "2 Ply Standard", "PACK", 12000, 8400, "TIS", "AUR"),
    ("AUR-TIS-002", "Toilet Roll", "3 Ply Premium", "PACK", 18000, 12600, "TIS", "AUR"),
    ("AUR-TIS-003", "Kitchen Towel", "2 Ply", "ROLL", 9000, 6300, "TIS", "AUR"),
    ("AUR-TIS-004", "M-Fold Hand Towel", "1 Ply", "PACK", 15000, 10500, "TIS", "AUR"),
    ("AUR-TIS-005", "C-Fold Hand Towel", "1 Ply", "PACK", 14000, 9800, "TIS", "AUR"),
    ("AUR-TIS-006", "Facial Tissue", "2 Ply", "PACK", 8000, 5600, "TIS", "AUR"),
    ("AUR-TIS-007", "Napkin Tissue", "1 Ply", "PACK", 6000, 4200, "TIS", "AUR"),
    ("AUR-TIS-008", "Dispenser Napkin", "1 Ply", "PACK", 7000, 4900, "TIS", "AUR"),
    ("APX-GB-001", "Black Garbage Bag 19x21", "19x21", "PACK", 5000, 3500, "GB", "APX"),
    ("APX-GB-002", "Black Garbage Bag 24x32", "24x32", "PACK", 7500, 5250, "GB", "APX"),
    ("APX-GB-003", "Black Garbage Bag 30x37", "30x37", "PACK", 10000, 7000, "GB", "APX"),
    ("APX-GB-004", "Bin Liner Small", "Small", "ROLL", 4000, 2800, "GB", "APX"),
    ("APX-GB-005", "Bin Liner Medium", "Medium", "ROLL", 5500, 3850, "GB", "APX"),
    ("APX-GB-006", "Bin Liner Large", "Large", "ROLL", 7000, 4900, "GB", "APX"),
    ("APX-GB-007", "Heavy Duty Garbage Bag 30x50", "30x50", "PACK", 14000, 9800, "GB", "APX"),
    ("APX-GB-008", "Heavy Duty Garbage Bag 36x48", "36x48", "PACK", 16000, 11200, "GB", "APX"),
    ("APX-GB-009", "Biodegradable Garbage Bag 24x32", "24x32 Bio", "PACK", 12000, 8400, "GB", "APX"),
]

# (code, name, parent_code) — the second level of the tree (R3.10). Products stay on the
# top-level categories, so a sub-category is a real "no products yet" row: deleting it is
# allowed, deleting its parent is not.
SUBCATEGORIES = [
    ("TIS1", "Toilet Rolls", "TIS"),
    ("TIS2", "Hand Towels", "TIS"),
    ("TIS3", "Napkins & Facial", "TIS"),
    ("GB1", "Bin Liners", "GB"),
    ("GB2", "Heavy Duty Sacks", "GB"),
    ("GB3", "Biodegradable", "GB"),
    ("CC1", "Floor Care", "CC"),
    ("CC2", "Washroom Chemicals", "CC"),
    ("FSD1", "Cups & Plates", "FSD"),
    ("FSD2", "Cutlery & Straws", "FSD"),
    ("GLV1", "Hand Protection", "GLV"),
    ("GA1", "Bath Amenities", "GA"),
]

# Third level under two of the above, so the tree is genuinely multi-level.
SUB_SUBCATEGORIES = [
    ("TS2A", "M-Fold", "TIS2"),
    ("TS2B", "C-Fold", "TIS2"),
    ("CC1A", "Neutral pH", "CC1"),
]

DEMO_CUSTOMERS = [
    ("CUST-0001", "Blue Fig Restaurant", "RESTAURANT", "Pune", "Maharashtra", 30000000, 30),
    ("CUST-0002", "Grand Sarovar Hotel", "HOTEL", "Mumbai", "Maharashtra", 50000000, 30),
    ("CUST-0003", "CafeMocha", "CAFE", "Pune", "Maharashtra", 20000000, 30),
]

# --- bulk catalogue + book (R2.13) ---------------------------------------
#
# Pagination and filtering are only real against hundreds of rows, so the demo
# data is generated rather than typed. Generation is deterministic — index
# arithmetic, no randomness — so a re-seed produces the same rows, `get_or_create`
# stays idempotent, and a test can name a row it expects to find. Status, stock
# and credit are deliberately uneven: an all-happy-row seed exercises no filter
# and no empty state (G14).

BULK_ITEMS: dict[str, list[str]] = {
    "TIS": ["Toilet Roll", "Kitchen Towel", "Hand Towel", "Facial Tissue", "Napkin"],
    "GB": ["Garbage Bag", "Bin Liner", "Compactor Sack", "Biohazard Bag"],
    "FP": ["Cling Film", "Aluminium Foil", "Butter Paper", "Food Container"],
    "FSD": ["Paper Cup", "Paper Plate", "Wooden Cutlery", "Straw", "Carry Bag"],
    "CC": ["Floor Cleaner", "Glass Cleaner", "Toilet Cleaner", "Degreaser", "Hand Wash"],
    "CT": ["Microfibre Cloth", "Mop Refill", "Scrub Pad", "Broom", "Squeegee"],
    "WS": ["Soap Dispenser", "Tissue Dispenser", "Air Freshener", "Urinal Screen"],
    "GLV": ["Nitrile Glove", "Latex Glove", "Face Mask", "Apron", "Shoe Cover"],
    "GA": ["Shampoo Sachet", "Bath Soap", "Dental Kit", "Shower Cap", "Sewing Kit"],
}
BULK_GRADES = ["Economy", "Standard", "Premium", "Industrial", "Eco"]
BULK_SIZES = ["Small", "Medium", "Large", "XL", "Jumbo", "Twin Pack", "Bulk Case"]
BULK_UOMS = ["PACK", "ROLL", "CASE", "PIECE"]
# Most of the catalogue is sellable; the rest exercises the status filter.
BULK_STATUSES = ["active"] * 7 + ["draft", "discontinued"]

BULK_CITIES = [
    ("Pune", "Maharashtra"), ("Mumbai", "Maharashtra"), ("Nashik", "Maharashtra"),
    ("Ahmedabad", "Gujarat"), ("Surat", "Gujarat"), ("Bengaluru", "Karnataka"),
    ("Hyderabad", "Telangana"), ("Indore", "Madhya Pradesh"),
]
BULK_CUSTOMER_WORDS = [
    "Green", "Royal", "Urban", "Coastal", "Golden", "Silver", "Spice", "Orchid",
    "Maple", "Sunrise", "Lotus", "Copper", "Velvet", "Harbour", "Summit", "Aster",
]
BULK_CUSTOMER_SUFFIX = {
    "RESTAURANT": ["Kitchen", "Diner", "Bistro", "Grill"],
    "HOTEL": ["Hotel", "Residency", "Inn", "Suites"],
    "CAFE": ["Cafe", "Coffee House", "Bakehouse"],
    "HOSPITAL": ["Hospital", "Clinic", "Care Centre"],
    "CORPORATE": ["Technologies", "Industries", "Solutions"],
    "SCHOOL": ["School", "Academy", "Campus"],
    "FACILITY_MANAGEMENT": ["Facilities", "Services", "Maintenance"],
}


def record_creation(
    db: Session, activity, *, entity_type: str, entity_id, summary: str, actor_id
) -> None:
    """Give a seeded record the `created` history line it would have had.

    The seed writes masters with `get_or_create` rather than through their service,
    so their change-history panel would be empty on the demo rows the founder
    actually clicks (R2.10, G14). The existence check makes it idempotent and also
    backfills a database seeded before this existed; `occurred_at` is then the
    backfill time rather than the original insert, which is the one thing a
    re-seeded demo database cannot recover.
    """
    if not db.scalar(
        select(func.count()).select_from(ActivityLog).where(ActivityLog.entity_id == entity_id)
    ):
        activity.log(
            actor_id=actor_id,
            verb="created",
            entity_type=entity_type,
            entity_id=entity_id,
            summary=summary,
        )


def bulk_products() -> list[tuple]:
    """~300 catalogue rows: (sku, name, spec, uom, sell, buy, cat, brand, status)."""
    rows: list[tuple] = []
    for cat_code, items in BULK_ITEMS.items():
        brand = "AUR" if cat_code == "TIS" else "APX"
        for item_no, item in enumerate(items):
            for variant in range(7):
                seq = len(rows) + 1
                grade = BULK_GRADES[(item_no + variant) % len(BULK_GRADES)]
                size = BULK_SIZES[variant % len(BULK_SIZES)]
                # Integer minor units only, and a margin that never rounds (G1).
                sell = 4000 + (seq % 37) * 500 + variant * 250
                rows.append((
                    f"{brand}-{cat_code}-{100 + seq:03d}",
                    f"{grade} {item}",
                    f"{size} · {grade}",
                    BULK_UOMS[seq % len(BULK_UOMS)],
                    sell,
                    sell * 7 // 10,
                    cat_code,
                    brand,
                    BULK_STATUSES[seq % len(BULK_STATUSES)],
                ))
    return rows


def bulk_customers(start_seq: int, count: int = 250) -> list[tuple]:
    """(code, name, type, city, state, credit_limit_minor, terms, status)."""
    types = list(BULK_CUSTOMER_SUFFIX)
    rows: list[tuple] = []
    for i in range(count):
        seq = start_seq + i
        ctype = types[i % len(types)]
        suffixes = BULK_CUSTOMER_SUFFIX[ctype]
        word = BULK_CUSTOMER_WORDS[(i * 3) % len(BULK_CUSTOMER_WORDS)]
        city, state = BULK_CITIES[i % len(BULK_CITIES)]
        rows.append((
            f"CUST-{seq:04d}",
            f"{word} {suffixes[i % len(suffixes)]} {seq}",
            ctype,
            city,
            state,
            # Every 9th is a cash-only account: a zero limit is a real state, not a gap.
            0 if i % 9 == 0 else (5000000 + (i % 8) * 2500000),
            [15, 30, 45, 60][i % 4],
            "inactive" if i % 11 == 0 else "active",
        ))
    return rows

# (code, name, supplier_type, city, state, gstin)
DEMO_SUPPLIERS = [
    ("SUPP-0001", "PaperWings Sanaswadi", "MANUFACTURER", "Sanaswadi", "Maharashtra", "27AAECP1234A1Z5"),
    ("SUPP-0002", "Baroda Packaging", "DISTRIBUTOR", "Vadodara", "Gujarat", "24AABCB5678B1Z2"),
    ("SUPP-0003", "K K Sales Corporation", "DISTRIBUTOR", "Pune", "Maharashtra", "27AADFK9012C1Z9"),
]


def run() -> dict:
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    try:
        # --- founder user ------------------------------------------------
        founder, _ = get_or_create(
            db,
            User,
            email="founder@apexsupply.example",
            defaults={
                "full_name": "Apex Founder",
                "role_name": "founder",
                "permission_codes": ["*"],
                "is_active": True,
            },
        )
        actor_id = founder.id
        activity = ActivityService(db)

        # --- org / config ------------------------------------------------
        bu, _ = get_or_create(
            db, BusinessUnit, code="APEX",
            defaults={"name": "Apex Core", "is_active": True, "created_by": actor_id},
        )
        founder.business_unit_id = bu.id

        brands = {}
        for code, name in [("AUR", "Aura"), ("APX", "Apex")]:
            b, _ = get_or_create(db, Brand, code=code, defaults={"name": name, "created_by": actor_id})
            brands[code] = b

        pmodels = {}
        for code, name in [
            ("PRIVATE_LABEL", "Private Label"),
            ("MASTER_DIST", "Master Distributor"),
            ("MFR_MASTER_DIST", "Manufacturer + Master Distributor"),
            ("CONTRACT_MFR", "Contract Manufacturer"),
        ]:
            p, _ = get_or_create(db, ProcurementModel, code=code, defaults={"name": name, "created_by": actor_id})
            pmodels[code] = p

        # Contract manufacturing partners (R3.1). Nothing references these yet — they
        # exist so the master is maintainable ahead of the sourcing work that will.
        for code, name, city in [
            ("MFR-PW", "PaperWings Mills", "Sanaswadi"),
            ("MFR-KC", "Kaveri Chemicals", "Hyderabad"),
            ("MFR-GP", "Gujarat Polyfilms", "Vadodara"),
        ]:
            get_or_create(
                db, Manufacturer, code=code,
                defaults={"name": name, "city": city, "created_by": actor_id},
            )

        uoms = {}
        for code, name in [("PACK", "Pack"), ("ROLL", "Roll"), ("CASE", "Case"), ("PIECE", "Piece")]:
            u, _ = get_or_create(db, Uom, code=code, defaults={"name": name, "created_by": actor_id})
            uoms[code] = u

        ctypes = {}
        for name in ["Restaurant", "Hotel", "Cafe", "Hospital", "Corporate", "School", "Facility Management"]:
            code = name.upper().replace(" ", "_")
            c, _ = get_or_create(db, CustomerType, code=code, defaults={"name": name, "created_by": actor_id})
            ctypes[code] = c

        stypes = {}
        for name in ["Manufacturer", "Distributor"]:
            st, _ = get_or_create(
                db, SupplierType, code=name.upper(),
                defaults={"name": name, "created_by": actor_id},
            )
            stypes[name.upper()] = st

        warehouse, _ = get_or_create(
            db, Warehouse, code="PUNE",
            defaults={"name": "Pune Main", "city": "Pune", "state_code": "27", "created_by": actor_id},
        )

        tax_rates = {}
        for code, name, bps in [
            ("GST_0", "GST 0%", 0),
            ("GST_5", "GST 5%", 500),
            ("GST_12", "GST 12%", 1200),
            ("GST_18", "GST 18%", 1800),
        ]:
            t, _ = get_or_create(
                db, TaxRate, code=code,
                defaults={
                    "name": name,
                    "rate_bps": bps,
                    # An explicit fiscal-year start rather than "today": a slab revised
                    # later needs a window that comes after this one (R3.6).
                    "valid_from": date(2025, 4, 1),
                    "created_by": actor_id,
                },
            )
            tax_rates[code] = t
        gst18 = tax_rates["GST_18"]

        # A second version of one slab (R3.10), through the service that owns the
        # versioning so history is appended rather than authored: GST on this line moved
        # 12% → 5%, and the 12% row stays readable with its own validity window (R3.6).
        slab_versions = db.scalar(
            select(func.count()).select_from(TaxRate).where(TaxRate.code == "GST_12")
        )
        if slab_versions == 1:
            TaxRateService(db).set_slab(
                TaxRateSlabCreate(
                    code="GST_12", name="GST 5% (revised)", rate_bps=500,
                    valid_from=date(2026, 4, 1),
                ),
                actor_id=actor_id,
            )
        # Repair any slab whose window closed before it opened — the artifact of a
        # database seeded on a day later than the revision above, back when these rows
        # took their `valid_from` from `current_date`. A demo with a window running
        # backwards teaches the founder to distrust the dates.
        for slab in db.scalars(select(TaxRate).where(TaxRate.valid_to.is_not(None))):
            if slab.valid_from >= slab.valid_to:
                slab.valid_from = date(2025, 4, 1)
        db.flush()

        # --- categories --------------------------------------------------
        categories = {}
        for i, (code, name, brand_code, pmodel_code) in enumerate(CATEGORIES):
            cat, _ = get_or_create(
                db, Category, code=code,
                defaults={
                    "name": name,
                    "business_unit_id": bu.id,
                    "procurement_model_id": pmodels[pmodel_code].id,
                    "sort_order": i,
                    "created_by": actor_id,
                },
            )
            categories[code] = cat

        # Two more levels (R3.10): a category tree is only exercised by a tree.
        for level in (SUBCATEGORIES, SUB_SUBCATEGORIES):
            for i, (code, name, parent_code) in enumerate(level):
                parent = categories[parent_code]
                child, _ = get_or_create(
                    db, Category, code=code,
                    defaults={
                        "name": name,
                        # A child rolls up to its parent's business unit (R3.4).
                        "business_unit_id": parent.business_unit_id,
                        "parent_category_id": parent.id,
                        "procurement_model_id": parent.procurement_model_id,
                        "sort_order": i,
                        "created_by": actor_id,
                    },
                )
                categories[code] = child

        # --- products + prices + opening stock ---------------------------
        # The named rows first (other seed steps order and invoice them by SKU),
        # then the generated catalogue that makes pagination real (R2.13).
        inventory = InventoryService(db)
        catalogue =[(*row, "active") for row in PRODUCTS] + bulk_products()
        for i, (sku, name, spec, uom_code, sell, buy, cat_code, brand_code, status) in enumerate(
            catalogue
        ):
            product, created = get_or_create(
                db, Product, sku_code=sku,
                defaults={
                    "name": name,
                    "specification": spec,
                    "category_id": categories[cat_code].id,
                    "brand_id": brands[brand_code].id,
                    "uom_id": uoms[uom_code].id,
                    "procurement_model_id": categories[cat_code].procurement_model_id,
                    "default_tax_rate_id": gst18.id,
                    "launch_phase": "Phase 1",
                    "reorder_level": Decimal("20"),
                    "status": status,
                    "business_unit_id": bu.id,
                    "created_by": actor_id,
                },
            )
            # Only the named rows get a history line; the generated hundreds would be
            # noise in the activity feed.
            if i < len(PRODUCTS):
                record_creation(
                    db, activity,
                    entity_type="product",
                    entity_id=product.id,
                    summary=f"Product {name} ({sku}) created",
                    actor_id=actor_id,
                )
            if created:
                now = datetime.now(UTC)
                db.add(SellingPrice(product_id=product.id, price_minor=sell, valid_from=now, created_by=actor_id))
                db.add(PurchasePrice(product_id=product.id, price_minor=buy, valid_from=now, created_by=actor_id))
                db.flush()
                # The named rows are fully stocked; the generated ones vary so the
                # low/out badges and the stock column have something to show. A
                # zero-stock product gets no movement at all — also a real state.
                qty = 100 if i < len(PRODUCTS) else (0, 5, 40, 75, 8, 120, 60)[i % 7]
                if qty:
                    inventory.record_movement(
                        product_id=product.id,
                        warehouse_id=warehouse.id,
                        qty_delta=Decimal(qty),
                        reason="PURCHASE",
                        ref_type="opening",
                        unit_cost_minor=buy,
                        actor_id=actor_id,
                    )

        # --- demo customers + credit policies ----------------------------
        # Named accounts first (the demo order and invoice belong to one), then the
        # generated book — codes continue the same CUST-#### sequence so
        # `next_code()` keeps handing out unused ones (R2.13).
        customers = {}
        book = [(*row, "active") for row in DEMO_CUSTOMERS] + bulk_customers(
            len(DEMO_CUSTOMERS) + 1
        )
        for i, (code, name, ctype_code, city, state, limit_minor, terms, status) in enumerate(book):
            cust, created = get_or_create(
                db, Customer, code=code,
                defaults={
                    "name": name,
                    "customer_type_id": ctypes[ctype_code].id,
                    "city": city,
                    "state": state,
                    "status": status,
                    "business_unit_id": bu.id,
                    "created_by": actor_id,
                },
            )
            customers[code] = cust
            # Every 13th generated account has no credit policy yet — the detail page
            # must render a customer whose terms were never set.
            if created and (i < len(DEMO_CUSTOMERS) or i % 13 != 0):
                db.add(CustomerCreditPolicy(
                    customer_id=cust.id,
                    credit_limit_minor=limit_minor,
                    payment_terms_days=terms,
                    status="active",
                    created_by=actor_id,
                ))
                db.flush()
            if i < len(DEMO_CUSTOMERS):
                record_creation(
                    db, activity,
                    entity_type="customer",
                    entity_id=cust.id,
                    summary=f"Customer {name} ({code}) created",
                    actor_id=actor_id,
                )

        # One real revision on a named account, so the change-history panel shows a
        # before → after diff in the booted app rather than only a creation line.
        # `CustomerService.update` writes it — the seed does not hand-author history.
        raised = customers["CUST-0002"]
        revised = db.scalar(
            select(func.count()).select_from(ActivityLog).where(
                ActivityLog.entity_id == raised.id, ActivityLog.verb == "updated"
            )
        )
        if not revised:
            CustomerService(db).update(
                raised.id,
                CustomerUpdate(credit_limit_minor=65000000, payment_terms_days=45),
                actor_id=actor_id,
            )

        # --- demo suppliers -------------------------------------------
        suppliers = {}
        for code, name, stype_code, city, state, gstin in DEMO_SUPPLIERS:
            sup, created = get_or_create(
                db, Supplier, code=code,
                defaults={
                    "name": name,
                    "supplier_type_id": stypes[stype_code].id,
                    "city": city,
                    "state": state,
                    "gstin": gstin,
                    "status": "active",
                    "business_unit_id": bu.id,
                    "created_by": actor_id,
                },
            )
            suppliers[code] = sup

        # Supplier-specific purchase prices for the paper SKUs (buy from PaperWings).
        paperwings = suppliers["SUPP-0001"]
        if db.scalar(
            select(func.count()).select_from(PurchasePrice).where(
                PurchasePrice.supplier_id == paperwings.id
            )
        ) == 0:
            now = datetime.now(UTC)
            for sku in ("AUR-TIS-001", "AUR-TIS-002", "AUR-TIS-003"):
                prod = db.scalar(select(Product).where(Product.sku_code == sku))
                if prod is None:
                    continue
                base = db.scalar(
                    select(PurchasePrice.price_minor).where(
                        PurchasePrice.product_id == prod.id,
                        PurchasePrice.supplier_id.is_(None),
                    )
                ) or 0
                db.add(PurchasePrice(
                    product_id=prod.id,
                    supplier_id=paperwings.id,
                    price_minor=int(base * 0.98) or base,  # a slightly keener supplier price
                    valid_from=now,
                    created_by=actor_id,
                ))
            db.flush()

        # --- one completed buy loop (create -> confirm -> receive -> bill) + partial payment
        existing_pos = db.scalar(select(func.count()).select_from(PurchaseOrder)) or 0
        po_result = None
        supplier_payment_result = None
        if existing_pos == 0:
            po_service = PurchaseOrderService(db)
            grn_service = GoodsReceiptService(db)
            tis1 = db.scalar(select(Product).where(Product.sku_code == "AUR-TIS-001"))
            tis2 = db.scalar(select(Product).where(Product.sku_code == "AUR-TIS-002"))
            po = po_service.create(
                PurchaseOrderCreate(
                    supplier_id=paperwings.id,
                    lines=[
                        PurchaseOrderLineCreate(product_id=tis1.id, qty=Decimal("50")),
                        PurchaseOrderLineCreate(product_id=tis2.id, qty=Decimal("30")),
                    ],
                ),
                actor_id=actor_id,
            )
            po_service.confirm(po.id, actor_id=actor_id)
            grn_service.receive(po.id, None, actor_id=actor_id)  # full receipt (stock IN)
            po_result = po_service.bill(po.id, actor_id=actor_id)

            bill = db.scalar(select(Bill).where(Bill.purchase_order_id == po.id))
            bill_service = BillService(db)
            supplier_payment_result = bill_service.add_payment(
                bill.id,
                BillPaymentCreate(amount_minor=bill.total_minor // 2, method="bank"),
                actor_id=actor_id,
            )

        # --- Part 3 C1: the pre-order flow (R4.15) -------------------------
        # Three requisitions on purpose, so /requisitions shows every state the
        # screen can be in: one still awaiting approval, one approved and already a
        # PO, and one approved and out as an RFQ with two quotes back to compare.
        preorder_result = None
        if (db.scalar(select(func.count()).select_from(PurchaseRequisition)) or 0) == 0:
            requisitions = RequisitionService(db)
            rfqs = RfqService(db)
            gb1 = db.scalar(select(Product).where(Product.sku_code == "APX-GB-001"))
            tis3 = db.scalar(select(Product).where(Product.sku_code == "AUR-TIS-003"))
            today = datetime.now(UTC).date()

            # 1. Awaiting approval — the one the founder lands on with a decision to make.
            pending_req = requisitions.create(
                RequisitionCreate(
                    needed_by=today + timedelta(days=21),
                    note="Warehouse running low ahead of the festive season",
                    lines=[
                        RequisitionLineCreate(product_id=gb1.id, qty=Decimal("400")),
                        RequisitionLineCreate(product_id=tis3.id, qty=Decimal("120")),
                    ],
                ),
                actor_id=actor_id,
            )

            # 2. Approved and converted straight to a PO — price already settled.
            direct_req = requisitions.create(
                RequisitionCreate(
                    needed_by=today + timedelta(days=10),
                    note="Repeat buy, price already agreed with PaperWings",
                    lines=[RequisitionLineCreate(product_id=tis3.id, qty=Decimal("60"))],
                ),
                actor_id=actor_id,
            )
            requisitions.approve(
                direct_req.id,
                reason="Within the monthly consumables budget",
                actor_id=actor_id,
            )
            req_po = requisitions.convert_to_po(
                direct_req.id, supplier_id=paperwings.id, actor_id=actor_id
            )

            # 3. Approved, out as an RFQ, two quotes in — the comparison screen's data.
            #    Deliberately not symmetric: the cheaper unit price comes with the
            #    slower lead time and a higher MOQ, so the screen has a real trade-off
            #    to show rather than one obviously-best column.
            quote_req = requisitions.create(
                RequisitionCreate(
                    needed_by=today + timedelta(days=45),
                    note="New line — no agreed price yet, ask the market",
                    lines=[RequisitionLineCreate(product_id=gb1.id, qty=Decimal("1000"))],
                ),
                actor_id=actor_id,
            )
            requisitions.approve(
                quote_req.id, reason="Volume justifies going out to quote", actor_id=actor_id
            )
            second_supplier = suppliers["SUPP-0002"]
            rfq = requisitions.convert_to_rfq(
                quote_req.id,
                supplier_ids=[paperwings.id, second_supplier.id],
                due_date=today + timedelta(days=14),
                actor_id=actor_id,
            )
            gb_buy = db.scalar(
                select(PurchasePrice.price_minor).where(
                    PurchasePrice.product_id == gb1.id, PurchasePrice.supplier_id.is_(None)
                )
            ) or 10000
            rfqs.capture_quote(
                rfq.id,
                QuotationCreate(
                    supplier_id=paperwings.id,
                    lead_time_days=7,
                    valid_until=today + timedelta(days=30),
                    note="Ex-works Pune, pallet quantities",
                    lines=[
                        QuotationLineInput(
                            product_id=gb1.id,
                            unit_price_minor=int(gb_buy * 1.02) or gb_buy,
                            moq=Decimal("500"),
                        )
                    ],
                ),
                actor_id=actor_id,
            )
            rfqs.capture_quote(
                rfq.id,
                QuotationCreate(
                    supplier_id=second_supplier.id,
                    lead_time_days=18,
                    valid_until=today + timedelta(days=45),
                    note="Cheaper per unit but a longer lead time and a bigger minimum",
                    lines=[
                        QuotationLineInput(
                            product_id=gb1.id,
                            unit_price_minor=int(gb_buy * 0.94) or gb_buy,
                            moq=Decimal("1000"),
                        )
                    ],
                ),
                actor_id=actor_id,
            )
            preorder_result = {
                "awaiting_approval": pending_req.requisition_no,
                "converted_to_po": f"{direct_req.requisition_no} → {req_po.po_no}",
                "rfq": rfq.rfq_no,
                "quotes": len(rfqs.get(rfq.id).quotations),
            }

            # --- Part 3 C2: a partial receipt with a live back order, then a
            #     revision (R4.15). The requisition's PO is the subject, so the
            #     screen tells one story end to end: requested → approved → ordered
            #     → part-delivered → renegotiated.
            #
            #     60 ordered, 40 arrived (back order 20), then the supplier admits
            #     they can only ship 50 in total, so version 2 cuts the order to 50
            #     and the back order becomes 10. Version 1 stays readable at 60, and
            #     the receipt stays stamped against version 1 — which is the whole
            #     point of R4.10.
            po_service = PurchaseOrderService(db)
            grn_service = GoodsReceiptService(db)
            po_service.confirm(req_po.id, actor_id=actor_id)
            grn_service.receive(
                req_po.id,
                GoodsReceiptCreate(
                    lines=[GoodsReceiptLineInput(product_id=tis3.id, qty=Decimal("40"))],
                    against_revision_no=1,
                ),
                actor_id=actor_id,
            )
            revised_po = po_service.revise(
                req_po.id,
                PurchaseOrderRevise(
                    reason="PaperWings can only supply 50 of the 60 ordered this month",
                    lines=[PurchaseOrderReviseLine(product_id=tis3.id, qty=Decimal("50"))],
                ),
                actor_id=actor_id,
            )
            preorder_result["revised_po"] = (
                f"{revised_po.po_no} v{revised_po.revision_no}, "
                f"back order {revised_po.open_qty_total}"
            )

        # --- one completed spine order (create -> confirm -> fulfill -> invoice) + partial payment
        existing_orders = db.scalar(select(func.count()).select_from(SalesOrder)) or 0
        order_result = None
        payment_result = None
        if existing_orders == 0:
            sales = SalesOrderService(db)
            tis = db.scalar(select(Product).where(Product.sku_code == "AUR-TIS-001"))
            gb = db.scalar(select(Product).where(Product.sku_code == "APX-GB-001"))
            created = sales.create(
                SalesOrderCreate(
                    customer_id=customers["CUST-0001"].id,
                    lines=[
                        SalesOrderLineCreate(product_id=tis.id, qty=Decimal("10")),
                        SalesOrderLineCreate(product_id=gb.id, qty=Decimal("20")),
                    ],
                ),
                actor_id=actor_id,
            )
            sales.confirm(created.id, actor_id=actor_id)
            sales.fulfill(created.id, actor_id=actor_id)
            order_result = sales.invoice(created.id, actor_id=actor_id)

            invoice = db.scalar(select(Invoice).where(Invoice.sales_order_id == created.id))
            finance = InvoiceService(db)
            payment_result = finance.add_payment(
                invoice.id,
                PaymentCreate(amount_minor=invoice.total_minor // 2, method="bank"),
                actor_id=actor_id,
            )

        # --- Phase B: second warehouse + a transfer, tasks, a document -----
        mumbai, _ = get_or_create(
            db, Warehouse, code="MUMBAI",
            defaults={"name": "Mumbai Central", "city": "Mumbai", "state_code": "27",
                      "created_by": actor_id},
        )

        # One inter-warehouse transfer (Pune -> Mumbai) if none exist yet.
        from app.modules.inventory.models import StockMovement  # noqa: E402

        existing_transfers = db.scalar(
            select(func.count()).select_from(StockMovement).where(
                StockMovement.reason == "TRANSFER"
            )
        ) or 0
        if existing_transfers == 0:
            transfer_sku = db.scalar(select(Product).where(Product.sku_code == "APX-GB-001"))
            if transfer_sku is not None:
                StockTransferService(db).transfer(
                    StockTransferCreate(
                        product_id=transfer_sku.id,
                        from_warehouse_id=warehouse.id,
                        to_warehouse_id=mumbai.id,
                        qty=Decimal("15"),
                        note="Opening allocation to Mumbai",
                    ),
                    actor_id=actor_id,
                )

        # A few demo tasks (one linked to the seeded purchase order).
        existing_tasks = db.scalar(select(func.count()).select_from(Task)) or 0
        if existing_tasks == 0:
            task_service = TaskService(db)
            po_row = db.scalar(select(PurchaseOrder).order_by(PurchaseOrder.created_at.asc()))
            task_service.create(
                TaskCreate(title="Call PaperWings about Q3 pricing", priority="high"),
                actor_id=actor_id,
            )
            task_service.create(
                TaskCreate(title="Reconcile Mumbai opening stock", priority="normal"),
                actor_id=actor_id,
            )
            if po_row is not None:
                task_service.create(
                    TaskCreate(
                        title=f"Verify goods received for {po_row.po_no}",
                        priority="normal",
                        entity_type="purchase_order",
                        entity_id=po_row.id,
                    ),
                    actor_id=actor_id,
                )

        # A sample document (local-disk fallback so it works without R2 creds).
        existing_docs = db.scalar(select(func.count()).select_from(Document)) or 0
        if existing_docs == 0:
            DocumentService(db).upload(
                filename="welcome.txt",
                content_type="text/plain",
                data=b"ApexOS document storage is live. Replace with real files.\n",
                entity_type=None,
                entity_id=None,
                business_unit_id=bu.id,
                actor_id=actor_id,
            )

        # --- Phase C: pipeline stages, leads, opportunity, competitors, notes
        stages = {}
        for i, (code, name, is_won, is_lost) in enumerate(
            [
                ("NEW", "New", False, False),
                ("QUALIFIED", "Qualified", False, False),
                ("PROPOSAL", "Proposal", False, False),
                ("WON", "Won", True, False),
                ("LOST", "Lost", False, True),
            ]
        ):
            st, _ = get_or_create(
                db, PipelineStage, code=code,
                defaults={"name": name, "sort_order": i, "is_won": is_won,
                          "is_lost": is_lost, "created_by": actor_id},
            )
            stages[code] = st

        existing_leads = db.scalar(select(func.count()).select_from(Lead)) or 0
        if existing_leads == 0:
            crm = CrmService(db)
            lead1 = crm.create_lead(
                LeadCreate(
                    company_name="Sunrise Banquets",
                    contact_name="Rohan Mehta",
                    city="Pune",
                    source="Referral",
                    customer_type_id=ctypes["HOTEL"].id,
                ),
                actor_id=actor_id,
            )
            crm.create_lead(
                LeadCreate(
                    company_name="Green Leaf Cafe",
                    contact_name="Anita Rao",
                    city="Mumbai",
                    source="Website",
                    customer_type_id=ctypes["CAFE"].id,
                ),
                actor_id=actor_id,
            )
            crm.create_opportunity(
                OpportunityCreate(
                    name="Sunrise Banquets — monthly consumables",
                    lead_id=lead1.id,
                    pipeline_stage_id=stages["QUALIFIED"].id,
                    estimated_value_minor=15000000,
                ),
                actor_id=actor_id,
            )
            crm.create_competitor(
                CompetitorCreate(name="BulkMart Distributors", strength="medium"),
                actor_id=actor_id,
            )

        existing_notes = db.scalar(select(func.count()).select_from(Notification)) or 0
        if existing_notes == 0:
            notes = NotificationService(db)
            notes.push(
                NotificationCreate(
                    title="Welcome to ApexOS",
                    body="Your command center is ready.",
                    level="info",
                ),
                actor_id=actor_id,
            )
            notes.push(
                NotificationCreate(
                    title="Low stock on some SKUs",
                    body="A few products are below reorder level.",
                    level="warning",
                ),
                actor_id=actor_id,
            )

        # --- master change history (last, so it catches every row) ---------
        # Every config master gets its `created` line (R2.10, G14, R3.1's audit column).
        # Most of these rows are written with `get_or_create` rather than through
        # `ConfigService`, so nothing logged them. This runs at the end because later
        # sections add masters too (the Phase B warehouse), and `record_creation` is
        # idempotent — it skips any row that already has activity of its own.
        for entity_type, model in (
            ("business_unit", BusinessUnit),
            ("brand", Brand),
            ("manufacturer", Manufacturer),
            ("procurement_model", ProcurementModel),
            ("uom", Uom),
            ("customer_type", CustomerType),
            ("supplier_type", SupplierType),
            ("warehouse", Warehouse),
            ("tax_rate", TaxRate),
            ("category", Category),
        ):
            label = MASTER_LABELS.get(entity_type, entity_type)
            for row in list(db.scalars(select(model).where(model.deleted_at.is_(None)))):
                record_creation(
                    db, activity,
                    entity_type=entity_type,
                    entity_id=row.id,
                    summary=f"{label} {row.name} ({row.code}) created",
                    actor_id=actor_id,
                )

        db.commit()

        # Reload the demo order for a clean data-shape return.
        summary = {"seeded": True}
        so = db.scalar(select(SalesOrder).order_by(SalesOrder.created_at.asc()))
        if so is not None:
            inv = db.scalar(select(Invoice).where(Invoice.sales_order_id == so.id))
            summary["sales_order"] = {
                "order_no": so.order_no,
                "status": so.status,
                "subtotal_minor": so.subtotal_minor,
                "tax_minor": so.tax_minor,
                "total_minor": so.total_minor,
            }
            if inv is not None:
                finance = InvoiceService(db)
                detail = finance.get(inv.id)
                summary["invoice"] = {
                    "invoice_no": inv.invoice_no,
                    "status": inv.status,
                    "total_minor": inv.total_minor,
                    "paid_minor": detail.paid_minor,
                    "balance_minor": detail.balance_minor,
                    "due_date": str(inv.due_date),
                }
        po = db.scalar(select(PurchaseOrder).order_by(PurchaseOrder.created_at.asc()))
        if po is not None:
            bill = db.scalar(select(Bill).where(Bill.purchase_order_id == po.id))
            summary["purchase_order"] = {
                "po_no": po.po_no,
                "status": po.status,
                "subtotal_minor": po.subtotal_minor,
                "tax_minor": po.tax_minor,
                "total_minor": po.total_minor,
            }
            if bill is not None:
                bill_detail = BillService(db).get(bill.id)
                summary["bill"] = {
                    "bill_no": bill.bill_no,
                    "status": bill.status,
                    "total_minor": bill.total_minor,
                    "paid_minor": bill_detail.paid_minor,
                    "balance_minor": bill_detail.balance_minor,
                    "due_date": str(bill.due_date),
                }
        if preorder_result is not None:
            summary["preorder"] = preorder_result
        summary["counts"] = {
            "products": db.scalar(select(func.count()).select_from(Product)) or 0,
            "customers": db.scalar(select(func.count()).select_from(Customer)) or 0,
            "suppliers": db.scalar(select(func.count()).select_from(Supplier)) or 0,
            "purchase_orders": db.scalar(select(func.count()).select_from(PurchaseOrder)) or 0,
            "requisitions": db.scalar(select(func.count()).select_from(PurchaseRequisition)) or 0,
            "rfqs": db.scalar(select(func.count()).select_from(Rfq)) or 0,
            "bills": db.scalar(select(func.count()).select_from(Bill)) or 0,
            "warehouses": db.scalar(select(func.count()).select_from(Warehouse)) or 0,
            "tasks": db.scalar(select(func.count()).select_from(Task)) or 0,
            "documents": db.scalar(select(func.count()).select_from(Document)) or 0,
            "leads": db.scalar(select(func.count()).select_from(Lead)) or 0,
            "opportunities": db.scalar(select(func.count()).select_from(Opportunity)) or 0,
            "notifications": db.scalar(select(func.count()).select_from(Notification)) or 0,
            "activities": db.scalar(select(func.count()).select_from(ActivityLog)) or 0,
        }
        return summary
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    import json

    result = run()
    print(json.dumps(result, indent=2, default=str))

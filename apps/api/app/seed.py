"""Idempotent seed of real Apex data + one completed spine sales order.

Run with:  python -m app.seed

Safe to re-run: every row is get-or-created by its natural key, prices/opening
stock are only written when a product is first created, and the demo sales order
+ payment are only generated once (when none exist yet).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
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
from app.modules.config.models import (  # noqa: E402
    Brand,
    BusinessUnit,
    Category,
    CustomerType,
    ProcurementModel,
    SupplierType,
    TaxRate,
    Uom,
    Warehouse,
)
from app.modules.customers.models import Customer, CustomerCreditPolicy  # noqa: E402
from app.modules.finance.models import Bill, Invoice  # noqa: E402
from app.modules.identity.models import User  # noqa: E402
from app.modules.inventory.service import InventoryService  # noqa: E402
from app.modules.pricing.models import PurchasePrice, SellingPrice  # noqa: E402
from app.modules.products.models import Product  # noqa: E402
from app.modules.sales.models import SalesOrder  # noqa: E402
from app.modules.sales.schemas import SalesOrderCreate, SalesOrderLineCreate  # noqa: E402
from app.modules.sales.service import SalesOrderService  # noqa: E402
from app.modules.finance.schemas import BillPaymentCreate, PaymentCreate  # noqa: E402
from app.modules.finance.service import BillService, InvoiceService  # noqa: E402
from app.modules.suppliers.models import Supplier  # noqa: E402
from app.modules.procurement.models import PurchaseOrder  # noqa: E402
from app.modules.procurement.schemas import (  # noqa: E402
    PurchaseOrderCreate,
    PurchaseOrderLineCreate,
)
from app.modules.procurement.service import (  # noqa: E402
    GoodsReceiptService,
    PurchaseOrderService,
)
from app.modules.inventory.schemas import StockTransferCreate  # noqa: E402
from app.modules.inventory.service import StockTransferService  # noqa: E402
from app.modules.tasks.models import Task  # noqa: E402
from app.modules.tasks.schemas import TaskCreate  # noqa: E402
from app.modules.tasks.service import TaskService  # noqa: E402
from app.modules.documents.models import Document  # noqa: E402
from app.modules.documents.service import DocumentService  # noqa: E402
from app.modules.crm.models import (  # noqa: E402
    Competitor,
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
from app.modules.notifications.models import Notification  # noqa: E402
from app.modules.notifications.schemas import NotificationCreate  # noqa: E402
from app.modules.notifications.service import NotificationService  # noqa: E402


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

DEMO_CUSTOMERS = [
    ("CUST-0001", "Blue Fig Restaurant", "RESTAURANT", "Pune", "Maharashtra", 30000000, 30),
    ("CUST-0002", "Grand Sarovar Hotel", "HOTEL", "Mumbai", "Maharashtra", 50000000, 30),
    ("CUST-0003", "CafeMocha", "CAFE", "Pune", "Maharashtra", 20000000, 30),
]

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
                defaults={"name": name, "rate_bps": bps, "created_by": actor_id},
            )
            tax_rates[code] = t
        gst18 = tax_rates["GST_18"]

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

        # --- products + prices + opening stock ---------------------------
        inventory = InventoryService(db)
        for sku, name, spec, uom_code, sell, buy, cat_code, brand_code in PRODUCTS:
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
                    "status": "active",
                    "business_unit_id": bu.id,
                    "created_by": actor_id,
                },
            )
            if created:
                now = datetime.now(timezone.utc)
                db.add(SellingPrice(product_id=product.id, price_minor=sell, valid_from=now, created_by=actor_id))
                db.add(PurchasePrice(product_id=product.id, price_minor=buy, valid_from=now, created_by=actor_id))
                db.flush()
                inventory.record_movement(
                    product_id=product.id,
                    warehouse_id=warehouse.id,
                    qty_delta=Decimal("100"),
                    reason="PURCHASE",
                    ref_type="opening",
                    unit_cost_minor=buy,
                    actor_id=actor_id,
                )

        # --- demo customers + credit policies ----------------------------
        customers = {}
        for code, name, ctype_code, city, state, limit_minor, terms in DEMO_CUSTOMERS:
            cust, created = get_or_create(
                db, Customer, code=code,
                defaults={
                    "name": name,
                    "customer_type_id": ctypes[ctype_code].id,
                    "city": city,
                    "state": state,
                    "status": "active",
                    "business_unit_id": bu.id,
                    "created_by": actor_id,
                },
            )
            customers[code] = cust
            if created:
                db.add(CustomerCreditPolicy(
                    customer_id=cust.id,
                    credit_limit_minor=limit_minor,
                    payment_terms_days=terms,
                    status="active",
                    created_by=actor_id,
                ))
                db.flush()

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
            now = datetime.now(timezone.utc)
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
        summary["counts"] = {
            "products": db.scalar(select(func.count()).select_from(Product)) or 0,
            "customers": db.scalar(select(func.count()).select_from(Customer)) or 0,
            "suppliers": db.scalar(select(func.count()).select_from(Supplier)) or 0,
            "purchase_orders": db.scalar(select(func.count()).select_from(PurchaseOrder)) or 0,
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

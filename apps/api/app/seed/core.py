"""`run()` — the seed orchestrator, plus the sections not yet extracted.

Sections still inline here predate the section-per-module split (Move 0, 2026-07-28).
**Do not add another one.** A new part writes `app/seed/<domain>.py` exposing
`def seed_<domain>(ctx: SeedContext)` and adds one call below, before the
master-change-history pass — which must stay last, because it backfills the
`created` line for every master any earlier section created.
"""
from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, engine
from app.db.metadata import Base
from app.modules.activity.models import ActivityLog
from app.modules.activity.service import ActivityService
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
from app.modules.config.schemas import TaxRateSlabCreate
from app.modules.config.service import MASTER_LABELS, TaxRateService
from app.modules.crm.models import (
    Lead,
    Opportunity,
    PipelineStage,
)
from app.modules.crm.schemas import (
    CompetitorCreate,
    LeadCreate,
    OpportunityCreate,
)
from app.modules.crm.service import CrmService
from app.modules.customers.models import Customer, CustomerCreditPolicy
from app.modules.customers.schemas import CustomerUpdate
from app.modules.customers.service import CustomerService
from app.modules.documents.models import Document
from app.modules.documents.service import DocumentService
from app.modules.finance.models import Bill, Invoice
from app.modules.finance.schemas import BillPaymentCreate, PaymentCreate
from app.modules.finance.service import BillService, InvoiceService
from app.modules.identity.models import User
from app.modules.inventory.schemas import StockTransferCreate
from app.modules.inventory.service import InventoryService, StockTransferService
from app.modules.notifications.models import Notification
from app.modules.notifications.schemas import NotificationCreate
from app.modules.notifications.service import NotificationService
from app.modules.pricing.models import PurchasePrice, SellingPrice
from app.modules.procurement.models import PurchaseOrder, PurchaseRequisition, Rfq
from app.modules.procurement.schemas import (
    PurchaseOrderCreate,
    PurchaseOrderLineCreate,
)
from app.modules.procurement.service import GoodsReceiptService, PurchaseOrderService
from app.modules.products.models import Product
from app.modules.sales.models import SalesOrder
from app.modules.sales.schemas import SalesOrderCreate, SalesOrderLineCreate
from app.modules.sales.service import SalesOrderService
from app.modules.suppliers.models import Supplier
from app.modules.tasks.models import Task
from app.modules.tasks.schemas import TaskCreate
from app.modules.tasks.service import TaskService
from app.seed.catalogue import (
    CATEGORIES,
    DEMO_CUSTOMERS,
    DEMO_SUPPLIERS,
    PRODUCTS,
    SUB_SUBCATEGORIES,
    SUBCATEGORIES,
    bulk_customers,
    bulk_products,
)
from app.seed.customers import seed_customer_depth
from app.seed.helpers import SeedContext, get_or_create, record_creation
from app.seed.inventory import seed_locations
from app.seed.preorder import seed_preorder
from app.seed.vendor import seed_vendor


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

        # --- Part 3's pre-order flow, extracted to app/seed/preorder.py (Move 0).
        #     New sections go in their own module too - see app/seed/__init__.py.
        preorder_result = seed_preorder(
            SeedContext(
                db=db, actor_id=actor_id, activity=activity, suppliers=suppliers
            )
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

        # --- Part 5's locations, putaway, reservation and aged purchases ----
        # MUST run before the transfer below: R7.5 dispatches into the destination's
        # `transit` bin and refuses if there isn't one, which is correct — you build the
        # warehouse before you move stock through it. It also needs the balances written
        # above, so this is the one point in run() where both hold.
        locations_result = seed_locations(
            SeedContext(db=db, actor_id=actor_id, activity=activity)
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

        # --- Part 4's vendor intelligence history, its own module (Move 0) --
        vendor_result = seed_vendor(
            SeedContext(
                db=db, actor_id=actor_id, activity=activity, suppliers=suppliers
            )
        )

        # --- Part 6's customer depth, its own module (G14) ------------------
        # After the sell loop, so the timeline has orders and payments to gather, and after
        # products have prices so the breaching order can be sized off a real total.
        customer_depth_result = seed_customer_depth(
            SeedContext(db=db, actor_id=actor_id, activity=activity)
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
        if vendor_result is not None:
            summary["vendor"] = vendor_result
        if locations_result is not None:
            summary["locations"] = locations_result
        if customer_depth_result is not None:
            summary["customer_depth"] = customer_depth_result
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

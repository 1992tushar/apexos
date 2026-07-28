"""Soft delete: the one mechanism, the entities wired to it, and the refusals.

Covers R1.1 (one mechanism), R1.2 (wired per entity), R1.3 (append-only tables
refuse with a readable reason), R1.6 (one activity_log row) and R1.7 (a deleted
row leaves the lists without breaking documents that reference it).
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select

from app.core.errors import ConflictError, NotFoundError
from app.db.soft_delete import PROTECTED_TABLES, soft_delete
from app.modules.activity.models import ActivityLog
from app.modules.config.service import CategoryService, ConfigService
from app.modules.crm.schemas import LeadCreate
from app.modules.crm.service import CrmService
from app.modules.customers.schemas import CustomerCreate
from app.modules.customers.service import CustomerService
from app.modules.products.schemas import ProductCreate
from app.modules.products.service import ProductService
from app.modules.suppliers.schemas import SupplierCreate
from app.modules.suppliers.service import SupplierService
from app.modules.tasks.schemas import TaskCreate
from app.modules.tasks.service import TaskService


def _a_customer_type(db) -> uuid.UUID:
    return ConfigService(db).customer_types()[0].id


def _a_supplier_type(db) -> uuid.UUID:
    return ConfigService(db).supplier_types()[0].id


def _activity_count(db, entity_id: uuid.UUID, verb: str = "deleted") -> int:
    return db.scalar(
        select(func.count())
        .select_from(ActivityLog)
        .where(ActivityLog.entity_id == entity_id, ActivityLog.verb == verb)
    ) or 0


# --- R1.2: every entity where deletion is valid has a working service verb ----

def test_delete_customer_removes_it_from_list_and_detail(db):
    svc = CustomerService(db)
    c = svc.create(
        CustomerCreate(name="Doomed Diner", customer_type_id=_a_customer_type(db)),
        actor_id=None,
    )
    svc.delete(c.id, actor_id=None)

    with pytest.raises(NotFoundError):
        svc.get(c.id)
    rows, _ = svc.list(search="Doomed Diner", page=1, page_size=50)
    assert rows == []


def test_delete_supplier(db):
    svc = SupplierService(db)
    s = svc.create(
        SupplierCreate(name="Doomed Supplies", supplier_type_id=_a_supplier_type(db)),
        actor_id=None,
    )
    svc.delete(s.id, actor_id=None)
    with pytest.raises(NotFoundError):
        svc.get(s.id)


def test_delete_product(db):
    cfg = ConfigService(db)
    svc = ProductService(db)
    p = svc.create(
        ProductCreate(
            name="Doomed Mop",
            category_id=cfg.categories()[0].id,
            brand_id=cfg.brands()[0].id,
            uom_id=cfg.uoms()[0].id,
        ),
        actor_id=None,
    )
    svc.delete(p.id, actor_id=None)
    with pytest.raises(NotFoundError):
        svc.get(p.id)


def test_delete_task_is_distinct_from_completing_it(db):
    svc = TaskService(db)
    t = svc.create(TaskCreate(title="Doomed task"), actor_id=None)
    svc.delete(t.id, actor_id=None)
    with pytest.raises(NotFoundError):
        svc.get(t.id)
    rows, _ = svc.list(status=None, entity_type=None, entity_id=None, page=1, page_size=200)
    assert t.id not in [row.id for row in rows]


def test_delete_lead(db):
    svc = CrmService(db)
    lead = svc.create_lead(LeadCreate(company_name="Doomed Leads Ltd"), actor_id=None)
    svc.delete_lead(lead.id, actor_id=None)
    rows, _ = svc.leads(status=None, page=1, page_size=200)
    assert lead.id not in [row.id for row in rows]


def test_delete_category(db):
    from app.modules.config.schemas import CategoryCreate

    svc = CategoryService(db)
    cat = svc.create(CategoryCreate(code="DMC1", name="Doomed Category"), actor_id=None)
    svc.delete(cat.id, actor_id=None)
    assert cat.id not in [c.id for c in ConfigService(db).categories()]


# --- R1.6: exactly one activity_log row per deletion --------------------------

def test_delete_writes_exactly_one_activity_row(db):
    svc = CustomerService(db)
    c = svc.create(
        CustomerCreate(name="Audited Co", customer_type_id=_a_customer_type(db)),
        actor_id=None,
    )
    assert _activity_count(db, c.id) == 0
    svc.delete(c.id, actor_id=None)
    assert _activity_count(db, c.id) == 1


def test_activity_row_names_the_entity_and_the_verb(db):
    svc = TaskService(db)
    t = svc.create(TaskCreate(title="Logged task"), actor_id=None)
    svc.delete(t.id, actor_id=None)
    row = db.scalar(
        select(ActivityLog).where(ActivityLog.entity_id == t.id, ActivityLog.verb == "deleted")
    )
    assert row is not None
    assert row.entity_type == "task"
    assert "Logged task" in row.summary


# --- R1.7: references survive -------------------------------------------------

def test_deleting_a_customer_leaves_its_invoice_renderable(client, db):
    """The seeded customer has an invoice. Delete the customer; the invoice page
    must still render, with the customer's name intact (R1.7)."""
    from app.modules.customers.models import Customer
    from app.modules.finance.models import Invoice
    from app.modules.finance.repository import FinanceRepository

    invoice = db.scalar(select(Invoice).where(Invoice.deleted_at.is_(None)))
    assert invoice is not None, "seed should have an invoice"
    customer_id = invoice.customer_id

    CustomerService(db).delete(customer_id, actor_id=None)
    db.commit()
    try:
        # The name still resolves off the now-hidden row, so documents render.
        assert FinanceRepository(db).customer_name(customer_id) is not None
        page = client.get(f"/invoices/{invoice.id}")
        assert page.status_code == 200
    finally:
        # Undo: the rest of the suite still expects the seeded customer to exist.
        db.get(Customer, customer_id).deleted_at = None
        db.commit()


# --- R1.3: append-only tables refuse, with a reason ---------------------------

@pytest.mark.parametrize(
    "table", ["invoice", "bill", "payment", "sales_order", "purchase_order", "stock_movement"]
)
def test_protected_tables_are_documented_with_a_reason(table):
    reason = PROTECTED_TABLES[table]
    assert len(reason) > 30, f"{table} needs a real explanation, not a stub"
    assert reason.rstrip().endswith("."), f"{table}'s reason should read as a sentence"


def test_soft_deleting_an_invoice_is_refused_with_a_readable_reason(db):
    from app.modules.finance.models import Invoice

    invoice = db.scalar(select(Invoice).where(Invoice.deleted_at.is_(None)))
    assert invoice is not None, "seed should have an invoice"
    with pytest.raises(ConflictError) as excinfo:
        soft_delete(db, invoice, actor_id=None)
    assert "credit note" in str(excinfo.value)
    assert invoice.deleted_at is None


def test_soft_deleting_a_stock_movement_is_refused(db):
    from app.modules.inventory.models import StockMovement

    movement = db.scalar(select(StockMovement))
    assert movement is not None, "seed should have stock movements"
    with pytest.raises(ConflictError) as excinfo:
        soft_delete(db, movement, actor_id=None)
    assert "append-only" in str(excinfo.value)


def test_soft_deleting_a_sales_order_is_refused(db):
    from app.modules.sales.models import SalesOrder

    order = db.scalar(select(SalesOrder).where(SalesOrder.deleted_at.is_(None)))
    assert order is not None, "seed should have a sales order"
    with pytest.raises(ConflictError):
        soft_delete(db, order, actor_id=None)


def test_refused_deletion_writes_no_activity_row(db):
    from app.modules.finance.models import Invoice

    invoice = db.scalar(select(Invoice).where(Invoice.deleted_at.is_(None)))
    before = _activity_count(db, invoice.id)
    with pytest.raises(ConflictError):
        soft_delete(db, invoice, actor_id=None)
    assert _activity_count(db, invoice.id) == before


# --- the mechanism's own guard rails -----------------------------------------

def test_deleting_twice_is_refused(db):
    svc = TaskService(db)
    t = svc.create(TaskCreate(title="Delete me once"), actor_id=None)
    svc.delete(t.id, actor_id=None)
    # The second attempt cannot even find it, so it is a not-found, not a re-delete.
    with pytest.raises(NotFoundError):
        svc.delete(t.id, actor_id=None)


def test_soft_delete_directly_refuses_an_already_deleted_row(db):
    from app.modules.tasks.models import Task

    svc = TaskService(db)
    t = svc.create(TaskCreate(title="Double tap"), actor_id=None)
    row = db.get(Task, t.id)
    soft_delete(db, row, actor_id=None)
    with pytest.raises(ConflictError, match="already deleted"):
        soft_delete(db, row, actor_id=None)


def test_category_with_children_is_refused(db):
    from app.modules.config.schemas import CategoryCreate

    svc = CategoryService(db)
    parent = svc.create(CategoryCreate(code="DMP2", name="Doomed Parent"), actor_id=None)
    svc.create(
        CategoryCreate(code="DMC2", name="Doomed Child", parent_category_id=parent.id),
        actor_id=None,
    )
    # Part 2 C3 moved this refusal onto the shared reference map, which also names the
    # blocking row — "which sub-category" is the actionable half (R3.7).
    with pytest.raises(ConflictError, match="sub-category") as raised:
        svc.delete(parent.id, actor_id=None)
    assert "Doomed Child" in str(raised.value)


def test_category_with_products_is_refused(db):
    from app.modules.config.schemas import CategoryCreate

    cfg = ConfigService(db)
    cat = CategoryService(db).create(
        CategoryCreate(code="DMP3", name="Doomed With Products"), actor_id=None
    )
    ProductService(db).create(
        ProductCreate(
            name="Blocker Mop",
            category_id=cat.id,
            brand_id=cfg.brands()[0].id,
            uom_id=cfg.uoms()[0].id,
        ),
        actor_id=None,
    )
    with pytest.raises(ConflictError, match="product"):
        CategoryService(db).delete(cat.id, actor_id=None)


def test_converted_lead_is_refused(db):
    from app.modules.crm.schemas import LeadConvert

    svc = CrmService(db)
    lead = svc.create_lead(
        LeadCreate(company_name="Converted Co", customer_type_id=_a_customer_type(db)),
        actor_id=None,
    )
    svc.convert_lead(lead.id, LeadConvert(), actor_id=None)
    with pytest.raises(ConflictError, match="converted"):
        svc.delete_lead(lead.id, actor_id=None)


def test_deleting_a_missing_row_raises_not_found(db):
    with pytest.raises(NotFoundError):
        CustomerService(db).delete(uuid.uuid4(), actor_id=None)

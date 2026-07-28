"""Part 5 C3 — cycle count, adjustment and the two-step transfer (R7.1–R7.6).

These build their own product and count sheet rather than asserting against the seed's,
so a later part adding stock cannot break them. The one thing asserted absolutely is what
the requirements state absolutely: a matching count writes NOTHING, and a varying line
writes EXACTLY ONE movement and ONE activity row.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.core.errors import ConflictError, ValidationError
from app.modules.activity.models import ActivityLog
from app.modules.inventory.models import StockMovement
from app.modules.inventory.schemas import (
    CountClose,
    CountEntry,
    CountOpen,
    CountRecord,
    StockAdjustmentCreate,
    TransferDispatch,
)
from app.modules.inventory.service import (
    CycleCountService,
    InventoryService,
    StockAdjustmentService,
    StockTransferService,
)


@pytest.fixture()
def warehouses(db):
    from app.modules.config.models import Warehouse

    rows = list(
        db.scalars(
            select(Warehouse).where(Warehouse.deleted_at.is_(None)).order_by(Warehouse.code)
        )
    )
    assert len(rows) >= 2, "the transfer tests need two warehouses"
    return rows


@pytest.fixture()
def stocked(db, warehouses):
    """A product with stock in the FIRST warehouse."""
    for row in InventoryService(db).stock():
        if row.warehouse_id == warehouses[0].id and row.qty_on_hand >= 20:
            return row
    pytest.fail("no product with enough stock in the first warehouse")


def _movements(db, product_id, reason: str) -> int:
    return db.scalar(
        select(func.count()).select_from(StockMovement).where(
            StockMovement.product_id == product_id,
            StockMovement.reason == reason,
            StockMovement.deleted_at.is_(None),
        )
    ) or 0


def _activity(db, entity_type: str) -> int:
    return db.scalar(
        select(func.count()).select_from(ActivityLog).where(
            ActivityLog.entity_type == entity_type
        )
    ) or 0


# --- R7.1 / R7.2 / R7.3: the count sheet -------------------------------------


def test_r7_1_a_count_sheet_snapshots_the_system_quantity(db, warehouses, stocked):
    sheet = CycleCountService(db).open(
        CountOpen(warehouse_id=warehouses[0].id, product_ids=[stocked.product_id]),
        actor_id=None,
    )

    assert sheet.status == "open"
    assert sheet.count_no.startswith("CNT-")
    assert len(sheet.lines) == 1
    line = sheet.lines[0]
    assert line.system_qty == stocked.qty_on_hand
    # Nothing counted yet, so no variance — and specifically not a variance of
    # minus-everything, which is what a naive `counted_qty = 0` default would mean.
    assert line.counted_qty is None
    assert line.variance is None
    assert not line.is_counted


def test_r7_2_a_count_with_no_variance_writes_no_adjustment_movement(db, warehouses, stocked):
    svc = CycleCountService(db)
    sheet = svc.open(
        CountOpen(warehouse_id=warehouses[0].id, product_ids=[stocked.product_id]),
        actor_id=None,
    )
    before = _movements(db, stocked.product_id, "COUNT")

    svc.record(
        sheet.id,
        CountRecord(entries=[
            CountEntry(product_id=stocked.product_id, counted_qty=stocked.qty_on_hand)
        ]),
        actor_id=None,
    )
    closed = svc.close(sheet.id, CountClose(reason="quarterly count"), actor_id=None)

    assert closed.status == "closed"
    assert closed.adjustments_posted == 0
    assert _movements(db, stocked.product_id, "COUNT") == before, (
        "a count that matched still wrote a movement"
    )


def test_r7_2_a_matching_count_is_a_normal_outcome_not_an_error(db, warehouses, stocked):
    """The one-line quick path used to raise ConflictError on a match, which made the
    desirable outcome of a stock count look like a failure."""
    from app.modules.inventory.schemas import StockCountCreate

    on_hand = InventoryService(db).on_hand(stocked.product_id, warehouses[0].id)
    result = StockAdjustmentService(db).count(
        StockCountCreate(
            product_id=stocked.product_id,
            warehouse_id=warehouses[0].id,
            counted_qty=on_hand,
        ),
        actor_id=None,
    )
    assert result.qty_delta == Decimal(0)
    assert result.on_hand == on_hand


def test_r7_3_a_variance_writes_exactly_one_movement_and_one_activity_row(
    db, warehouses, stocked
):
    svc = CycleCountService(db)
    sheet = svc.open(
        CountOpen(warehouse_id=warehouses[0].id, product_ids=[stocked.product_id]),
        actor_id=None,
    )
    movements_before = _movements(db, stocked.product_id, "COUNT")
    activity_before = _activity(db, "stock_count")

    short_by = stocked.qty_on_hand - Decimal("3")
    svc.record(
        sheet.id,
        CountRecord(entries=[
            CountEntry(product_id=stocked.product_id, counted_qty=short_by)
        ]),
        actor_id=None,
    )
    closed = svc.close(sheet.id, CountClose(reason="found 3 fewer on the shelf"), actor_id=None)

    assert closed.adjustments_posted == 1
    assert _movements(db, stocked.product_id, "COUNT") == movements_before + 1
    # `open` wrote one row and `close` wrote one — closing is ONE decision however many
    # lines varied (G5).
    assert _activity(db, "stock_count") == activity_before + 1
    assert InventoryService(db).on_hand(stocked.product_id, warehouses[0].id) == short_by


def test_r7_1_an_uncounted_line_is_left_alone_on_close(db, warehouses, stocked):
    """The failure this prevents: treating "not counted" as "counted zero" and wiping
    the stock of every line the founder did not get to."""
    svc = CycleCountService(db)
    sheet = svc.open(CountOpen(warehouse_id=warehouses[0].id, limit=4), actor_id=None)
    assert len(sheet.lines) >= 2

    target, untouched = sheet.lines[0], sheet.lines[1]
    before = InventoryService(db).on_hand(untouched.product_id, warehouses[0].id)

    svc.record(
        sheet.id,
        CountRecord(entries=[
            CountEntry(product_id=target.product_id, counted_qty=target.system_qty + 1)
        ]),
        actor_id=None,
    )
    closed = svc.close(sheet.id, CountClose(reason="spot check"), actor_id=None)

    assert closed.adjustments_posted == 1
    assert InventoryService(db).on_hand(untouched.product_id, warehouses[0].id) == before


def test_r7_1_closing_a_sheet_nobody_counted_is_refused(db, warehouses):
    svc = CycleCountService(db)
    sheet = svc.open(CountOpen(warehouse_id=warehouses[0].id, limit=2), actor_id=None)

    with pytest.raises(ValidationError, match="has been counted"):
        svc.close(sheet.id, CountClose(reason="nothing counted"), actor_id=None)


def test_r7_1_a_closed_sheet_cannot_be_closed_again(db, warehouses, stocked):
    svc = CycleCountService(db)
    sheet = svc.open(
        CountOpen(warehouse_id=warehouses[0].id, product_ids=[stocked.product_id]),
        actor_id=None,
    )
    svc.record(
        sheet.id,
        CountRecord(entries=[
            CountEntry(product_id=stocked.product_id, counted_qty=stocked.qty_on_hand)
        ]),
        actor_id=None,
    )
    svc.close(sheet.id, CountClose(reason="first close"), actor_id=None)

    with pytest.raises(ConflictError, match="already closed"):
        svc.close(sheet.id, CountClose(reason="second close"), actor_id=None)


def test_r7_1_a_product_not_on_the_sheet_is_refused(db, warehouses, stocked):
    svc = CycleCountService(db)
    sheet = svc.open(
        CountOpen(warehouse_id=warehouses[0].id, product_ids=[stocked.product_id]),
        actor_id=None,
    )
    with pytest.raises(ValidationError, match="is not on count sheet"):
        svc.record(
            sheet.id,
            CountRecord(entries=[CountEntry(product_id=uuid.uuid4(), counted_qty=Decimal(1))]),
            actor_id=None,
        )


# --- R7.4: a reason is mandatory ---------------------------------------------


def test_r7_4_an_adjustment_without_a_reason_is_refused(db, warehouses, stocked):
    """The schema requires a non-empty string; the service also refuses whitespace,
    because `"   "` passes a length check and tells a later reader nothing."""
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        StockAdjustmentCreate(
            product_id=stocked.product_id,
            warehouse_id=warehouses[0].id,
            qty_delta=Decimal("1"),
            note="",
        )

    whitespace = StockAdjustmentCreate(
        product_id=stocked.product_id,
        warehouse_id=warehouses[0].id,
        qty_delta=Decimal("1"),
        note="   ",
    )
    with pytest.raises(ValidationError, match="needs a reason"):
        StockAdjustmentService(db).adjust(whitespace, actor_id=None)


def test_r7_4_an_adjustment_with_a_reason_posts_and_records_it(db, warehouses, stocked):
    before = InventoryService(db).on_hand(stocked.product_id, warehouses[0].id)
    result = StockAdjustmentService(db).adjust(
        StockAdjustmentCreate(
            product_id=stocked.product_id,
            warehouse_id=warehouses[0].id,
            qty_delta=Decimal("2"),
            note="found two behind the rack",
        ),
        actor_id=None,
    )
    assert result.on_hand == before + Decimal("2")


def test_r7_4_closing_a_count_without_a_reason_is_refused(db, warehouses, stocked):
    svc = CycleCountService(db)
    sheet = svc.open(
        CountOpen(warehouse_id=warehouses[0].id, product_ids=[stocked.product_id]),
        actor_id=None,
    )
    svc.record(
        sheet.id,
        CountRecord(entries=[
            CountEntry(product_id=stocked.product_id, counted_qty=Decimal("1"))
        ]),
        actor_id=None,
    )
    with pytest.raises(ValidationError, match="needs a reason"):
        svc.close(sheet.id, CountClose(reason="   "), actor_id=None)


# --- R7.5: the two-step transfer ---------------------------------------------


def test_r7_5_dispatch_puts_stock_in_transit_without_losing_it(db, warehouses, stocked):
    inventory = InventoryService(db)
    src, dst = warehouses[0], warehouses[1]
    total_before = inventory.on_hand(stocked.product_id)
    src_before = inventory.on_hand(stocked.product_id, src.id)

    transfer = StockTransferService(db).dispatch(
        TransferDispatch(
            product_id=stocked.product_id,
            from_warehouse_id=src.id,
            to_warehouse_id=dst.id,
            qty=Decimal("5"),
        ),
        actor_id=None,
    )

    assert transfer.status == "in_transit"
    assert transfer.transfer_no.startswith("TRF-")
    # Off the source's shelf...
    assert inventory.on_hand(stocked.product_id, src.id) == src_before - Decimal("5")
    # ...but NOT gone: the business still holds every unit. This is the assertion R7.5
    # exists for — stock must never be invisible mid-flight.
    assert inventory.on_hand(stocked.product_id) == total_before
    # And it is reported as in transit, derived from the bin's kind.
    state = next(
        s for s in inventory.states(dst.id) if s.product_id == stocked.product_id
    )
    assert state.in_transit >= Decimal("5")
    # In transit is on hand but NOT available to promise.
    assert state.available == state.on_hand - state.in_transit - state.quarantined - state.reserved


def test_r7_5_receive_lands_the_stock_and_clears_in_transit(db, warehouses, stocked):
    inventory = InventoryService(db)
    svc = StockTransferService(db)
    src, dst = warehouses[0], warehouses[1]

    dst_before = inventory.on_hand(stocked.product_id, dst.id)
    transfer = svc.dispatch(
        TransferDispatch(
            product_id=stocked.product_id,
            from_warehouse_id=src.id,
            to_warehouse_id=dst.id,
            qty=Decimal("5"),
        ),
        actor_id=None,
    )
    in_transit_after_dispatch = next(
        s for s in inventory.states(dst.id) if s.product_id == stocked.product_id
    ).in_transit

    received = svc.receive(transfer.id, actor_id=None)

    assert received.status == "received"
    assert received.received_at is not None
    assert inventory.on_hand(stocked.product_id, dst.id) == dst_before + Decimal("5")
    after = next(s for s in inventory.states(dst.id) if s.product_id == stocked.product_id)
    assert after.in_transit == in_transit_after_dispatch - Decimal("5")


def test_r7_5_a_dispatched_transfer_is_listed_as_outstanding(db, warehouses, stocked):
    svc = StockTransferService(db)
    transfer = svc.dispatch(
        TransferDispatch(
            product_id=stocked.product_id,
            from_warehouse_id=warehouses[0].id,
            to_warehouse_id=warehouses[1].id,
            qty=Decimal("2"),
        ),
        actor_id=None,
    )
    assert transfer.id in {t.id for t in svc.in_transit()}

    svc.receive(transfer.id, actor_id=None)
    assert transfer.id not in {t.id for t in svc.in_transit()}


def test_r7_5_a_transfer_cannot_be_received_twice(db, warehouses, stocked):
    svc = StockTransferService(db)
    transfer = svc.dispatch(
        TransferDispatch(
            product_id=stocked.product_id,
            from_warehouse_id=warehouses[0].id,
            to_warehouse_id=warehouses[1].id,
            qty=Decimal("2"),
        ),
        actor_id=None,
    )
    svc.receive(transfer.id, actor_id=None)
    with pytest.raises(ConflictError, match="already received"):
        svc.receive(transfer.id, actor_id=None)


def test_r7_5_transferring_more_than_is_on_hand_is_refused(db, warehouses, stocked):
    with pytest.raises(ValidationError, match="exceeds on-hand"):
        StockTransferService(db).dispatch(
            TransferDispatch(
                product_id=stocked.product_id,
                from_warehouse_id=warehouses[0].id,
                to_warehouse_id=warehouses[1].id,
                qty=Decimal("999999"),
            ),
            actor_id=None,
        )


def test_r7_5_the_one_call_transfer_is_still_dispatch_then_receive(db, warehouses, stocked):
    """`transfer` is kept for callers that do not model the in-flight state. It must be
    the two steps back to back, not a second implementation of the arithmetic."""
    from app.modules.inventory.schemas import StockTransferCreate

    inventory = InventoryService(db)
    src, dst = warehouses[0], warehouses[1]
    total_before = inventory.on_hand(stocked.product_id)
    dst_before = inventory.on_hand(stocked.product_id, dst.id)

    result = StockTransferService(db).transfer(
        StockTransferCreate(
            product_id=stocked.product_id,
            from_warehouse_id=src.id,
            to_warehouse_id=dst.id,
            qty=Decimal("4"),
        ),
        actor_id=None,
    )

    assert result.to_on_hand == dst_before + Decimal("4")
    assert inventory.on_hand(stocked.product_id) == total_before
    # Nothing left in transit — it dispatched AND received.
    assert not [
        t for t in StockTransferService(db).in_transit()
        if t.product_id == stocked.product_id and t.qty == Decimal("4")
    ]


def test_r7_5_dispatch_refuses_when_the_destination_has_no_transit_bin(db, warehouses, stocked):
    """Silently posting unaddressed stock would make the in-transit state unreportable,
    which is the one thing R7.5 exists to prevent. The refusal names the fix."""
    from app.modules.config.models import Warehouse

    bare = Warehouse(code=f"BARE{uuid.uuid4().hex[:4].upper()}", name="No Racks Depot")
    db.add(bare)
    db.flush()

    with pytest.raises(ValidationError, match="no transit bin"):
        StockTransferService(db).dispatch(
            TransferDispatch(
                product_id=stocked.product_id,
                from_warehouse_id=warehouses[0].id,
                to_warehouse_id=bare.id,
                qty=Decimal("1"),
            ),
            actor_id=None,
        )


# --- R7.6 / R3.7: the invariants ---------------------------------------------


def test_r7_6_every_operation_writes_through_record_movement(db):
    """G8 by source walk, extended to C3's new services: a count or a transfer that
    inlined `StockMovement(...)` would bypass every rule `record_movement` enforces."""
    from pathlib import Path

    app_dir = Path(__file__).resolve().parents[1] / "app"
    allowed = {
        Path("modules/inventory/service.py"),
        Path("modules/inventory/models.py"),
        Path("modules/inventory/repository.py"),
    }
    offenders = [
        str(p.relative_to(app_dir))
        for p in app_dir.rglob("*.py")
        if p.relative_to(app_dir) not in allowed
        and "StockMovement(" in p.read_text(encoding="utf-8")
    ]
    assert not offenders, f"these bypass G8: {offenders}"


def test_r7_14_the_seed_holds_an_in_transit_transfer_and_both_kinds_of_count(db):
    """R7.14. The clean count matters as much as the varying one: without it, R7.2's
    "no adjustment" path is a code branch with no demo data behind it."""
    transfers = StockTransferService(db).in_transit()
    assert transfers, "the seed holds no transfer awaiting receipt"

    sheets = CycleCountService(db).sheets()
    closed = [s for s in sheets if s.status == "closed"]
    assert len(closed) >= 2, "the seed needs a variance count AND a clean one"

    svc = CycleCountService(db)
    details = [svc.detail(s.id) for s in closed]
    assert any(d.variance_lines for d in details), "no seeded count found a variance"
    assert any(not d.variance_lines for d in details), "no seeded count matched exactly"


def test_r7_1_the_count_flow_walks_end_to_end_through_the_screens(client, db, warehouses):
    """R7.1's acceptance is "walk the flow", so this walks it over HTTP."""
    opened = client.post(
        "/warehouse/counts",
        data={"warehouse_id": str(warehouses[0].id), "limit": "3"},
        follow_redirects=False,
    )
    assert opened.status_code == 303
    location = opened.headers["location"]
    assert "/warehouse/counts/" in location

    count_id = location.split("/warehouse/counts/")[1].split("?")[0]
    sheet_html = client.get(f"/warehouse/counts/{count_id}").text
    assert "System" in sheet_html and "Counted" in sheet_html
    assert "uncounted" in sheet_html
    # The sheet must say what a blank line means, or the founder cannot know that leaving
    # one alone is safe.
    assert "not a count of" in sheet_html

    detail = CycleCountService(db).detail(uuid.UUID(count_id))
    first = detail.lines[0]
    recorded = client.post(
        f"/warehouse/counts/{count_id}/record",
        data={
            "product_id": str(first.product_id),
            "counted_qty": str(first.system_qty - Decimal("1")),
        },
        follow_redirects=False,
    )
    assert recorded.status_code == 303

    closed = client.post(
        f"/warehouse/counts/{count_id}/close",
        data={"reason": "walked the flow"},
        follow_redirects=False,
    )
    assert closed.status_code == 303
    after = CycleCountService(db).detail(uuid.UUID(count_id))
    assert after.status == "closed"


def test_r7_4_the_adjustment_form_requires_a_reason(client):
    html = client.get("/warehouse").text
    # The field exists and is required, or R7.4 is enforced only in the service and the
    # screen lets the founder submit something that will always be refused.
    assert 'name="note" required' in html
    assert "an adjustment nobody can explain later" in html


def test_r7_5_the_warehouse_page_lists_in_transit_stock_with_a_receive_action(client, db):
    html = client.get("/warehouse").text

    assert "In transit" in html
    transfers = StockTransferService(db).in_transit()
    assert transfers, "nothing in transit to render"
    assert transfers[0].transfer_no in html
    assert f"/inventory/transfers/{transfers[0].id}/receive" in html
    # And the dispatch form for step one.
    assert 'action="/inventory/transfers/dispatch"' in html


def test_r7_5_receiving_through_the_screen_clears_it_from_the_list(client, db):
    svc = StockTransferService(db)
    transfer = svc.in_transit()[0]

    received = client.post(
        f"/inventory/transfers/{transfer.id}/receive", follow_redirects=False
    )
    assert received.status_code == 303
    assert transfer.transfer_no not in client.get("/warehouse").text


def test_r3_7_the_new_operations_models_declare_their_blocking_references(db, warehouses, stocked):
    from app.db.references import REFERENCES, blocking_references
    from app.modules.inventory.models import StockCount

    for table in ("stock_count", "stock_count_line", "stock_transfer"):
        assert table in REFERENCES, f"{table} owes references.py an entry (R3.7)"

    # Exercised, not merely present: a Reference names its column by STRING, so a wrong
    # one raises AttributeError at check time rather than import time.
    sheet = CycleCountService(db).open(
        CountOpen(warehouse_id=warehouses[0].id, product_ids=[stocked.product_id]),
        actor_id=None,
    )
    row = db.get(StockCount, sheet.id)
    assert any("counted line" in phrase for phrase in blocking_references(db, row)), (
        "an open count sheet should be blocked by its own lines"
    )

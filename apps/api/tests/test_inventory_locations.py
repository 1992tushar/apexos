"""Part 5 C1 — locations, stock states and the reservation ledger (R6.1–R6.6, R6.11, R6.15).

Every test here asserts a *delta* against whatever the seed happens to hold rather than an
absolute quantity: the seed moves between parts, and a hard-coded on-hand is the gotcha that
already cost Part 4 a test. The one place an absolute is asserted is where the requirement is
itself absolute — "no boolean reserved column exists".
"""
from __future__ import annotations

import uuid
from decimal import Decimal
from pathlib import Path

import pytest

from app.db.references import REFERENCES, blocking_references
from app.modules.inventory.models import StockMovement, StorageBin, StorageRack
from app.modules.inventory.schemas import BinCreate, RackCreate, ReservationCreate
from app.modules.inventory.service import (
    InventoryService,
    LocationService,
    ReservationService,
)

APP_DIR = Path(__file__).resolve().parents[1] / "app"


@pytest.fixture()
def warehouse(db):
    from sqlalchemy import select

    from app.modules.config.models import Warehouse

    return db.scalar(select(Warehouse).where(Warehouse.deleted_at.is_(None)))


@pytest.fixture()
def stocked(db, warehouse):
    """A (product_id, warehouse_id) pair the seed left with stock on hand.

    Reservation needs something to reserve, so a product with a zero balance would make
    every availability assertion vacuous.
    """
    for row in InventoryService(db).stock():
        if row.warehouse_id == warehouse.id and row.qty_on_hand > 0:
            return row
    pytest.fail("seed has no product with positive on-hand — the fixtures need revisiting")


def _rack_and_bin(db, warehouse, *, suffix: str, kind: str = "stock"):
    svc = LocationService(db)
    rack = svc.create_rack(
        RackCreate(warehouse_id=warehouse.id, code=f"R-{suffix}", name=f"Rack {suffix}"),
        actor_id=None,
    )
    row = svc.create_bin(
        BinCreate(storage_rack_id=rack.id, code=f"B-{suffix}", kind=kind), actor_id=None
    )
    return rack, row


# --- R6.1 / R6.2 / R6.3: the location tree and what carries it ---------------


def test_r6_1_locations_nest_warehouse_then_rack_then_bin(db, warehouse):
    rack, bin_row = _rack_and_bin(db, warehouse, suffix="A1")

    assert rack.warehouse_id == warehouse.id
    assert bin_row.storage_rack_id == rack.id
    assert bin_row.kind == "stock"
    # The tree is navigable from the warehouse down, which is what the screen renders.
    svc = LocationService(db)
    assert rack.id in {r.id for r in svc.racks(warehouse.id)}
    assert bin_row.id in {b.id for b in svc.bins(rack.id)}


def test_r6_1_a_rack_code_is_unique_within_its_warehouse(db, warehouse):
    from app.core.errors import ConflictError

    _rack_and_bin(db, warehouse, suffix="A2")
    with pytest.raises(ConflictError, match="already exists"):
        LocationService(db).create_rack(
            RackCreate(warehouse_id=warehouse.id, code="R-A2"), actor_id=None
        )


def test_r6_1_a_bin_kind_outside_the_known_set_is_refused(db, warehouse):
    from app.core.errors import ValidationError

    rack, _ = _rack_and_bin(db, warehouse, suffix="A3")
    with pytest.raises(ValidationError, match="Unknown bin kind"):
        LocationService(db).create_bin(
            BinCreate(storage_rack_id=rack.id, code="B-X", kind="freezer"), actor_id=None
        )


def test_r6_2_stock_movement_carries_the_location(db, warehouse, stocked):
    _rack, bin_row = _rack_and_bin(db, warehouse, suffix="A4")

    movement = InventoryService(db).record_movement(
        product_id=stocked.product_id,
        warehouse_id=warehouse.id,
        bin_id=bin_row.id,
        qty_delta=Decimal("5"),
        reason="ADJUSTMENT",
    )

    assert movement.bin_id == bin_row.id
    # And it reads back addressed to that bin, not merely stored against it.
    addressed = [
        r
        for r in InventoryService(db).bin_stock(warehouse.id)
        if r.bin_id == bin_row.id and r.product_id == stocked.product_id
    ]
    assert len(addressed) == 1
    assert addressed[0].qty_on_hand == Decimal("5")
    assert addressed[0].location.endswith("B-A4")


def test_r6_3_bin_id_is_nullable_so_existing_movements_keep_working(db):
    """The recorded decision: nullable, not backfilled.

    Backfilling would UPDATE an append-only ledger (G4) and invent a bin that was never
    recorded. This test pins the decision so a later part cannot quietly reverse it.
    """
    assert StockMovement.__table__.c.bin_id.nullable is True


def test_r6_3_a_movement_with_no_bin_is_still_counted_and_labelled(db, warehouse, stocked):
    svc = InventoryService(db)
    before = svc.on_hand(stocked.product_id, warehouse.id)

    svc.record_movement(
        product_id=stocked.product_id,
        warehouse_id=warehouse.id,
        qty_delta=Decimal("3"),
        reason="ADJUSTMENT",
    )

    # It counts towards on-hand...
    assert svc.on_hand(stocked.product_id, warehouse.id) == before + Decimal("3")
    # ...and the location view states that no bin was recorded rather than dropping it.
    unaddressed = [
        r
        for r in svc.bin_stock(warehouse.id)
        if r.product_id == stocked.product_id and r.bin_id is None
    ]
    assert unaddressed, "unaddressed stock vanished from the location view"
    assert unaddressed[0].location == "no bin recorded"


# --- R6.4: the four states, all derived --------------------------------------


def test_r6_4_the_four_states_are_reported_distinctly(db, warehouse, stocked):
    svc = InventoryService(db)
    _rack, transit_bin = _rack_and_bin(db, warehouse, suffix="T1", kind="transit")
    _rack2, damaged_bin = _rack_and_bin(db, warehouse, suffix="Q1", kind="quarantine")

    svc.record_movement(
        product_id=stocked.product_id, warehouse_id=warehouse.id, bin_id=transit_bin.id,
        qty_delta=Decimal("7"), reason="TRANSFER",
    )
    svc.record_movement(
        product_id=stocked.product_id, warehouse_id=warehouse.id, bin_id=damaged_bin.id,
        qty_delta=Decimal("2"), reason="ADJUSTMENT",
    )
    reserved_before = svc.reserved(stocked.product_id, warehouse.id)
    ReservationService(db).reserve(
        ReservationCreate(
            product_id=stocked.product_id, warehouse_id=warehouse.id, qty=Decimal("4")
        ),
        actor_id=None,
    )

    row = next(
        r
        for r in svc.states(warehouse.id)
        if r.product_id == stocked.product_id and r.warehouse_id == warehouse.id
    )

    assert row.in_transit == Decimal("7")
    assert row.quarantined == Decimal("2")
    assert row.reserved == reserved_before + Decimal("4")
    # Available excludes transit and quarantine stock, and the reservation.
    assert row.available == row.on_hand - row.in_transit - row.quarantined - row.reserved


def test_r6_4_no_state_is_stored_as_a_column(db):
    """R6.4's states are derived (G7) — none of them is a stored quantity."""
    for table in ("stock_movement", "stock_reservation", "storage_bin", "storage_rack"):
        columns = {c.name for c in StockMovement.metadata.tables[table].columns}
        assert not columns & {
            "available", "reserved_qty", "in_transit", "quarantined", "qty_on_hand",
        }, f"{table} stores a state that must be derived"


# --- R6.5 / R6.6: reservation as a ledger ------------------------------------


def test_r6_5_no_boolean_reserved_column_exists_anywhere(db):
    """The acceptance for R6.5 is literally the absence of a flag.

    Walks every mapped table rather than the ones this part happened to add, so a later
    part that reaches for the easy `reserved = True` fails here.
    """
    offenders = []
    for name, table in StockMovement.metadata.tables.items():
        for column in table.columns:
            looks_boolean = str(column.type).upper().startswith("BOOLEAN")
            if looks_boolean and "reserv" in column.name.lower():
                offenders.append(f"{name}.{column.name}")
    assert not offenders, f"reservation must be a ledger, not a flag: {offenders}"
    assert len(StockMovement.metadata.tables) > 20, "the table walk found almost nothing"


def test_r6_5_reservation_reduces_available_without_reducing_on_hand(db, warehouse, stocked):
    svc = InventoryService(db)
    on_hand_before = svc.on_hand(stocked.product_id, warehouse.id)
    available_before = svc.available(stocked.product_id, warehouse.id)
    reserved_before = svc.reserved(stocked.product_id, warehouse.id)

    result = ReservationService(db).reserve(
        ReservationCreate(
            product_id=stocked.product_id, warehouse_id=warehouse.id, qty=Decimal("6")
        ),
        actor_id=None,
    )

    assert result.on_hand == on_hand_before, "reserving moved stock — it must not"
    assert result.available == available_before - Decimal("6")
    assert result.reserved == reserved_before + Decimal("6")


def test_r6_5_release_restores_available(db, warehouse, stocked):
    svc = ReservationService(db)
    payload = ReservationCreate(
        product_id=stocked.product_id, warehouse_id=warehouse.id, qty=Decimal("6")
    )
    available_before = InventoryService(db).available(stocked.product_id, warehouse.id)
    reserved_before = InventoryService(db).reserved(stocked.product_id, warehouse.id)

    reserved = svc.reserve(payload, actor_id=None)
    # Assert the dip as well as the recovery: comparing only before-and-after would pass
    # even if `available` ignored reservations entirely, since both ends would be wrong.
    assert reserved.available == available_before - Decimal("6")

    released = svc.release(payload, actor_id=None)
    assert released.reserved == reserved_before
    assert released.available == available_before


def test_r6_5_consume_retires_the_reservation_without_moving_stock(db, warehouse, stocked):
    svc = ReservationService(db)
    payload = ReservationCreate(
        product_id=stocked.product_id, warehouse_id=warehouse.id, qty=Decimal("5")
    )
    on_hand_before = InventoryService(db).on_hand(stocked.product_id, warehouse.id)
    reserved_before = InventoryService(db).reserved(stocked.product_id, warehouse.id)

    svc.reserve(payload, actor_id=None)
    consumed = svc.consume(payload, actor_id=None)

    assert consumed.reserved == reserved_before
    # Consuming records that the commitment is over; the outbound movement is the
    # caller's job and remains the only thing that changes on-hand (G8).
    assert consumed.on_hand == on_hand_before


def test_r6_5_the_ledger_is_append_only_not_edited(db, warehouse, stocked):
    svc = ReservationService(db)
    payload = ReservationCreate(
        product_id=stocked.product_id, warehouse_id=warehouse.id, qty=Decimal("4")
    )
    svc.reserve(payload, actor_id=None)
    svc.release(payload, actor_id=None)

    entries = [
        e for e in svc.entries(stocked.product_id) if e.warehouse_id == warehouse.id
    ][:2]
    reasons = {e.reason for e in entries}
    assert reasons == {"RESERVE", "RELEASE"}, "release must append, not edit"
    assert sum(e.qty_delta for e in entries) == Decimal("0")


def test_r6_5_reserving_more_than_available_is_refused_with_the_numbers(db, warehouse, stocked):
    from app.core.errors import ConflictError

    available = InventoryService(db).available(stocked.product_id, warehouse.id)
    with pytest.raises(ConflictError) as excinfo:
        ReservationService(db).reserve(
            ReservationCreate(
                product_id=stocked.product_id,
                warehouse_id=warehouse.id,
                qty=available + Decimal("1"),
            ),
            actor_id=None,
        )
    message = str(excinfo.value)
    # A refusal the founder can act on states the numbers, not just "no".
    assert "available" in message and "on hand" in message and "already reserved" in message


def test_r6_5_releasing_more_than_is_reserved_is_refused(db, warehouse, stocked):
    from app.core.errors import ConflictError

    with pytest.raises(ConflictError, match="only .* is reserved"):
        ReservationService(db).release(
            ReservationCreate(
                product_id=stocked.product_id, warehouse_id=warehouse.id, qty=Decimal("9999")
            ),
            actor_id=None,
        )


def test_r6_6_each_reservation_verb_writes_exactly_one_activity_row(db, warehouse, stocked):
    from sqlalchemy import func, select

    from app.modules.activity.models import ActivityLog

    def rows() -> int:
        return db.scalar(
            select(func.count()).select_from(ActivityLog).where(
                ActivityLog.entity_type == "stock_reservation"
            )
        ) or 0

    svc = ReservationService(db)
    payload = ReservationCreate(
        product_id=stocked.product_id, warehouse_id=warehouse.id, qty=Decimal("3")
    )

    before = rows()
    svc.reserve(payload, actor_id=None)
    assert rows() == before + 1, "reserve must write exactly one activity row (G5)"
    svc.consume(payload, actor_id=None)
    assert rows() == before + 2, "consume must write exactly one activity row (G5)"


def test_r6_6_the_reservation_verb_is_callable_as_part_7_will_call_it(db, warehouse, stocked):
    """R6.6 exists so R9.8 has one verb to call. This pins its shape.

    Part 7 confirms a sales order and reserves against it, so the entry must be able to
    carry what it was reserved *for* and read back as a linked record.
    """
    order_id = uuid.uuid4()
    reserved_before = InventoryService(db).reserved(stocked.product_id, warehouse.id)
    result = ReservationService(db).reserve(
        ReservationCreate(
            product_id=stocked.product_id,
            warehouse_id=warehouse.id,
            qty=Decimal("2"),
            ref_type="sales_order",
            ref_id=order_id,
            note="confirmed SO",
        ),
        actor_id=None,
    )
    assert result.reserved == reserved_before + Decimal("2")
    entry = ReservationService(db).entries(stocked.product_id)[0]
    assert entry.ref_type == "sales_order"
    assert entry.ref_id == order_id


# --- R6.11: the rollup -------------------------------------------------------


def test_r6_11_bin_totals_roll_up_to_rack_and_warehouse(db, warehouse, stocked):
    svc = InventoryService(db)
    rack, bin_a = _rack_and_bin(db, warehouse, suffix="U1")
    bin_b = LocationService(db).create_bin(
        BinCreate(storage_rack_id=rack.id, code="B-U2"), actor_id=None
    )

    svc.record_movement(
        product_id=stocked.product_id, warehouse_id=warehouse.id, bin_id=bin_a.id,
        qty_delta=Decimal("11"), reason="ADJUSTMENT",
    )
    svc.record_movement(
        product_id=stocked.product_id, warehouse_id=warehouse.id, bin_id=bin_b.id,
        qty_delta=Decimal("4"), reason="ADJUSTMENT",
    )

    tree = next(r for r in svc.location_rollup(warehouse.id) if r.id == warehouse.id)
    rack_row = next(r for r in tree.children if r.id == rack.id)
    bins = {b.code: b.qty_on_hand for b in rack_row.children}

    assert bins["B-U1"] == Decimal("11")
    assert bins["B-U2"] == Decimal("4")
    # Each level is the sum of the one below it, by construction.
    assert rack_row.qty_on_hand == Decimal("15")
    assert tree.qty_on_hand == sum(r.qty_on_hand for r in tree.children)
    # And the warehouse total agrees with the flat balance view — the two must not drift.
    flat = sum(
        r.qty_on_hand for r in svc.bin_stock(warehouse.id)
    )
    assert tree.qty_on_hand == flat


# --- R6.15 / R3.7: the invariants this part must not break -------------------


def test_r6_15_record_movement_is_still_the_only_writer_of_stock_movement(db):
    """G8 by source walk: nothing outside the inventory module constructs a movement.

    A service that inlines `StockMovement(...)` bypasses every rule `record_movement`
    enforces, and that is invisible to a behavioural test.
    """
    allowed = {
        Path("modules/inventory/service.py"),
        Path("modules/inventory/models.py"),
        Path("modules/inventory/repository.py"),
    }
    offenders = []
    checked = 0
    for path in APP_DIR.rglob("*.py"):
        checked += 1
        relative = path.relative_to(APP_DIR)
        if relative in allowed:
            continue
        text = path.read_text(encoding="utf-8")
        if "StockMovement(" in text:
            offenders.append(str(relative))
    assert checked > 40, "the source walk found almost no files — it is not walking app/"
    assert not offenders, f"these construct StockMovement directly, bypassing G8: {offenders}"


def test_r3_7_every_new_part_5_model_declares_its_blocking_references(db, warehouse, stocked):
    """R3.7 — and *exercised*, not merely present.

    A `Reference` names its column by string, so a wrong one raises AttributeError at
    check time rather than import time. That bug hid in the warehouse entry for five
    checkpoints; calling `blocking_references` here is what would have caught it.
    """
    for table in ("storage_rack", "storage_bin", "stock_reservation"):
        assert table in REFERENCES, f"{table} owes references.py an entry (R3.7)"

    rack, bin_row = _rack_and_bin(db, warehouse, suffix="X1")

    # An empty bin blocks nothing; a rack with a bin in it does.
    assert blocking_references(db, bin_row) == []
    assert any("bin" in phrase for phrase in blocking_references(db, rack))

    # Put stock in the bin and it is now in use.
    InventoryService(db).record_movement(
        product_id=stocked.product_id, warehouse_id=warehouse.id, bin_id=bin_row.id,
        qty_delta=Decimal("1"), reason="ADJUSTMENT",
    )
    assert any("stock movement" in phrase for phrase in blocking_references(db, bin_row))


def test_r3_7_a_reservation_entry_declares_nothing_blocks_it(db):
    """Deliberately empty, and exercised so the empty tuple is a decision not a gap."""
    assert REFERENCES["stock_reservation"] == ()


def test_r6_5_storage_models_are_soft_deletable_like_every_other_master(db):
    for model in (StorageRack, StorageBin):
        assert hasattr(model, "deleted_at"), f"{model.__name__} must soft-delete"


# --- R6.14: the demo data C1 owes the screens --------------------------------


def test_r6_14_the_seed_gives_every_warehouse_racks_and_bins(db):
    from sqlalchemy import select

    from app.modules.config.models import Warehouse

    warehouses = list(db.scalars(select(Warehouse).where(Warehouse.deleted_at.is_(None))))
    assert len(warehouses) >= 2, "R6.14 asks for two warehouses"

    svc = LocationService(db)
    for warehouse in warehouses:
        racks = svc.racks(warehouse.id)
        assert racks, f"{warehouse.code} has no racks"
        assert any(svc.bins(rack.id) for rack in racks), f"{warehouse.code} has no bins"

    # All three bin kinds are represented, or R6.4's screen shows three zeros.
    kinds = {b.kind for b in svc.bins()}
    assert kinds == {"stock", "transit", "quarantine"}


def test_r6_14_putaway_changed_the_address_not_the_quantity(db):
    """The seed addresses existing stock as a net-zero PAIR of movements.

    If a later section "fixes" the putaway by writing only the inbound half, on-hand
    silently inflates across the whole catalogue. This is the assertion that catches it.
    """
    from sqlalchemy import func, select

    net = db.scalar(
        select(func.coalesce(func.sum(StockMovement.qty_delta), 0)).where(
            StockMovement.reason == "PUTAWAY", StockMovement.deleted_at.is_(None)
        )
    )
    assert Decimal(net) == Decimal("0"), "putaway must not change on-hand, only location"

    addressed = db.scalar(
        select(func.count()).select_from(StockMovement).where(
            StockMovement.bin_id.isnot(None), StockMovement.deleted_at.is_(None)
        )
    )
    assert addressed > 0, "nothing was put away — the location view would be empty"


def test_r6_14_the_seed_holds_one_live_reservation(db):
    """So `/inventory` shows available < on hand for a reason worth clicking."""
    committed = [
        r for r in InventoryService(db).states() if r.reserved > 0
    ]
    assert committed, "the seed holds no reservation — R6.4's screen has nothing to show"
    row = committed[0]
    assert row.available == row.on_hand - row.in_transit - row.quarantined - row.reserved

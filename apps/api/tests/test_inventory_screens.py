"""Part 5 C1's screens — R6.1's location maintenance and R6.4's state reporting.

The acceptance for R6.1 and R6.4 is "screen + test" / "screen review", so these assert
what actually reaches the page rather than what the service returned. They assert markers
the shared macros emit, not `<tbody>` counts — the Part 2 idiom of counting tbodies is
wrong on any page carrying an entry form, and these pages carry two.
"""
from __future__ import annotations

import re
from decimal import Decimal

from app.modules.inventory.service import InventoryService


def test_r6_4_the_inventory_page_reports_all_four_states(client):
    html = client.get("/inventory").text

    for label in ("Available", "Reserved", "In transit", "Damaged / quarantined"):
        assert label in html, f"/inventory does not report the {label!r} state"
    # And it explains what "available" means rather than just printing a number (G11's
    # habit, applied to a screen that is not itself an Explained).
    assert "sellable stock minus" in html


def test_r6_4_the_state_table_carries_a_row_per_product_and_warehouse(client, db):
    html = client.get("/inventory").text
    states = InventoryService(db).states()
    assert states, "no states to render — the seed or the service regressed"

    # A floor, not an exact count: the seed grows between parts and an exact number
    # would be a maintenance tax. Asserting nothing at all is the failure mode this
    # avoids — a walk that finds zero rows must not pass.
    shown = sum(1 for s in states[:20] if s.sku_code in html)
    assert shown >= 10, f"only {shown} of the first 20 state rows reached the page"


def test_r6_1_the_warehouse_page_shows_the_rack_and_bin_tree(client, db):
    html = client.get("/warehouse").text

    assert "Locations" in html
    from app.modules.inventory.service import LocationService

    racks = LocationService(db).racks()
    assert racks, "the seed created no racks"
    for rack in racks[:2]:
        assert rack.code in html
        for b in LocationService(db).bins(rack.id)[:2]:
            assert b.code in html


def test_r6_1_the_warehouse_page_offers_both_maintenance_forms(client):
    html = client.get("/warehouse").text

    assert 'action="/warehouse/racks"' in html
    assert 'action="/warehouse/bins"' in html
    # The bin form must offer every kind, or the transit and quarantine states are
    # unreachable from the UI and R6.4 is only half true.
    for kind in ("stock", "transit", "quarantine"):
        assert f'value="{kind}"' in html


def test_r6_11_the_inventory_page_renders_the_location_rollup(client, db):
    html = client.get("/inventory").text
    assert "Stock by location" in html

    tree = InventoryService(db).location_rollup()
    assert tree, "nothing to roll up"
    warehouse = tree[0]
    assert warehouse.code in html
    # Every level of the tree reaches the page, not just the top.
    assert warehouse.children, "the rollup has no racks"
    assert warehouse.children[0].code in html


def test_r6_3_the_page_states_that_some_stock_has_no_recorded_bin(client, db):
    """R6.3's decision has to be visible, not just documented in a docstring."""
    unaddressed = sum(
        (r.qty_on_hand for r in InventoryService(db).bin_stock() if r.bin_id is None),
        Decimal(0),
    )
    html = client.get("/inventory").text
    if unaddressed:
        assert "no recorded bin" in html
        assert "no bin recorded" in html
    else:  # pragma: no cover - the seed always leaves some unaddressed today
        assert "Stock by location" in html


def test_r6_1_adding_a_rack_then_a_bin_works_through_the_forms(client, db):
    from sqlalchemy import select

    from app.modules.config.models import Warehouse

    warehouse = db.scalar(select(Warehouse).where(Warehouse.deleted_at.is_(None)))

    created = client.post(
        "/warehouse/racks",
        data={"warehouse_id": str(warehouse.id), "code": "WEB-R", "name": "Added on screen"},
        follow_redirects=False,
    )
    assert created.status_code == 303

    html = client.get("/warehouse").text
    assert "WEB-R" in html

    rack_id = re.search(
        r'<option value="([0-9a-f-]{36})">WEB-R', html
    )
    assert rack_id, "the new rack is not selectable in the bin form"

    added = client.post(
        "/warehouse/bins",
        data={"storage_rack_id": rack_id.group(1), "code": "WEB-B", "kind": "quarantine"},
        follow_redirects=False,
    )
    assert added.status_code == 303
    assert "WEB-B" in client.get("/warehouse").text


def test_r6_1_a_duplicate_rack_code_is_refused_with_a_flash(client, db):
    from sqlalchemy import select

    from app.modules.config.models import Warehouse

    warehouse = db.scalar(select(Warehouse).where(Warehouse.deleted_at.is_(None)))
    data = {"warehouse_id": str(warehouse.id), "code": "DUP-R", "name": ""}

    assert client.post("/warehouse/racks", data=data, follow_redirects=False).status_code == 303
    again = client.post("/warehouse/racks", data=data, follow_redirects=False)
    # Post/Redirect/Get holds for refusals too — the founder lands back on the page
    # with a flash rather than on an unreloadable error body.
    assert again.status_code == 303
    assert "err" in again.headers.get("location", "") or "err" in again.headers.get(
        "set-cookie", ""
    )

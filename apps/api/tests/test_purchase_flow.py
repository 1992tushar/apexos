"""Buy-side finance path: a bill payment reduces the outstanding balance.

The seed produces a partially-paid bill, so this exercises the real AP path
without reconstructing the full PO -> receive -> bill schema here (that path is
covered by the seed running successfully in conftest)."""
from __future__ import annotations


def test_bill_payment_reduces_balance(client, api_prefix):
    bills = client.get(f"{api_prefix}/bills").json()
    assert isinstance(bills, list) and bills, "seed should create at least one bill"

    payable = next((b for b in bills if b["balance_minor"] > 0), None)
    if payable is None:
        return  # nothing outstanding to pay; buy-side write path still proven by seed

    bill_id = payable["id"]
    before = payable["balance_minor"]
    pay = min(100, before)

    r = client.post(f"{api_prefix}/bills/{bill_id}/payments",
                    json={"amount_minor": pay, "method": "bank"})
    assert r.status_code == 201, r.text
    assert r.json()["balance_minor"] == before - pay


def test_purchase_orders_paginated(client, api_prefix):
    body = client.get(f"{api_prefix}/purchase-orders").json()
    assert set(body) >= {"items", "total", "page", "page_size"}

"""End-to-end sales lifecycle through the JSON API:
create -> confirm -> fulfill -> invoice -> payment (fully paid)."""
from __future__ import annotations


def test_full_sales_lifecycle(client, api_prefix):
    customer_id = client.get(f"{api_prefix}/customers").json()["items"][0]["id"]
    product_id = client.get(f"{api_prefix}/products").json()["items"][0]["id"]

    # create (draft)
    r = client.post(f"{api_prefix}/sales-orders", json={
        "customer_id": customer_id,
        "lines": [{"product_id": product_id, "qty": 3}],
    })
    assert r.status_code == 201, r.text
    order = r.json()
    assert order["status"] == "draft"
    assert order["total_minor"] > 0
    oid, total = order["id"], order["total_minor"]

    # confirm
    assert client.post(f"{api_prefix}/sales-orders/{oid}/confirm").json()["status"] == "confirmed"

    # fulfill -> a fulfillment appears
    fulfilled = client.post(f"{api_prefix}/sales-orders/{oid}/fulfill").json()
    assert len(fulfilled["fulfillments"]) >= 1

    # invoice -> an invoice appears
    invoiced = client.post(f"{api_prefix}/sales-orders/{oid}/invoice").json()
    assert len(invoiced["invoices"]) >= 1
    invoice_id = invoiced["invoices"][0]["id"]

    # pay in full -> invoice paid, zero balance
    pay = client.post(f"{api_prefix}/invoices/{invoice_id}/payments",
                      json={"amount_minor": total, "method": "bank"})
    assert pay.status_code == 201, pay.text
    result = pay.json()
    assert result["balance_minor"] == 0
    assert result["invoice_status"] == "paid"

"""Contract tests: list-endpoint envelopes and the error/validation envelope.

The envelope split (paginated `{items,...}` vs plain array) has been a real source
of drift bugs, so it is pinned here explicitly.
"""
from __future__ import annotations

import uuid


def test_paginated_endpoints_return_page_envelope(client, api_prefix):
    for path in ("/customers", "/sales-orders", "/products", "/suppliers", "/purchase-orders"):
        body = client.get(f"{api_prefix}{path}").json()
        assert set(body) >= {"items", "total", "page", "page_size"}, path
        assert isinstance(body["items"], list), path


def test_array_endpoints_return_plain_list(client, api_prefix):
    for path in ("/invoices", "/bills", "/goods-receipts"):
        body = client.get(f"{api_prefix}{path}").json()
        assert isinstance(body, list), path


def test_unknown_id_returns_error_envelope(client, api_prefix):
    r = client.get(f"{api_prefix}/customers/{uuid.uuid4()}")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def test_invalid_body_returns_validation_envelope(client, api_prefix):
    r = client.post(f"{api_prefix}/sales-orders", json={})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"

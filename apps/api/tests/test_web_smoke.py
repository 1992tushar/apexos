"""Smoke tests: every nav page renders, detail pages render, bad ids degrade gracefully."""
from __future__ import annotations

import uuid

import pytest

NAV_PAGES = [
    "/", "/sales", "/customers", "/leads", "/products", "/categories",
    "/inventory", "/warehouse", "/procurement", "/purchase-orders",
    "/suppliers", "/finance", "/reports", "/analytics", "/tasks",
    "/documents", "/settings",
]


@pytest.mark.parametrize("path", NAV_PAGES)
def test_nav_page_renders(client, path):
    r = client.get(path)
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_customer_detail_page_renders(client, api_prefix):
    cid = client.get(f"{api_prefix}/customers").json()["items"][0]["id"]
    r = client.get(f"/customers/{cid}")
    assert r.status_code == 200


def test_unknown_customer_detail_renders_error_page_not_500(client):
    r = client.get(f"/customers/{uuid.uuid4()}")
    # Should be a rendered HTML error page (not a 500, not a raw JSON envelope).
    assert r.status_code == 404
    assert "text/html" in r.headers["content-type"]

"""Smoke tests: every page renders, detail pages render, bad ids degrade gracefully.

The page list is **discovered, not written down**. It used to be 17 literal paths,
which meant the nine `/masters/*` screens Part 2 shipped were only ever checked by
booting uvicorn and clicking through by hand. Walking the router instead means a
screen added in a later part is covered the moment it exists.
"""
from __future__ import annotations

import uuid

import pytest
from _web_routes import plain_get_paths

from app.web.pages.masters import MASTERS

# Every web GET that takes no path parameter, so it can be requested blind.
PLAIN_GET_PATHS = plain_get_paths()

# `/masters/{slug}` serves nine screens off one route (Part 2 decision 15), so the
# slugs come from the registry rather than the path.
MASTER_SLUGS = sorted(m.slug for m in MASTERS)


def test_the_page_walk_finds_the_whole_surface():
    """Companion to `test_the_route_walk_finds_the_whole_web_surface`.

    `build_web_router()` logs and skips a page module that fails to import, so a
    broken import would quietly shrink the parametrised list below instead of
    failing. Assert the floor.
    """
    assert len(PLAIN_GET_PATHS) > 20, f"walked only {len(PLAIN_GET_PATHS)} pages"
    assert len(MASTER_SLUGS) == 9, f"expected 9 masters, registry has {len(MASTER_SLUGS)}"


@pytest.mark.parametrize("path", PLAIN_GET_PATHS)
def test_page_renders(client, path):
    r = client.get(path)
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


@pytest.mark.parametrize("slug", MASTER_SLUGS)
def test_master_screen_renders(client, slug):
    r = client.get(f"/masters/{slug}")
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

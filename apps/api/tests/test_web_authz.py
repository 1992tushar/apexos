"""The web authorization guard (R1.4, R1.5) and bad-URL rendering (R1.10).

Per decision D-B ApexOS has one user, whose actor carries `*`, so the guard never
denies in normal operation. These tests drive it with a deliberately
permission-less actor to prove both rendering paths work, and assert the guard is
actually attached to the web POST routes.
"""
from __future__ import annotations

import uuid

import pytest
from _web_routes import web_routes_for
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient

from app.core.errors import PermissionDeniedError, register_error_handlers
from app.core.security import Actor, get_current_actor
from app.web.core import render
from app.web.errors import register_web_error_handlers
from app.web.security import permission_phrase, require_web_permission


def _app_with_guarded_routes() -> FastAPI:
    """A miniature app with one guarded GET and one guarded POST.

    Built here rather than reusing the real app because the real app's single actor
    holds `*` — the point is to exercise the deny branches, which needs an actor
    that holds nothing.
    """
    app = FastAPI()
    register_error_handlers(app)
    register_web_error_handlers(app)

    @app.get("/guarded")
    def guarded_get(
        request: Request,
        actor: Actor = Depends(require_web_permission("widget.read")),
    ):
        return render(request, "error.html", code="OK", message="allowed")

    @app.post("/guarded")
    def guarded_post(actor: Actor = Depends(require_web_permission("widget.create"))):
        return {"ok": True}

    def _nobody() -> Actor:
        return Actor(id=uuid.uuid4(), email="nobody@example.com", role="none",
                     permissions=frozenset())

    app.dependency_overrides[get_current_actor] = _nobody
    return app


def test_denied_get_renders_403_error_page():
    with TestClient(_app_with_guarded_routes()) as client:
        r = client.get("/guarded")
    assert r.status_code == 403
    assert "text/html" in r.headers["content-type"]
    assert "permission" in r.text.lower()


def test_denied_post_redirects_back_with_an_error_flash():
    with TestClient(_app_with_guarded_routes()) as client:
        r = client.post("/guarded", headers={"referer": "http://testserver/widgets?page=2"},
                        follow_redirects=False)
    assert r.status_code == 303
    location = r.headers["location"]
    assert location.startswith("/widgets?page=2")
    assert "err=" in location


def test_denied_post_without_a_referer_falls_back_to_the_dashboard():
    with TestClient(_app_with_guarded_routes()) as client:
        r = client.post("/guarded", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"].startswith("/?err=")


def test_denied_post_ignores_an_offsite_referer():
    """A foreign referer must not choose our redirect target — only its path is used."""
    with TestClient(_app_with_guarded_routes()) as client:
        r = client.post("/guarded", headers={"referer": "https://evil.example.com/steal"},
                        follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"].startswith("/steal")


def test_allowed_request_passes_through():
    app = _app_with_guarded_routes()

    def _founder() -> Actor:
        return Actor(id=uuid.uuid4(), email="founder@example.com", role="founder",
                     permissions=frozenset({"*"}))

    app.dependency_overrides[get_current_actor] = _founder
    with TestClient(app) as client:
        assert client.get("/guarded").status_code == 200
        assert client.post("/guarded").status_code == 200


def test_guard_raises_permission_denied_error():
    dep = require_web_permission("widget.create")
    nobody = Actor(id=uuid.uuid4(), email="x@y.z", role="none", permissions=frozenset())
    with pytest.raises(PermissionDeniedError):
        dep(nobody)
    founder = Actor(id=uuid.uuid4(), email="x@y.z", role="founder",
                    permissions=frozenset({"*"}))
    assert dep(founder) is founder


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("customer.create", "create customers"),
        ("sales_order.confirm", "confirm sales orders"),
        ("config.write", "write configs"),
    ],
)
def test_permission_phrase_reads_as_a_sentence(code, expected):
    assert permission_phrase(code) == expected


# --- R1.5: the guard is actually wired onto the web POST routes ---------------

def test_the_route_walk_finds_the_whole_web_surface():
    """Guard-rail for the walk below, and for the smoke test's.

    This assertion exists because the walk it protects failed silently. It read
    `build_web_router().routes` directly, which in FastAPI >= 0.140 is a list of
    `_IncludedRouter` wrappers with no `.methods` — so it matched nothing and
    asserted `[] == []` for free. A dependency upgrade quietly disarmed a P0 test
    and the suite stayed green. If enumeration breaks again, fail here loudly
    rather than pass everywhere cheaply.
    """
    posts = web_routes_for("POST")
    assert len(posts) > 40, f"expected the full web POST surface, walked only {len(posts)}"


def test_every_web_post_route_carries_the_guard():
    """Spot-check turned exhaustive because it is cheap: no web POST route may
    depend on the bare actor. A new mutation added without a guard fails here."""
    unguarded = []
    for route in web_routes_for("POST"):
        sources = [
            d.call.__qualname__
            for d in route.dependant.dependencies
            if getattr(d, "call", None) is not None
        ]
        if not any("require_web_permission" in s for s in sources):
            unguarded.append(route.path)
    assert unguarded == []


# --- R1.10: a bad id or a bad URL renders error.html, never a stack trace -----

def test_unknown_uuid_on_a_detail_route_renders_error_page(client):
    r = client.get(f"/customers/{uuid.uuid4()}")
    assert r.status_code == 404
    assert "text/html" in r.headers["content-type"]
    assert "Traceback" not in r.text


def test_malformed_uuid_on_a_detail_route_renders_error_page(client):
    """FastAPI rejects this before the handler runs, so it needs its own path."""
    r = client.get("/customers/not-a-uuid")
    assert r.status_code == 422
    assert "text/html" in r.headers["content-type"]
    assert "Traceback" not in r.text


def test_unrouted_web_path_renders_error_page(client):
    r = client.get("/no-such-page")
    assert r.status_code == 404
    assert "text/html" in r.headers["content-type"]


def test_api_paths_keep_their_json_envelope(client, api_prefix):
    """The HTML handlers must not have swallowed the machine-readable surface."""
    r = client.get(f"{api_prefix}/customers/not-a-uuid")
    assert r.status_code == 422
    assert "application/json" in r.headers["content-type"]
    assert r.json()["error"]["code"] == "validation_error"

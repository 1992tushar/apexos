"""Unit tests for the foundation layer: config, errors, security, presentation."""
from __future__ import annotations

import uuid
from datetime import UTC

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.errors import ConflictError, NotFoundError, register_error_handlers
from app.core.security import Actor
from app.web import core as webcore


# --- error envelope ----------------------------------------------------------
def _errapp() -> TestClient:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/missing")
    def _missing():
        raise NotFoundError("nope", details={"k": "v"})

    @app.get("/conflict")
    def _conflict():
        raise ConflictError("dupe")

    return TestClient(app)


def test_app_error_serializes_to_standard_envelope():
    c = _errapp()
    r = c.get("/missing")
    assert r.status_code == 404
    body = r.json()
    assert body == {"error": {"code": "not_found", "message": "nope", "details": {"k": "v"}}}


def test_conflict_error_status_and_code():
    r = _errapp().get("/conflict")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "conflict"


# --- authorization primitive -------------------------------------------------
def test_actor_wildcard_grants_everything():
    a = Actor(id=uuid.uuid4(), email="x@y.z", role="founder", permissions=frozenset({"*"}))
    assert a.has("anything.at.all")


def test_actor_explicit_permission_only():
    a = Actor(
        id=uuid.uuid4(), email="x@y.z", role="ops", permissions=frozenset({"customer.create"})
    )
    assert a.has("customer.create")
    assert not a.has("customer.delete")


# --- config ------------------------------------------------------------------
def test_settings_documents_backend_defaults_to_local():
    from app.core.config import Settings

    s = Settings()
    assert s.documents_backend == "local"


def test_settings_cors_origin_list_splits_and_strips():
    from app.core.config import Settings

    s = Settings(cors_origins="http://a.com, http://b.com ,")
    assert s.cors_origin_list == ["http://a.com", "http://b.com"]


# --- presentation filters (web/core.py) --------------------------------------
def test_money_formats_indian_grouping_and_paise():
    assert webcore.money(1234567) == "₹12,345.67"
    assert webcore.money(0) == "₹0.00"
    assert webcore.money(-100) == "-₹1.00"
    assert webcore.money(None) == "₹0.00"


def test_number_indian_grouping():
    assert webcore.number(1234567) == "12,34,567"
    assert webcore.number(None) == "0"


def test_status_class_mapping():
    assert webcore.status_class("paid") == "ok"
    assert webcore.status_class("pending") == "warn"
    assert webcore.status_class("cancelled") == "bad"
    assert webcore.status_class("weird") == "muted"


def test_filesize_human_readable():
    assert webcore.filesize(0) == "0 B"
    assert webcore.filesize(2048) == "2.0 KB"


def test_time_ago_handles_naive_datetime_without_crashing():
    # SQLite hands back naive datetimes; the filter must not raise on naive input.
    from datetime import datetime

    assert webcore.time_ago(datetime.now(UTC).replace(tzinfo=None)) == "just now"
    assert webcore.time_ago(None) == ""


def test_humanize_snakecase():
    assert webcore.humanize("in_progress") == "In Progress"

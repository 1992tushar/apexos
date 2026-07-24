"""Test fixtures.

The whole suite runs against a throwaway SQLite file (never the real `apexos.db`).
We point `DATABASE_URL` at a temp file *before* importing anything from `app`, so
the app's module-level engine binds to it. The DB is seeded once per session with
the real demo data, then shared read-mostly across tests; flow tests create their
own rows and assert on returned objects, not on global counts.
"""
from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

# --- bind the app to a throwaway DB BEFORE any `app.*` import ----------------
_DB_FILE = Path(tempfile.gettempdir()) / "apexos_test.db"
if _DB_FILE.exists():
    _DB_FILE.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_FILE.as_posix()}"
os.environ["APP_ENV"] = "test"

# Keep the httpx TestClient request log out of test output.
logging.getLogger("httpx").setLevel(logging.WARNING)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="session")
def _seeded() -> None:
    """Create the schema and load the real demo data once for the whole run."""
    from app.seed import run

    run()


@pytest.fixture(scope="session")
def client(_seeded) -> TestClient:
    """A TestClient bound to the seeded throwaway DB (runs app lifespan)."""
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture()
def db(_seeded):
    """A request-style session against the seeded DB for service-level tests."""
    from app.core.database import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(scope="session")
def api_prefix() -> str:
    from app.core.config import settings

    return settings.api_v1_prefix

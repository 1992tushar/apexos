"""FastAPI application factory for ApexOS."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, text

from app.api import api_router
from app.core.config import settings
from app.core.database import engine
from app.core.errors import register_error_handlers
from app.core.logging import CorrelationIdMiddleware, configure_logging
from app.db.metadata import Base, import_all_models
from app.web import build_web_router
from app.web.core import STATIC_DIR


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Self-initialize the schema on startup.

    With Alembic removed (SQLite: the DB is just a file), a fresh database file
    bootstraps itself here — import every model so `Base.metadata` is complete,
    then create any missing tables. `create_all` is a no-op for tables that
    already exist, so this is safe on every boot.
    """
    import_all_models()
    Base.metadata.create_all(bind=engine)
    _ensure_new_columns()
    yield


# Columns added to existing models after a DB file already exists. `create_all`
# only creates whole missing tables — it never ALTERs an existing one — so with
# no migration tool we patch in additive, nullable/defaulted columns here. Each
# entry is idempotent (skipped when the column is already present).
_ADDITIVE_COLUMNS: dict[str, dict[str, str]] = {
    "document": {"category": "VARCHAR(32) NOT NULL DEFAULT 'other'"},
}


def _ensure_new_columns() -> None:
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table, columns in _ADDITIVE_COLUMNS.items():
            if table not in existing_tables:
                continue  # create_all already built it with every column
            present = {c["name"] for c in inspector.get_columns(table)}
            for name, ddl in columns.items():
                if name not in present:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


def create_app() -> FastAPI:
    configure_logging()

    app = FastAPI(
        title=f"{settings.app_name} API",
        version="0.1.0",
        description="The internal operating system of Apex Supply Solutions Pvt. Ltd.",
        openapi_url=f"{settings.api_v1_prefix}/openapi.json",
        docs_url="/docs",
        lifespan=lifespan,
    )

    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_error_handlers(app)

    @app.get("/health", tags=["meta"])
    def health() -> dict[str, str]:
        """Liveness probe."""
        return {"status": "ok", "app": settings.app_name, "env": settings.app_env}

    app.include_router(api_router, prefix=settings.api_v1_prefix)

    # Server-rendered web UI (Jinja2): static assets + auto-discovered page routers.
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.include_router(build_web_router())
    return app


app = create_app()


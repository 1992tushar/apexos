"""FastAPI application factory for ApexOS."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router
from app.core.config import settings
from app.core.database import engine
from app.core.errors import register_error_handlers
from app.core.logging import CorrelationIdMiddleware, configure_logging
from app.db.metadata import Base, import_all_models


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
    yield


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
    return app


app = create_app()


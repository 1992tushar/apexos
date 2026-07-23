"""Database engine, session factory, and the `get_db` FastAPI dependency."""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

url = settings.database_url
# SQLite needs check_same_thread=False so a session can be used across the
# threadpool FastAPI runs sync endpoints on; other backends take no extra args.
connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
engine = create_engine(
    url,
    connect_args=connect_args,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Iterator[Session]:
    """Yield a request-scoped SQLAlchemy session, committing on success."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

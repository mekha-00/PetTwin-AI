"""Database engine, session factory and the FastAPI session dependency.

The production target is PostgreSQL. SQLite is never configured here: it is not
a fallback and it is not a substitute. Tests inject their own engine through the
``get_db`` override in ``tests/conftest.py``.
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    """Declarative base shared by every ORM model."""


if settings.is_database_configured:
    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        future=True,
    )
else:
    engine = None

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    future=True,
) if engine is not None else None


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a request-scoped database session."""
    if SessionLocal is None:
        raise RuntimeError(
            "Database is not configured. Set POSTGRES_USER and POSTGRES_DB "
            "(or DATABASE_URL) in your .env file."
        )
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def create_all() -> None:
    """Create tables from the model metadata.

    Intended for local development and tests only. Production schema changes are
    handled by migrations, which are not part of Phase 2.
    """
    if engine is None:
        raise RuntimeError("Database is not configured.")
    from app import models  # noqa: F401  (ensures every model is registered)

    Base.metadata.create_all(bind=engine)

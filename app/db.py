"""Database setup.

The engine is configured from the ``DATABASE_URL`` environment variable.
When it is not set the service falls back to a local SQLite file, so the
whole project runs anywhere with zero setup. In Docker Compose / AWS the
variable points at PostgreSQL (``postgresql+psycopg2://...``).
"""

from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./uptime.db")

_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=_connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def init_db() -> None:
    """Create all tables if they do not exist yet."""
    from app import models  # noqa: F401  (import registers the models)

    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency: yield a session and always close it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

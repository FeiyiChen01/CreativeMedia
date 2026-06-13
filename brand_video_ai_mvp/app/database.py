"""Database configuration and session management for the MVP.

This module keeps the SQLite/SQLAlchemy setup in one place so route handlers
can request a database session through FastAPI dependencies.
"""

import os
from collections.abc import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")

# SQLite needs check_same_thread=False when FastAPI uses sessions across request handlers.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    future=True,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=Session,
    future=True,
)


class Base(DeclarativeBase):
    """Base class for SQLAlchemy ORM models."""


def init_db() -> None:
    """Create database tables on app startup.

    Importing app.models here registers the SQLAlchemy models with Base.metadata
    without creating a circular import at module import time.
    """

    from app import models  # noqa: F401  # pylint: disable=unused-import,import-outside-toplevel

    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Yield a database session and close it after the request finishes."""

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

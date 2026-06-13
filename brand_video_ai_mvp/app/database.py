"""Database configuration and session management for the MVP."""

import os
from collections.abc import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")

# SQLite needs check_same_thread=False when FastAPI uses sessions across request handlers.
is_sqlite = DATABASE_URL.startswith("sqlite")
connect_args = {"check_same_thread": False} if is_sqlite else {}
engine_kwargs = {
    "connect_args": connect_args,
    "future": True,
}

if not is_sqlite:
    engine_kwargs["pool_pre_ping"] = True

engine = create_engine(DATABASE_URL, **engine_kwargs)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=Session,
    future=True,
)


class Base(DeclarativeBase):
    """Base class for SQLAlchemy ORM models."""


def _add_missing_sqlite_columns() -> None:
    """Add simple compatibility columns for existing local SQLite databases."""

    if not is_sqlite:
        return

    sqlite_columns_by_table = {
        "users": {
            "full_name": "VARCHAR(255)",
            "company_name": "VARCHAR(255)",
            "avatar_url": "VARCHAR(500)",
            "phone": "VARCHAR(50)",
            "email_verified": "BOOLEAN NOT NULL DEFAULT 0",
            "email_verified_at": "DATETIME",
            "role": "VARCHAR(20) NOT NULL DEFAULT 'user'",
            "is_active": "BOOLEAN NOT NULL DEFAULT 1",
            "last_login_at": "DATETIME",
        },
        "video_assets": {
            "prompt_package_id": "INTEGER",
            "storage_backend": "VARCHAR(50)",
            "file_size": "INTEGER",
        },
    }

    with engine.begin() as connection:
        for table_name, sqlite_columns in sqlite_columns_by_table.items():
            existing_columns = {
                row[1] for row in connection.execute(text(f"PRAGMA table_info({table_name})")).all()
            }
            if not existing_columns:
                continue
            for column_name, column_type in sqlite_columns.items():
                if column_name not in existing_columns:
                    connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"))


def init_db() -> None:
    """Create database tables on app startup.

    Importing app.models here registers the SQLAlchemy models with Base.metadata
    without creating a circular import at module import time.
    """

    from app import models  # noqa: F401  # pylint: disable=unused-import,import-outside-toplevel

    Base.metadata.create_all(bind=engine)
    _add_missing_sqlite_columns()


def get_db() -> Generator[Session, None, None]:
    """Yield a database session and close it after the request finishes."""

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

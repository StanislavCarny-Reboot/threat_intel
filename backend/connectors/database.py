"""Synchronous database connector for Prefect workflows."""

import os

from dotenv import load_dotenv
from loguru import logger
from sqlalchemy import MetaData, create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# Load environment variables
load_dotenv()

# Default schema for all ORM models
DB_SCHEMA = os.getenv("DB_SCHEMA", "dev")


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    metadata = MetaData(schema=DB_SCHEMA)


# Module-level engine (created once)
_engine = None
_Session = None


def _get_engine():
    global _engine
    if _engine is None:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise ValueError(
                "DATABASE_URL environment variable is required but not set"
            )

        sync_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
        _engine = create_engine(
            sync_url,
            connect_args={"sslmode": "prefer", "gssencmode": "disable"},
            pool_size=2,
            max_overflow=2,
        )

        # Ensure schema and tables exist
        with _engine.begin() as conn:
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {DB_SCHEMA}"))
        Base.metadata.create_all(bind=_engine)

        logger.info(f"Database engine created, schema '{DB_SCHEMA}' ensured")

    return _engine


def get_db_session():
    """Create a synchronous SQLAlchemy session."""
    global _Session
    if _Session is None:
        _Session = sessionmaker(bind=_get_engine())
    return _Session()

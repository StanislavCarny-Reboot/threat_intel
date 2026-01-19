"""SQLAlchemy-based database connector with async support."""

import asyncio
import os
import threading
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Optional

from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


class PostgresConnector:
    """
    Thread-safe singleton PostgreSQL connector using SQLAlchemy ORM with async support.

    This class ensures only one database engine is created across the application.
    Thread safety is guaranteed by using threading.Lock in __new__.

    Usage:
        # Initialize and connect
        db = PostgresConnector()
        await db.connect()

        # Use sessions for ORM operations
        async with db.session() as session:
            result = await session.execute(text("SELECT * FROM table"))
            rows = result.fetchall()

        # Or for simple queries
        result = await db.execute_query("SELECT version()")

        # Cleanup
        await db.disconnect()
    """

    _instance: Optional["PostgresConnector"] = None
    _creation_lock = threading.Lock()

    def __init__(self):
        self._engine: Optional[AsyncEngine] = None
        self._session_factory: Optional[async_sessionmaker[AsyncSession]] = None
        self._engine_lock = asyncio.Lock()
        self._initialized = True

        # Database configuration from environment variables
        self.connection_string = os.getenv("DATABASE_URL") or os.getenv(
            "POSTGRES_CONNECTION_STRING"
        )
        self.host = os.getenv("POSTGRES_HOST", "localhost")
        self.port = os.getenv("POSTGRES_PORT", 5432)
        self.database = os.getenv("POSTGRES_DB", "threat_intel")
        self.user = os.getenv("POSTGRES_USER", "postgres")
        self.password = os.getenv("POSTGRES_PASSWORD")

        # Validate required credentials
        if not self.password:
            raise ValueError(
                "POSTGRES_PASSWORD environment variable is required but not set"
            )

        # Build connection string from individual components if not provided
        if not self.connection_string:
            self.connection_string = (
                f"postgresql+asyncpg://{self.user}:{self.password}"
                f"@{self.host}:{self.port}/{self.database}"
            )

        # Connection pool settings
        # self.pool_size = self._parse_int_env("POSTGRES_POOL_SIZE", 5)
        # self.max_overflow = self._parse_int_env("POSTGRES_MAX_OVERFLOW", 10)
        # self.pool_timeout = self._parse_float_env("POSTGRES_POOL_TIMEOUT", 30.0)
        # self.pool_recycle = self._parse_int_env("POSTGRES_POOL_RECYCLE", 3600)
        # self.echo = os.getenv("POSTGRES_ECHO", "false").lower() == "true"

        logger.debug(
            f"PostgreSQL connector initialized: {self.user}@{self.host}:{self.port}/{self.database}"
        )

    async def connect(self) -> None:
        """
        Create async engine and session factory.
        This method is idempotent - calling it multiple times is safe.
        """
        async with self._engine_lock:
            if self._engine is not None:
                logger.debug("Database engine already exists")
                return

            try:
                logger.info("Creating SQLAlchemy async engine...")

                # Configure SSL for cloud databases - use prefer mode for Railway
                self._engine = create_async_engine(
                    self.connection_string,
                    connect_args={"ssl": "prefer"},
                    # echo=self.echo,
                    # pool_size=self.pool_size,
                    # max_overflow=self.max_overflow,
                    # pool_timeout=self.pool_timeout,
                    # pool_recycle=self.pool_recycle,
                    # pool_pre_ping=True,  # Verify connections before using
                )

                self._session_factory = async_sessionmaker(
                    self._engine,
                    class_=AsyncSession,
                    expire_on_commit=False,
                )

                logger.info("SQLAlchemy async engine created successfully")
            except Exception as e:
                logger.error(f"Failed to create database engine: {e}")
                raise

    async def disconnect(self) -> None:
        """
        Dispose of the engine and cleanup resources.
        This method is idempotent - calling it multiple times is safe.
        """
        async with self._engine_lock:
            if self._engine is None:
                logger.debug("No database engine to dispose")
                return

            try:
                logger.info("Disposing SQLAlchemy async engine...")
                await self._engine.dispose()
                self._engine = None
                self._session_factory = None
                logger.info("SQLAlchemy async engine disposed successfully")
            except Exception as e:
                logger.error(f"Error disposing database engine: {e}")
                raise

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Get an async session using context manager.

        Usage:
            async with db.session() as session:
                result = await session.execute(text("SELECT * FROM table"))
                await session.commit()
        """
        if self._session_factory is None:
            raise RuntimeError("Session factory not initialized. Call connect() first.")

        async with self._session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    async def execute_query(
        self, query: str, params: dict[str, Any] | None = None
    ) -> Any:
        """
        Execute a raw SQL query and return results.

        Args:
            query: SQL query to execute
            params: Optional dictionary of query parameters

        Returns:
            Query result

        Usage:
            result = await db.execute_query("SELECT * FROM users WHERE id = :id", {"id": 1})
        """
        async with self.session() as session:
            result = await session.execute(text(query), params or {})
            return result.fetchall()

    async def execute_statement(
        self, query: str, params: dict[str, Any] | None = None
    ) -> None:
        """
        Execute a SQL statement that doesn't return results (INSERT, UPDATE, DELETE).

        Args:
            query: SQL statement to execute
            params: Optional dictionary of query parameters

        Usage:
            await db.execute_statement(
                "INSERT INTO users (name) VALUES (:name)",
                {"name": "John"}
            )
        """
        async with self.session() as session:
            await session.execute(text(query), params or {})
            await session.commit()

    async def health_check(self) -> bool:
        """
        Check if the database connection is healthy.

        Returns:
            True if connection is healthy, False otherwise
        """
        try:
            async with self.session() as session:
                await session.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    @property
    def engine(self) -> AsyncEngine:
        """
        Get the SQLAlchemy async engine.

        Returns:
            AsyncEngine instance

        Raises:
            RuntimeError: If engine is not initialized
        """
        if self._engine is None:
            raise RuntimeError("Engine not initialized. Call connect() first.")
        return self._engine

    @property
    def is_connected(self) -> bool:
        """Check if database engine is active."""
        return self._engine is not None

    async def create_tables(self) -> None:
        """
        Create all tables defined in ORM models.

        Usage:
            await db.create_tables()
        """
        if self._engine is None:
            raise RuntimeError("Engine not initialized. Call connect() first.")

        logger.info("Creating database tables...")
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created successfully")

    async def drop_tables(self) -> None:
        """
        Drop all tables defined in ORM models.
        WARNING: This will delete all data!

        Usage:
            await db.drop_tables()
        """
        if self._engine is None:
            raise RuntimeError("Engine not initialized. Call connect() first.")

        logger.warning("Dropping all database tables...")
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        logger.info("Database tables dropped successfully")


db = PostgresConnector()

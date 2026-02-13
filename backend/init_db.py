"""Initialize database tables in Supabase."""

import asyncio
from connectors.database import db
from loguru import logger

# Import all entities to register them with Base metadata
from models.entities import (  # noqa: F401
    Article,
    ArticleClassificationLabel,
    DataSources,
    RssItem,
    RssParseRun,
)


async def main() -> None:
    """Create all database tables."""
    try:
        logger.info("Connecting to database...")
        await db.connect()

        logger.info("Creating tables...")
        await db.create_tables()

        logger.info("Tables created successfully!")

        # Test connection
        is_healthy = await db.health_check()
        if is_healthy:
            logger.info("Database health check passed!")
        else:
            logger.error("Database health check failed!")

    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise
    finally:
        logger.info("Disconnecting from database...")
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())

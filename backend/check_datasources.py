"""Check what datasources are currently in the database."""

import asyncio
from connectors.database import db
from models.entities import DataSources
from sqlalchemy import select
from loguru import logger


async def main() -> None:
    """Check datasources in database."""
    try:
        logger.info("Connecting to database...")
        await db.connect()

        async with db.session() as session:
            result = await session.execute(select(DataSources))
            sources = result.scalars().all()

            if not sources:
                logger.info("No datasources found in database")
            else:
                logger.info(f"Found {len(sources)} datasources:")
                for source in sources:
                    logger.info(f"  ID: {source.id}, Name: {source.name}, Active: {source.active}")

    except Exception as e:
        logger.error(f"Error checking datasources: {e}")
        raise
    finally:
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())

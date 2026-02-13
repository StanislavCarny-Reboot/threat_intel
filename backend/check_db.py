"""Check what tables exist in the database."""

import asyncio
from connectors.database import db
from loguru import logger
from sqlalchemy import text


async def main() -> None:
    """List all tables in the database."""
    try:
        logger.info("Connecting to database...")
        await db.connect()

        # Query to list all tables in the public schema
        query = """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        ORDER BY table_name;
        """

        logger.info("Fetching tables from database...")
        async with db.session() as session:
            result = await session.execute(text(query))
            tables = result.fetchall()

        if tables:
            logger.info(f"Found {len(tables)} tables:")
            for table in tables:
                logger.info(f"  - {table[0]}")
        else:
            logger.warning("No tables found in the public schema!")

        # Check connection details
        logger.info(f"Database URL: {db.connection_string.split('@')[1]}")  # Hide password

    except Exception as e:
        logger.error(f"Error checking database: {e}")
        raise
    finally:
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())

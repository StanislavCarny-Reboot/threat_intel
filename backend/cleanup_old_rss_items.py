"""
Remove old RSS items without run_id to test run tracking with fresh data.
"""

import asyncio
from loguru import logger
from sqlalchemy import delete, select, func
from dotenv import load_dotenv

from connectors.database import db
from models.entities import RssItem

load_dotenv()


async def cleanup_old_items():
    """Remove RSS items that don't have a run_id (pre-tracking items)."""
    await db.connect()
    logger.info("Database connected")

    async with db.session() as session:
        # Count items before deletion
        count_before = await session.execute(select(func.count(RssItem.id)))
        total_before = count_before.scalar()

        count_without_run_id = await session.execute(
            select(func.count(RssItem.id)).where(RssItem.run_id.is_(None))
        )
        items_to_delete = count_without_run_id.scalar()

        logger.info(f"Total items in database: {total_before}")
        logger.info(f"Items without run_id to delete: {items_to_delete}")

        if items_to_delete == 0:
            logger.info("No items to delete. Database is clean.")
            await db.disconnect()
            return

        # Delete items without run_id
        logger.info("Deleting old items...")
        result = await session.execute(
            delete(RssItem).where(RssItem.run_id.is_(None))
        )
        await session.commit()

        deleted_count = result.rowcount
        logger.info(f"✓ Deleted {deleted_count} old RSS items")

        # Verify deletion
        count_after = await session.execute(select(func.count(RssItem.id)))
        total_after = count_after.scalar()

        logger.info(f"Items remaining in database: {total_after}")
        logger.info("Cleanup complete! You can now run the parser to see run_id tracking.")

    await db.disconnect()


if __name__ == "__main__":
    asyncio.run(cleanup_old_items())

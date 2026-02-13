"""Quick check to see run_id distribution in rss_items table."""

import asyncio
from loguru import logger
from sqlalchemy import select, func, text
from dotenv import load_dotenv

from connectors.database import db
from models.entities import RssItem, RssParseRun

load_dotenv()


async def check_run_ids():
    """Check run_id values in database."""
    await db.connect()

    async with db.session() as session:
        # Check total items
        total_result = await session.execute(select(func.count(RssItem.id)))
        total = total_result.scalar()

        # Check items with run_id
        with_run_id = await session.execute(
            select(func.count(RssItem.id)).where(RssItem.run_id.isnot(None))
        )
        with_id_count = with_run_id.scalar()

        # Check items without run_id
        without_id_count = total - with_id_count

        logger.info(f"Total items: {total}")
        logger.info(f"Items WITH run_id: {with_id_count}")
        logger.info(f"Items WITHOUT run_id (null): {without_id_count}")

        # Show recent items
        logger.info("\n=== Recent 10 items ===")
        recent = await session.execute(
            select(RssItem).order_by(RssItem.created_at.desc()).limit(10)
        )
        for item in recent.scalars():
            logger.info(f"  {item.created_at} | run_id: {item.run_id} | {item.title[:50]}")

        # Check runs
        logger.info("\n=== Parse Runs ===")
        runs = await session.execute(select(RssParseRun))
        for run in runs.scalars():
            logger.info(
                f"Run {run.run_id}: extracted={run.items_extracted}, "
                f"inserted={run.items_inserted}"
            )

    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(check_run_ids())

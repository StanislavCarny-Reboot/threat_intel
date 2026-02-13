"""
Test script to verify run_id tracking is working correctly.

This script:
1. Queries recent runs from rss_parse_runs table
2. Verifies items have correct run_id
3. Counts pre-tracking items (null run_id)
"""

import asyncio
from datetime import datetime, timedelta
from loguru import logger
from sqlalchemy import select, func
from dotenv import load_dotenv

from connectors.database import db
from models.entities import RssParseRun, RssItem

load_dotenv()


async def test_run_tracking():
    """Test and display run tracking information."""
    await db.connect()
    logger.info("Database connected")

    async with db.session() as session:
        # Query recent runs
        logger.info("\n=== Recent RSS Parse Runs ===")
        result = await session.execute(
            select(RssParseRun)
            .order_by(RssParseRun.started_at.desc())
            .limit(10)
        )
        runs = result.scalars().all()

        if not runs:
            logger.warning("No parse runs found in database")
        else:
            for run in runs:
                duration = "N/A"
                if run.completed_at:
                    delta = run.completed_at - run.started_at
                    duration = f"{delta.total_seconds():.2f}s"

                logger.info(
                    f"\nRun ID: {run.run_id}\n"
                    f"  Status: {run.status}\n"
                    f"  Started: {run.started_at}\n"
                    f"  Completed: {run.completed_at}\n"
                    f"  Duration: {duration}\n"
                    f"  Sources Processed: {run.sources_processed}\n"
                    f"  Items Extracted: {run.items_extracted}\n"
                    f"  Items Inserted: {run.items_inserted}\n"
                    f"  Error: {run.error_message or 'None'}"
                )

        # Count items with and without run_id
        logger.info("\n=== RSS Items Statistics ===")

        # Total items
        total_result = await session.execute(select(func.count(RssItem.id)))
        total_count = total_result.scalar()

        # Items with run_id
        tracked_result = await session.execute(
            select(func.count(RssItem.id)).where(RssItem.run_id.isnot(None))
        )
        tracked_count = tracked_result.scalar()

        # Items without run_id (pre-tracking)
        untracked_count = total_count - tracked_count

        logger.info(f"Total RSS items: {total_count}")
        logger.info(f"Items with run_id (tracked): {tracked_count}")
        logger.info(f"Items without run_id (pre-tracking): {untracked_count}")

        # If we have runs, show items from most recent run
        if runs:
            latest_run = runs[0]
            logger.info(f"\n=== Items from Latest Run ({latest_run.run_id[:8]}...) ===")

            items_result = await session.execute(
                select(RssItem)
                .where(RssItem.run_id == latest_run.run_id)
                .limit(5)
            )
            items = items_result.scalars().all()

            if items:
                for item in items:
                    logger.info(
                        f"  - {item.source_name}: {item.title[:50]}... "
                        f"(run_id: {item.run_id[:8]}...)"
                    )
                logger.info(f"  ... and {latest_run.items_inserted - len(items)} more items")
            else:
                logger.warning("No items found for this run")

        # Show run statistics
        if len(runs) > 0:
            logger.info("\n=== Run Statistics ===")
            completed_runs = [r for r in runs if r.status == "completed"]
            failed_runs = [r for r in runs if r.status == "failed"]

            logger.info(f"Total runs: {len(runs)}")
            logger.info(f"Completed runs: {len(completed_runs)}")
            logger.info(f"Failed runs: {len(failed_runs)}")

            if completed_runs:
                avg_extracted = sum(r.items_extracted for r in completed_runs) / len(completed_runs)
                avg_inserted = sum(r.items_inserted for r in completed_runs) / len(completed_runs)
                logger.info(f"Average items extracted per run: {avg_extracted:.1f}")
                logger.info(f"Average items inserted per run: {avg_inserted:.1f}")

                if avg_extracted > 0:
                    insertion_rate = (avg_inserted / avg_extracted) * 100
                    logger.info(f"Average insertion rate: {insertion_rate:.1f}%")

    await db.disconnect()
    logger.info("\nTest complete!")


if __name__ == "__main__":
    asyncio.run(test_run_tracking())

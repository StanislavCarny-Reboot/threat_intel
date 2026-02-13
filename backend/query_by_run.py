"""
Example queries demonstrating run_id usage.

This script shows various ways to query and analyze RSS parse runs.
"""

import asyncio
from datetime import datetime, timedelta
from loguru import logger
from sqlalchemy import select, func, and_
from dotenv import load_dotenv

from connectors.database import db
from models.entities import RssParseRun, RssItem

load_dotenv()


async def query_by_run_examples():
    """Demonstrate various queries using run_id."""
    await db.connect()
    logger.info("Database connected")

    async with db.session() as session:
        # Example 1: Get all items from a specific run
        logger.info("\n=== Example 1: Items from Latest Run ===")
        latest_run_result = await session.execute(
            select(RssParseRun).order_by(RssParseRun.started_at.desc()).limit(1)
        )
        latest_run = latest_run_result.scalar_one_or_none()

        if latest_run:
            items_result = await session.execute(
                select(RssItem).where(RssItem.run_id == latest_run.run_id)
            )
            items = items_result.scalars().all()
            logger.info(f"Latest run {latest_run.run_id} has {len(items)} items")
            for item in items[:3]:  # Show first 3
                logger.info(f"  - {item.source_name}: {item.title[:60]}...")

        # Example 2: Get runs from last 24 hours
        logger.info("\n=== Example 2: Runs from Last 24 Hours ===")
        yesterday = datetime.utcnow() - timedelta(days=1)
        recent_runs_result = await session.execute(
            select(RssParseRun)
            .where(RssParseRun.started_at >= yesterday)
            .order_by(RssParseRun.started_at.desc())
        )
        recent_runs = recent_runs_result.scalars().all()
        logger.info(f"Found {len(recent_runs)} runs in last 24 hours")
        for run in recent_runs:
            logger.info(
                f"  - {run.run_id[:8]}... - Status: {run.status}, "
                f"Extracted: {run.items_extracted}, Inserted: {run.items_inserted}"
            )

        # Example 3: Calculate success rate
        logger.info("\n=== Example 3: Success Rate ===")
        all_runs_result = await session.execute(select(RssParseRun))
        all_runs = all_runs_result.scalars().all()

        if all_runs:
            completed = len([r for r in all_runs if r.status == "completed"])
            failed = len([r for r in all_runs if r.status == "failed"])
            total = len(all_runs)

            success_rate = (completed / total) * 100 if total > 0 else 0
            logger.info(f"Total runs: {total}")
            logger.info(f"Completed: {completed}")
            logger.info(f"Failed: {failed}")
            logger.info(f"Success rate: {success_rate:.1f}%")

        # Example 4: Find runs with errors
        logger.info("\n=== Example 4: Failed Runs ===")
        failed_runs_result = await session.execute(
            select(RssParseRun)
            .where(RssParseRun.status == "failed")
            .order_by(RssParseRun.started_at.desc())
        )
        failed_runs = failed_runs_result.scalars().all()

        if failed_runs:
            logger.info(f"Found {len(failed_runs)} failed runs")
            for run in failed_runs:
                logger.info(
                    f"  - {run.run_id[:8]}... at {run.started_at}\n"
                    f"    Error: {run.error_message}"
                )
        else:
            logger.info("No failed runs found")

        # Example 5: Average insertion rate
        logger.info("\n=== Example 5: Insertion Rate Analysis ===")
        completed_runs_result = await session.execute(
            select(RssParseRun).where(RssParseRun.status == "completed")
        )
        completed_runs = completed_runs_result.scalars().all()

        if completed_runs:
            total_extracted = sum(r.items_extracted for r in completed_runs)
            total_inserted = sum(r.items_inserted for r in completed_runs)

            if total_extracted > 0:
                overall_rate = (total_inserted / total_extracted) * 100
                logger.info(f"Total items extracted: {total_extracted}")
                logger.info(f"Total items inserted: {total_inserted}")
                logger.info(f"Overall insertion rate: {overall_rate:.1f}%")

                # Show individual run rates
                logger.info("\nIndividual run insertion rates:")
                for run in completed_runs[-5:]:  # Last 5 runs
                    if run.items_extracted > 0:
                        rate = (run.items_inserted / run.items_extracted) * 100
                        logger.info(
                            f"  - {run.run_id[:8]}... at {run.started_at}: "
                            f"{rate:.1f}% ({run.items_inserted}/{run.items_extracted})"
                        )

        # Example 6: Items from specific source in latest run
        logger.info("\n=== Example 6: Items by Source from Latest Run ===")
        if latest_run:
            sources_result = await session.execute(
                select(RssItem.source_name, func.count(RssItem.id))
                .where(RssItem.run_id == latest_run.run_id)
                .group_by(RssItem.source_name)
            )
            sources = sources_result.all()

            if sources:
                logger.info(f"Source breakdown for run {latest_run.run_id[:8]}...")
                for source_name, count in sources:
                    logger.info(f"  - {source_name}: {count} items")

        # Example 7: Find duplicate detection effectiveness
        logger.info("\n=== Example 7: Duplicate Detection ===")
        if completed_runs:
            logger.info("Runs showing duplicate detection:")
            for run in completed_runs[-5:]:  # Last 5 runs
                extracted = run.items_extracted
                inserted = run.items_inserted
                duplicates = extracted - inserted
                if extracted > 0:
                    dup_rate = (duplicates / extracted) * 100
                    logger.info(
                        f"  - {run.run_id[:8]}... at {run.started_at}: "
                        f"{duplicates} duplicates ({dup_rate:.1f}%)"
                    )

    await db.disconnect()
    logger.info("\nQuery examples complete!")


if __name__ == "__main__":
    asyncio.run(query_by_run_examples())

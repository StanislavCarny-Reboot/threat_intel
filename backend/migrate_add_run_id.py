"""
Migration script to add run_id tracking to RSS parser.

This script:
1. Adds run_id column to rss_items table
2. Creates rss_parse_runs audit table
3. Creates necessary indexes
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports when running directly
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger
from sqlalchemy import text
from dotenv import load_dotenv

from connectors.database import db

load_dotenv()


async def check_column_exists(session, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    query = text("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = :table_name
        AND column_name = :column_name
    """)
    result = await session.execute(query, {"table_name": table_name, "column_name": column_name})
    return result.first() is not None


async def check_table_exists(session, table_name: str) -> bool:
    """Check if a table exists."""
    query = text("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_name = :table_name
    """)
    result = await session.execute(query, {"table_name": table_name})
    return result.first() is not None


async def migrate():
    """Run migration to add run_id tracking."""
    await db.connect()
    logger.info("Database connected")

    async with db.session() as session:
        # Check and add run_id column to rss_items
        has_run_id = await check_column_exists(session, "rss_items", "run_id")

        if not has_run_id:
            logger.info("Adding run_id column to rss_items table...")
            await session.execute(text("""
                ALTER TABLE rss_items
                ADD COLUMN run_id VARCHAR(36) NULL
            """))
            await session.commit()
            logger.info("✓ Added run_id column")

            # Create index
            logger.info("Creating index on run_id...")
            await session.execute(text("""
                CREATE INDEX idx_rss_items_run_id ON rss_items(run_id)
            """))
            await session.commit()
            logger.info("✓ Created index idx_rss_items_run_id")
        else:
            logger.info("✓ Column run_id already exists in rss_items")

        # Check and create rss_parse_runs table
        has_runs_table = await check_table_exists(session, "rss_parse_runs")

        if not has_runs_table:
            logger.info("Creating rss_parse_runs table...")
            await session.execute(text("""
                CREATE TABLE rss_parse_runs (
                    run_id VARCHAR(36) PRIMARY KEY,
                    started_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    completed_at TIMESTAMP NULL,
                    status VARCHAR(50) NOT NULL DEFAULT 'running',
                    sources_processed INTEGER DEFAULT 0,
                    items_extracted INTEGER DEFAULT 0,
                    items_inserted INTEGER DEFAULT 0,
                    error_message TEXT NULL,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """))
            await session.commit()
            logger.info("✓ Created rss_parse_runs table")
        else:
            logger.info("✓ Table rss_parse_runs already exists")

    logger.info("Migration completed successfully!")
    await db.disconnect()


if __name__ == "__main__":
    asyncio.run(migrate())

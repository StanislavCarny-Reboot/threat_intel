"""
Script 1: Parse RSS feeds using regex patterns to extract article links.

This script:
1. Fetches all active RSS sources from the database
2. Downloads each RSS feed
3. Uses source-specific regex patterns to extract article URLs, titles, and dates
4. Saves new RSS items to the database

Prefect-compatible: uses @flow / @task decorators and Prefect concurrency limits.
"""

import asyncio
import sys
import uuid
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports when running directly
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from loguru import logger
from prefect import flow, task
from prefect.concurrency.asyncio import concurrency
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from dotenv import load_dotenv

from connectors.database import db
from models.entities import DataSources, RssItem, RssParseRun
from rss_regex.config.source_patterns import (
    get_source_config,
    detect_feed_type,
    DEFAULT_ATOM_CONFIG,
    SourceConfig,
)


load_dotenv()

# ---------------------------------------------------------------------------
# Concurrency limit name – create once via CLI or Prefect UI:
#   prefect gcl create rss-feed-fetch --limit 5
# The slot is acquired inside process_source so at most 5 feeds are fetched
# concurrently.
# ---------------------------------------------------------------------------
RSS_CONCURRENCY_LIMIT = "rss-feed-fetch"


@task(retries=3, retry_delay_seconds=2, name="fetch-rss-feed")
async def fetch_rss_feed(url: str, timeout: int = 30) -> tuple[str | None, int | None]:
    """
    Fetch RSS feed content from URL.

    Returns:
        Tuple of (content, status_code). Content is None on error.
    """
    try:
        response = await asyncio.to_thread(
            requests.get,
            url,
            timeout=timeout,
            headers={"User-Agent": "ThreatIntel RSS Parser/1.0"},
        )
        return response.text, response.status_code
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch {url}: {e}")
        raise  # let Prefect retry


def parse_date(date_str: str, date_format: str) -> datetime | None:
    """Parse date string to datetime, handling common variations."""
    # Try the specified format first
    try:
        dt = datetime.strptime(date_str.strip(), date_format)
        return dt.replace(tzinfo=None)  # Remove timezone for consistency
    except ValueError:
        pass

    # Try common alternative formats
    alt_formats = [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
        "%a, %d %b %Y %H:%M:%S GMT",
    ]
    for fmt in alt_formats:
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            return dt.replace(tzinfo=None)
        except ValueError:
            continue

    logger.warning(f"Could not parse date: {date_str}")
    return datetime.utcnow()


def extract_items_from_feed(
    content: str, source_name: str, config: SourceConfig, http_status_code: int
) -> list[dict]:
    """
    Extract article items from RSS/Atom feed content using regex patterns.

    Returns:
        List of dicts with keys: source_name, title, url, published_at, http_status_code
    """
    items = []
    patterns = config.rss_patterns

    # Find all item blocks
    item_matches = patterns.item_pattern.findall(content)

    for item_block in item_matches:
        # Extract URL
        url_match = patterns.url_pattern.search(item_block)
        if not url_match:
            continue
        url = url_match.group(1).strip()

        # Skip non-article URLs (feeds, categories, etc.)
        if "/feed" in url.lower() or "/category/" in url.lower():
            continue

        # Extract title
        title_match = patterns.title_pattern.search(item_block)
        title = title_match.group(1).strip() if title_match else "Untitled"

        # Clean CDATA from title if present
        title = title.replace("<![CDATA[", "").replace("]]>", "").strip()

        # Extract date
        date_match = patterns.date_pattern.search(item_block)
        if date_match:
            published_at = parse_date(date_match.group(1), patterns.date_format)
        else:
            published_at = datetime.utcnow()

        items.append(
            {
                "source_name": source_name,
                "title": title,
                "url": url,
                "published_at": published_at,
                "http_status_code": http_status_code,
                "fetch_error": None,
            }
        )

    return items


@task(name="process-rss-source")
async def process_source(source: DataSources) -> list[dict]:
    """
    Process a single RSS source: fetch feed and extract items.

    Acquires a Prefect concurrency slot so at most N sources are fetched in
    parallel (configured via the ``rss-feed-fetch`` global concurrency limit).
    """
    logger.info(f"Processing source: {source.name}")

    async with concurrency(RSS_CONCURRENCY_LIMIT, occupy=1):
        try:
            content, status_code = await fetch_rss_feed(source.url)
        except Exception:
            # All retries exhausted
            content, status_code = None, None

    if content is None or status_code != 200:
        error = str(status_code) if status_code else "connection_failed"
        logger.warning(f"Failed to fetch {source.name}: {error}")
        return [
            {
                "source_name": source.name,
                "title": f"Feed fetch failed: {error}",
                "url": source.url,
                "published_at": datetime.utcnow(),
                "http_status_code": status_code,
                "fetch_error": error,
            }
        ]

    # Detect feed type and get appropriate config
    feed_type = detect_feed_type(content)

    # Get source-specific config
    config = get_source_config(source.name)

    # For Atom feeds, use Atom patterns if using generic config
    if feed_type == "atom" and config.name == "Generic RSS":
        config = DEFAULT_ATOM_CONFIG

    items = extract_items_from_feed(content, source.name, config, status_code)
    logger.info(f"Extracted {len(items)} items from {source.name}")

    return items


@task(name="create-run-record")
async def create_run_record(run_id: str) -> None:
    """Create initial run record with 'running' status."""
    async with db.session() as session:
        run_record = RssParseRun(
            run_id=run_id, started_at=datetime.utcnow(), status="running"
        )
        session.add(run_record)
        await session.commit()
        logger.info(f"Created run record: {run_id}")


@task(retries=3, retry_delay_seconds=2, name="update-run-record")
async def update_run_record(
    run_id: str,
    status: str,
    sources_processed: int = 0,
    items_extracted: int = 0,
    items_inserted: int = 0,
    error_message: str | None = None,
) -> None:
    """Update run record with final results."""
    async with db.session() as session:
        result = await session.execute(
            select(RssParseRun).where(RssParseRun.run_id == run_id)
        )
        run_record = result.scalar_one_or_none()

        if run_record:
            run_record.completed_at = datetime.utcnow()
            run_record.status = status
            run_record.sources_processed = sources_processed
            run_record.items_extracted = items_extracted
            run_record.items_inserted = items_inserted
            run_record.error_message = error_message
            await session.commit()
            logger.info(f"Updated run record: {run_id} - Status: {status}")


@task(retries=3, retry_delay_seconds=2, name="save-items-to-db")
async def save_items_to_db(items: list[dict], run_id: str) -> int:
    """
    Save RSS items to database, skipping duplicates.

    Args:
        items: List of RSS items to save
        run_id: Unique identifier for this parsing run

    Returns:
        Number of new items inserted
    """
    if not items:
        return 0

    # Add run_id to each item
    for item in items:
        item["run_id"] = run_id

    async with db.session() as session:
        stmt = (
            insert(RssItem)
            .values(items)
            .on_conflict_do_nothing(index_elements=[RssItem.url])
        )
        result = await session.execute(stmt)
        await session.commit()

        # PostgreSQL returns rowcount for inserts
        return result.rowcount if result.rowcount else 0


@flow(name="parse-rss-feeds", log_prints=True)
async def run(run_id: str | None = None, disconnect_after: bool = True) -> str:
    """Main Prefect flow for RSS parsing.

    Args:
        run_id: Optional run ID. If not provided, a new UUID will be generated.
        disconnect_after: Whether to disconnect from database after completion.
                         Set to False when called from API to preserve connection.

    Returns:
        The run_id used for this execution.
    """
    # Generate unique run ID if not provided
    if run_id is None:
        run_id = str(uuid.uuid4())
    logger.info(f"Starting RSS parse run: {run_id}")

    # Only connect if not already connected (API might have already connected)
    if not db.is_connected:
        await db.connect()
        logger.info("Database connected")
    else:
        logger.info("Using existing database connection")

    try:
        # Create run record only if it doesn't exist (API might have already created it)
        async with db.session() as session:
            result = await session.execute(
                select(RssParseRun).where(RssParseRun.run_id == run_id)
            )
            existing_run = result.scalar_one_or_none()

            if not existing_run:
                await create_run_record(run_id)
            else:
                logger.info(f"Run record already exists for: {run_id}")

        # Load active sources
        async with db.session() as session:
            result = await session.execute(
                select(DataSources).where(DataSources.active == "true")
            )
            sources = result.scalars().all()

        if not sources:
            logger.warning("No active data sources found")
            await update_run_record(
                run_id=run_id,
                status="completed",
                sources_processed=0,
                items_extracted=0,
                items_inserted=0,
            )
            return run_id

        logger.info(f"Processing {len(sources)} RSS sources")

        # Submit all source-processing tasks concurrently.
        # Prefect concurrency limit (rss-feed-fetch) gates how many run at once.
        results = await asyncio.gather(
            *(process_source(src) for src in sources), return_exceptions=True
        )

        # Collect all items
        all_items: list[dict] = []
        for i, task_result in enumerate(results):
            if isinstance(task_result, Exception):
                logger.error(f"Error processing {sources[i].name}: {task_result}")
            else:
                all_items.extend(task_result)

        # Save to database
        new_count = await save_items_to_db(all_items, run_id)

        logger.info(
            f"Parsing complete: {len(all_items)} items extracted, {new_count} new items saved"
        )

        # Update run record with success
        await update_run_record(
            run_id=run_id,
            status="completed",
            sources_processed=len(sources),
            items_extracted=len(all_items),
            items_inserted=new_count,
        )

    except Exception as e:
        logger.error(f"Error during RSS parsing: {e}")
        # Update run record with failure
        await update_run_record(run_id=run_id, status="failed", error_message=str(e))
        raise

    finally:
        # Only disconnect if requested (when running standalone)
        if disconnect_after:
            await db.disconnect()
            logger.info("Database disconnected")

    return run_id


if __name__ == "__main__":
    run.deploy(name="parse-rss-feeds")

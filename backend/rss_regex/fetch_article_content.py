"""
Script 2: Fetch article content from RSS links using Playwright.

This script:
1. Queries RssItem entries with http_status_code=200 that haven't been fetched
2. Opens each URL in headless Chromium via Playwright
3. Saves HTTP status + raw article content to Article table
4. Updates RssItem status to 'fetched' or 'error'
"""

import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports when running directly
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from loguru import logger
from playwright.async_api import async_playwright
from sqlalchemy import select, update, or_, and_
from sqlalchemy.dialects.postgresql import insert

from connectors.database import db
from models.entities import RssItem, Article


async def update_rss_item_status(
    rss_item_id: int, http_status: int, error: str | None, status: str
):
    """Update RssItem with fetch results."""
    async with db.session() as session:
        stmt = (
            update(RssItem)
            .where(RssItem.id == rss_item_id)
            .values(
                status=status,
                http_status_code=http_status if http_status else None,
                fetch_error=error,
                fetched_at=datetime.utcnow(),
            )
        )
        await session.execute(stmt)
        await session.commit()


async def save_article(
    source_name: str, url: str, content: str, http_status_code: int, published_at: datetime | None
):
    """Save article content to Article table."""
    async with db.session() as session:
        stmt = (
            insert(Article)
            .values(
                source_name=source_name,
                text=content,
                url=url,
                http_status_code=http_status_code,
                published_at=published_at or datetime.utcnow(),
            )
            .on_conflict_do_nothing(index_elements=[Article.url])
        )
        await session.execute(stmt)
        await session.commit()


async def process_rss_item(browser, item: RssItem) -> dict:
    """
    Process a single RSS item: open page with Playwright and extract text.

    Returns:
        Dict with url, status_code, status, error
    """
    page = await browser.new_page()
    try:
        response = await page.goto(item.url, wait_until="networkidle", timeout=30000)
        status_code = response.status if response else 0

        if status_code == 200:
            text = await page.inner_text("body")
            await save_article(item.source_name, item.url, text, status_code, item.published_at)
            await update_rss_item_status(item.id, status_code, None, "fetched")
            logger.info(f"[{status_code}] Scraped: {item.url} ({len(text)} chars)")
            return {"url": item.url, "status_code": status_code, "status": "fetched", "error": None}
        else:
            error = f"HTTP {status_code}"
            await update_rss_item_status(item.id, status_code, error, "error")
            logger.warning(f"[{status_code}] Failed: {item.url}")
            return {"url": item.url, "status_code": status_code, "status": "error", "error": error}
    except Exception as e:
        error_msg = str(e)[:200]
        await update_rss_item_status(item.id, 0, error_msg, "error")
        logger.warning(f"[ERR] Failed: {item.url} - {error_msg}")
        return {"url": item.url, "status_code": 0, "status": "error", "error": error_msg}
    finally:
        try:
            await page.close()
        except Exception:
            pass


async def run(batch_size: int = 50, concurrency: int = 10, retry_errors: bool = False):
    """
    Main entry point for content fetching.

    Args:
        batch_size: Number of items to process per batch
        concurrency: Maximum concurrent browser pages
        retry_errors: If True, also retry items with status='error'
    """
    await db.connect()
    logger.info("Database connected")

    # Query items to process: items with http_status_code=200 that haven't been fetched yet
    async with db.session() as session:
        if retry_errors:
            status_filter = and_(
                RssItem.http_status_code == 200,
                or_(RssItem.status.is_(None), RssItem.status == "error"),
            )
        else:
            status_filter = and_(
                RssItem.http_status_code == 200,
                RssItem.status.is_(None),
            )

        result = await session.execute(
            select(RssItem).where(status_filter).limit(batch_size)
        )
        items = result.scalars().all()

    if not items:
        logger.info("No items to fetch")
        await db.disconnect()
        return

    logger.info(f"Fetching {len(items)} articles (concurrency={concurrency})")

    semaphore = asyncio.Semaphore(concurrency)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        async def process_with_limit(item):
            async with semaphore:
                return await process_rss_item(browser, item)

        results = await asyncio.gather(
            *(process_with_limit(item) for item in items), return_exceptions=True
        )

        await browser.close()

    # Build summary
    fetched = [r for r in results if isinstance(r, dict) and r["status"] == "fetched"]
    errors = [r for r in results if isinstance(r, dict) and r["status"] == "error"]
    exceptions = [r for r in results if isinstance(r, Exception)]

    logger.info("=" * 60)
    logger.info(f"SCRAPING SUMMARY: {len(items)} items processed")
    logger.info(f"  Scraped OK : {len(fetched)}")
    logger.info(f"  Errors     : {len(errors)}")
    if exceptions:
        logger.info(f"  Exceptions : {len(exceptions)}")
    logger.info("-" * 60)

    # Group errors by status code
    if errors:
        error_by_code: dict[int, list[str]] = {}
        for e in errors:
            code = e["status_code"]
            error_by_code.setdefault(code, []).append(e["url"])

        logger.warning("Failed URLs by HTTP status:")
        for code, urls in sorted(error_by_code.items()):
            logger.warning(f"  HTTP {code}: {len(urls)} items")
            for url in urls[:5]:
                logger.warning(f"    - {url}")
            if len(urls) > 5:
                logger.warning(f"    ... and {len(urls) - 5} more")

    if exceptions:
        logger.error("Unhandled exceptions:")
        for ex in exceptions:
            logger.error(f"  {ex}")

    logger.info("=" * 60)

    await db.disconnect()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Fetch article content from RSS items"
    )
    parser.add_argument(
        "--batch-size", type=int, default=50, help="Items per batch"
    )
    parser.add_argument(
        "--concurrency", type=int, default=10, help="Max concurrent pages"
    )
    parser.add_argument(
        "--retry-errors", action="store_true", help="Retry failed items"
    )

    args = parser.parse_args()
    asyncio.run(run(args.batch_size, args.concurrency, args.retry_errors))

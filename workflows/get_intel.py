from playwright.async_api import async_playwright
import asyncio
from loguru import logger
from sqlalchemy import select
from connectors.database import db
from models.entities import Article
from models.entities import RssItem
from sqlalchemy.dialects.postgresql import insert


def common_prefix_length(*lists):
    if not lists:
        return 0

    for i, values in enumerate(zip(*lists)):
        if len(set(values)) != 1:
            return i

    return min(len(lst) for lst in lists)


def common_suffix_length(*lists):
    if not lists:
        return 0

    for i, values in enumerate(zip(*(reversed(lst) for lst in lists))):
        if len(set(values)) != 1:
            return i

    return min(len(lst) for lst in lists)


async def load_rss_items():
    """Load all RSS items from the database."""
    logger.info("Loading RSS items from database...")
    async with db.session() as session:
        result = await session.execute(select(RssItem))
        rss_items = result.scalars().all()
        logger.success(f"Loaded {len(rss_items)} RSS items")
        return rss_items


async def run_playwright_item(browser, data: dict):
    logger.info(f"Processing URL: {data['url']}")
    page = await browser.new_page()
    try:
        await page.goto(data["url"], wait_until="networkidle")
        text = await page.inner_text("body")
        return {"source_name": data["source_name"], "text": text, "url": data["url"]}
    finally:
        try:
            await page.close()
        except Exception:
            # If closing the page fails, continue to avoid leaking the browser
            pass


async def run_web_scraper(data: list[dict], concurrency: int = 4):
    # Launch a single browser instance and limit concurrent pages
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        semaphore = asyncio.Semaphore(concurrency)

        async def process_item(item: dict):
            async with semaphore:
                try:
                    return await run_playwright_item(browser, item)
                except Exception as e:
                    logger.error(f"Failed to process {item.get('url')}: {e}")
                    return None

        tasks = [process_item(item) for item in data]
        results = await asyncio.gather(*tasks, return_exceptions=False)

        # Filter out failures
        successes = [r for r in results if r is not None]
        logger.success(f"Scraping done: {len(successes)}/{len(data)} succeeded")

        return successes


async def run():
    """Main workflow function."""
    await db.connect()
    rss_items = await load_rss_items()
    async with db.session() as session:
        result = await session.execute(select(Article.url))
        existing_urls = {row[0] for row in result.all()}

    data_dict = [i.__dict__ for i in rss_items if i.url not in existing_urls]

    if not data_dict:
        logger.info("No new URLs to scrape; skipping web scraper")
        return

    data_content = await run_web_scraper(data_dict)

    words = [i["text"].split(" ") for i in data_content]
    content_indexes = common_prefix_length(*words), common_suffix_length(*words)

    new_articles = [
        " ".join(word_list[content_indexes[0] : len(word_list) - content_indexes[1]])
        for word_list in words
    ]
    for i, article in enumerate(new_articles):
        data_content[i]["text"] = article

    async with db.session() as session:
        stmt = (
            insert(Article)
            .values(data_content)
            .on_conflict_do_nothing(index_elements=[Article.url])
        )
        await session.execute(stmt)
        await session.commit()


if __name__ == "__main__":
    asyncio.run(run())

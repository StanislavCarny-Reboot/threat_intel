from playwright.async_api import async_playwright
import asyncio
from loguru import logger
from sqlalchemy import select
import re

from connectors.database import db
from models.entities import Article
from models.entities import RssItem


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


async def run_playwright(data: dict):
    logger.info(f"Processing URL: {data['url']}")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(data["url"], wait_until="networkidle")
        text = await page.inner_text("body")

        await browser.close()
    return {"source_name": data["source_name"], "text": text, "url": data["url"]}


async def run_web_scraper(data: list[dict]):
    tasks = [run_playwright(item) for item in data]
    results = await asyncio.gather(*tasks)
    logger.success("all done")

    return results


async def run():
    """Main workflow function."""
    await db.connect()
    rss_items = await load_rss_items()
    await db.disconnect()
    data_dict = [i.__dict__ for i in rss_items]
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
        articles = [Article(**item) for item in data_content]
        session.add_all(articles)
        await session.commit()

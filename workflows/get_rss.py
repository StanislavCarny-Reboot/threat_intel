import requests
from google import genai
from google.genai import types
from dotenv import load_dotenv
import json
import os
import asyncio
from datetime import datetime
from models.entities import RssItem, DataSources
from models.schemas import LLMRSSFeed
from loguru import logger
from connectors.database import db
import re
from tenacity import retry, wait_fixed, stop_after_attempt
from prompts.rss_extraction import (
    RSS_EXTRACTION_PROMPT,
    RSS_EXTRACTION_PROMPT_ERROR_HANDLING,
)
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import select
from main import mlflow


load_dotenv()


client = genai.Client(api_key=os.getenv("API_KEY"))


URL_PATTERN_WITH_OPTIONAL_PROTOCOL = (
    r"(?:https?://)?(?:www\.)?[a-zA-Z0-9-]+\.[a-zA-Z]{2,}(?:/[^\s]*)?"
)


def extract_urls(text: str) -> list[str]:
    pattern = URL_PATTERN_WITH_OPTIONAL_PROTOCOL
    urls = set(re.findall(pattern, text, re.IGNORECASE))

    return list(urls)


async def get_rss_feed(url: str) -> requests.Response | int:
    try:
        rss_feed_raw = await asyncio.to_thread(requests.get, url)
        if rss_feed_raw.status_code != 200:
            logger.error(
                f"Failed to fetch RSS feed from {url}, status code: {rss_feed_raw.status_code} reason: {rss_feed_raw.reason}"
            )
            return rss_feed_raw.status_code

        return rss_feed_raw
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching RSS feed from {url}: {e}")
        return None


@retry(wait=wait_fixed(2), stop=stop_after_attempt(3))
async def call_llm(rss_feed_raw: requests.Response) -> dict:

    system_instruction = RSS_EXTRACTION_PROMPT

    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-2.5-flash",
            contents=rss_feed_raw.text,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=LLMRSSFeed,
                system_instruction=system_instruction,
            ),
        )
        logger.info("LLM call successful")
        feed_data = json.loads(response.text)

        for item in feed_data["items"]:
            item["published_at"] = datetime.fromisoformat(item["published_at"])
            item["published_at"] = (
                item["published_at"].replace(tzinfo=None)
                if item["published_at"].tzinfo
                else item["published_at"]
            )

    except Exception as e:
        logger.error(f"Error calling LLM: {e}")
        system_instruction += RSS_EXTRACTION_PROMPT_ERROR_HANDLING.format(
            error_message=str(e)
        )
        logger.info(
            f"Retrying LLM call with error handling prompt :{system_instruction}"
        )
        raise e
    return feed_data


@mlflow.trace
async def process_source_atomic(source: DataSources) -> int:
    """Process a single source atomically: fetch RSS, call LLM, and save to DB in one operation"""
    try:
        # Step 1: Fetch RSS feed
        rss_feed_raw = await get_rss_feed(source.url)
        if rss_feed_raw != 200:
            logger.warning(f"Skipping source '{source.name}' due to fetch error")
            return rss_feed_raw

        # Step 2: Call LLM to process the feed
        try:
            feed_data = await call_llm(rss_feed_raw)
        finally:
            # Ensure the HTTP response is closed to free file descriptors
            try:
                rss_feed_raw.close()
            except Exception:
                pass

        # Step 3: Save to database immediately after successful LLM call
        async with db.session() as session:
            stmt = (
                insert(RssItem)
                .values(feed_data["items"])
                .on_conflict_do_nothing(index_elements=[RssItem.url])
            )
            await session.execute(stmt)
            await session.commit()

        items_count = len(feed_data.get("items", []))
        logger.info(
            f"Successfully processed source '{source.name}': {items_count} items"
        )
        return items_count

    except Exception as e:
        logger.error(f"Error processing source '{source.name}': {e}")
        return 0


async def run():
    await db.connect()
    logger.info("Database connected successfully")

    async with db.session() as session:
        result = await session.execute(
            select(DataSources).where(DataSources.active == "true")
        )
        sources = result.scalars().all()

    if not sources:
        logger.error("No active data sources found in database")
        return

    # Process each source atomically
    results = await asyncio.gather(
        *(process_source_atomic(src) for src in sources), return_exceptions=True
    )

    # Count successful results and log any exceptions
    successful_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"Source '{sources[i].name}' failed with exception: {result}")
        else:
            successful_results.append(result)

    total_items = sum(successful_results)
    successful_sources = len(successful_results)

    logger.info(
        f"Processed {len(sources)} sources; {successful_sources} successful; inserted {total_items} total items"
    )

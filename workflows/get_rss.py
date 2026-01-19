import requests
import yaml
from google import genai
from google.genai import types
from dotenv import load_dotenv
import json
import os
from datetime import datetime
from models.entities import RssItem
from models.schemas import LLMRSSFeed
import asyncio
from loguru import logger
from connectors.database import db
import re
from tenacity import retry, wait_fixed, stop_after_attempt


load_dotenv()


client = genai.Client(api_key=os.getenv("API_KEY"))


with open("data_sources/data_sources.yaml", "r") as file:
    data_sources = yaml.safe_load(file)


URL_PATTERN_WITH_OPTIONAL_PROTOCOL = (
    r"(?:https?://)?(?:www\.)?[a-zA-Z0-9-]+\.[a-zA-Z]{2,}(?:/[^\s]*)?"
)


def extract_urls(text: str) -> list[str]:
    pattern = URL_PATTERN_WITH_OPTIONAL_PROTOCOL
    urls = set(re.findall(pattern, text, re.IGNORECASE))

    return list(urls)


async def get_rss_feed(url: str):
    try:
        rss_feed_raw = requests.get(url)
        rss_feed_raw.raise_for_status()
        return rss_feed_raw
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching RSS feed: {e}")
        return None


@retry(wait=wait_fixed(2), stop=stop_after_attempt(3))
async def call_llm(rss_feed_raw):
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=rss_feed_raw.text,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=LLMRSSFeed,
                system_instruction="Extract the following fields from the RSS feed item: source_name, title, url, published_at",
            ),
        )
        logger.info("LLM call successful")
        feed_data = json.loads(response.text)

        for item in feed_data["items"]:
            item["published_at"] = datetime.strptime(
                item["published_at"], "%Y-%m-%d %H:%M:%SZ"
            )

    except Exception as e:
        logger.error(f"Error calling LLM: {e}")
        raise e
    return feed_data


async def run():

    rss_feed_raw = await get_rss_feed(data_sources["rss_feed"][0]["url"])
    feed_data = await call_llm(rss_feed_raw)

    await db.connect()
    logger.info("Database connected successfully")
    db_items = [RssItem(**item) for item in feed_data["items"]]
    async with db.session() as session:
        session.add_all(db_items)
        await session.commit()

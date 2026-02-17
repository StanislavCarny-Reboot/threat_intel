import requests
from google import genai
from google.genai import types
from dotenv import load_dotenv
import json
import os
import time
from datetime import datetime
from models.entities import RssItem, SourcesMasterList
from models.schemas import LLMRSSFeed
from loguru import logger
from tenacity import (
    retry,
    wait_exponential,
    stop_after_attempt,
    retry_if_exception_type,
)
from prompts.rss_extraction import (
    RSS_EXTRACTION_PROMPT,
    RSS_EXTRACTION_PROMPT_ERROR_HANDLING,
)
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import select, create_engine
from sqlalchemy.orm import sessionmaker
from prefect import task, flow
from connectors.database import Base

# from main import mlflow


load_dotenv()


def get_genai_client() -> genai.Client:
    """Get GenAI client - initialized on demand to avoid pickling issues"""
    return genai.Client(api_key=os.getenv("API_KEY"))


def get_sync_db_session():
    """Get synchronous database session"""
    database_url = os.getenv("DATABASE_URL")
    # Convert async URL to sync (replace postgresql+asyncpg with postgresql+psycopg2)
    sync_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
    engine = create_engine(sync_url, connect_args={"sslmode": "prefer"})
    Session = sessionmaker(bind=engine)
    return Session()


@task(
    name="fetch-rss-feed",
    retries=2,
    retry_delay_seconds=2,
    tags=["rss-fetch"],
)
def get_rss_feed(url: str) -> requests.Response | int:
    """
    Fetch RSS feed and limit content to ~50,000 tokens (~200,000 characters).
    This prevents overwhelming the LLM with extremely large feeds.
    """
    MAX_CHARS = 50_000

    try:
        rss_feed_raw = requests.get(url)
        if rss_feed_raw.status_code != 200:
            logger.error(
                f"Failed to fetch RSS feed from {url}, status code: {rss_feed_raw.status_code} reason: {rss_feed_raw.reason}"
            )
            return rss_feed_raw.status_code

        # Truncate content if it exceeds the limit
        original_length = len(rss_feed_raw.text)
        if original_length > MAX_CHARS:
            logger.warning(
                f"RSS feed from {url} is {original_length:,} chars. Truncating to {MAX_CHARS:,} chars (~12k tokens)"
            )
            # Create a mock response with truncated content
            rss_feed_raw._content = rss_feed_raw.text[:MAX_CHARS].encode("utf-8")

        return rss_feed_raw
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching RSS feed from {url}: {e}")
        return None


@task(
    name="call-llm-extraction",
    task_run_name="extract-{rss_feed_raw.url}",
    tags=["llm-api", "llm", "extraction"],
)
@retry(
    wait=wait_exponential(multiplier=2, min=5, max=60),  # 5s, 10s, 20s, 40s, 60s
    stop=stop_after_attempt(5),
    reraise=True,
)
def call_llm(rss_feed_raw: requests.Response) -> dict:
    import re

    system_instruction = RSS_EXTRACTION_PROMPT
    client = get_genai_client()  # Initialize client inside task

    try:
        response = client.models.generate_content(
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
        error_msg = str(e)

        # Check if it's a rate limit error (429)
        if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
            # Try to extract the suggested retry delay from the error message
            retry_match = re.search(r"retry in ([\d.]+)s", error_msg, re.IGNORECASE)
            if retry_match:
                retry_delay = float(retry_match.group(1))
                logger.warning(
                    f"Rate limit hit. API suggests waiting {retry_delay}s. Sleeping before retry..."
                )
                time.sleep(retry_delay + 2)  # Add 2 extra seconds as buffer
            else:
                logger.warning(
                    "Rate limit hit. Waiting 15s before retry (no delay specified in error)..."
                )
                time.sleep(15)

        logger.error(f"Error calling LLM: {e}")
        raise e
    return feed_data


# @mlflow.trace
@task(
    name="process-source",
    retries=1,
    retry_delay_seconds=5,
    task_run_name="process-{source.source_name}",
    tags=["global-rss-workflow", "rss-processing", "data-ingestion"],
)
def process_source_atomic(source: SourcesMasterList) -> int:
    """Process a single source atomically: fetch RSS, call LLM, and save to DB in one operation"""
    session = None
    try:
        # Step 1: Fetch RSS feed
        rss_feed_raw = get_rss_feed(source.source_url)
        if not isinstance(rss_feed_raw, requests.Response):
            logger.warning(
                f"Skipping source '{source.source_name}' due to fetch error (status: {rss_feed_raw})"
            )
            return 0

        # Step 2: Call LLM to process the feed
        try:
            feed_data = call_llm(rss_feed_raw)
        finally:
            # Ensure the HTTP response is closed to free file descriptors
            try:
                rss_feed_raw.close()
            except Exception:
                pass

        # Step 3: Save to database immediately after successful LLM call
        session = get_sync_db_session()

        # Ensure source_name is set for all items
        for item in feed_data["items"]:
            item["source_name"] = source.source_name

        stmt = (
            insert(RssItem)
            .values(feed_data["items"])
            .on_conflict_do_nothing(index_elements=[RssItem.url])
        )
        session.execute(stmt)
        session.commit()

        items_count = len(feed_data.get("items", []))
        logger.info(
            f"Successfully processed source '{source.source_name}': {items_count} items"
        )
        return items_count

    except Exception as e:
        logger.error(f"Error processing source '{source.source_name}': {e}")
        if session:
            session.rollback()
        return 0
    finally:
        if session:
            session.close()


@flow(name="rss-feed-processing", log_prints=True)
def run():
    logger.info("Starting RSS feed processing flow")

    # Get RSS sources from sources_master_list table
    session = get_sync_db_session()
    try:
        result = session.execute(
            select(SourcesMasterList).where(
                (SourcesMasterList.url_scraping_method == "RSS")
                & SourcesMasterList.is_active
            )
        )
        sources = result.scalars().all()
    finally:
        session.close()

    if not sources:
        logger.error("No RSS sources found in sources_master_list table")
        return

    logger.info(f"Found {len(sources)} RSS sources to process")

    # Process each source using Prefect concurrency (submit tasks in parallel)
    # Add a small stagger to avoid overwhelming the API at startup
    futures = []
    for i, src in enumerate(sources):
        futures.append(process_source_atomic.submit(src))
        # Add a small delay every 5 submissions to stagger the load
        if (i + 1) % 5 == 0 and i < len(sources) - 1:
            time.sleep(2)  # 2-second pause every 5 submissions

    # Wait for all tasks to complete and get results
    results = []
    for i, future in enumerate(futures):
        try:
            result = future.result()
            results.append(result)
        except Exception as e:
            logger.error(
                f"Source '{sources[i].source_name}' failed with exception: {e}"
            )
            results.append(0)

    # Count successful results
    successful_results = [r for r in results if r > 0]
    total_items = sum(successful_results)
    successful_sources = len(successful_results)

    logger.info(
        f"Processed {len(sources)} sources; {successful_sources} successful; inserted {total_items} total items"
    )


# Removed direct execution - use Prefect deployment instead
# To run: uv run deploy_rss_flow.py

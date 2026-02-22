"""Article content scraper - Prefect flow."""

from __future__ import annotations

import json
import time
from collections import defaultdict
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright
from prefect import flow, get_run_logger, task
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from connectors.database import get_sync_db_session
from models.entities import Article, ExtractedArticleUrl, SourceErrorLog


# --- Utility functions (pure) ---


def common_prefix_length(*lists) -> int:
    if not lists:
        return 0
    for i, values in enumerate(zip(*lists)):
        if len(set(values)) != 1:
            return i
    return min(len(lst) for lst in lists)


def common_suffix_length(*lists) -> int:
    if not lists:
        return 0
    for i, values in enumerate(zip(*(reversed(lst) for lst in lists))):
        if len(set(values)) != 1:
            return i
    return min(len(lst) for lst in lists)


# --- Prefect Tasks ---


@task(name="fetch-new-extracted-urls", tags=["scraping-db"])
def fetch_new_rss_items(limit: int = 0) -> list[dict]:
    """Load extracted article URLs that have no matching Article record yet."""
    logger = get_run_logger()
    session = get_sync_db_session()
    try:
        extracted = list(session.execute(select(ExtractedArticleUrl)).scalars().all())
        existing_urls: set[str] = {
            row[0] for row in session.execute(select(Article.url)).all()
        }
        new_items = [
            {
                "url": item.article_url_final,
                "source_name": item.source_url,
                "source_uuid": item.source_uuid,
                "article_uuid": item.article_uuid,
            }
            for item in extracted
            if item.article_url_final and item.article_url_final not in existing_urls
        ]
        if limit > 0:
            new_items = new_items[:limit]
        logger.info(
            "Extracted total=%d existing=%d new=%d limit=%s",
            len(extracted),
            len(existing_urls),
            len(new_items),
            limit or "none",
        )
        return new_items
    finally:
        session.close()


def _do_scrape(url: str) -> str:
    """Launch a headless browser and return the page body text."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            return page.inner_text("body")
        finally:
            page.close()
            browser.close()


@task(name="scrape-source-urls", tags=["scraping"])
def scrape_source_urls(items: list[dict]) -> tuple[list[dict], list[dict]]:
    """Scrape all URLs for one source sequentially with a 2 s fixed delay between requests."""
    logger = get_run_logger()
    scraped: list[dict] = []
    errors: list[dict] = []

    for i, item in enumerate(items):
        if i > 0:
            time.sleep(2)
        url = item["url"]
        try:
            text = _do_scrape(url)
            scraped.append({"source_name": item["source_name"], "text": text, "url": url})
            logger.info("Scraped %s", url)
        except Exception as exc:
            logger.warning("Failed to scrape %s: %s", url, exc)
            errors.append(
                {
                    "source_uuid": item["source_uuid"],
                    "article_uuid": item["article_uuid"],
                    "url": url,
                    "error_message": str(exc),
                }
            )

    return scraped, errors


@task(name="save-articles", tags=["scraping-db"])
def save_articles(articles: list[dict]) -> int:
    """Upsert scraped articles into the database, ignoring duplicates."""
    logger = get_run_logger()
    session = get_sync_db_session()
    try:
        stmt = (
            insert(Article)
            .values(articles)
            .on_conflict_do_nothing(index_elements=[Article.url])
        )
        result = session.execute(stmt)
        session.commit()
        inserted = result.rowcount or 0
        logger.info("Saved %d new articles (duplicates skipped)", inserted)
        return inserted
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@task(name="save-scraping-errors", tags=["scraping-db"])
def save_scraping_errors(errors: list[dict]) -> int:
    """Persist scraping failures to source_error_log with JSON error payload."""
    logger = get_run_logger()
    session = get_sync_db_session()
    try:
        now = datetime.now(tz=timezone.utc)
        records = [
            SourceErrorLog(
                source_uuid=e["source_uuid"],
                source_url=e["url"],
                status_code="SCRAPE_ERROR",
                error_message=json.dumps(
                    {
                        "source_uuid": e["source_uuid"],
                        "article_uuid": e["article_uuid"],
                        "error_message": e["error_message"],
                    }
                ),
                detected_at=now,
                created_at=now,
            )
            for e in errors
        ]
        session.add_all(records)
        session.commit()
        logger.info("Saved %d scraping errors", len(records))
        return len(records)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# --- Prefect Flow ---


@flow(name="get-link-content", log_prints=True)
def run(limit: int = 0) -> None:
    """Scrape article body text for all new RSS items and persist to the database."""
    logger = get_run_logger()
    new_items = fetch_new_rss_items(limit)

    if not new_items:
        logger.info("No new URLs to scrape; skipping web scraper")
        return

    grouped: dict[str, list[dict]] = defaultdict(list)
    for item in new_items:
        grouped[item["source_uuid"]].append(item)

    futures = [scrape_source_urls.submit(items) for items in grouped.values()]
    results = [f.result(raise_on_failure=False) for f in futures]

    all_scraped: list[dict] = []
    all_errors: list[dict] = []
    for result in results:
        if isinstance(result, tuple):
            scraped, errors = result
            all_scraped.extend(scraped)
            all_errors.extend(errors)
        else:
            logger.error("Source scraping task failed: %s", result)

    logger.info(
        "Scraping done: %d/%d succeeded, %d failed",
        len(all_scraped),
        len(new_items),
        len(all_errors),
    )

    if all_errors:
        save_scraping_errors(all_errors)

    if not all_scraped:
        logger.warning("No articles scraped successfully; nothing to save")
        return

    words = [article["text"].split(" ") for article in all_scraped]
    prefix = common_prefix_length(*words)
    suffix = common_suffix_length(*words)

    for article, word_list in zip(all_scraped, words):
        article["text"] = " ".join(word_list[prefix : len(word_list) - suffix])

    save_articles(all_scraped)


if __name__ == "__main__":
    run.serve()

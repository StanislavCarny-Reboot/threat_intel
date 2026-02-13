"""
Script 3: Clean article content using regex patterns.

This script:
1. Queries Article entries that haven't been cleaned
2. Applies source-specific regex patterns to remove headers/footers
3. Updates Article text with cleaned content
"""

import argparse
import asyncio
import re
import sys
from pathlib import Path

# Add parent directory to path for imports when running directly
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))

from bs4 import BeautifulSoup
from loguru import logger
from sqlalchemy import select, update
from dotenv import load_dotenv

from connectors.database import db
from models.entities import Article
from rss_regex.config.source_patterns import get_source_config, ContentCleanPatterns


load_dotenv()


def html_to_text(html_content: str) -> str:
    """Convert HTML to plain text, preserving structure."""
    soup = BeautifulSoup(html_content, "html.parser")

    # Remove script and style elements
    for element in soup(["script", "style", "nav", "header", "footer", "aside"]):
        element.decompose()

    # Get text with newlines for block elements
    text = soup.get_text(separator="\n", strip=True)

    # Clean up excessive whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" {2,}", " ", text)

    return text.strip()


def apply_clean_patterns(text: str, patterns: ContentCleanPatterns) -> str:
    """Apply source-specific cleaning patterns to text."""
    cleaned = text

    # Apply header patterns (remove from beginning)
    for pattern in patterns.header_patterns:
        match = pattern.search(cleaned)
        if match:
            cleaned = cleaned[match.end() :].strip()

    # Apply footer patterns (remove from end)
    for pattern in patterns.footer_patterns:
        match = pattern.search(cleaned)
        if match:
            cleaned = cleaned[: match.start()].strip()

    # Apply remove patterns throughout
    for pattern in patterns.remove_patterns:
        cleaned = pattern.sub("", cleaned)

    # Extract main content if pattern exists
    if patterns.main_content_pattern:
        match = patterns.main_content_pattern.search(cleaned)
        if match:
            cleaned = match.group(1) if match.groups() else match.group(0)

    # Final cleanup
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"^\s+", "", cleaned, flags=re.MULTILINE)

    return cleaned.strip()


def clean_article_content(content: str, source_name: str) -> str:
    """
    Clean article content using source-specific patterns.

    Args:
        content: Raw HTML or text content
        source_name: Name of the source for pattern lookup

    Returns:
        Cleaned text content
    """
    # Convert HTML to text if needed
    if "<html" in content.lower() or "<body" in content.lower():
        text = html_to_text(content)
    else:
        text = content

    # Get source-specific patterns
    config = get_source_config(source_name)

    # Apply cleaning patterns
    cleaned = apply_clean_patterns(text, config.clean_patterns)

    return cleaned


async def process_article(article: Article) -> bool:
    """
    Clean a single article and update in database.

    Returns:
        True if successful, False otherwise
    """
    try:
        original_length = len(article.text)
        cleaned = clean_article_content(article.text, article.source_name)
        cleaned_length = len(cleaned)

        # Only update if we actually changed something
        if cleaned != article.text:
            async with db.session() as session:
                stmt = (
                    update(Article).where(Article.id == article.id).values(text=cleaned)
                )
                await session.execute(stmt)
                await session.commit()

            reduction = ((original_length - cleaned_length) / original_length) * 100
            logger.debug(
                f"Cleaned article {article.id}: {original_length} -> {cleaned_length} "
                f"({reduction:.1f}% reduction)"
            )

        return True

    except Exception as e:
        logger.error(f"Error cleaning article {article.id}: {e}")
        return False


async def run(batch_size: int = 100, dry_run: bool = False):
    """
    Main entry point for article cleaning.

    Args:
        batch_size: Number of articles to process per batch
        dry_run: If True, show what would be cleaned without saving
    """
    await db.connect()
    logger.info("Database connected")

    # Query articles to clean
    async with db.session() as session:
        result = await session.execute(select(Article).limit(batch_size))
        articles = result.scalars().all()

    if not articles:
        logger.info("No articles to clean")
        await db.disconnect()
        return

    logger.info(f"Cleaning {len(articles)} articles")

    if dry_run:
        # Show sample of what would be cleaned
        for article in articles[:3]:
            original = (
                article.text[:500] + "..."
                if len(article.text) > 500
                else article.text
            )
            cleaned = clean_article_content(article.text, article.source_name)
            cleaned_preview = cleaned[:500] + "..." if len(cleaned) > 500 else cleaned

            logger.info(f"\n--- Article {article.id} ({article.source_name}) ---")
            logger.info(f"Original ({len(article.text)} chars): {original}")
            logger.info(f"Cleaned ({len(cleaned)} chars): {cleaned_preview}")
        await db.disconnect()
        return

    # Process articles
    results = await asyncio.gather(
        *(process_article(article) for article in articles), return_exceptions=True
    )

    success = sum(1 for r in results if r is True)
    failed = sum(1 for r in results if r is False or isinstance(r, Exception))

    logger.info(f"Cleaning complete: {success} successful, {failed} failed")

    await db.disconnect()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Clean article content using regex"
    )
    parser.add_argument(
        "--batch-size", type=int, default=100, help="Articles per batch"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview without saving"
    )

    args = parser.parse_args()
    asyncio.run(run(args.batch_size, args.dry_run))

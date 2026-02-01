#!/usr/bin/env -S uv run python
"""Export articles from database to XLSX format using pandas."""

import asyncio
import sys
from datetime import datetime
from pathlib import Path

# Add project root to Python path for direct execution
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from loguru import logger
from sqlalchemy import select

from connectors.database import db
from models.entities import Article


async def export_articles_to_xlsx(output_file: str | None = None) -> str:
    """
    Query all articles from the database and export to XLSX format.

    Args:
        output_file: Optional path to output file. If not provided, generates
                    a timestamped filename in the current directory.

    Returns:
        Path to the created XLSX file
    """
    # Connect to database
    await db.connect()
    logger.info("Database connected successfully")

    # Query all articles
    async with db.session() as session:
        result = await session.execute(select(Article))
        articles = result.scalars().all()

    if not articles:
        logger.warning("No articles found in database")
        return None

    logger.info(f"Found {len(articles)} articles to export")

    pd.DataFrame

    # Generate output filename if not provided
    if output_file is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"data/articles_export_{timestamp}.xlsx"

    # Ensure output directory exists
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Convert articles to DataFrame
    data = []
    for article in articles:
        data.append(
            {
                "ID": article.id,
                "Source Name": article.source_name,
                "URL": article.url,
                "Text": article.text,
                "Published At": article.published_at,
                "Created At": article.created_at,
            }
        )

    return data
    pd.DataFrame(data).to_excel(output_file, index=False)

    logger.info(f"Successfully exported {len(articles)} articles to {output_file}")
    return output_file


async def main():
    """Main entry point for the export script."""
    try:
        output_file = await export_articles_to_xlsx()
        if output_file:
            print(f"Export completed successfully: {output_file}")
        else:
            print("No articles to export")
    except Exception as e:
        logger.error(f"Error during export: {e}")
        raise
    finally:
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())

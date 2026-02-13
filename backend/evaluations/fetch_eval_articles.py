#!/usr/bin/env -S uv run python
"""
Fetch article content from URLs in Active_Campaigns_Randomized.xlsx.

This script:
1. Reads URLs from data/urls/Active_Campaigns_Randomized.xlsx
2. Fetches article content using Playwright
3. Saves articles to Excel file in outputs/ directory
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path

# Add project root to Python path for direct execution
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from dotenv import load_dotenv
from loguru import logger
from playwright.async_api import async_playwright

load_dotenv()


async def fetch_article_content(browser, url: str) -> dict:
    """
    Fetch article content from a single URL using Playwright.

    Args:
        browser: Playwright browser instance
        url: URL to fetch

    Returns:
        dict: Contains url, status_code, content, error
    """
    page = await browser.new_page()
    try:
        response = await page.goto(url, wait_until="networkidle", timeout=30000)
        status_code = response.status if response else 0

        if status_code == 200:
            text = await page.inner_text("body")
            logger.info(f"[{status_code}] Fetched: {url} ({len(text)} chars)")
            return {
                "url": url,
                "status_code": status_code,
                "content": text,
                "error": None,
                "fetched_at": datetime.now()
            }
        else:
            error = f"HTTP {status_code}"
            logger.warning(f"[{status_code}] Failed: {url}")
            return {
                "url": url,
                "status_code": status_code,
                "content": None,
                "error": error,
                "fetched_at": datetime.now()
            }
    except Exception as e:
        error_msg = str(e)[:200]
        logger.warning(f"[ERR] Failed: {url} - {error_msg}")
        return {
            "url": url,
            "status_code": 0,
            "content": None,
            "error": error_msg,
            "fetched_at": datetime.now()
        }
    finally:
        try:
            await page.close()
        except Exception:
            pass


async def run(
    input_file: str = None,
    output_file: str = None,
    concurrency: int = 5,
    limit: int = None
):
    """
    Main function to fetch articles from URLs and save to Excel.

    Args:
        input_file: Path to input Excel file with URLs
        output_file: Path to output Excel file
        concurrency: Maximum concurrent browser pages
        limit: Maximum number of URLs to process (None for all)
    """
    # Determine input file
    if input_file is None:
        input_file = Path(__file__).parent.parent / "data" / "urls" / "Active_Campaigns_Randomized.xlsx"
    else:
        input_file = Path(input_file)

    if not input_file.exists():
        logger.error(f"Input file not found: {input_file}")
        return

    logger.info(f"Loading URLs from {input_file}")

    # Load URLs from Excel
    df = pd.read_excel(input_file)

    # Try to find URL column (handle different possible column names)
    url_column = None
    for col in df.columns:
        if col.lower() in ['url', 'urls', 'link', 'links']:
            url_column = col
            break

    if url_column is None:
        logger.error(f"No URL column found. Available columns: {list(df.columns)}")
        return

    # Extract URLs
    urls = df[url_column].dropna().unique().tolist()

    if limit:
        urls = urls[:limit]

    logger.info(f"Found {len(urls)} unique URLs to fetch")

    # Fetch articles using Playwright
    semaphore = asyncio.Semaphore(concurrency)
    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        async def fetch_with_limit(url):
            async with semaphore:
                return await fetch_article_content(browser, url)

        logger.info(f"Fetching articles (concurrency={concurrency})...")
        results = await asyncio.gather(
            *(fetch_with_limit(url) for url in urls),
            return_exceptions=True
        )

        await browser.close()

    # Process results
    successful = [r for r in results if isinstance(r, dict) and r["status_code"] == 200]
    failed = [r for r in results if isinstance(r, dict) and r["status_code"] != 200]
    exceptions = [r for r in results if isinstance(r, Exception)]

    logger.info("=" * 60)
    logger.info(f"FETCH SUMMARY: {len(urls)} URLs processed")
    logger.info(f"  Success    : {len(successful)}")
    logger.info(f"  Failed     : {len(failed)}")
    if exceptions:
        logger.info(f"  Exceptions : {len(exceptions)}")
    logger.info("=" * 60)

    # Prepare output data
    output_data = []
    for result in results:
        if isinstance(result, dict):
            output_data.append({
                "URL": result["url"],
                "Status Code": result["status_code"],
                "Content": result["content"],
                "Error": result["error"],
                "Fetched At": result["fetched_at"]
            })

    output_df = pd.DataFrame(output_data)

    # Generate output filename if not provided
    if output_file is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path(__file__).parent.parent / "outputs"
        output_file = output_dir / f"eval_articles_{timestamp}.xlsx"
    else:
        output_file = Path(output_file)

    # Ensure output directory exists
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Save to Excel
    with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
        output_df.to_excel(writer, index=False, sheet_name="Articles")

        # Auto-adjust column widths
        worksheet = writer.sheets["Articles"]
        for idx, col in enumerate(output_df.columns):
            max_length = max(
                output_df[col].astype(str).apply(len).max(),
                len(str(col))
            )
            max_length = min(max_length + 2, 100)
            col_letter = (
                chr(65 + idx)
                if idx < 26
                else chr(65 + idx // 26 - 1) + chr(65 + idx % 26)
            )
            worksheet.column_dimensions[col_letter].width = max_length

    logger.info(f"Results saved to {output_file}")
    logger.info(f"  - {len(successful)} articles with content")
    logger.info(f"  - {len(failed)} failed fetches")

    return output_file


async def main():
    """Main entry point for the script."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Fetch article content from URLs in Excel file"
    )
    parser.add_argument(
        "--input-file",
        type=str,
        default=None,
        help="Input Excel file with URLs (default: data/urls/Active_Campaigns_Randomized.xlsx)"
    )
    parser.add_argument(
        "--output-file",
        type=str,
        default=None,
        help="Output Excel file path (default: outputs/eval_articles_TIMESTAMP.xlsx)"
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=5,
        help="Maximum concurrent browser pages (default: 5)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of URLs to process (default: all)"
    )

    args = parser.parse_args()

    try:
        await run(
            input_file=args.input_file,
            output_file=args.output_file,
            concurrency=args.concurrency,
            limit=args.limit
        )
    except Exception as e:
        logger.error(f"Error during fetch: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env -S uv run python
"""Generate article summaries using two different prompts."""

import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path

# Add project root to Python path for direct execution
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from dotenv import load_dotenv
from google import genai
from google.genai import types
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_fixed

from prompts.article_summary import SUMMARY_1, SUMMARY_2

load_dotenv()

client = genai.Client(api_key=os.getenv("API_KEY"))


@retry(wait=wait_fixed(2), stop=stop_after_attempt(3))
async def generate_summary(article_text: str, prompt: str, article_url: str) -> str:
    """
    Call the LLM to generate a summary using the provided prompt.

    Args:
        article_text: The text content of the article
        prompt: The system prompt to use for summarization
        article_url: The URL of the article (for logging)

    Returns:
        str: Generated summary text
    """
    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-2.5-flash",
            contents=article_text,
            config=types.GenerateContentConfig(
                system_instruction=prompt,
                temperature=0.0,
            ),
        )
        logger.info(f"Summary generated successfully for article: {article_url}")
        return response.text.strip()

    except Exception as e:
        logger.error(f"Error calling LLM for article {article_url}: {e}")
        raise e


async def process_article(article_row: dict, row_index: int) -> dict:
    """
    Process a single article: generate both summaries.

    Args:
        article_row: Dictionary containing article data (Content, URL, etc.)
        row_index: Index of the row in the DataFrame

    Returns:
        dict: Contains row_index and both summaries
    """
    try:
        # Generate both summaries concurrently
        summary_1_task = generate_summary(
            article_row["Content"], SUMMARY_1, article_row["URL"]
        )
        summary_2_task = generate_summary(
            article_row["Content"], SUMMARY_2, article_row["URL"]
        )

        summary_1, summary_2 = await asyncio.gather(summary_1_task, summary_2_task)

        logger.info(
            f"Article {row_index} ({article_row['URL']}) - "
            f"Summary 1: {len(summary_1)} chars, Summary 2: {len(summary_2)} chars"
        )

        return {
            "row_index": row_index,
            "summary_1": summary_1,
            "summary_2": summary_2,
        }

    except Exception as e:
        logger.error(f"Error processing article {row_index}: {e}")
        return {
            "row_index": row_index,
            "summary_1": "Error",
            "summary_2": "Error",
        }


async def run(input_file: str = None, output_file: str = None):
    """Main function to process all articles and generate summaries.

    Args:
        input_file: Path to input Excel file. If None, uses outputs/my_articles.xlsx
        output_file: Path to output Excel file. If None, overwrites input file
    """
    # Find input file
    if input_file is None:
        input_file = Path(__file__).parent.parent / "outputs" / "my_articles.xlsx"
    else:
        input_file = Path(input_file)

    if not input_file.exists():
        logger.error(f"Input file not found: {input_file}")
        return

    logger.info(f"Loading articles from {input_file}")

    # Load articles from Excel
    df = pd.read_excel(input_file)

    if df.empty:
        logger.warning("No articles found in file")
        return

    # Filter out rows with missing Content or error status
    df_valid = df[
        (df["Content"].notna()) & (df["Content"] != "") & (df["Status Code"] == 200)
    ].copy()

    if df_valid.empty:
        logger.warning("No valid articles with content found")
        return

    logger.info(
        f"Found {len(df_valid)} valid articles to summarize (out of {len(df)} total)"
    )

    # Convert DataFrame to list of dicts with row indices
    articles = [{"row_index": idx, **row} for idx, row in df_valid.iterrows()]

    # Process articles in batches to avoid overwhelming the LLM API
    batch_size = 5
    all_results = []

    for i in range(0, len(articles), batch_size):
        batch = articles[i : i + batch_size]
        logger.info(f"Processing batch {i // batch_size + 1} ({len(batch)} articles)")

        # Process batch concurrently
        results = await asyncio.gather(
            *(process_article(article, article["row_index"]) for article in batch),
            return_exceptions=True,
        )

        # Collect results
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Batch processing error: {result}")
            else:
                all_results.append(result)

        # Small delay between batches to avoid rate limiting
        if i + batch_size < len(articles):
            await asyncio.sleep(1)

    # Add summary results to DataFrame
    df["summary_1"] = ""
    df["summary_2"] = ""

    for result in all_results:
        row_idx = result["row_index"]
        df.at[row_idx, "summary_1"] = result["summary_1"]
        df.at[row_idx, "summary_2"] = result["summary_2"]

    # Generate output filename if not provided
    if output_file is None:
        output_file = input_file  # Overwrite the input file
    else:
        output_file = Path(output_file)

    # Ensure output directory exists
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Save to Excel with formatting
    with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Articles")

        # Auto-adjust column widths
        worksheet = writer.sheets["Articles"]
        for idx, col in enumerate(df.columns):
            max_length = max(df[col].astype(str).apply(len).max(), len(str(col)))
            # Limit width to 100 characters
            max_length = min(max_length + 2, 100)
            col_letter = (
                chr(65 + idx)
                if idx < 26
                else chr(65 + idx // 26 - 1) + chr(65 + idx % 26)
            )
            worksheet.column_dimensions[col_letter].width = max_length

    # Summary statistics
    success_count = sum(
        1
        for r in all_results
        if r.get("summary_1") != "Error" and r.get("summary_2") != "Error"
    )

    logger.info(
        f"Summarization complete: {success_count} articles successfully summarized "
        f"(out of {len(all_results)} processed)"
    )
    logger.info(f"Results saved to {output_file}")


async def main():
    """Main entry point for the script."""
    try:
        await run()
    except Exception as e:
        logger.error(f"Error during summarization: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())

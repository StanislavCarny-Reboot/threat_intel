#!/usr/bin/env -S uv run python
"""Classify articles as cyber attack campaigns or general news using LLM."""

import asyncio
import json
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

from models.schemas import ArticleClassification
from prompts.attack_classification import ATTACK_CLASSIFICATION_PROMPT

load_dotenv()

client = genai.Client(api_key=os.getenv("API_KEY"))


@retry(wait=wait_fixed(2), stop=stop_after_attempt(3))
async def classify_article(article_text: str, article_url: str) -> dict:
    """
    Call the LLM to classify an article as a cyber attack campaign or general news.

    Args:
        article_text: The text content of the article
        article_url: The URL of the article (for logging)

    Returns:
        dict: Classification result with 'classification', 'confidence', and 'reasoning'
    """
    system_instruction = ATTACK_CLASSIFICATION_PROMPT

    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            # model="gemini-2.5-flash",
            model="gemini-3-pro-preview",
            contents=article_text,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ArticleClassification,
                system_instruction=system_instruction,
            ),
        )
        logger.info(f"LLM classification successful for article: {article_url}")
        classification_data = json.loads(response.text)
        return classification_data

    except Exception as e:
        logger.error(f"Error calling LLM for article {article_url}: {e}")
        raise e


async def process_article(article_row: dict) -> dict:
    """
    Process a single article: classify it using LLM and return the result.

    Args:
        article_row: Dictionary containing article data (ID, Text, URL, etc.)

    Returns:
        dict: Contains article_id and classification data
    """
    try:
        # Call LLM to classify the article
        classification = await classify_article(article_row["Text"], article_row["URL"])

        logger.info(
            f"Article {article_row['ID']} classified as '{classification['classification']}' "
            f"with {classification['confidence']} confidence"
        )

        return {
            "article_id": article_row["ID"],
            "classification": classification["classification"],
            "confidence": classification["confidence"],
            "reasoning": classification["reasoning"],
        }

    except Exception as e:
        logger.error(f"Error processing article {article_row['ID']}: {e}")
        return {
            "article_id": article_row["ID"],
            "classification": "Error",
            "confidence": "N/A",
            "reasoning": "",
        }


async def run(input_file: str = None, output_file: str = None):
    """Main function to process all articles and classify them.

    Args:
        input_file: Path to input Excel file. If None, uses latest file in data/
        output_file: Path to output Excel file. If None, generates timestamped filename
    """
    # Find input file
    if input_file is None:
        data_dir = Path(__file__).parent.parent / "data"
        excel_files = list(data_dir.glob("articles_*.xlsx"))
        if not excel_files:
            logger.error("No article export files found in data/")
            return
        input_file = max(excel_files, key=lambda p: p.stat().st_mtime)
    else:
        input_file = Path(input_file)

    logger.info(f"Loading articles from {input_file}")

    # Load articles from Excel
    df = pd.read_excel(input_file, sheet_name="Articles")

    if df.empty:
        logger.warning("No articles found in file")
        return

    logger.info(f"Found {len(df)} articles to classify")

    # Convert DataFrame to list of dicts

    dff = df[~df["Threat Intel"].isna()]
    articles = dff.to_dict("records")

    # Process articles in batches to avoid overwhelming the LLM API
    batch_size = 10
    all_results = []

    for i in range(0, len(articles), batch_size):
        batch = articles[i : i + batch_size]
        logger.info(f"Processing batch {i // batch_size + 1} ({len(batch)} articles)")

        # Process batch concurrently
        results = await asyncio.gather(
            *(process_article(article) for article in batch),
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

    # Add classification results to DataFrame
    classification_map = {r["article_id"]: r for r in all_results}
    dff["Classification"] = dff["ID"].map(
        lambda x: classification_map.get(x, {}).get("classification", "Error")
    )
    dff["Confidence"] = dff["ID"].map(
        lambda x: classification_map.get(x, {}).get("confidence", "N/A")
    )
    dff["Reasoning"] = dff["ID"].map(
        lambda x: classification_map.get(x, {}).get("reasoning", "")
    )

    # Generate output filename if not provided
    if output_file is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = (
            Path(__file__).parent.parent
            / "data"
            / f"articles_classified_{timestamp}.xlsx"
        )
    else:
        output_file = Path(output_file)

    # Ensure output directory exists
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Save to Excel with formatting
    with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
        dff.to_excel(writer, index=False, sheet_name="Classified Articles")

        # Auto-adjust column widths
        worksheet = writer.sheets["Classified Articles"]
        for idx, col in enumerate(dff.columns):
            max_length = max(dff[col].astype(str).apply(len).max(), len(str(col)))
            # Limit width to 100 characters
            max_length = min(max_length + 2, 100)
            col_letter = (
                chr(65 + idx)
                if idx < 26
                else chr(65 + idx // 26 - 1) + chr(65 + idx % 26)
            )
            worksheet.column_dimensions[col_letter].width = max_length

    # Summary statistics
    attack_campaigns = sum(
        1 for r in all_results if r["classification"] == "Cyber Attack Campaign"
    )
    general_news = sum(1 for r in all_results if r["classification"] == "General News")
    not_sure = sum(1 for r in all_results if r["classification"] == "Not Sure")

    logger.info(
        f"Classification complete: {attack_campaigns} attack campaigns, "
        f"{general_news} general news, {not_sure} not sure"
    )
    logger.info(f"Results saved to {output_file}")


async def main():
    """Main entry point for the script."""
    try:
        await run()
    except Exception as e:
        logger.error(f"Error during classification: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())

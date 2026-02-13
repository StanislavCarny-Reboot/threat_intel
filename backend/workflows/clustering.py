#!/usr/bin/env -S uv run python
"""Cluster articles about cyber attack campaigns using LLM."""

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

# Load environment variables BEFORE importing any local modules
load_dotenv()

from google import genai
from google.genai import types
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_fixed

from models.schemas import ClusteringResult
from prompts.article_summary import SUMMARY_1, SUMMARY_2
from prompts.clustering import CLUSTERING

client = genai.Client(api_key=os.getenv("API_KEY"))


@retry(wait=wait_fixed(2), stop=stop_after_attempt(3))
async def summarize_article(
    article_text: str, article_url: str, prompt_version: int = 1
) -> str:
    """
    Generate a summary of an article for clustering purposes.

    Args:
        article_text: The cleaned text content of the article
        article_url: The URL of the article (for logging)
        prompt_version: Which clustering prompt to use (1 or 2)

    Returns:
        str: Article summary optimized for clustering
    """
    system_instruction = SUMMARY_1 if prompt_version == 1 else SUMMARY_2

    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-3-pro-preview",
            contents=article_text,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
            ),
        )
        logger.info(f"Summary generated for article: {article_url}")
        return response.text.strip()

    except Exception as e:
        logger.error(f"Error generating summary for article {article_url}: {e}")
        raise e


@retry(wait=wait_fixed(2), stop=stop_after_attempt(3))
async def cluster_articles(article_summaries: list[dict[str, str]]) -> ClusteringResult:
    """
    Cluster articles based on their summaries using LLM with structured output.

    Args:
        article_summaries: List of dicts with 'url' and 'summary' keys

    Returns:
        ClusteringResult: Structured clustering result with campaigns and grouped URLs
    """
    # Build prompt content with summaries in the format expected by CLUSTERING prompt
    summaries_text = "\n\n".join(
        [
            f"[{idx}]\nURL: {item['url']}\nSUMMARY: {item['summary']}"
            for idx, item in enumerate(article_summaries)
        ]
    )

    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-3-pro-preview",
            contents=summaries_text,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ClusteringResult,
                system_instruction=CLUSTERING,
            ),
        )
        logger.info(f"Clustering completed successfully")
        clustering_data = json.loads(response.text)
        return ClusteringResult(**clustering_data)

    except Exception as e:
        logger.error(f"Error clustering articles: {e}")
        raise e


async def cluster_threat_articles(
    articles: list[dict], prompt_version: int = 1, batch_size: int = 5
) -> ClusteringResult:
    """
    Main function to summarize and cluster threat intelligence articles.

    Args:
        articles: List of dicts with 'cleaned_text' and 'url' keys
        prompt_version: Which clustering prompt to use (1=detailed, 2=ultra-compact)
        batch_size: Number of articles to process concurrently in each batch

    Returns:
        ClusteringResult: Structured clustering result
    """
    logger.info(f"Starting clustering for {len(articles)} articles")

    # Step 1: Generate summaries for all articles
    all_summaries = []

    for i in range(0, len(articles), batch_size):
        batch = articles[i : i + batch_size]
        logger.info(f"Summarizing batch {i // batch_size + 1} ({len(batch)} articles)")

        # Process batch concurrently
        summaries = await asyncio.gather(
            *(
                summarize_article(
                    article["cleaned_text"], article["url"], prompt_version
                )
                for article in batch
            ),
            return_exceptions=True,
        )

        # Collect successful summaries
        for article, summary in zip(batch, summaries):
            if isinstance(summary, Exception):
                logger.error(f"Failed to summarize {article['url']}: {summary}")
            else:
                all_summaries.append({"url": article["url"], "summary": summary})

        # Small delay between batches to avoid rate limiting
        if i + batch_size < len(articles):
            await asyncio.sleep(1)

    logger.info(f"Generated {len(all_summaries)} summaries")

    # Step 2: Cluster the summarized articles
    clustering_result = await cluster_articles(all_summaries)

    logger.info(f"Identified {len(clustering_result.clusters)} clusters")

    return clustering_result


async def run_clustering_from_summaries(
    summary_column: str, input_file: str = None, output_file: str = None
):
    """
    Run clustering on pre-generated summaries from Excel file.

    Args:
        summary_column: Column name with summaries ('summary_1' or 'summary_2')
        input_file: Path to input Excel file with summaries
        output_file: Path to output Excel file. If None, generates timestamped filename
    """
    # Use default input file if not provided
    if input_file is None:
        input_file = Path(__file__).parent.parent / "outputs" / "summary.xlsx"
    else:
        input_file = Path(input_file)

    logger.info(f"Loading summaries from {input_file} (column: {summary_column})")

    # Load summaries from Excel
    df = pd.read_excel(input_file)

    # Filter out rows where the summary column is NaN
    df = df[df[summary_column].notna()]

    if df.empty:
        logger.warning(f"No valid summaries found in column {summary_column}")
        return

    logger.info(f"Found {len(df)} articles with summaries in {summary_column}")

    # Prepare summaries for clustering
    article_summaries = []
    for _, row in df.iterrows():
        article_summaries.append(
            {
                "url": row["URL"],
                "summary": row[summary_column],
            }
        )

    # Run clustering directly on summaries (no need to regenerate them)
    logger.info(f"Starting clustering for {len(article_summaries)} articles")
    clustering_result = await cluster_articles(article_summaries)

    # Prepare output data
    output_data = []
    for cluster in clustering_result.clusters:
        logger.debug(f"Processing cluster '{cluster.campaign_name}' with {len(cluster.article_urls)} URLs: {cluster.article_urls}")
        if not cluster.article_urls:
            logger.warning(f"Cluster '{cluster.campaign_name}' has no article URLs!")
        for url in cluster.article_urls:
            output_data.append(
                {
                    "Campaign Name": cluster.campaign_name,
                    "Article URL": url,
                    "Reasoning": cluster.reasoning,
                    "Cluster Urls": "\n".join(cluster.article_urls),
                }
            )

    output_df = pd.DataFrame(output_data)
    logger.info(f"Created DataFrame with {len(output_df)} rows from {len(clustering_result.clusters)} clusters")

    # Generate output filename if not provided
    if output_file is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = (
            Path(__file__).parent.parent
            / "outputs"
            / f"articles_clustered_{summary_column}_{timestamp}.xlsx"
        )
    else:
        output_file = Path(output_file)

    # Ensure output directory exists
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Save to Excel
    with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
        output_df.to_excel(writer, index=False, sheet_name="Clustered Articles")

        # Auto-adjust column widths
        worksheet = writer.sheets["Clustered Articles"]
        for idx, col in enumerate(output_df.columns):
            max_length = max(output_df[col].astype(str).apply(len).max(), len(str(col)))
            max_length = min(max_length + 2, 100)
            col_letter = (
                chr(65 + idx)
                if idx < 26
                else chr(65 + idx // 26 - 1) + chr(65 + idx % 26)
            )
            worksheet.column_dimensions[col_letter].width = max_length

    logger.info(
        f"Clustering complete: {len(clustering_result.clusters)} campaigns identified"
    )
    logger.info(f"Results saved to {output_file}")

    # Print summary
    for cluster in clustering_result.clusters:
        logger.info(
            f"  - {cluster.campaign_name}: {len(cluster.article_urls)} articles"
        )


async def run(input_file: str = None, output_file: str = None, prompt_version: int = 1):
    """
    Main function to load articles, cluster them, and save results.

    Args:
        input_file: Path to input Excel file with articles
        output_file: Path to output Excel file. If None, generates timestamped filename
        prompt_version: Which clustering prompt to use (1=detailed, 2=ultra-compact)
    """
    # Find input file
    if input_file is None:
        data_dir = Path(__file__).parent.parent / "data"
        excel_files = list(data_dir.glob("articles_classified_*.xlsx"))
        if not excel_files:
            logger.error("No classified article files found in data/")
            return
        input_file = max(excel_files, key=lambda p: p.stat().st_mtime)
    else:
        input_file = Path(input_file)

    logger.info(f"Loading articles from {input_file}")

    # Load articles from Excel
    df = pd.read_excel(input_file, sheet_name=0)

    # Filter for active campaigns only
    if "Active Campaign" in df.columns:
        df = df[df["Active Campaign"] == "True"]
        logger.info(f"Filtered to {len(df)} active campaign articles")

    if df.empty:
        logger.warning("No articles found for clustering")
        return

    # Prepare articles for clustering
    articles = []
    for _, row in df.iterrows():
        articles.append(
            {
                "url": row.get("URL", ""),
                "cleaned_text": row.get("Text", ""),
            }
        )

    # Run clustering
    clustering_result = await cluster_threat_articles(
        articles, prompt_version=prompt_version
    )

    # Prepare output data
    output_data = []
    for cluster in clustering_result.clusters:
        for url in cluster.article_urls:
            output_data.append(
                {
                    "Campaign Name": cluster.campaign_name,
                    "Article URL": url,
                    "Reasoning": cluster.reasoning,
                    "Cluster Urls": "\n".join(cluster.article_urls),
                }
            )

    output_df = pd.DataFrame(output_data)

    # Generate output filename if not provided
    if output_file is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = (
            Path(__file__).parent.parent
            / "outputs"
            / f"articles_clustered_{timestamp}.xlsx"
        )
    else:
        output_file = Path(output_file)

    # Ensure output directory exists
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Save to Excel
    with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
        output_df.to_excel(writer, index=False, sheet_name="Clustered Articles")

        # Auto-adjust column widths
        worksheet = writer.sheets["Clustered Articles"]
        for idx, col in enumerate(output_df.columns):
            max_length = max(output_df[col].astype(str).apply(len).max(), len(str(col)))
            max_length = min(max_length + 2, 100)
            col_letter = (
                chr(65 + idx)
                if idx < 26
                else chr(65 + idx // 26 - 1) + chr(65 + idx % 26)
            )
            worksheet.column_dimensions[col_letter].width = max_length

    logger.info(
        f"Clustering complete: {len(clustering_result.clusters)} campaigns identified"
    )
    logger.info(f"Results saved to {output_file}")

    # Print summary
    for cluster in clustering_result.clusters:
        logger.info(
            f"  - {cluster.campaign_name}: {len(cluster.article_urls)} articles"
        )


async def main():
    """Main entry point for the script - runs clustering for both summary columns."""
    try:
        logger.info("=" * 80)
        logger.info("Starting clustering for summary_1")
        logger.info("=" * 80)
        await run_clustering_from_summaries(summary_column="summary_1")

        logger.info("\n" + "=" * 80)
        logger.info("Starting clustering for summary_2")
        logger.info("=" * 80)
        await run_clustering_from_summaries(summary_column="summary_2")

        logger.info("\n" + "=" * 80)
        logger.info("All clustering tasks completed successfully!")
        logger.info("=" * 80)
    except Exception as e:
        logger.error(f"Error during clustering: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())

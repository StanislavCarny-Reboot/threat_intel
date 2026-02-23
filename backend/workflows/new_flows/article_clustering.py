"""Cluster articles about cyber attack campaigns using LLM - Prefect flow."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from google import genai
from google.genai import types
from prefect import flow, get_run_logger, task

from models.schemas import ClusteringResult
from prompts.article_summary import SUMMARY_1, SUMMARY_2
from prompts.clustering import CLUSTERING

load_dotenv()

client = genai.Client(api_key=os.getenv("API_KEY"))

FLOW_NAME = "cluster-articles"


# --- Prefect Tasks ---


@task(name="load-articles-for-clustering", tags=["clustering-io"])
def load_articles(input_file: Path | None = None) -> list[dict]:
    """Load active campaign articles from the most recent classified Excel file."""
    logger = get_run_logger()

    if input_file is None:
        data_dir = Path(__file__).parent.parent / "data"
        excel_files = list(data_dir.glob("articles_classified_*.xlsx"))
        if not excel_files:
            logger.error("No classified article files found in data/")
            return []
        input_file = max(excel_files, key=lambda p: p.stat().st_mtime)

    logger.info("Loading articles from %s", input_file)
    df = pd.read_excel(input_file, sheet_name=0)

    if "Active Campaign" in df.columns:
        df = df[df["Active Campaign"] == "True"]
        logger.info("Filtered to %d active campaign articles", len(df))

    if df.empty:
        logger.warning("No articles found for clustering")
        return []

    return [
        {"url": row.get("URL", ""), "cleaned_text": row.get("Text", "")}
        for _, row in df.iterrows()
    ]


@task(name="summarize-article", tags=["LLM_CALLS"], retries=3, retry_delay_seconds=2)
def summarize_article(
    article_text: str, article_url: str, prompt_version: int = 1
) -> str:
    """Generate a summary of an article optimised for clustering."""
    logger = get_run_logger()
    system_instruction = SUMMARY_1 if prompt_version == 1 else SUMMARY_2

    response = client.models.generate_content(
        model="gemini-3-pro-preview",
        contents=article_text,
        config=types.GenerateContentConfig(system_instruction=system_instruction),
    )
    logger.info("Summary generated for article: %s", article_url)
    return response.text.strip()


@task(name="cluster-articles", tags=["LLM_CALLS"], retries=3, retry_delay_seconds=2)
def cluster_articles(article_summaries: list[dict]) -> ClusteringResult:
    """Cluster articles by campaign using LLM structured output."""
    logger = get_run_logger()

    summaries_text = "\n\n".join(
        f"[{idx}]\nURL: {item['url']}\nSUMMARY: {item['summary']}"
        for idx, item in enumerate(article_summaries)
    )

    response = client.models.generate_content(
        model="gemini-3-pro-preview",
        contents=summaries_text,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ClusteringResult,
            system_instruction=CLUSTERING,
        ),
    )
    logger.info("Clustering completed successfully")
    return ClusteringResult(**json.loads(response.text))


@task(name="save-clustering-results", tags=["clustering-io"])
def save_clustering_results(
    clustering_result: ClusteringResult, output_file: Path | None = None
) -> Path:
    """Persist clustering results to an Excel file."""
    logger = get_run_logger()

    output_data = [
        {
            "Campaign Name": cluster.campaign_name,
            "Article URL": url,
            "Reasoning": cluster.reasoning,
            "Cluster Urls": "\n".join(cluster.article_urls),
        }
        for cluster in clustering_result.clusters
        for url in cluster.article_urls
    ]

    output_df = pd.DataFrame(output_data)
    logger.info(
        "Created DataFrame with %d rows from %d clusters",
        len(output_df),
        len(clustering_result.clusters),
    )

    if output_file is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = (
            Path(__file__).parent.parent
            / "outputs"
            / f"articles_clustered_{timestamp}.xlsx"
        )

    output_file.parent.mkdir(parents=True, exist_ok=True)

    with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
        output_df.to_excel(writer, index=False, sheet_name="Clustered Articles")
        worksheet = writer.sheets["Clustered Articles"]
        for idx, col in enumerate(output_df.columns):
            max_length = min(
                max(output_df[col].astype(str).apply(len).max(), len(str(col))) + 2,
                100,
            )
            col_letter = (
                chr(65 + idx)
                if idx < 26
                else chr(65 + idx // 26 - 1) + chr(65 + idx % 26)
            )
            worksheet.column_dimensions[col_letter].width = max_length

    logger.info("Results saved to %s", output_file)
    return output_file


# --- Prefect Flow ---


@flow(name="cluster-articles", log_prints=True)
def run(
    input_file: str | None = None,
    output_file: str | None = None,
    prompt_version: int = 1,
) -> None:
    """Summarize and cluster active campaign articles from the classified Excel file.

    Concurrency for LLM calls is controlled by Prefect concurrency limits on the
    'LLM_CALLS' tag (configure in the Prefect UI or via CLI).
    """
    logger = get_run_logger()

    input_path = Path(input_file) if input_file else None
    output_path = Path(output_file) if output_file else None

    articles = load_articles(input_path)
    if not articles:
        logger.warning("No articles to cluster; exiting")
        return

    # Submit all summarisation tasks; Prefect concurrency limits on LLM_CALLS
    # tag control actual parallelism without manual batching.
    futures = [
        (
            article,
            summarize_article.submit(
                article["cleaned_text"], article["url"], prompt_version
            ),
        )
        for article in articles
    ]

    article_summaries: list[dict] = []
    failed_count = 0
    for article, future in futures:
        result = future.result(raise_on_failure=False)
        if isinstance(result, Exception):
            logger.error("Failed to summarise %s: %s", article["url"], result)
            failed_count += 1
        else:
            article_summaries.append({"url": article["url"], "summary": result})

    logger.info(
        "Summarisation done: %d/%d succeeded, %d failed",
        len(article_summaries),
        len(articles),
        failed_count,
    )

    if not article_summaries:
        logger.warning("No summaries generated; cannot cluster")
        return

    clustering_result = cluster_articles(article_summaries)

    save_clustering_results(clustering_result, output_path)

    logger.info(
        "Clustering complete: %d campaigns identified",
        len(clustering_result.clusters),
    )
    for cluster in clustering_result.clusters:
        logger.info(
            "  - %s: %d articles", cluster.campaign_name, len(cluster.article_urls)
        )


if __name__ == "__main__":
    run.serve()

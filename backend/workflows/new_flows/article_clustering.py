"""Cluster articles about cyber attack campaigns using LLM - Prefect flow."""

from __future__ import annotations

import json
import os

from dotenv import load_dotenv
from google import genai
from google.genai import types
from prefect import flow, get_run_logger, runtime, task

from connectors import get_sync_db_session
from models.entities import Article, ArticleClassificationLabel, Cluster, ClusterArticle
from models.schemas import ArticleCluster, ClusteringResult
from prompts.article_summary import SUMMARY_1, SUMMARY_2
from prompts.clustering import CLUSTERING

load_dotenv()

client = genai.Client(api_key=os.getenv("API_KEY"))

FLOW_NAME = "cluster-articles"


# --- Prefect Tasks ---


@task(name="load-articles-for-clustering", tags=["clustering-io"])
def load_articles() -> list[dict]:
    """Load active campaign articles from the database."""
    logger = get_run_logger()

    session = get_sync_db_session()
    try:
        rows = (
            session.query(Article.url, Article.cleaned_text)
            .join(
                ArticleClassificationLabel,
                Article.id == ArticleClassificationLabel.article_id,
            )
            .filter(ArticleClassificationLabel.active_campaign == "True")
            .all()
        )
    finally:
        session.close()

    if not rows:
        logger.warning("No active campaign articles found in database")
        return []

    logger.info("Loaded %d active campaign articles from database", len(rows))
    return [{"url": row.url, "cleaned_text": row.cleaned_text or ""} for row in rows]


@task(name="summarize-article", tags=["LLM_CALLS"], retries=3, retry_delay_seconds=2)
def summarize_article(
    article_text: str, article_url: str, prompt_version: int = 1
) -> str:
    """Generate a summary of an article optimised for clustering."""
    logger = get_run_logger()
    system_instruction = SUMMARY_1 if prompt_version == 1 else SUMMARY_2

    response = client.models.generate_content(
        model="gemini-2.5-pro",
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
        model="gemini-2.5-pro",
        contents=summaries_text,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ClusteringResult,
            system_instruction=CLUSTERING,
        ),
    )
    logger.info("Clustering completed successfully")
    return ClusteringResult(**json.loads(response.text))


@task(name="save-cluster-to-db", tags=["clustering-io"])
def save_cluster_to_db(cluster_data: ArticleCluster, run_id: str | None = None) -> int:
    """Persist a single cluster and its articles to the database."""
    logger = get_run_logger()

    session = get_sync_db_session()
    try:
        cluster = Cluster(
            campaign_name=cluster_data.campaign_name,
            reasoning=cluster_data.reasoning,
            run_id=run_id,
        )
        session.add(cluster)
        session.flush()

        for url in cluster_data.article_urls:
            session.add(ClusterArticle(cluster_id=cluster.id, article_url=url))

        session.commit()
        logger.info(
            "Saved cluster '%s' (%d articles)",
            cluster_data.campaign_name,
            len(cluster_data.article_urls),
        )
        return cluster.id
    except Exception as e:
        session.rollback()
        logger.error("Failed to save cluster '%s': %s", cluster_data.campaign_name, e)
        raise
    finally:
        session.close()


# --- Prefect Flow ---


@flow(name="cluster-articles", log_prints=True)
def run(prompt_version: int = 1, limit: int | None = None) -> None:
    """Summarize and cluster active campaign articles from the database.

    Concurrency for LLM calls is controlled by Prefect concurrency limits on the
    'LLM_CALLS' tag (configure in the Prefect UI or via CLI).
    """
    logger = get_run_logger()
    flow_run_id = str(runtime.flow_run.id) if runtime.flow_run.id else None

    articles = load_articles()
    if limit:
        articles = articles[:limit]
        logger.info("Limited to %d articles", len(articles))
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

    for cluster in clustering_result.clusters:
        save_cluster_to_db.submit(cluster, flow_run_id)
        logger.info(
            "  - %s: %d articles", cluster.campaign_name, len(cluster.article_urls)
        )

    logger.info(
        "Clustering complete: %d campaigns identified", len(clustering_result.clusters)
    )


if __name__ == "__main__":
    run.serve()

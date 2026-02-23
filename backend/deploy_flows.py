"""Deploy all Prefect flows for the threat-intel pipeline."""

from pathlib import Path

from workflows.new_flows.article_clustering import run as cluster_articles_run
from workflows.new_flows.get_link_content import run as get_link_content_run
from workflows.new_flows.parse_rss import run as parse_rss_run
from workflows.new_flows.relevant_article_classification import (
    run as classify_articles_run,
)

BASE_PATH = str(Path(__file__).parent)
WORK_POOL = "default-worker"

if __name__ == "__main__":
    parse_rss_run.from_source(
        source=BASE_PATH,
        entrypoint="workflows/new_flows/parse_rss.py:run",
    ).deploy(
        name="rss-url-collector",
        work_pool_name=WORK_POOL,
        tags=["rss", "threat-intel", "url-collection"],
        description="Collect RSS article URLs published in the last 24 hours",
        parameters={
            "window_hours": 24,
            "max_items_per_feed": 100,
            "limit_sources": 0,
            "dry_run": False,
        },
    )

    get_link_content_run.from_source(
        source=BASE_PATH,
        entrypoint="workflows/new_flows/get_link_content.py:run",
    ).deploy(
        name="get-link-content",
        work_pool_name=WORK_POOL,
        tags=["scraping", "threat-intel", "content"],
        description="Scrape article body text for all new RSS items",
    )

    classify_articles_run.from_source(
        source=BASE_PATH,
        entrypoint="workflows/new_flows/relevant_article_classification.py:run",
    ).deploy(
        name="classify-articles",
        work_pool_name=WORK_POOL,
        tags=["classification", "threat-intel", "llm"],
        description="Classify articles as cyber attack campaigns, CVEs, or digest using LLM",
    )

    cluster_articles_run.from_source(
        source=BASE_PATH,
        entrypoint="workflows/new_flows/article_clustering.py:run",
    ).deploy(
        name="cluster-articles",
        work_pool_name=WORK_POOL,
        tags=["clustering", "threat-intel", "llm"],
        description="Summarize and cluster active campaign articles into cyber attack campaigns",
        parameters={"prompt_version": 1},
    )

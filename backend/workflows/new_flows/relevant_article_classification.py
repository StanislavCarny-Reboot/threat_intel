"""Classify articles as cyber attack campaigns or general news - Prefect flow."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import mlflow
from dotenv import load_dotenv
from google import genai
from google.genai import types
from prefect import flow, get_run_logger, task
from sqlalchemy import select
from tenacity import retry, stop_after_attempt, wait_fixed

from connectors.database import get_sync_db_session
from models.entities import Article, ArticleClassificationLabel, SourceErrorLog
from models.schemas import ArticleClassification
from prompts.attack_classification import ATTACK_CLASSIFICATION_PROMPT

FLOW_NAME = "classify-articles"

load_dotenv()

client = genai.Client(api_key=os.getenv("API_KEY"))


# --- Prefect Tasks ---


@task(name="load-articles", tags=["classification-db"])
def load_articles() -> list[dict]:
    """Load unclassified articles from the database."""
    logger = get_run_logger()
    session = get_sync_db_session()
    try:
        classified_ids = {
            row[0]
            for row in session.execute(
                select(ArticleClassificationLabel.article_id)
            ).all()
        }
        rows = (
            session.execute(select(Article).where(Article.text.isnot(None)))
            .scalars()
            .all()
        )
        articles = [
            {"id": a.id, "text": a.text, "url": a.url}
            for a in rows
            if a.id not in classified_ids
        ]
        logger.info(
            "Found %d unclassified articles (skipped %d already classified)",
            len(articles),
            len(classified_ids),
        )
        return articles
    finally:
        session.close()


@task(name="classify-article", tags=["LLM_CALLS"], retries=3, retry_delay_seconds=2)
def classify_article(article_row: dict) -> dict:
    """Call the LLM to classify a single article and return the result."""
    logger = get_run_logger()
    article_url = article_row["url"]
    article_text = article_row["text"]

    try:
        response = client.models.generate_content(
            # model="gemini-3-pro-preview",
            model="gemini-2.5-pro",
            contents=article_text,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ArticleClassification,
                system_instruction=ATTACK_CLASSIFICATION_PROMPT,
            ),
        )
        classification = json.loads(response.text)
        logger.info(
            "Article %s classified - active_campaign=%s cve=%s digest=%s",
            article_row["id"],
            classification["active_campaign"],
            classification["cve"],
            classification["digest"],
        )
        return {
            "article_id": article_row["id"],
            "active_campaign": classification["active_campaign"],
            "cve": classification["cve"],
            "digest": classification["digest"],
        }

    except Exception as exc:
        logger.error("Error classifying article %s: %s", article_url, exc)
        raise


@task(name="save-classifications-to-db", tags=["classification-db"])
def save_classifications_to_db(results: list[dict]) -> int:
    """Persist classification results to article_classification_labels."""
    logger = get_run_logger()
    session = get_sync_db_session()
    try:
        saved_count = 0
        for result in results:
            session.add(
                ArticleClassificationLabel(
                    article_id=result["article_id"],
                    active_campaign=result["active_campaign"],
                    cve=result["cve"],
                    digest=result["digest"],
                    label_source="llm",
                )
            )
            saved_count += 1
        session.commit()
        logger.info("Saved %d classification records to database", saved_count)
        return saved_count
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@task(name="save-errors-to-log", tags=["classification-db"])
def save_errors_to_log(errors: list[dict]) -> None:
    """Persist classification errors to source_error_log."""
    logger = get_run_logger()
    session = get_sync_db_session()
    try:
        now = datetime.now(tz=timezone.utc)
        session.add_all(
            [
                SourceErrorLog(
                    source_uuid=str(e["article_id"]),
                    source_url=e["url"],
                    status_code="CLASSIFICATION_ERROR",
                    error_message=e["error_message"],
                    process=FLOW_NAME,
                    detected_at=now,
                    created_at=now,
                )
                for e in errors
            ]
        )
        session.commit()
        logger.info("Logged %d classification errors to source_error_log", len(errors))
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# --- Prefect Flow ---


@flow(name="classify-articles", log_prints=True)
def run() -> None:
    """Classify unclassified articles from the DB and persist to article_classification_labels.

    Concurrency for LLM calls is controlled by Prefect concurrency limits on the
    'classification-llm' tag (configure in the Prefect UI or via CLI).
    """
    logger = get_run_logger()

    articles = load_articles()
    if not articles:
        logger.warning("No articles to classify; exiting")
        return

    futures = [(article, classify_article.submit(article)) for article in articles]

    results: list[dict] = []
    errors: list[dict] = []
    for article, future in futures:
        result = future.result(raise_on_failure=False)
        if isinstance(result, Exception):
            logger.error(
                "Classification failed for article %s: %s", article["id"], result
            )
            errors.append(
                {
                    "article_id": article["id"],
                    "url": article["url"],
                    "error_message": str(result),
                }
            )
        else:
            results.append(result)

    logger.info("Classification done: %d/%d succeeded", len(results), len(articles))
    logger.info(
        "Summary: %d active campaigns, %d CVEs, %d digests",
        sum(1 for r in results if r.get("active_campaign") == "True"),
        sum(1 for r in results if r.get("cve") == "True"),
        sum(1 for r in results if r.get("digest") == "True"),
    )

    if results:
        save_classifications_to_db(results)

    if errors:
        save_errors_to_log(errors)


if __name__ == "__main__":
    run.serve()

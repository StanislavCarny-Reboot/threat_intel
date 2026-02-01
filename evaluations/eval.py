#!/usr/bin/env -S uv run python
"""Evaluate article classification using MLflow."""

import asyncio
import sys
from pathlib import Path


# Add project root to Python path for direct execution
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables before any other imports
from dotenv import load_dotenv

load_dotenv()

import mlflow
from mlflow.genai.datasets import create_dataset, set_dataset_tags
from mlflow.genai import evaluate
from evaluations.sample_dataset import data
from mlflow.genai.scorers import scorer
from mlflow.entities import AssessmentSource, Feedback
from workflows.filter_attacks import classify_article
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

mlflow.set_tracking_uri("http://localhost:5002")
mlflow.set_experiment("threat-intel-article-classification-eval")

MLFLOW_GENAI_EVAL_SKIP_TRACE_VALIDATION = True


import pandas as pd

df = pd.read_excel("data/labeled.xlsx", sheet_name="Labeled")
df.dropna(subset=["active_campaign"], inplace=True)


# Rename columns to match database
df_transformed = df.rename(
    columns={
        "ID": "id",
        "Source Name": "source_name",
        "URL": "url",
        "Text": "text",
    }
)

# Convert classification floats to boolean strings
df_transformed["active_campaign"] = df_transformed["active_campaign"].apply(
    lambda x: "True" if x == 1.0 else "False"
)
df_transformed["cve"] = df_transformed["cve"].apply(
    lambda x: "True" if x == 1.0 else "False"
)
df_transformed["digest"] = df_transformed["digest"].apply(
    lambda x: "True" if x == 1.0 else "False"
)

# Select only the columns you need
df_final = df_transformed[
    ["id", "source_name", "text", "url", "active_campaign", "cve", "digest"]
]

# Convert DataFrame to MLflow dataset format
validation_data = []
for _, row in df_final.iterrows():
    validation_data.append(
        {
            "inputs": {
                "article_text": row["text"],  # TODO: Need to add article text
                "article_url": row["url"],
            },
            "expectations": {
                "active_campaign": row["active_campaign"],
                "cve": row["cve"],
                "digest": row["digest"],
            },
        }
    )

dataset = create_dataset(
    name="Threat Intelligence Articles Classification Evaluation Dataset",
    experiment_id=["1"],
)
dataset.merge_records(validation_data)


@scorer
def active_campaign_accuracy(outputs: dict, expectations: dict):
    """Score accuracy for active_campaign classification."""
    try:
        output_value = outputs.get("active_campaign")
        expected_value = expectations.get("active_campaign")

        if output_value == expected_value:
            return Feedback(
                value=1.0,
                rationale=f"Active campaign classification matches: '{output_value}' == '{expected_value}'",
            )
        return Feedback(
            value=0.0,
            rationale=f"Active campaign classification does not match: '{output_value}' != '{expected_value}'",
        )
    except Exception as e:
        return Feedback(
            value=0.0,
            rationale=f"Exception during active_campaign scoring: {str(e)}",
        )


@scorer
def cve_accuracy(outputs: dict, expectations: dict):
    """Score accuracy for cve classification."""
    try:
        output_value = outputs.get("cve")
        expected_value = expectations.get("cve")

        if output_value == expected_value:
            return Feedback(
                value=1.0,
                rationale=f"CVE classification matches: '{output_value}' == '{expected_value}'",
            )
        return Feedback(
            value=0.0,
            rationale=f"CVE classification does not match: '{output_value}' != '{expected_value}'",
        )
    except Exception as e:
        return Feedback(
            value=0.0,
            rationale=f"Exception during CVE scoring: {str(e)}",
        )


@scorer
def digest_accuracy(outputs: dict, expectations: dict):
    """Score accuracy for digest classification."""
    try:
        output_value = outputs.get("digest")
        expected_value = expectations.get("digest")

        if output_value == expected_value:
            return Feedback(
                value=1.0,
                rationale=f"Digest classification matches: '{output_value}' == '{expected_value}'",
            )
        return Feedback(
            value=0.0,
            rationale=f"Digest classification does not match: '{output_value}' != '{expected_value}'",
        )
    except Exception as e:
        return Feedback(
            value=0.0,
            rationale=f"Exception during digest scoring: {str(e)}",
        )


# Precision scorers - score 1.0 for True Positives, 0.0 for False Positives, None for others
@scorer
def active_campaign_precision(outputs: dict, expectations: dict):
    """Score precision for active_campaign classification."""
    try:
        output_value = outputs.get("active_campaign")
        expected_value = expectations.get("active_campaign")

        # True Positive
        if output_value == "True" and expected_value == "True":
            return Feedback(value=1.0, rationale="True Positive")
        # False Positive
        elif output_value == "True" and expected_value == "False":
            return Feedback(value=0.0, rationale="False Positive")
        # Not predicted as True, doesn't affect precision
        else:
            return None
    except Exception as e:
        return Feedback(value=0.0, rationale=f"Exception: {str(e)}")


@scorer
def active_campaign_recall(outputs: dict, expectations: dict):
    """Score recall for active_campaign classification."""
    try:
        output_value = outputs.get("active_campaign")
        expected_value = expectations.get("active_campaign")

        # True Positive
        if output_value == "True" and expected_value == "True":
            return Feedback(value=1.0, rationale="True Positive")
        # False Negative
        elif output_value == "False" and expected_value == "True":
            return Feedback(value=0.0, rationale="False Negative")
        # Not actually True, doesn't affect recall
        else:
            return None
    except Exception as e:
        return Feedback(value=0.0, rationale=f"Exception: {str(e)}")


@scorer
def cve_precision(outputs: dict, expectations: dict):
    """Score precision for CVE classification."""
    try:
        output_value = outputs.get("cve")
        expected_value = expectations.get("cve")

        # True Positive
        if output_value == "True" and expected_value == "True":
            return Feedback(value=1.0, rationale="True Positive")
        # False Positive
        elif output_value == "True" and expected_value == "False":
            return Feedback(value=0.0, rationale="False Positive")
        else:
            return None
    except Exception as e:
        return Feedback(value=0.0, rationale=f"Exception: {str(e)}")


@scorer
def cve_recall(outputs: dict, expectations: dict):
    """Score recall for CVE classification."""
    try:
        output_value = outputs.get("cve")
        expected_value = expectations.get("cve")

        # True Positive
        if output_value == "True" and expected_value == "True":
            return Feedback(value=1.0, rationale="True Positive")
        # False Negative
        elif output_value == "False" and expected_value == "True":
            return Feedback(value=0.0, rationale="False Negative")
        else:
            return None
    except Exception as e:
        return Feedback(value=0.0, rationale=f"Exception: {str(e)}")


@scorer
def digest_precision(outputs: dict, expectations: dict):
    """Score precision for digest classification."""
    try:
        output_value = outputs.get("digest")
        expected_value = expectations.get("digest")

        # True Positive
        if output_value == "True" and expected_value == "True":
            return Feedback(value=1.0, rationale="True Positive")
        # False Positive
        elif output_value == "True" and expected_value == "False":
            return Feedback(value=0.0, rationale="False Positive")
        else:
            return None
    except Exception as e:
        return Feedback(value=0.0, rationale=f"Exception: {str(e)}")


@scorer
def digest_recall(outputs: dict, expectations: dict):
    """Score recall for digest classification."""
    try:
        output_value = outputs.get("digest")
        expected_value = expectations.get("digest")

        # True Positive
        if output_value == "True" and expected_value == "True":
            return Feedback(value=1.0, rationale="True Positive")
        # False Negative
        elif output_value == "False" and expected_value == "True":
            return Feedback(value=0.0, rationale="False Negative")
        else:
            return None
    except Exception as e:
        return Feedback(value=0.0, rationale=f"Exception: {str(e)}")


def sync_predict_fn(article_text, article_url):
    """Synchronous wrapper for async classify_article function."""
    import nest_asyncio

    logger.info(f"Processing article URL: {article_url}")

    nest_asyncio.apply()
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(classify_article(article_text, article_url))

    # Add URL to the output for tracking
    if isinstance(result, dict):
        result["article_url"] = article_url

    return result


with mlflow.start_run(run_name="article_classification_evaluation_2"):
    results = evaluate(
        data=dataset,
        predict_fn=sync_predict_fn,
        scorers=[
            active_campaign_accuracy,
            active_campaign_precision,
            active_campaign_recall,
            cve_accuracy,
            cve_precision,
            cve_recall,
            digest_accuracy,
            digest_precision,
            digest_recall,
        ],
    )

    logger.info("\n" + "=" * 50)
    logger.info("Evaluation completed!")
    logger.info("=" * 50)

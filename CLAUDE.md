# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python-based threat intelligence project managed with `uv` (a fast Python package manager). The project is in early development stages.

## Development Environment

- **Python Version**: 3.11 (specified in `.python-version`)
- **Package Manager**: uv
- **Project Structure**: Currently minimal with entry point in `main.py`

## Common Commands

### Running the Application
```bash
uv run main.py
```

### Dependency Management
```bash
# Add a new dependency
uv add <package-name>

# Add a development dependency
uv add --dev <package-name>

# Sync dependencies
uv sync
```

### Python Environment
```bash
# Activate the virtual environment
source .venv/bin/activate  # On Unix/macOS
.venv\Scripts\activate     # On Windows
```

## CI/CD

### GitHub Actions
- **run-main.yml**: Runs on push to main, PRs, and can be manually triggered. Executes `main.py` using uv.

## Architecture

### Project Structure

```
threat_intel/
├── workflows/          # Main processing workflows
│   ├── filter_attacks.py    # Article classification using LLM
│   ├── get_intel.py         # Threat intelligence extraction
│   ├── get_rss.py           # RSS feed processing
│   └── get_data.py          # Data collection
├── evaluations/        # MLflow evaluation system
│   ├── classify_evaluation.py    # Evaluation runner
│   ├── create_eval_template.py   # Template generator
│   ├── example_usage.py          # Usage examples
│   └── README.md                 # Evaluation documentation
├── models/             # Data models and schemas
│   ├── schemas.py      # Pydantic models (ArticleClassification, ThreatCampaign)
│   └── entities.py     # Database entities
├── prompts/            # LLM prompts
│   ├── attack_classification.py
│   └── rss_extraction.py
├── connectors/         # External service connectors
│   └── database.py     # Database connections
├── utils/              # Utility functions
└── data/               # Data files (Excel files, evaluation data)
```

### Key Components

#### Workflows
- **filter_attacks.py**: Classifies articles using LLM (Gemini) to identify cyber attack campaigns, general news, or CVEs
  - `classify_article()`: Main classification function
  - Uses structured output with Pydantic schemas
  - Async processing with batching and rate limiting

#### Evaluations (MLflow Integration)
- **classify_evaluation.py**: MLflow-based evaluation system for article classification
  - Load evaluation data from Excel files
  - Run evaluations and track metrics (accuracy, per-class performance)
  - Add evaluation datapoints programmatically or from Excel
  - Automatic artifact logging and experiment tracking

### Running Evaluations

```bash
# Create evaluation template
uv run evaluations/create_eval_template.py

# Run evaluation
uv run evaluations/classify_evaluation.py --eval-file data/my_evaluation.xlsx

# View results in MLflow UI
mlflow ui --backend-store-uri mlruns/
```

See `evaluations/README.md` for detailed documentation.

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

The project is currently minimal with a single entry point:
- `main.py`: Main application entry point with `main()` function

As the project grows, this section should be updated with architecture patterns, module organization, and key components.

#!/bin/bash
# Start the FastAPI server

uv run uvicorn api:app --reload --host 0.0.0.0 --port 8000

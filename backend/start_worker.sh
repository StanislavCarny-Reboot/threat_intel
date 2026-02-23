#!/bin/sh
set -e

echo "Creating work pool 'default-worker' if it doesn't exist..."
/opt/venv/bin/prefect work-pool create default-worker --type process 2>/dev/null || true

echo "Registering deployments..."
/opt/venv/bin/prefect deploy --all

echo "Starting Prefect worker with hot-reload..."
exec watchmedo auto-restart \
  --directory=/app \
  --pattern="*.py" \
  --recursive \
  -- \
  /opt/venv/bin/prefect worker start --pool default-worker

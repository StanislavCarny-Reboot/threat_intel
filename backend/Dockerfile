FROM python:3.11-slim

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv and watchdog (for hot-reload via watchmedo)
RUN pip install --no-cache-dir uv watchdog

# Install deps into /opt/venv so the volume mount at /app doesn't overwrite them
WORKDIR /build
COPY pyproject.toml uv.lock ./
RUN UV_PROJECT_ENVIRONMENT=/opt/venv uv sync --frozen --no-install-project

# Put venv on PATH
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app
# Code is mounted via volume at runtime (hot reload)

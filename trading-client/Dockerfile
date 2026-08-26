# Alvora Trading Client — Backend Dockerfile
# Multi-stage build: Python 3.12 slim

FROM python:3.12-slim AS base

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY app/ ./app/

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/api/health/live || exit 1

# Run
CMD ["uvicorn", "app.api.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]

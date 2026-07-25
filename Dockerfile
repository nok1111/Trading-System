FROM python:3.12-slim AS base

WORKDIR /app

# Instalar dependencias del sistema para compilar psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./

RUN pip install --no-cache-dir -e "."

FROM base AS dev

COPY tests ./tests
COPY scripts ./scripts
COPY docs ./docs

# Por defecto ejecuta migraciones y pruebas (FASE 1)
CMD ["bash", "-c", "alembic upgrade head && pytest -v"]

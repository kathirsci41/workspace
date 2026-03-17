FROM python:3.12-slim AS base

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl libgl1 libglib2.0-0 libsm6 libxext6 libxrender-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# API server — runs DB migrations then starts uvicorn
FROM base AS api
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]

# Celery worker — no migrations, just starts the worker
FROM base AS worker
CMD ["celery", "-A", "app.celery_app", "worker", "--loglevel=info", "--concurrency=2"]

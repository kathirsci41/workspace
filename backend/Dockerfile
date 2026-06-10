FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir fastapi uvicorn sqlalchemy python-multipart pymupdf openpyxl psycopg[binary]

COPY backend/app ./app
COPY backend/migrations ./migrations
COPY shared ./shared

ENV APP_ENV=production
ENV ENABLE_DEV_TOOLS=false
ENV DATABASE_URL=sqlite:///./order_assurance.db
ENV STORAGE_DIR=/app/storage/documents

EXPOSE 8100

CMD ["sh", "-c", "python -m app.migrations.runner up && exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8100"]

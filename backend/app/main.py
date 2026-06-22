from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.bundles import router as bundles_router
from app.api.routes.dev import router as dev_router
from app.api.routes.documents import router as documents_router
from app.api.routes.extractions import router as extractions_router
from app.api.routes.health import router as health_router
from app.config import settings, validate_ocr_runtime_settings
from app.database import init_db, wait_for_database
from app.logging_config import configure_logging, request_logging_middleware
from app.middleware.tenant import TenantMiddleware


@asynccontextmanager
async def lifespan(_: FastAPI):
    validate_ocr_runtime_settings()
    wait_for_database()
    if settings.app_env == "development":
        init_db()
    yield


configure_logging()

app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.middleware("http")(request_logging_middleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5180", "http://localhost:5180"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)
app.add_middleware(TenantMiddleware)
app.include_router(health_router, prefix=settings.api_prefix)
app.include_router(bundles_router, prefix=settings.api_prefix)
app.include_router(documents_router, prefix=settings.api_prefix)
app.include_router(extractions_router, prefix=settings.api_prefix)
if settings.app_env == "development":
    app.include_router(dev_router, prefix=settings.api_prefix)

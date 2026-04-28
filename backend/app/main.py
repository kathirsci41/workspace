import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import InterfaceError

from app.config import settings
from app.api.router import api_router
from app.logging_config import setup_logging
from app.database import async_engine

setup_logging("app")

logger = logging.getLogger("app.api")

# Validate benchmark configuration on startup
settings.validate_benchmark_config()

app = FastAPI(
    title="Document Platform V3.0",
    description="Centric Document Management",
    version="3.0.0",
    debug=settings.debug,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router, prefix="/api/v1")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error(
        "Unhandled exception on %s %s", request.method, request.url.path,
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


@app.get("/")
async def root():
    return {"status": "ok", "app": "Document Platform V3.0"}

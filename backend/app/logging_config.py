"""
Centralised logging configuration for Document Platform V3.0.

Dedicated log files (all under <project_root>/logs/):

  app.log      — FastAPI HTTP layer: requests, responses, API errors, uvicorn
  celery.log   — Celery worker: task queue, retries, task lifecycle
  ai.log       — AI/OCR pipeline: extraction, OCR, two-layer, SO validation
  db.log       — Database: SQLAlchemy queries, migrations, connection events

All files:
  - Rotate daily at midnight
  - Keep 30 days of history
  - Mirror to console (terminal stays usable during dev)

Usage:
  from app.logging_config import setup_logging
  setup_logging("app")     # in main.py      -> app.log
  setup_logging("celery")  # in celery_app.py -> celery.log
"""

import io
import logging
import logging.config
import logging.handlers
import sys
from pathlib import Path

from app.config import _PROJECT_ROOT


class _UTF8StreamHandler(logging.StreamHandler):
    """StreamHandler that forces UTF-8 on stdout regardless of terminal encoding.

    Fixes UnicodeEncodeError on Windows where the default console uses cp1252
    and cannot encode characters like arrows, accented letters, or Devanagari
    script that may appear in extracted document text.

    Also handles ValueError('I/O operation on closed file') which occurs in
    uvicorn subprocesses when our wrapper holds a stale reference to the old
    sys.stdout.buffer after the process's stdout is replaced or closed.
    """

    def __init__(self):
        stream = io.TextIOWrapper(
            sys.stdout.buffer,
            encoding="utf-8",
            errors="replace",
            line_buffering=True,
        )
        super().__init__(stream)

    def emit(self, record):
        try:
            if not getattr(self.stream, "closed", False):
                super().emit(record)
        except (ValueError, OSError):
            pass

    def handleError(self, record):
        # Called by StreamHandler.emit() when a write fails.
        # Suppress closed-stream errors that occur in the uvicorn/async lifecycle.
        # Re-raise everything else so real problems are still visible.
        t, _, _ = sys.exc_info()
        if t in (ValueError, OSError):
            return
        super().handleError(record)

class _SafeTimedRotatingFileHandler(logging.handlers.TimedRotatingFileHandler):
    """TimedRotatingFileHandler that silently ignores PermissionError during rotation.

    On Windows, all Celery worker subprocesses import celery_app.py and each
    creates its own TimedRotatingFileHandler. When the date changes they all
    try to rename celery.log → celery.log.<date> simultaneously. Only the first
    succeeds; the rest get WinError 32. Catching the error here prevents the
    noisy '--- Logging error ---' spam in the terminal.
    """

    def rotate(self, source, dest):
        try:
            super().rotate(source, dest)
        except PermissionError:
            pass  # Another worker process already rotated the file — that's fine


LOGS_DIR = _PROJECT_ROOT / "logs"

# Maps log_name → which Python loggers feed into that file
_LOGGER_MAP = {
    "app": [
        "app.api",
        "app.services.customer_service",
        "app.services.document_service",
        "app.services.storage_service",
        "app.services.po_service",
        "app.services.search_service",
        "uvicorn",
        "uvicorn.access",
        "uvicorn.error",
        "fastapi",
    ],
    "celery": [
        "celery",
        "celery.task",
        "celery.worker",
        "app.celery_app",
    ],
    "ai": [
        "app.services.extraction",
        "app.services.extraction.tasks",
        "app.services.extraction.ocr_client",
        "app.services.extraction.two_layer_client",
        "app.services.extraction.hybrid_router",
        "app.services.extraction.digital_extractor",
        "app.services.extraction.pdf_converter",
        "app.services.extraction.scan_preprocessor",
        "app.services.extraction.response_parser",
        "app.services.extraction.field_validator",
        "app.services.extraction.invoice_validator",
        "app.services.extraction.so_validator",
        "app.services.extraction.glm_ocr_prompts",
        "app.services.extraction.prompts",
        "httpx",  # Ollama HTTP calls
    ],
    "db": [
        "sqlalchemy.engine",
        "sqlalchemy.pool",
        "sqlalchemy.dialects",
        "alembic",
    ],
}


def _make_file_handler(name: str) -> dict:
    return {
        "class": "app.logging_config._SafeTimedRotatingFileHandler",
        "formatter": "detailed",
        "filename": str(LOGS_DIR / f"{name}.log"),
        "when": "midnight",
        "backupCount": 30,
        "encoding": "utf-8",
        "delay": True,
        "level": "DEBUG",
    }


def setup_logging(component: str = "app") -> None:
    """Configure dedicated per-component log files.

    Args:
        component: One of "app" | "celery" | "ai" | "db".
                   Determines which file gets the primary output.
                   All four files are always created; this just sets
                   the log level for the calling component's loggers.
    """
    LOGS_DIR.mkdir(exist_ok=True)

    handlers = {
        "console": {
            "class": "app.logging_config._UTF8StreamHandler",
            "formatter": "simple",
            "level": "DEBUG",
        },
        "file_app": _make_file_handler("app"),
        "file_celery": _make_file_handler("celery"),
        "file_ai": _make_file_handler("ai"),
        "file_db": _make_file_handler("db"),
    }

    formatters = {
        "detailed": {
            "format": (
                "%(asctime)s | %(levelname)-8s | %(name)s | "
                "%(filename)s:%(lineno)d | %(message)s"
            ),
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "simple": {
            "format": "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            "datefmt": "%H:%M:%S",
        },
    }

    # Build logger configs from the map
    loggers = {}
    for log_name, logger_names in _LOGGER_MAP.items():
        file_handler = f"file_{log_name}"
        for logger_name in logger_names:
            loggers[logger_name] = {
                "handlers": ["console", file_handler],
                "level": "DEBUG" if log_name == component else "INFO",
                "propagate": False,
            }

    # app.* catch-all — routes to the active component's file
    loggers["app"] = {
        "handlers": ["console", f"file_{component}"],
        "level": "DEBUG",
        "propagate": False,
    }

    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": formatters,
        "handlers": handlers,
        "loggers": loggers,
        "root": {
            "handlers": ["console", f"file_{component}"],
            "level": "WARNING",
        },
    }

    logging.config.dictConfig(config)

    logging.getLogger("app").info(
        "Logging initialised [component=%s] -> %s", component, str(LOGS_DIR)
    )

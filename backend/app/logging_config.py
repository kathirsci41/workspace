from __future__ import annotations

import contextvars
import json
import logging
import sys
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import Request, Response

from app.config import settings


request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_id", default=None)

RESERVED_LOG_ATTRS = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "message",
    "module",
    "msecs",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "timestamp": self.formatTime(record, self.datefmt),
        }
        for key, value in record.__dict__.items():
            if key not in RESERVED_LOG_ATTRS and not key.startswith("_"):
                payload[key] = value
        return json.dumps(payload, default=str, separators=(",", ":"))


def configure_logging() -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(level)
    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        root.addHandler(handler)
    formatter: logging.Formatter
    if settings.log_format.lower() == "json":
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    for handler in root.handlers:
        handler.setLevel(level)
        handler.setFormatter(formatter)


def current_request_id() -> str | None:
    return request_id_var.get()


def log_event(event: str, **fields: Any) -> None:
    extra = {"event": event, **_clean_fields(fields)}
    request_id = current_request_id()
    if request_id and not extra.get("request_id"):
        extra["request_id"] = request_id
    logging.getLogger("order_assurance.events").info(event, extra=extra)


async def request_logging_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    token = request_id_var.set(request_id)
    started = time.perf_counter()
    status_code = 500
    error: str | None = None
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    except Exception as exc:
        error = str(exc)
        raise
    finally:
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        log_event(
            "api_request",
            method=request.method,
            path=request.url.path,
            status_code=status_code,
            duration_ms=duration_ms,
            error=error,
        )
        if "response" in locals():
            response.headers["X-Request-ID"] = request_id
        request_id_var.reset(token)


def _clean_fields(fields: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in fields.items() if value is not None}

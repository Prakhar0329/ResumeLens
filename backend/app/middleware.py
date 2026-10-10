"""Request ID middleware, structured JSON logging and an in-memory rate limiter.

Logging policy: request logs contain method, path, status, duration and a request ID.
Resume text, job description text and uploaded file contents are never logged.
"""

from __future__ import annotations

import json
import logging
import sys
import threading
import time
import uuid
from collections import deque
from contextvars import ContextVar
from datetime import UTC, datetime

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.errors import RateLimitExceededError

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")
REQUEST_ID_HEADER = "X-Request-ID"

access_logger = logging.getLogger("resumelens.access")


class JsonFormatter(logging.Formatter):
    """Formats each log record as one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": request_id_ctx.get(),
        }
        fields = getattr(record, "fields", None)
        if isinstance(fields, dict):
            payload.update(fields)
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())
    # Uvicorn's access log would duplicate our structured access log.
    logging.getLogger("uvicorn.access").disabled = True
    for noisy in ("pdfminer", "httpx", "sentence_transformers", "urllib3", "filelock"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attaches a request ID (incoming header or generated) and logs one line per request."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        incoming = request.headers.get(REQUEST_ID_HEADER, "")
        request_id = incoming if 0 < len(incoming) <= 64 and incoming.isprintable() else uuid.uuid4().hex
        token = request_id_ctx.set(request_id)
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers[REQUEST_ID_HEADER] = request_id
            return response
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 1)
            access_logger.info(
                "request",
                extra={
                    "fields": {
                        "method": request.method,
                        "path": request.url.path,
                        "status": status,
                        "duration_ms": duration_ms,
                        "client_ip": client_ip(request),
                    }
                },
            )
            request_id_ctx.reset(token)


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


class InMemoryRateLimiter:
    """Sliding-window limiter keyed by client IP.

    Suitable for a single-process deployment. Behind a reverse proxy, run uvicorn with
    ``--proxy-headers`` so ``request.client.host`` is the real client address. For
    multiple workers or replicas use a shared store such as Redis instead.
    """

    def __init__(self, limit_per_minute: int, window_seconds: float = 60.0) -> None:
        self.limit = limit_per_minute
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and now - hits[0] >= self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                retry_after = max(1, int(self.window - (now - hits[0])) + 1)
                raise RateLimitExceededError(
                    f"Rate limit exceeded: at most {self.limit} requests per minute. "
                    f"Try again in {retry_after} seconds.",
                    headers={"Retry-After": str(retry_after)},
                )
            hits.append(now)
            if len(self._hits) > 10_000:  # bound memory under abuse
                self._evict(now)

    def _evict(self, now: float) -> None:
        stale = [k for k, q in self._hits.items() if not q or now - q[-1] >= self.window]
        for k in stale:
            del self._hits[k]

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()

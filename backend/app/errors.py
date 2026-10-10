"""Typed application errors and the handlers that render them.

Every error response has the same shape::

    {"error": {"code": "file_too_large", "message": "Resume must be at most 5 MB."}}
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("resumelens.errors")


class AppError(Exception):
    """Base class for errors that map cleanly onto an HTTP response."""

    status_code: int = 400
    code: str = "bad_request"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        status_code: int | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code
        self.headers = headers or {}


class BadRequestError(AppError):
    status_code = 400
    code = "bad_request"


class InvalidFileTypeError(AppError):
    status_code = 415
    code = "unsupported_media_type"


class FileTooLargeError(AppError):
    status_code = 413
    code = "file_too_large"


class TooManyPagesError(AppError):
    status_code = 413
    code = "too_many_pages"


class UnreadablePDFError(AppError):
    status_code = 422
    code = "unreadable_pdf"


class InvalidJobDescriptionError(AppError):
    status_code = 422
    code = "invalid_job_description"


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class RateLimitExceededError(AppError):
    status_code = 429
    code = "rate_limited"


class FeatureUnavailableError(AppError):
    status_code = 501
    code = "feature_unavailable"


class UpstreamServiceError(AppError):
    status_code = 502
    code = "upstream_error"


_STATUS_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    413: "payload_too_large",
    415: "unsupported_media_type",
    422: "validation_error",
    429: "rate_limited",
    500: "internal_error",
    501: "not_implemented",
}


def error_body(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


def _format_validation_errors(exc: RequestValidationError) -> str:
    parts: list[str] = []
    for err in exc.errors():
        loc = [str(p) for p in err.get("loc", ()) if p not in ("body", "query", "path", "form")]
        field = ".".join(loc) or "request"
        parts.append(f"{field}: {err.get('msg', 'invalid value')}")
    return "; ".join(parts) or "Invalid request."


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(exc.code, exc.message),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=error_body("validation_error", _format_validation_errors(exc)),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _STATUS_CODES.get(exc.status_code, "http_error")
        message = exc.detail if isinstance(exc.detail, str) else "Request failed."
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(code, message),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        # Log type and traceback only; never the request payload.
        logger.exception("unhandled_error", extra={"fields": {"error_type": type(exc).__name__}})
        return JSONResponse(
            status_code=500,
            content=error_body("internal_error", "An unexpected error occurred."),
        )

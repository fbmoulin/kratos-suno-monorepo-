"""Structured logging + request-id middleware + global exception handler."""
from __future__ import annotations
import contextvars
import logging
import sys
import uuid

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings

# Context var accessible anywhere via structlog.contextvars
_REQUEST_ID: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


def _configure_structlog() -> None:
    renderer = (
        structlog.processors.JSONRenderer()
        if settings.log_format == "json"
        else structlog.dev.ConsoleRenderer()
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
        cache_logger_on_first_use=True,
    )


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        req_id = request.headers.get("X-Request-Id") or uuid.uuid4().hex
        token = _REQUEST_ID.set(req_id)
        structlog.contextvars.bind_contextvars(request_id=req_id)
        log = structlog.get_logger("http")
        log.info("request.start", method=request.method, path=request.url.path)
        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.unbind_contextvars("request_id")
            _REQUEST_ID.reset(token)
        response.headers["X-Request-Id"] = req_id
        log.info("request.end", status=response.status_code)
        return response


def setup_logging(app: FastAPI) -> None:
    _configure_structlog()
    app.add_middleware(RequestIdMiddleware)

    async def _global_handler(request: Request, exc: Exception) -> JSONResponse:
        req_id = _REQUEST_ID.get()
        log = structlog.get_logger("error")
        log.error(
            "unhandled_exception",
            exc_type=type(exc).__name__,
            exc_msg=str(exc),
            path=request.url.path,
        )
        detail = str(exc) if settings.debug else "Internal server error"
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_error",
                "code": "E_INTERNAL",
                "detail": detail,
                "request_id": req_id,
            },
            headers={"X-Request-Id": req_id},
        )

    app.add_exception_handler(Exception, _global_handler)

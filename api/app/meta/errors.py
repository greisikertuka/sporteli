"""Contract error shape: ``{"detail": {"code": str, "message": {"sq": ..., "en": ...}}}``.

Every response uses it, including unexpected server errors: a pure ASGI middleware that sits
inside CORS turns any unhandled exception into a JSON 500 (so the browser gets CORS headers and
a message it can show, not an opaque network failure), and an oversized request body is
refused with 413 before it is read.
"""

import logging

import duckdb
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger("sportel.api")

MAX_REQUEST_BYTES = 16 * 1024 * 1024
"""Largest request body accepted (a 15 MB upload plus multipart overhead)."""


def api_error(status_code: int, code: str, sq: str, en: str) -> HTTPException:
    """Build an HTTPException in the contract error shape; ``raise api_error(...)``."""
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": {"sq": sq, "en": en}},
    )


_GENERIC = {
    400: ("bad_request", "Kërkesa nuk është e vlefshme.", "The request is not valid."),
    401: ("unauthorized", "Nevojitet identifikimi.", "Authentication is required."),
    403: ("forbidden", "Veprimi nuk lejohet.", "This action is not allowed."),
    404: ("not_found", "Burimi i kërkuar nuk u gjet.", "The requested resource was not found."),
    405: ("method_not_allowed", "Metoda nuk lejohet.", "This method is not allowed."),
    413: ("too_large", "Kërkesa është shumë e madhe.", "The request is too large."),
}


def _is_contract_detail(detail: object) -> bool:
    return (
        isinstance(detail, dict)
        and isinstance(detail.get("code"), str)
        and isinstance(detail.get("message"), dict)
    )


async def _http_error(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
    if isinstance(exc.__cause__, _BodyTooLarge):  # FastAPI wraps body-parsing errors in a 400
        return too_large_response()
    detail = exc.detail
    if not _is_contract_detail(detail):
        code, sq, en = _GENERIC.get(
            exc.status_code, ("http_error", "Kërkesa dështoi.", "The request failed.")
        )
        detail = {"code": code, "message": {"sq": sq, "en": en}}
    return JSONResponse(
        {"detail": detail}, status_code=exc.status_code, headers=getattr(exc, "headers", None)
    )


async def _validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = [
        {
            "loc": [str(part) for part in err.get("loc", ())],
            "type": str(err.get("type", "")),
            "msg": str(err.get("msg", "")),
        }
        for err in exc.errors()
    ]
    fields = ", ".join(
        dict.fromkeys(".".join(e["loc"][1:]) or e["loc"][0] if e["loc"] else "?" for e in errors)
    )
    return JSONResponse(
        {
            "detail": {
                "code": "invalid_request",
                "message": {
                    "sq": f"Kërkesa nuk është e vlefshme: kontrolloni fushat {fields}.",
                    "en": f"The request is not valid: check the fields {fields}.",
                },
                "errors": errors,
            }
        },
        status_code=422,
    )


def _detail(code: str, sq: str, en: str) -> dict:
    return {"detail": {"code": code, "message": {"sq": sq, "en": en}}}


def internal_error_response() -> JSONResponse:
    return JSONResponse(
        _detail("internal_error", "Ndodhi një gabim i brendshëm.", "An internal error occurred."),
        status_code=500,
    )


def too_large_response() -> JSONResponse:
    return JSONResponse(
        _detail(
            "file_too_large",
            "Kërkesa është më e madhe se 16 MB (skedari lejohet deri në 15 MB).",
            "The request is larger than 16 MB (files are allowed up to 15 MB).",
        ),
        status_code=413,
    )


async def _database_error(_request: Request, exc: Exception) -> JSONResponse:
    logger.exception("database error", exc_info=exc)
    return JSONResponse(
        _detail(
            "database_error",
            "Baza e të dhënave nuk e përfundoi kërkesën. Provoni përsëri.",
            "The database could not complete the request. Please try again.",
        ),
        status_code=500,
    )


async def _unhandled_error(_request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled error", exc_info=exc)
    return internal_error_response()


class _BodyTooLarge(Exception):
    pass


class GuardMiddleware:
    """Pure ASGI middleware (inside CORS): refuses bodies over ``MAX_REQUEST_BYTES`` early (by
    Content-Length, and by counting streamed chunks when the length is absent or wrong) and
    turns any unhandled exception into the contract's JSON 500."""

    def __init__(self, app: ASGIApp, max_bytes: int = MAX_REQUEST_BYTES) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        for name, value in scope.get("headers", ()):
            if name == b"content-length":
                try:
                    declared = int(value)
                except ValueError:
                    declared = 0
                if declared > self.max_bytes:
                    await too_large_response()(scope, receive, send)
                    return
        received = 0
        started = False

        async def counted_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise _BodyTooLarge
            return message

        async def tracked_send(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, counted_receive, tracked_send)
        except _BodyTooLarge:
            if started:
                raise
            await too_large_response()(scope, receive, send)
        except Exception as exc:
            if started:
                raise
            if isinstance(exc.__cause__, _BodyTooLarge) or isinstance(
                exc.__context__, _BodyTooLarge
            ):
                await too_large_response()(scope, receive, send)
                return
            logger.exception("unhandled error", exc_info=exc)
            await internal_error_response()(scope, receive, send)


def install_error_handlers(app: FastAPI) -> None:
    """Every error, including FastAPI's own validation and routing errors, database errors and
    unexpected exceptions, uses the contract shape, so the web client can always show
    ``detail.message[locale]``. Call before adding CORS so CORS wraps the guard."""
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(duckdb.Error, _database_error)
    app.add_exception_handler(Exception, _unhandled_error)
    app.add_middleware(GuardMiddleware)

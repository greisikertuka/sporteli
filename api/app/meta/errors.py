"""Contract error shape: ``{"detail": {"code": str, "message": {"sq": ..., "en": ...}}}``."""

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


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


def install_error_handlers(app: FastAPI) -> None:
    """Every 4xx, including FastAPI's own validation and routing errors, uses the contract
    shape, so the web client can always show ``detail.message[locale]``."""
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(RequestValidationError, _validation_error)

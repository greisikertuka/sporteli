"""Contract error shape: ``{"detail": {"code": str, "message": {"sq": ..., "en": ...}}}``."""

from fastapi import HTTPException


def api_error(status_code: int, code: str, sq: str, en: str) -> HTTPException:
    """Build an HTTPException in the contract error shape; ``raise api_error(...)``."""
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": {"sq": sq, "en": en}},
    )

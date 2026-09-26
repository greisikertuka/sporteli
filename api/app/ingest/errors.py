"""Ingest errors carry a stable code and a bilingual message (contract error shape)."""

from __future__ import annotations

from app.meta.errors import api_error


class IngestError(Exception):
    """A user-facing ingest failure; routers turn it into ``{"detail": {code, message}}``."""

    def __init__(self, code: str, sq: str, en: str, status_code: int = 422):
        super().__init__(en)
        self.code = code
        self.message = {"sq": sq, "en": en}
        self.status_code = status_code

    def http(self):
        return api_error(self.status_code, self.code, self.message["sq"], self.message["en"])

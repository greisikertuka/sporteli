"""Ingest pipeline: read → header → exclusions → PII gate → profile → recipe → mapping → load.

Public API: ``preview``, ``commit``, ``ingest_path``, ``reset_demo``, ``IngestError``.
"""

from app.ingest.errors import IngestError
from app.ingest.pipeline import commit, ingest_path, preview, remap, reset_demo

__all__ = ["IngestError", "commit", "ingest_path", "preview", "remap", "reset_demo"]

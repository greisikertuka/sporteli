"""Ingest endpoints (mounted under /api/v1 by app.main), contract §7.

- POST   /ingest/preview           multipart "file" (+ optional "dataset")  -> IngestPreview
- POST   /ingest/remap             { preview_id, dataset }                  -> IngestPreview
- POST   /ingest/commit            { preview_id, dataset, mapping, save_recipe } -> LoadReceipt
- GET    /ingest/recipes           -> Recipe[]
- DELETE /ingest/recipes           -> { ok: true, deleted }   (behind demo_reset_enabled)
- GET    /sources                  -> SourceInfo[]
- GET    /samples                  -> SampleFile[]
- GET    /samples/{name}/file      -> the sample file itself (download)
- POST   /samples/{name}/preview   -> IngestPreview
- POST   /demo/reset               -> { ok: true, coverage: { computable, total } }
"""

from __future__ import annotations

from typing import Annotated

import duckdb
from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.config import get_settings
from app.ingest import pipeline, recipes
from app.ingest.errors import IngestError
from app.ingest.reader import MAX_BYTES
from app.meta.errors import api_error
from app.warehouse.db import get_cursor

router = APIRouter(tags=["ingest"])

Cursor = Annotated[duckdb.DuckDBPyConnection, Depends(get_cursor)]


class MappingItem(BaseModel):
    column: str
    field: str | None = None


class CommitBody(BaseModel):
    preview_id: str
    dataset: str
    mapping: list[MappingItem] = Field(default_factory=list)
    save_recipe: bool = False


class RemapBody(BaseModel):
    preview_id: str
    dataset: str


def _read_upload(file: UploadFile) -> bytes:
    data = file.file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise IngestError(
            "file_too_large",
            "Skedari është më i madh se 15 MB.",
            "The file is larger than 15 MB.",
            status_code=413,
        )
    return data


def _demo_enabled() -> None:
    if not get_settings().demo_reset_enabled:
        raise api_error(
            403,
            "demo_reset_disabled",
            "Rivendosja e demos është e çaktivizuar në këtë server.",
            "Demo reset is disabled on this server.",
        )


@router.post("/ingest/preview")
def ingest_preview(
    con: Cursor,
    file: Annotated[UploadFile, File(description="CSV, XLSX or XLS export (max 15 MB)")],
    dataset: Annotated[str | None, Form()] = None,
) -> dict:
    try:
        data = _read_upload(file)
        return pipeline.preview(data, file.filename or "", dataset=dataset or None, con=con)
    except IngestError as exc:
        raise exc.http() from exc


@router.post("/ingest/remap")
def ingest_remap(body: RemapBody, con: Cursor) -> dict:
    try:
        return pipeline.remap(body.preview_id, body.dataset, con=con)
    except IngestError as exc:
        raise exc.http() from exc


@router.post("/ingest/commit")
def ingest_commit(body: CommitBody, con: Cursor) -> dict:
    try:
        return pipeline.commit(
            body.preview_id,
            body.dataset,
            [m.model_dump() for m in body.mapping],
            body.save_recipe,
            con=con,
        )
    except IngestError as exc:
        raise exc.http() from exc


@router.get("/ingest/recipes")
def list_recipes(con: Cursor) -> list[dict]:
    return [r.api() for r in recipes.list_all(con)]


@router.delete("/ingest/recipes")
def delete_recipes(con: Cursor) -> dict:
    _demo_enabled()
    return {"ok": True, "deleted": pipeline.delete_recipes(con)}


@router.get("/sources", tags=["sources"])
def sources(con: Cursor) -> list[dict]:
    return pipeline.list_sources(con)


@router.get("/samples", tags=["samples"])
def samples(con: Cursor) -> list[dict]:
    return pipeline.sample_files(con)


@router.get("/samples/{name}/file", tags=["samples"])
def sample_file(name: str) -> FileResponse:
    try:
        path = pipeline.sample_path(name)
    except IngestError as exc:
        raise exc.http() from exc
    return FileResponse(path, filename=path.name)


@router.post("/samples/{name}/preview", tags=["samples"])
def sample_preview(name: str, con: Cursor, dataset: str | None = None) -> dict:
    try:
        path = pipeline.sample_path(name)
        return pipeline.preview(path.read_bytes(), path.name, dataset=dataset, con=con)
    except IngestError as exc:
        raise exc.http() from exc


@router.post("/demo/reset", tags=["demo"])
def demo_reset(con: Cursor) -> dict:
    _demo_enabled()
    try:
        return pipeline.reset_demo(con)
    except IngestError as exc:
        raise exc.http() from exc

"""System endpoints: GET /health, GET /datasets."""

from typing import Annotated

import duckdb
from fastapi import APIRouter, Depends

from app.catalog import DATASETS
from app.config import get_settings
from app.llm.client import get_llm
from app.warehouse.db import get_cursor

router = APIRouter()

Cursor = Annotated[duckdb.DuckDBPyConnection, Depends(get_cursor)]


def any_synthetic_source(con: duckdb.DuckDBPyConnection) -> bool:
    """True when any loaded source is flagged synthetic (drives the UI badge)."""
    row = con.execute("SELECT coalesce(bool_or(synthetic), false) FROM source").fetchone()
    return bool(row[0])


@router.get("/health", tags=["system"])
def health(con: Cursor) -> dict:
    settings = get_settings()
    try:
        db_ok = con.execute("SELECT 1").fetchone()[0] == 1
    except duckdb.Error:
        db_ok = False
    try:
        synthetic = any_synthetic_source(con) if db_ok else False
    except duckdb.Error:
        synthetic = False
    llm = get_llm()
    return {
        "status": "ok",
        "db": db_ok,
        "llm": llm.available,
        "mode": llm.mode,
        "version": settings.app_version,
        "spent_usd": round(llm.spent_usd, 6),
        "budget_usd": llm.budget_usd,
        "synthetic": synthetic,
    }


def dataset_infos(con: duckdb.DuckDBPyConnection) -> list[dict]:
    """``DatasetInfo[]``: catalog entries plus loaded/sources/rows from the warehouse."""
    out = []
    for ds in DATASETS.values():
        rows, sources = con.execute(
            f"SELECT count(*), count(DISTINCT source_id) FROM {ds.table}"
        ).fetchone()
        info = ds.api()
        info.update({"loaded": rows > 0, "sources": int(sources), "rows": int(rows)})
        out.append(info)
    return out


@router.get("/datasets", tags=["system"])
def datasets(con: Cursor) -> list[dict]:
    return dataset_infos(con)

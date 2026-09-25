from collections.abc import Iterator
from pathlib import Path

import duckdb

from app.config import get_settings


def connect(path: str) -> duckdb.DuckDBPyConnection:
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(path)


def get_connection() -> Iterator[duckdb.DuckDBPyConnection]:
    """FastAPI dependency: one connection per request."""
    con = connect(get_settings().duckdb_path)
    try:
        yield con
    finally:
        con.close()

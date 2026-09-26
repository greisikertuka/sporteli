"""One process-wide DuckDB connection; request handlers work on cursors.

DuckDB refuses a ``read_only`` connection to a file that the same process already holds
read-write, so everything (API, seed, LLM log) goes through ``get_db()``. A cursor is a
lightweight child connection that is safe to use from one thread at a time.
"""

import datetime as dt
import threading
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any

import duckdb
import pyarrow as pa

from app.config import get_settings
from app.warehouse.schema import init_schema

_lock = threading.RLock()
_db: duckdb.DuckDBPyConnection | None = None
_db_path: str | None = None


def connect(path: str) -> duckdb.DuckDBPyConnection:
    """Open a new DuckDB connection (creates the parent directory). Prefer ``get_db()``."""
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(path)


def get_db() -> duckdb.DuckDBPyConnection:
    """The process-wide connection, opened lazily with the schema initialised.

    If the configured path changes (tests point ``DUCKDB_PATH`` at a temp file), the old
    connection is closed and a new one is opened.
    """
    global _db, _db_path
    path = get_settings().duckdb_file
    with _lock:
        if _db is not None and _db_path != path:
            _close_locked()
        if _db is None:
            con = connect(path)
            init_schema(con)
            _db, _db_path = con, path
        return _db


def new_cursor() -> duckdb.DuckDBPyConnection:
    """A fresh cursor on the process-wide connection (close it when done)."""
    with _lock:
        return get_db().cursor()


def _close_locked() -> None:
    global _db, _db_path
    if _db is not None:
        try:
            _db.close()
        finally:
            _db, _db_path = None, None


def close_db() -> None:
    """Close the process-wide connection (app shutdown, tests)."""
    with _lock:
        _close_locked()


def get_cursor() -> Iterator[duckdb.DuckDBPyConnection]:
    """FastAPI dependency: a cursor for the duration of one request."""
    cur = new_cursor()
    try:
        yield cur
    finally:
        cur.close()


get_connection = get_cursor
"""Backwards-compatible name for the FastAPI dependency."""


_ARROW_TYPES = {
    "VARCHAR": (pa.string(), str),
    "INTEGER": (pa.int64(), int),
    "BIGINT": (pa.int64(), int),
    "DOUBLE": (pa.float64(), float),
    "DATE": (pa.date32(), lambda v: v.date() if isinstance(v, dt.datetime) else v),
    "BOOLEAN": (pa.bool_(), bool),
    "TIMESTAMP": (pa.timestamp("us"), None),
}


def insert_rows(
    con: duckdb.DuckDBPyConnection,
    table: str,
    rows: Sequence[Sequence[Any] | Mapping[str, Any]],
    columns: Sequence[str] | None = None,
) -> int:
    """Bulk-insert rows through Arrow (``executemany`` is ~100x slower in DuckDB).

    ``rows`` are tuples in ``columns`` order (default: all table columns) or dicts keyed by
    column. Values are converted to the column's type (None stays NULL). Returns the count.
    """
    if not rows:
        return 0
    described = con.execute(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_name = ? ORDER BY ordinal_position",
        [table],
    ).fetchall()
    types = dict(described)
    cols = list(columns) if columns is not None else [c for c, _ in described]
    arrays = []
    for i, col in enumerate(cols):
        arrow_type, convert = _ARROW_TYPES.get(types[col], (None, None))
        values = [r.get(col) if isinstance(r, Mapping) else r[i] for r in rows]
        if convert is not None:
            values = [None if v is None else convert(v) for v in values]
        arrays.append(pa.array(values, type=arrow_type))
    view = f"_insert_{table}_{threading.get_ident()}"
    con.register(view, pa.Table.from_arrays(arrays, names=cols))
    try:
        con.execute(f"INSERT INTO {table} ({', '.join(cols)}) SELECT * FROM {view}")
    finally:
        con.unregister(view)
    return len(rows)

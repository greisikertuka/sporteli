"""Sandbox: run a guarded SELECT on an isolated in-memory copy of the allowlisted tables.

The main warehouse is never exposed to model-written SQL. For each run:

1. the allowlisted tables the query reads are copied from the main database as Arrow
   snapshots into a fresh ``:memory:`` DuckDB connection (system tables are never copied);
2. the sandbox locks itself down: ``enable_external_access=false`` (no files, no network,
   no extensions, no ATTACH), Python replacement scans off (no access to Python variables),
   extension autoload/autoinstall off, small memory and thread limits, and finally
   ``lock_configuration=true`` so the query cannot change any of it;
3. the query runs under a timer thread that calls ``interrupt()`` after the timeout.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import decimal
import math
import threading
import time
from collections.abc import Iterable
from dataclasses import dataclass

import duckdb

from app.sqlguard.guard import ALLOWED_TABLES, MAX_ROWS

DEFAULT_TIMEOUT_S = 3.0
MAX_CELL_CHARS = 500
"""Longest string cell returned; longer values are cut and end with an ellipsis."""
MAX_RESULT_BYTES = 1_000_000
"""Approximate size budget of a result (JSON characters); rows past it are dropped and the
result is marked truncated. ``memory_limit`` does not bound what DuckDB hands to Python."""
_FETCH_BATCH = 16

_LOCKDOWN = (
    "SET enable_external_access = false",
    "SET python_enable_replacements = false",
    "SET autoinstall_known_extensions = false",
    "SET autoload_known_extensions = false",
    "SET memory_limit = '256MB'",
    "SET threads = 2",
    "SET lock_configuration = true",
)


class SandboxError(Exception):
    """The query failed inside the sandbox (SQL error, permission error, ...)."""


class SandboxTimeout(SandboxError):
    """The query ran longer than the timeout and was interrupted."""


@dataclass(frozen=True)
class SandboxResult:
    columns: list[str]
    rows: list[list[str | int | float | bool | None]]
    truncated: bool
    """True when the result hit the row cap or the size budget."""
    elapsed_ms: int


def _arrow_snapshot(source: duckdb.DuckDBPyConnection, table: str):
    res = source.execute(f"SELECT * FROM {table}")
    to_table = getattr(res, "to_arrow_table", None) or res.fetch_arrow_table
    return to_table()


def open_sandbox(
    source: duckdb.DuckDBPyConnection, tables: Iterable[str]
) -> duckdb.DuckDBPyConnection:
    """A locked-down in-memory connection holding copies of ``tables`` (allowlist only)."""
    wanted = sorted({t for t in tables if t in ALLOWED_TABLES})
    unknown = sorted(set(tables) - ALLOWED_TABLES)
    if unknown:
        raise SandboxError(f"tables not allowed in the sandbox: {unknown}")
    sandbox = duckdb.connect(":memory:")
    try:
        for table in wanted:
            snapshot = _arrow_snapshot(source, table)
            view = f"_snapshot_{table}"
            sandbox.register(view, snapshot)
            try:
                sandbox.execute(f"CREATE TABLE {table} AS SELECT * FROM {view}")
            finally:
                sandbox.unregister(view)
        for statement in _LOCKDOWN:
            sandbox.execute(statement)
    except Exception:
        sandbox.close()
        raise
    return sandbox


def _cut(text: str) -> str:
    return text if len(text) <= MAX_CELL_CHARS else text[: MAX_CELL_CHARS - 1] + "…"


def _jsonable(value: object) -> str | int | float | None:
    """JSON cell value: numbers stay numbers; dates, booleans and the rest become strings
    (strings longer than ``MAX_CELL_CHARS`` are cut)."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None or isinstance(value, int):
        return value
    if isinstance(value, str):
        return _cut(value)
    if isinstance(value, float):
        return None if math.isnan(value) or math.isinf(value) else round(value, 6)
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, dt.datetime | dt.date | dt.time):
        return value.isoformat()
    if isinstance(value, bytes | bytearray | memoryview):
        return _cut(bytes(value[:MAX_CELL_CHARS]).hex())
    return _cut(str(value)[: MAX_CELL_CHARS + 1])


def _cell_size(value: str | int | float | None) -> int:
    return len(value) + 4 if isinstance(value, str) else 12


def run_sandboxed(
    source: duckdb.DuckDBPyConnection,
    sql: str,
    tables: Iterable[str],
    *,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    max_rows: int = MAX_ROWS,
) -> SandboxResult:
    """Run guarded ``sql`` over snapshots of ``tables``; raises SandboxError/SandboxTimeout."""
    started = time.perf_counter()
    sandbox = open_sandbox(source, tables)
    timed_out = threading.Event()

    def _stop() -> None:
        timed_out.set()
        with contextlib.suppress(Exception):  # the connection may already be closed
            sandbox.interrupt()

    timer = threading.Timer(timeout_s, _stop)
    timer.daemon = True
    try:
        timer.start()
        try:
            cursor = sandbox.execute(sql)
            columns = [d[0] for d in (cursor.description or [])]
            rows: list[list] = []
            size = sum(len(c) + 4 for c in columns)
            truncated = False
            while not truncated:
                batch = cursor.fetchmany(_FETCH_BATCH)
                if not batch:
                    break
                for raw in batch:
                    if len(rows) >= max_rows:
                        truncated = True
                        break
                    row = [_jsonable(v) for v in raw]
                    size += sum(_cell_size(v) for v in row)
                    if size > MAX_RESULT_BYTES and rows:
                        truncated = True
                        break
                    rows.append(row)
        except duckdb.Error as exc:
            if timed_out.is_set() or isinstance(exc, duckdb.InterruptException):
                raise SandboxTimeout(f"query interrupted after {timeout_s:g} s") from exc
            raise SandboxError(str(exc).splitlines()[0][:300]) from exc
    finally:
        timer.cancel()
        sandbox.close()
    return SandboxResult(
        columns=columns,
        rows=rows,
        truncated=truncated,
        elapsed_ms=int((time.perf_counter() - started) * 1000),
    )

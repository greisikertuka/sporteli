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
    """True when the result hit the row cap."""
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


def _jsonable(value: object) -> str | int | float | None:
    """JSON cell value: numbers stay numbers; dates, booleans and the rest become strings."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None or isinstance(value, int | str):
        return value
    if isinstance(value, float):
        return None if math.isnan(value) or math.isinf(value) else round(value, 6)
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, dt.datetime | dt.date | dt.time):
        return value.isoformat()
    return str(value)


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
            raw = cursor.fetchmany(max_rows + 1)
        except duckdb.Error as exc:
            if timed_out.is_set() or isinstance(exc, duckdb.InterruptException):
                raise SandboxTimeout(f"query interrupted after {timeout_s:g} s") from exc
            raise SandboxError(str(exc).splitlines()[0][:300]) from exc
    finally:
        timer.cancel()
        sandbox.close()
    truncated = len(raw) > max_rows
    rows = [[_jsonable(v) for v in r] for r in raw[:max_rows]]
    return SandboxResult(
        columns=columns,
        rows=rows,
        truncated=truncated,
        elapsed_ms=int((time.perf_counter() - started) * 1000),
    )

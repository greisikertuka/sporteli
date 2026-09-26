"""Board, passport, lineage and definition-pin logic behind the indicator endpoints.

Everything here is deterministic code over the warehouse: values come from each passport's
fixed SQL (``registry.compute``), signals from ``signals.evaluate``, provenance from the
``source`` table. Nothing calls an LLM.

``previous`` on the board is the indicator's value as it stood one month earlier, computed by
re-running the passport's ``value_sql`` on the data cut at the end of the previous month
(see ``AsOfViews``). That keeps it comparable with ``value`` for year-to-date sums, ratios and
stocks alike, instead of mixing a year-to-date value with one month of the series.
"""

from __future__ import annotations

import datetime as dt
import logging
from collections.abc import Iterable, Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager, suppress
from dataclasses import dataclass, field

import duckdb

from app.catalog import OWNERS, POPULATION_BASES, area, get_dataset, owner
from app.indicators import registry as reg
from app.indicators import signals as sig
from app.warehouse.schema import table_columns

log = logging.getLogger(__name__)

TIME_FILTERS: dict[str, str] = {
    "request": "created_at <= DATE '{cutoff}'",
    "budget_line": "month <= DATE '{cutoff}'",
    "waste_collection": "month <= DATE '{cutoff}'",
    "revenue": "month <= DATE '{cutoff}'",
    "staff": "as_of <= DATE '{cutoff}'",
}
"""How each time-indexed fact table is cut "as of" a date (population is a reference table)."""

BASIS_PIN_KEY = "population_basis"


# --------------------------------------------------------------------------------------------
# Source metadata
# --------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class SourceMeta:
    id: str
    filename: str
    file_hash: str | None
    dataset: str | None
    synthetic: bool
    rows_read: int | None
    rows_loaded: int | None
    rows_excluded_json: str | None
    reconciliation_json: str | None
    loaded_at: dt.datetime | None


def _looks_synthetic(name: str) -> bool:
    return "SINTETIKE" in name.upper()


def source_meta(con: duckdb.DuckDBPyConnection) -> dict[str, SourceMeta]:
    """Every row of the ``source`` table keyed by id, oldest load first."""
    rows = con.execute(
        "SELECT id, filename, file_hash, dataset, synthetic, rows_read, rows_loaded, "
        "rows_excluded_json, reconciliation_json, loaded_at FROM source "
        "ORDER BY loaded_at NULLS FIRST, id"
    ).fetchall()
    out = {}
    for r in rows:
        filename = r[1] or r[0]
        synthetic = bool(r[4]) if r[4] is not None else _looks_synthetic(filename)
        out[r[0]] = SourceMeta(r[0], filename, r[2], r[3], synthetic, r[5], r[6], r[7], r[8], r[9])
    return out


def _meta_for(meta: dict[str, SourceMeta], source_id: str) -> SourceMeta:
    m = meta.get(source_id)
    if m is not None:
        return m
    return SourceMeta(
        source_id, source_id, None, None, _looks_synthetic(source_id), None, None, None, None, None
    )


# --------------------------------------------------------------------------------------------
# "As of" views for previous-period values
# --------------------------------------------------------------------------------------------


def cutoff_before(period: str | None) -> dt.date | None:
    """Last day of the month before ``period`` ("2026-08" → 2026-07-31)."""
    if not period:
        return None
    try:
        year, month = (int(x) for x in period.split("-")[:2])
        return dt.date(year, month, 1) - dt.timedelta(days=1)
    except ValueError:
        return None


class AsOfViews:
    """Child cursors on which the time-indexed fact tables are cut at a date.

    Each cursor shadows ``request``, ``budget_line``, ``waste_collection``, ``revenue`` and
    ``staff`` with temporary views (temporary objects are private to one DuckDB connection,
    so other requests never see them). Passport SQL then runs unchanged "as of" the cutoff.
    """

    def __init__(self, con: duckdb.DuckDBPyConnection):
        self._con = con
        self._cursors: dict[dt.date, duckdb.DuckDBPyConnection] = {}

    def cursor(self, cutoff: dt.date) -> duckdb.DuckDBPyConnection:
        cur = self._cursors.get(cutoff)
        if cur is None:
            cur = self._con.cursor()
            catalog = cur.execute("SELECT current_database()").fetchone()[0]
            for table, condition in TIME_FILTERS.items():
                where = condition.format(cutoff=cutoff.isoformat())
                cur.execute(
                    f"CREATE OR REPLACE TEMP VIEW {table} AS "
                    f'SELECT * FROM "{catalog}".main.{table} WHERE {where}'
                )
            self._cursors[cutoff] = cur
        return cur

    def close(self) -> None:
        for cur in self._cursors.values():
            with suppress(duckdb.Error):  # closing is best effort
                cur.close()
        self._cursors.clear()


@contextmanager
def as_of_views(con: duckdb.DuckDBPyConnection) -> Iterator[AsOfViews]:
    views = AsOfViews(con)
    try:
        yield views
    finally:
        views.close()


def previous_value(
    p: reg.Passport,
    con: duckdb.DuckDBPyConnection,
    period: str | None,
    basis: str,
    views: AsOfViews | None = None,
) -> float | None:
    """The passport's value computed on the data as of the end of the month before ``period``."""
    cutoff = cutoff_before(period)
    if cutoff is None:
        return None
    own = views is None
    views = views or AsOfViews(con)
    try:
        cur = views.cursor(cutoff)
        res = reg._run(cur, p.value_sql, basis)
        cols = [d[0] for d in res.description]
        row = res.fetchone()
        if not row:
            return None
        return reg._num(dict(zip(cols, row, strict=False)).get("value"))
    except duckdb.Error as exc:  # pragma: no cover - defensive: never break the board
        log.warning("previous value for %s failed: %s", p.code, exc)
        return None
    finally:
        if own:
            views.close()


# --------------------------------------------------------------------------------------------
# Evaluation of one passport
# --------------------------------------------------------------------------------------------


@dataclass
class Evaluated:
    passport: reg.Passport
    state: str
    missing: list[str]
    basis: str | None
    """Population basis (per-capita passports only; the pinned one)."""
    result: reg.ComputeResult | None = None
    previous: float | None = None
    signals: list[sig.Signal] = field(default_factory=list)
    """Active signals (shown on the tile)."""
    accepted: list[tuple[sig.Signal, sig.Acceptance]] = field(default_factory=list)
    """Signals whose rule was accepted with a reason for this indicator (passport only)."""
    sources: list[dict] = field(default_factory=list)
    lineage: list[dict] = field(default_factory=list)
    error: str | None = None

    @property
    def value(self) -> float | None:
        return self.result.value if self.result else None

    @property
    def period(self) -> str | None:
        return self.result.period if self.result else None


def breakdown_series(
    p: reg.Passport, con: duckdb.DuckDBPyConnection, basis: str
) -> dict[str, list[sig.Point]]:
    """``{dimension: [Point, ...]}`` from ``breakdown_sql`` (empty if the passport has none)."""
    if not p.breakdown_sql:
        return {}
    out: dict[str, list[sig.Point]] = {}
    for period, dim, value in reg._run(con, p.breakdown_sql, basis).fetchall():
        if period is None:
            continue
        out.setdefault(str(dim), []).append(sig.Point(str(period), reg._num(value)))
    for pts in out.values():
        pts.sort(key=lambda pt: pt.period)
    return out


def evaluate_passport(
    p: reg.Passport,
    con: duckdb.DuckDBPyConnection,
    *,
    basis: str,
    loaded: set[str],
    meta: dict[str, SourceMeta],
    views: AsOfViews | None = None,
    acks: dict[str, sig.Acceptance] | None = None,
) -> Evaluated:
    missing = [d for d in p.required_datasets if d not in loaded]
    e = Evaluated(
        passport=p,
        state="missing" if missing else "computable",
        missing=missing,
        basis=basis if p.uses_basis else None,
    )
    if missing:
        return e
    try:
        r = reg.compute(p, con, basis, loaded=loaded)
    except duckdb.Error as exc:
        log.exception("computing %s failed", p.code)
        e.error = type(exc).__name__
        e.signals = [
            sig.Signal(
                "compute_error",
                "warn",
                {
                    "sq": "Treguesi nuk u llogarit me të dhënat e ngarkuara. Kontrolloni "
                    "llojet e kolonave në eksport.",
                    "en": "The indicator could not be computed from the loaded data. Check "
                    "the column types in the export.",
                },
                None,
            )
        ]
        return e
    e.result = r
    e.previous = previous_value(p, con, r.period, basis, views) if r.value is not None else None
    e.lineage = [
        {
            "source_id": s.source_id,
            "filename": _meta_for(meta, s.source_id).filename,
            "file_hash": s.file_hash or _meta_for(meta, s.source_id).file_hash or "",
            "row_count": s.row_count,
            "row_ranges": s.row_ranges,
        }
        for s in r.lineage
    ]
    e.sources = [
        {
            "source_id": s.source_id,
            "filename": _meta_for(meta, s.source_id).filename,
            "synthetic": _meta_for(meta, s.source_id).synthetic,
        }
        for s in r.lineage
    ]
    recons = [
        rec
        for s in r.lineage
        for rec in sig.parse_reconciliation(
            _meta_for(meta, s.source_id).filename,
            _meta_for(meta, s.source_id).reconciliation_json,
        )
    ]
    points = [sig.Point(s.period, s.value) for s in r.series]
    needs_breakdown = {"placeholder_value", "swing"} & set(p.checks)
    found = sig.evaluate(
        p,
        value=r.value,
        period=r.period,
        series=points,
        breakdown=breakdown_series(p, con, basis) if needs_breakdown else None,
        reconciliations=recons,
    )
    acks = acks or {}
    e.signals = [s for s in found if s.rule not in acks]
    e.accepted = [(s, acks[s.rule]) for s in found if s.rule in acks]
    return e


def _load_pack(pack: str) -> reg.Pack:
    """A passport pack or ``KeyError`` (coverage packs such as al_smp are not passport packs)."""
    try:
        return reg.load_pack(pack)
    except (KeyError, ValueError) as exc:
        raise KeyError(pack) from exc


MAX_WORKERS = 4
"""Passports are evaluated on this many child cursors in parallel (DuckDB releases the GIL
while a query runs; one board goes from ~0.5 s to ~0.15 s on the synthetic samples)."""


def evaluate_pack(
    con: duckdb.DuckDBPyConnection, pack: str = "core_kpi", *, workers: int = MAX_WORKERS
) -> list[Evaluated]:
    """Evaluate every passport of a pack, in pack order.

    Each dataset is checked once. Passports are shared round-robin across ``workers`` child
    cursors (created here, on the calling thread), each with its own "as of" views.
    """
    pk = _load_pack(pack)
    basis = reg.get_population_basis(con)
    needed = {d for p in pk.passports for d in p.required_datasets}
    loaded = reg.loaded_datasets(con, needed)
    meta = source_meta(con)
    acks = acceptances(con)
    n = max(1, min(workers, len(pk.passports)))
    if n == 1:
        with as_of_views(con) as views:
            return [
                evaluate_passport(
                    p,
                    con,
                    basis=basis,
                    loaded=loaded,
                    meta=meta,
                    views=views,
                    acks=acks.get(p.code),
                )
                for p in pk.passports
            ]

    def run(cur: duckdb.DuckDBPyConnection, chunk: list[int]) -> list[tuple[int, Evaluated]]:
        with as_of_views(cur) as views:
            return [
                (
                    i,
                    evaluate_passport(
                        pk.passports[i],
                        cur,
                        basis=basis,
                        loaded=loaded,
                        meta=meta,
                        views=views,
                        acks=acks.get(pk.passports[i].code),
                    ),
                )
                for i in chunk
            ]

    chunks = [list(range(k, len(pk.passports), n)) for k in range(n)]
    cursors = [con.cursor() for _ in range(n)]
    try:
        with ThreadPoolExecutor(max_workers=n, thread_name_prefix="passport") as pool:
            futures = [
                pool.submit(run, cur, chunk) for cur, chunk in zip(cursors, chunks, strict=True)
            ]
            done = [pair for f in futures for pair in f.result()]
    finally:
        for cur in cursors:
            cur.close()
    return [e for _, e in sorted(done, key=lambda pair: pair[0])]


def evaluate_one(con: duckdb.DuckDBPyConnection, code: str, pack: str = "core_kpi") -> Evaluated:
    """Evaluate one passport; ``KeyError`` for an unknown code or pack."""
    p = _load_pack(pack).get(code)
    basis = reg.get_population_basis(con)
    loaded = reg.loaded_datasets(con, p.required_datasets)
    with as_of_views(con) as views:
        return evaluate_passport(
            p,
            con,
            basis=basis,
            loaded=loaded,
            meta=source_meta(con),
            views=views,
            acks=acceptances(con).get(p.code),
        )


# --------------------------------------------------------------------------------------------
# API shapes
# --------------------------------------------------------------------------------------------


def missing_entries(datasets: Iterable[str]) -> list[dict]:
    out = []
    for key in datasets:
        ds = get_dataset(key)
        out.append({"dataset": key, "name": dict(ds.name), "owner": dict(OWNERS[ds.owner])})
    return out


def summary(e: Evaluated) -> dict:
    """``IndicatorSummary``."""
    p, r = e.passport, e.result
    return {
        "code": p.code,
        "area": area(p.area),
        "name": dict(p.name),
        "unit": p.unit,
        "unit_label": p.label,
        "state": e.state,
        "value": r.value if r else None,
        "period": p.reported_period(r.period) if r else None,
        "previous": e.previous,
        "target": p.target,
        "direction": p.direction,
        "status": reg.status_vs_target(p, r.value) if r else None,
        "owner": owner(p.owner),
        "missing": missing_entries(e.missing),
        "signals": [s.api() for s in e.signals],
        "sources": list(e.sources),
        "smp_ref": p.smp_ref,
        "version": p.version,
        "formula_status": p.formula_status,
        "basis": e.basis,
        "sparkline": [{"period": s.period, "value": s.value} for s in r.series] if r else [],
    }


def display_sql(p: reg.Passport, basis: str | None) -> str:
    """The value SQL as shown to people: ``$basis`` replaced by the quoted basis in use."""
    sql = p.value_sql.strip()
    if basis and "$basis" in sql:
        sql = sql.replace("$basis", f"'{basis}'")
    return sql


def passport_detail(e: Evaluated) -> dict:
    """``Passport`` = ``IndicatorSummary`` plus formula, SQL, series, lineage and checks."""
    p, r = e.passport, e.result
    out = summary(e)
    out.update(
        {
            "formula": dict(p.formula),
            "question": dict(p.question),
            "sql": display_sql(p, e.basis),
            "series": [{"period": s.period, "value": s.value} for s in r.series] if r else [],
            "lineage": list(e.lineage),
            "required_datasets": list(p.required_datasets),
            "checks": sig.check_results(p, e.signals, e.accepted) if r else [],
            "computed_at": r.computed_at if r else None,
        }
    )
    return out


def board(con: duckdb.DuckDBPyConnection, pack: str = "core_kpi") -> dict:
    """``IndicatorBoard``."""
    evaluated = evaluate_pack(con, pack)
    return board_from(evaluated, con, pack)


def board_from(evaluated: list[Evaluated], con: duckdb.DuckDBPyConnection, pack: str) -> dict:
    computable = sum(1 for e in evaluated if e.state == "computable")
    periods = [e.period for e in evaluated if e.period]
    return {
        "pack": pack,
        "as_of": max(periods) if periods else None,
        "coverage": {
            "computable": computable,
            "missing": len(evaluated) - computable,
            "document": 0,
            "national": 0,
            "total": len(evaluated),
        },
        "basis": {"population": reg.get_population_basis(con)},
        "indicators": [summary(e) for e in evaluated],
    }


# --------------------------------------------------------------------------------------------
# Lineage rows
# --------------------------------------------------------------------------------------------


def _allocate(limit: int, sizes: list[int]) -> list[int]:
    """Share ``limit`` rows across sources as evenly as their sizes allow."""
    quotas = [0] * len(sizes)
    remaining = limit
    active = [i for i, s in enumerate(sizes) if s > 0]
    while remaining > 0 and active:
        share = max(1, remaining // len(active))
        for i in list(active):
            take = min(share, sizes[i] - quotas[i], remaining)
            quotas[i] += take
            remaining -= take
            if quotas[i] >= sizes[i]:
                active.remove(i)
            if remaining == 0:
                break
    return quotas


def _json_value(v: object) -> str | int | float | None:
    if v is None or isinstance(v, str | int | float):
        return v  # type: ignore[return-value]
    if isinstance(v, dt.datetime):
        return v.isoformat(timespec="seconds")
    if isinstance(v, dt.date):
        return v.isoformat()
    try:
        return float(v)  # Decimal and friends
    except (TypeError, ValueError):
        return str(v)


def _table_for_source(
    con: duckdb.DuckDBPyConnection, source_id: str, tables: list[str], meta: SourceMeta
) -> str | None:
    if meta.dataset:
        try:
            table = get_dataset(meta.dataset).table
        except KeyError:
            table = None
        if table in tables:
            return table
    for table in tables:
        hit = con.execute(
            f"SELECT EXISTS (SELECT 1 FROM {table} WHERE source_id = ?)", [source_id]
        ).fetchone()[0]
        if hit:
            return table
    return None


def lineage_rows(
    con: duckdb.DuckDBPyConnection, code: str, limit: int = 50, pack: str = "core_kpi"
) -> dict:
    """``LineageRows``: the first contributing rows (shared across source files)."""
    p = _load_pack(pack).get(code)
    out: dict = {"code": p.code, "columns": [], "total": 0, "rows": []}
    if reg.missing_datasets(p, con):
        return out
    basis = reg.get_population_basis(con)
    pairs = reg.lineage_rows(p, con, basis)
    out["total"] = len(pairs)
    by_source: dict[str, list[int]] = {}
    for sid, row_no in pairs:
        by_source.setdefault(sid, []).append(row_no)
    for nums in by_source.values():
        nums.sort()
    quotas = _allocate(max(limit, 0), [len(v) for v in by_source.values()])
    meta = source_meta(con)
    tables = [get_dataset(d).table for d in p.required_datasets]
    columns: list[str] = []
    rows: list[dict] = []
    for (sid, nums), quota in zip(by_source.items(), quotas, strict=True):
        if quota <= 0:
            continue
        m = _meta_for(meta, sid)
        table = _table_for_source(con, sid, tables, m)
        if table is None:
            continue
        cols = [c for c in table_columns(con, table) if c not in ("source_id", "row_no")]
        for c in cols:
            if c not in columns:
                columns.append(c)
        wanted = nums[:quota]
        result = con.execute(
            f"SELECT row_no, {', '.join(cols)} FROM {table} "
            "WHERE source_id = ? AND list_contains(?, row_no) ORDER BY row_no",
            [sid, wanted],
        ).fetchall()
        for rec in result:
            rows.append(
                {
                    "source_file": m.filename,
                    "row_no": int(rec[0]),
                    "values": {c: _json_value(v) for c, v in zip(cols, rec[1:], strict=True)},
                }
            )
    out["columns"] = columns
    out["rows"] = rows
    return out


# --------------------------------------------------------------------------------------------
# Population basis pin
# --------------------------------------------------------------------------------------------


def basis_pin(con: duckdb.DuckDBPyConnection) -> dict:
    """The current pin: ``{value, reason, pinned_at}`` (default basis when never pinned)."""
    row = con.execute(
        "SELECT value, reason, pinned_at FROM definition_pin WHERE key = ?", [BASIS_PIN_KEY]
    ).fetchone()
    value = reg.get_population_basis(con)
    if not row or row[0] != value:
        return {"value": value, "reason": None, "pinned_at": None}
    pinned = row[2].isoformat(timespec="seconds") if row[2] else None
    return {"value": value, "reason": row[1], "pinned_at": pinned}


def basis_response(con: duckdb.DuckDBPyConnection, pack: str = "core_kpi") -> dict:
    """``POST/GET /definitions/population_basis`` response: the pin and affected indicators."""
    pin = basis_pin(con)
    loaded = reg.loaded_datasets(con)
    indicators = []
    for p in reg.load_pack(pack).passports:
        if not p.uses_basis:
            continue
        value = period = None
        if set(p.required_datasets) <= loaded:
            r = reg.compute(p, con, pin["value"])
            value, period = r.value, p.reported_period(r.period)
        indicators.append(
            {
                "code": p.code,
                "name": dict(p.name),
                "value": value,
                "period": period,
                "basis": pin["value"],
            }
        )
    totals = dict(
        con.execute("SELECT basis, sum(residents) FROM population GROUP BY basis").fetchall()
    )
    return {
        "ok": True,
        "key": BASIS_PIN_KEY,
        "value": pin["value"],
        "label": dict(POPULATION_BASES[pin["value"]]),
        "reason": pin["reason"],
        "pinned_at": pin["pinned_at"],
        "options": [
            {
                "value": key,
                "label": dict(label),
                "residents": int(totals[key]) if totals.get(key) is not None else None,
            }
            for key, label in POPULATION_BASES.items()
        ],
        "indicators": indicators,
    }


def pin_population_basis(
    con: duckdb.DuckDBPyConnection, value: str, reason: str | None = None
) -> None:
    """Pin the population basis used by per-capita passports. ``ValueError`` if unknown."""
    if value not in POPULATION_BASES:
        raise ValueError(value)
    now = dt.datetime.now(dt.UTC).replace(tzinfo=None, microsecond=0)
    text = (reason or "").strip() or None
    con.execute("BEGIN TRANSACTION")
    try:
        con.execute("DELETE FROM definition_pin WHERE key = ?", [BASIS_PIN_KEY])
        con.execute(
            "INSERT INTO definition_pin (key, value, pinned_at, reason) VALUES (?, ?, ?, ?)",
            [BASIS_PIN_KEY, value, now, text],
        )
        con.execute("COMMIT")
    except duckdb.Error:
        con.execute("ROLLBACK")
        raise


# --------------------------------------------------------------------------------------------
# Accepting a signal with a reason (against alert fatigue)
# --------------------------------------------------------------------------------------------

ACCEPTED = "accepted"


def acceptances(con: duckdb.DuckDBPyConnection) -> dict[str, dict[str, sig.Acceptance]]:
    """``{indicator_code: {rule: Acceptance}}`` from ``signal_ack`` (latest row wins)."""
    rows = con.execute(
        "SELECT indicator_code, rule, reason, ts FROM signal_ack WHERE status = ? "
        "ORDER BY ts NULLS FIRST",
        [ACCEPTED],
    ).fetchall()
    out: dict[str, dict[str, sig.Acceptance]] = {}
    for code, rule, reason, ts in rows:
        stamp = ts.isoformat(timespec="seconds") if ts else ""
        out.setdefault(code, {})[rule] = sig.Acceptance(rule, reason or "", stamp)
    return out


def accept_signal(
    con: duckdb.DuckDBPyConnection, code: str, rule: str, reason: str, pack: str = "core_kpi"
) -> dict:
    """Accept a passport's signal rule with a reason. ``KeyError``/``ValueError`` if invalid."""
    p = _load_pack(pack).get(code)
    if rule not in p.checks:
        raise ValueError(f"{code} has no check {rule}")
    text = (reason or "").strip()
    if len(text) < 3:
        raise ValueError("a reason is required")
    now = dt.datetime.now(dt.UTC).replace(tzinfo=None, microsecond=0)
    con.execute("BEGIN TRANSACTION")
    try:
        con.execute("DELETE FROM signal_ack WHERE indicator_code = ? AND rule = ?", [code, rule])
        con.execute(
            "INSERT INTO signal_ack (indicator_code, rule, status, reason, ts) "
            "VALUES (?, ?, ?, ?, ?)",
            [code, rule, ACCEPTED, text, now],
        )
        con.execute("COMMIT")
    except duckdb.Error:
        con.execute("ROLLBACK")
        raise
    return {
        "ok": True,
        "code": code,
        "rule": rule,
        "status": ACCEPTED,
        "reason": text,
        "ts": now.isoformat(timespec="seconds"),
    }


def withdraw_acceptance(con: duckdb.DuckDBPyConnection, code: str, rule: str) -> dict:
    """Remove an acceptance so the signal shows on the board again."""
    n = con.execute(
        "SELECT count(*) FROM signal_ack WHERE indicator_code = ? AND rule = ?", [code, rule]
    ).fetchone()[0]
    con.execute("DELETE FROM signal_ack WHERE indicator_code = ? AND rule = ?", [code, rule])
    return {"ok": True, "code": code, "rule": rule, "deleted": int(n)}

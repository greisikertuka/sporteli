"""Indicator passport registry: load packs, decide state, compute values, format answers.

A passport's numbers always come from its fixed SQL run by code; answer text is a template
filled with values formatted here. Nothing in this module calls an LLM.

Public API (used by the indicators, ingest and copilot modules):

- ``load_pack(name="core_kpi") -> Pack`` (cached) and ``get_passport(code) -> Passport``
- ``dataset_loaded(con, dataset)``, ``loaded_datasets(con)``, ``missing_datasets(p, con)``
- ``state(p, con)`` → ``"computable" | "missing"``; ``states(con)``; ``computable_codes(con)``
- ``compute(p, con, basis=None) -> ComputeResult`` (value, period, previous, series, lineage)
- ``coverage(con, pack)`` → ``{computable, missing, document, national, total}``
- ``newly_unlocked(before, after)`` and ``describe_codes(codes)``
- ``get_population_basis(con)``; ``format_value``/``format_period``/``render_answer``
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable, Mapping
from decimal import ROUND_HALF_UP, Decimal
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

import duckdb
import yaml
from pydantic import AfterValidator, BaseModel, ConfigDict

from app.catalog import (
    DATASETS,
    DEFAULT_POPULATION_BASIS,
    MONTH_NAMES_EN,
    MONTH_NAMES_SQ,
    POPULATION_BASES,
    UNIT_LABELS,
    L10n,
    get_dataset,
)

PACKS_DIR = Path(__file__).parent / "packs"
LOCALES = ("sq", "en")

Unit = Literal["count", "percent", "days", "kg_per_resident", "lek_per_ton", "per_1000"]
Direction = Literal["higher_better", "lower_better", "none"]
Area = Literal["requests", "finance", "waste", "revenue", "hr"]
State = Literal["computable", "missing"]
CheckRule = Literal["placeholder_value", "swing", "rate_bounds", "off_target", "parts_vs_total"]

UNIT_DECIMALS: dict[str, int] = {
    "count": 0,
    "percent": 1,
    "days": 1,
    "kg_per_resident": 1,
    "lek_per_ton": 0,
    "per_1000": 1,
}


def _check_l10n(value: dict[str, str]) -> dict[str, str]:
    missing = [loc for loc in LOCALES if not value.get(loc)]
    if missing:
        raise ValueError(f"L10n text missing locale(s): {missing}")
    return value


L10nText = Annotated[dict[str, str], AfterValidator(_check_l10n)]


class Aliases(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    sq: list[str]
    en: list[str]


class Passport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    version: str
    area: Area
    name: L10nText
    question: L10nText
    aliases: Aliases
    formula: L10nText
    formula_status: Literal["draft", "from_source", "validated"] = "draft"
    unit: Unit
    unit_label: L10nText | None = None
    direction: Direction
    target: float | None = None
    required_datasets: list[str]
    owner: str
    smp_ref: str | None = None
    smp_note: L10nText | None = None
    checks: list[CheckRule] = []
    answer: L10nText
    value_sql: str
    series_sql: str
    lineage_sql: str
    breakdown_sql: str | None = None
    decimals: int | None = None
    period_kind: Literal["ytd", "point"] = "ytd"
    """``ytd``: the value covers 1 January to the end of the latest month; ``point``: a stock
    at the end of the latest month (e.g. open overdue requests, headcount)."""

    @property
    def uses_basis(self) -> bool:
        """True for per-capita passports (their SQL takes the ``$basis`` parameter)."""
        return "$basis" in self.value_sql

    def reported_period(self, period: str | None) -> str | None:
        """The period as reported to people and clients.

        Year-to-date values report an ISO 8601 month range (``"2026-01/2026-08"``) so a
        headline value is never read as a single month; stocks report the month itself.
        Internally (previous values, signals, answer templates) the latest month is used.
        """
        if not period or self.period_kind != "ytd" or "/" in period:
            return period
        year, _, month = period.partition("-")
        if not month or month[:2] == "01":
            return period
        return f"{year}-01/{period}"

    @property
    def label(self) -> L10n:
        """Unit label shown next to the value."""
        return dict(self.unit_label or UNIT_LABELS[self.unit])

    def phrasings(self, locale: str | None = None) -> list[str]:
        """Canonical question plus aliases (both locales unless ``locale`` is given)."""
        locs = [locale] if locale else list(LOCALES)
        out: list[str] = []
        for loc in locs:
            out.append(self.question[loc])
            out.extend(getattr(self.aliases, loc))
        return out


class Pack(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    pack: str
    version: str
    label: L10nText
    passports: list[Passport]

    def get(self, code: str) -> Passport:
        for p in self.passports:
            if p.code == code:
                return p
        raise KeyError(f"unknown indicator: {code}")

    @property
    def codes(self) -> list[str]:
        return [p.code for p in self.passports]


@lru_cache
def load_pack(name: str = "core_kpi") -> Pack:
    """Load and validate a passport pack from ``packs/{name}.yaml`` (cached)."""
    path = PACKS_DIR / f"{name}.yaml"
    if not path.is_file():
        raise KeyError(f"unknown pack: {name}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    pack = Pack.model_validate(raw)
    codes = pack.codes
    if len(codes) != len(set(codes)):
        raise ValueError(f"duplicate passport codes in {name}")
    for p in pack.passports:
        for ds in p.required_datasets:
            get_dataset(ds)  # raises on unknown datasets
    return pack


def get_passport(code: str, pack: str = "core_kpi") -> Passport:
    return load_pack(pack).get(code)


# --------------------------------------------------------------------------------------------
# State
# --------------------------------------------------------------------------------------------


def dataset_loaded(con: duckdb.DuckDBPyConnection, dataset: str) -> bool:
    """True when the dataset's canonical table has at least one row."""
    table = get_dataset(dataset).table
    return bool(con.execute(f"SELECT EXISTS (SELECT 1 FROM {table})").fetchone()[0])


def loaded_datasets(
    con: duckdb.DuckDBPyConnection, datasets: Iterable[str] | None = None
) -> set[str]:
    """Dataset keys (default: all catalog datasets) whose table has rows."""
    keys = list(datasets) if datasets is not None else list(DATASETS)
    return {k for k in keys if dataset_loaded(con, k)}


def missing_datasets(passport: Passport, con: duckdb.DuckDBPyConnection) -> list[str]:
    return [d for d in passport.required_datasets if not dataset_loaded(con, d)]


def state(passport: Passport, con: duckdb.DuckDBPyConnection) -> State:
    return "missing" if missing_datasets(passport, con) else "computable"


def states(con: duckdb.DuckDBPyConnection, pack: str = "core_kpi") -> dict[str, State]:
    """``{code: state}`` in pack order (each dataset is checked once)."""
    p = load_pack(pack)
    needed = {d for x in p.passports for d in x.required_datasets}
    loaded = loaded_datasets(con, needed)
    return {
        x.code: "computable" if set(x.required_datasets) <= loaded else "missing"
        for x in p.passports
    }


def computable_codes(con: duckdb.DuckDBPyConnection, pack: str = "core_kpi") -> set[str]:
    return {c for c, s in states(con, pack).items() if s == "computable"}


def coverage(con: duckdb.DuckDBPyConnection, pack: str = "core_kpi") -> dict[str, int]:
    """Counts by state for a passport pack (document/national are 0 for computed packs)."""
    st = states(con, pack)
    computable = sum(1 for s in st.values() if s == "computable")
    return {
        "computable": computable,
        "missing": len(st) - computable,
        "document": 0,
        "national": 0,
        "total": len(st),
    }


def newly_unlocked(
    before: Mapping[str, str] | Iterable[str], after: Mapping[str, str] | Iterable[str]
) -> list[str]:
    """Codes computable in ``after`` but not in ``before``.

    Accepts ``states()`` dicts or iterables of computable codes; keeps ``after``'s order.
    """

    def computable(x: Mapping[str, str] | Iterable[str]) -> list[str]:
        if isinstance(x, Mapping):
            return [c for c, s in x.items() if s == "computable"]
        return list(x)

    prev = set(computable(before))
    return [c for c in computable(after) if c not in prev]


def describe_codes(codes: Iterable[str], pack: str = "core_kpi") -> list[dict]:
    """``[{code, name}]`` for codes (e.g. ``LoadReceipt.indicators_unlocked``)."""
    p = load_pack(pack)
    return [{"code": c, "name": dict(p.get(c).name)} for c in codes]


def get_population_basis(con: duckdb.DuckDBPyConnection) -> str:
    """The pinned population basis (``definition_pin`` key ``population_basis``)."""
    row = con.execute("SELECT value FROM definition_pin WHERE key = 'population_basis'").fetchone()
    if row and row[0] in POPULATION_BASES:
        return row[0]
    return DEFAULT_POPULATION_BASIS


# --------------------------------------------------------------------------------------------
# Compute
# --------------------------------------------------------------------------------------------


class SeriesPoint(BaseModel):
    period: str
    value: float | None


class LineageSource(BaseModel):
    source_id: str
    filename: str
    file_hash: str | None
    row_count: int
    row_ranges: str


class ComputeResult(BaseModel):
    code: str
    value: float | None
    period: str | None
    previous: float | None
    """Previous point of the series (the month before ``period``), if any."""
    series: list[SeriesPoint]
    lineage: list[LineageSource]
    basis: str | None
    """Population basis used (per-capita passports only)."""
    sql: str
    computed_at: str


class NotComputable(Exception):
    def __init__(self, code: str, missing: list[str]):
        super().__init__(f"{code} is missing datasets: {missing}")
        self.code = code
        self.missing = missing


def _params(sql: str, basis: str) -> dict | None:
    return {"basis": basis} if "$basis" in sql else None


def _run(con: duckdb.DuckDBPyConnection, sql: str, basis: str):
    params = _params(sql, basis)
    return con.execute(sql, params) if params else con.execute(sql)


def _num(x: object) -> float | None:
    if x is None:
        return None
    f = float(x)  # type: ignore[arg-type]
    return None if f != f else round(f, 6)  # NaN guard


def row_ranges(row_nos: Iterable[int]) -> str:
    """Compress row numbers: [4, 5, 6, 9] → "4–6, 9"."""
    nums = sorted(set(row_nos))
    if not nums:
        return ""
    parts = []
    start = prev = nums[0]
    for n in nums[1:]:
        if n == prev + 1:
            prev = n
            continue
        parts.append(f"{start}–{prev}" if prev > start else str(start))
        start = prev = n
    parts.append(f"{start}–{prev}" if prev > start else str(start))
    return ", ".join(parts)


def lineage_rows(
    passport: Passport, con: duckdb.DuckDBPyConnection, basis: str | None = None
) -> list[tuple[str, int]]:
    """``(source_id, row_no)`` of every row that contributes to the value."""
    b = basis or get_population_basis(con)
    return [(r[0], int(r[1])) for r in _run(con, passport.lineage_sql, b).fetchall()]


def summarize_lineage(
    con: duckdb.DuckDBPyConnection, rows: Iterable[tuple[str, int]]
) -> list[LineageSource]:
    """Group lineage rows per source with filename/hash from the ``source`` table."""
    by_source: dict[str, list[int]] = {}
    for sid, row_no in rows:
        by_source.setdefault(sid, []).append(row_no)
    if not by_source:
        return []
    ids = list(by_source)
    placeholders = ", ".join("?" for _ in ids)
    meta = {
        r[0]: (r[1], r[2])
        for r in con.execute(
            f"SELECT id, filename, file_hash FROM source WHERE id IN ({placeholders})", ids
        ).fetchall()
    }
    out = []
    for sid, nums in by_source.items():
        filename, file_hash = meta.get(sid, (None, None))
        out.append(
            LineageSource(
                source_id=sid,
                filename=filename or sid,
                file_hash=file_hash,
                row_count=len(nums),
                row_ranges=row_ranges(nums),
            )
        )
    return out


def compute(
    passport: Passport,
    con: duckdb.DuckDBPyConnection,
    basis: str | None = None,
    *,
    loaded: set[str] | None = None,
) -> ComputeResult:
    """Run the passport's SQL. Raises ``NotComputable`` when a required dataset is empty.

    ``loaded`` (optional) is the set of loaded dataset keys when the caller already knows it,
    which saves one query per dataset.
    """
    if loaded is not None:
        missing = [d for d in passport.required_datasets if d not in loaded]
    else:
        missing = missing_datasets(passport, con)
    if missing:
        raise NotComputable(passport.code, missing)
    b = basis or get_population_basis(con)

    res = _run(con, passport.value_sql, b)
    cols = [d[0] for d in res.description]
    row = res.fetchone()
    record = dict(zip(cols, row, strict=False)) if row else {}
    value = _num(record.get("value"))
    period = record.get("period")

    series = [
        SeriesPoint(period=str(p), value=_num(v))
        for p, v in _run(con, passport.series_sql, b).fetchall()
        if p is not None
    ]
    if period is None and series:
        period = series[-1].period
    previous = None
    if period is not None:
        earlier = [s for s in series if s.period < period]
        previous = earlier[-1].value if earlier else None

    lineage = summarize_lineage(con, lineage_rows(passport, con, b))
    return ComputeResult(
        code=passport.code,
        value=value,
        period=str(period) if period is not None else None,
        previous=previous,
        series=series,
        lineage=lineage,
        basis=b if passport.uses_basis else None,
        sql=passport.value_sql.strip(),
        computed_at=dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
    )


# --------------------------------------------------------------------------------------------
# Formatting (code formats every number)
# --------------------------------------------------------------------------------------------


def format_number(value: float | None, decimals: int = 0, locale: str = "sq") -> str:
    """Locale-aware number with half-up rounding: sq 1.234,5 / en 1,234.5; None → "—"."""
    if value is None:
        return "—"
    q = Decimal(str(value)).quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP)
    text = f"{q:,.{decimals}f}"
    if locale == "sq":
        text = text.replace(",", "\u0000").replace(".", ",").replace("\u0000", ".")
    return text


def format_value(
    value: float | None, unit: str, locale: str = "sq", decimals: int | None = None
) -> str:
    """Format a passport value; percentages carry "%", other units are written by templates."""
    d = UNIT_DECIMALS.get(unit, 1) if decimals is None else decimals
    text = format_number(value, d, locale)
    if unit == "percent" and value is not None:
        text += "%"
    return text


def format_period(period: str | None, locale: str = "sq") -> str:
    """ "2026-08" → "gusht 2026" / "August 2026"; "2026-01/2026-08" → "janar – gusht 2026"."""
    if not period:
        return "—"
    if "/" in period:
        start, _, end = period.partition("/")
        a, b = format_period(start, locale), format_period(end, locale)
        a_month, _, a_year = a.rpartition(" ")
        if a_month and a_year == b.rpartition(" ")[2]:
            return f"{a_month} – {b}"
        return f"{a} – {b}"
    try:
        year, month = (int(x) for x in period.split("-")[:2])
    except ValueError:
        return period
    names = MONTH_NAMES_SQ if locale == "sq" else MONTH_NAMES_EN
    return f"{names[month - 1]} {year}"


def render_answer(
    passport: Passport,
    value: float | None,
    period: str | None,
    basis: str | None = None,
) -> L10n:
    """Fill the passport's answer template for both locales with code-formatted values."""
    out: dict[str, str] = {}
    for loc in LOCALES:
        target = (
            format_value(passport.target, passport.unit, loc, 0)
            if passport.target is not None
            else "—"
        )
        basis_label = POPULATION_BASES.get(basis or "", {}).get(loc, "—")
        out[loc] = passport.answer[loc].format(
            value=format_value(value, passport.unit, loc, passport.decimals),
            period=format_period(period, loc),
            target=target,
            basis=basis_label,
        )
    return out


def status_vs_target(
    passport: Passport, value: float | None
) -> Literal["on_track", "off_track", "no_target"] | None:
    """Tile status: on/off track against the target, or no_target."""
    if value is None:
        return None
    if passport.target is None or passport.direction == "none":
        return "no_target"
    if passport.direction == "higher_better":
        return "on_track" if value >= passport.target else "off_track"
    return "on_track" if value <= passport.target else "off_track"

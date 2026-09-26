"""Response models for the indicator endpoints (contract §7).

They serialise to exactly the keys of the TypeScript shapes in the build contract, so the
frontend can copy them into ``web/src/lib/api.ts``. Every user-facing string is an L10n dict.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

L10n = dict[str, str]
IndicatorState = Literal["computable", "missing", "document", "national", "manual"]
Severity = Literal["info", "warn"]
Direction = Literal["higher_better", "lower_better", "none"]
Status = Literal["on_track", "off_track", "no_target"]
FormulaStatus = Literal["draft", "from_source", "validated"]
Basis = Literal["census_2023", "civil_registry"]


class OwnerOut(BaseModel):
    key: str
    name: L10n


class AreaOut(BaseModel):
    key: str
    name: L10n


class SignalOut(BaseModel):
    rule: str
    severity: Severity
    message: L10n
    period: str | None


class MissingOut(BaseModel):
    dataset: str
    name: L10n
    owner: L10n


class SourceRefOut(BaseModel):
    source_id: str
    filename: str
    synthetic: bool


class SeriesPointOut(BaseModel):
    period: str
    value: float | None


class IndicatorSummary(BaseModel):
    code: str
    area: AreaOut
    name: L10n
    unit: str
    unit_label: L10n
    state: IndicatorState
    value: float | None
    period: str | None
    previous: float | None
    target: float | None
    direction: Direction
    status: Status | None
    owner: OwnerOut
    missing: list[MissingOut]
    signals: list[SignalOut]
    sources: list[SourceRefOut]
    smp_ref: str | None
    # additive (not in the contract's minimum shape): how to read the SMP chip, the period
    # and the sparkline/series
    smp_kind: Literal["direct", "internal_view"] = "direct"
    smp_note: L10n | None = None
    period_kind: Literal["ytd", "point"] = "ytd"
    series_kind: Literal["monthly", "ytd_running"] = "monthly"
    version: str
    formula_status: FormulaStatus
    basis: str | None
    sparkline: list[SeriesPointOut]


class BoardCoverage(BaseModel):
    computable: int
    missing: int
    document: int
    national: int
    total: int


class BoardBasis(BaseModel):
    population: Basis


class IndicatorBoard(BaseModel):
    pack: str
    as_of: str | None
    coverage: BoardCoverage
    basis: BoardBasis
    indicators: list[IndicatorSummary]


class LineageSourceOut(BaseModel):
    source_id: str
    filename: str
    file_hash: str
    row_count: int
    row_ranges: str


class CheckOut(BaseModel):
    rule: str
    label: L10n
    passed: bool
    message: L10n | None


class PassportOut(IndicatorSummary):
    formula: L10n
    question: L10n
    sql: str | None
    series: list[SeriesPointOut]
    lineage: list[LineageSourceOut]
    required_datasets: list[str]
    checks: list[CheckOut]
    computed_at: str | None


class LineageRowOut(BaseModel):
    source_file: str
    row_no: int
    values: dict[str, str | int | float | None]


class LineageRowsOut(BaseModel):
    code: str
    columns: list[str]
    total: int
    rows: list[LineageRowOut]


class BasisPinIn(BaseModel):
    value: str
    reason: str | None = None


class BasisIndicatorOut(BaseModel):
    code: str
    name: L10n
    value: float | None
    period: str | None
    basis: str


class BasisPinOut(BaseModel):
    ok: bool
    key: str
    value: Basis
    label: L10n
    reason: str | None
    pinned_at: str | None
    options: list[dict]
    indicators: list[BasisIndicatorOut]


class SignalAcceptIn(BaseModel):
    reason: str


class SignalAcceptOut(BaseModel):
    ok: bool
    code: str
    rule: str
    status: str
    reason: str
    ts: str


class SignalWithdrawOut(BaseModel):
    ok: bool
    code: str
    rule: str
    deleted: int


class CoverageItemOut(BaseModel):
    number: int
    area: L10n
    name_sq: str
    state: IndicatorState
    passport_code: str | None
    owner: L10n | None
    note: L10n | None


class CoverageOut(BaseModel):
    pack: Literal["al_smp"]
    label: L10n
    approval: Literal["pending", "approved"]
    counts: dict[IndicatorState, int]
    total: int
    items: list[CoverageItemOut]

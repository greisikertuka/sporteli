"""Copilot API shapes (contract §7). Field names serialise exactly to the TypeScript types."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

AskLabel = Literal["verified", "exploratory", "blocked", "not_answerable"]
ExampleKind = Literal["verified", "gap", "exploratory", "blocked"]
Locale = Literal["sq", "en"]


class L10n(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sq: str
    en: str


class AskRequest(BaseModel):
    """Lenient on purpose: length and locale are checked in code so errors use the contract
    shape (``{detail: {code, message}}``)."""

    model_config = ConfigDict(extra="ignore")
    question: str = ""
    locale: str = "sq"
    example_id: str | None = None


class AskTable(BaseModel):
    columns: list[str]
    rows: list[list[str | int | float | None]]


class AskSource(BaseModel):
    source_id: str
    filename: str
    rows: str


class AskGap(BaseModel):
    dataset: str
    name: L10n
    owner: L10n
    sample: str | None


class AskLLM(BaseModel):
    used: bool
    model: str | None
    latency_ms: int | None
    cost_usd: float | None
    cached: bool


class AskAnswer(BaseModel):
    label: AskLabel
    question: str
    interpreted_as: L10n
    answer: L10n
    value: float | None
    unit: str | None
    passport_code: str | None
    sql: str | None
    table: AskTable | None
    sources: list[AskSource]
    gap: AskGap | None
    blocked_reason: L10n | None
    llm: AskLLM
    method: L10n | None = None
    """How the number is calculated, in plain words (the passport's formula), or None.
    Set when a passport answered; the Ask screen shows this instead of the SQL."""


class AskExample(BaseModel):
    id: str
    question: L10n
    passport_code: str | None
    kind: ExampleKind


class EvalLabel(BaseModel):
    label: AskLabel
    matched: int
    total: int


class EvalSummary(BaseModel):
    model_config = ConfigDict(extra="allow")
    run_at: str
    commit: str | None
    mode: Literal["live", "rules"]
    by_label: list[EvalLabel]


class LLMCallRow(BaseModel):
    ts: str | None
    purpose: str | None
    model: str | None
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: int
    ok: bool
    error: str | None
    sent: object | None = None


class LLMCalls(BaseModel):
    spent_usd: float
    budget_usd: float
    mode: Literal["live", "rules"]
    calls: list[LLMCallRow]

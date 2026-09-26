"""Copilot endpoints (mounted under /api/v1 by app.main).

- POST /ask           -> AskAnswer (label decided in code; numbers computed by code)
- GET  /ask/examples  -> AskExample[]
- GET  /ask/eval      -> eval summary written by scripts/run_eval.py (404 if never run)
- GET  /llm/calls     -> { spent_usd, budget_usd, mode, calls } (what left the building)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import duckdb
from fastapi import APIRouter, Depends, Query

from app.config import API_DIR
from app.copilot.examples import examples
from app.copilot.models import AskAnswer, AskExample, AskRequest, EvalSummary, LLMCalls
from app.copilot.service import AskError, ask
from app.llm.client import get_llm
from app.meta.errors import api_error
from app.warehouse.db import get_cursor

router = APIRouter()

Cursor = Annotated[duckdb.DuckDBPyConnection, Depends(get_cursor)]

EVAL_RESULT_PATH: Path = API_DIR / "eval_result.json"
"""Written by ``scripts/run_eval.py``; tests point this elsewhere."""


@router.post("/ask", tags=["copilot"], response_model=AskAnswer)
def post_ask(body: AskRequest, con: Cursor) -> dict:
    try:
        return ask(con, body.question, body.locale, body.example_id)
    except AskError as exc:
        raise api_error(exc.status, exc.code, exc.message["sq"], exc.message["en"]) from exc


@router.get("/ask/examples", tags=["copilot"], response_model=list[AskExample])
def get_examples() -> list[dict]:
    return [e.api() for e in examples()]


@router.get("/ask/eval", tags=["copilot"], response_model=EvalSummary)
def get_eval() -> dict:
    path = EVAL_RESULT_PATH
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise api_error(
            404,
            "eval_not_run",
            "Vlerësimi me 24 pyetje nuk është ekzekutuar ende.",
            "The 24-question evaluation has not been run yet.",
        ) from exc
    except (OSError, ValueError) as exc:
        raise api_error(
            500,
            "eval_unreadable",
            "Rezultati i vlerësimit nuk mund të lexohej.",
            "The evaluation result could not be read.",
        ) from exc
    return data


@router.get("/llm/calls", tags=["copilot"], response_model=LLMCalls)
def get_llm_calls(limit: Annotated[int, Query(ge=1, le=500)] = 100) -> dict:
    llm = get_llm()
    return {
        "spent_usd": round(llm.spent_usd, 6),
        "budget_usd": llm.budget_usd,
        "mode": llm.mode,
        "calls": llm.recent_calls(limit),
    }

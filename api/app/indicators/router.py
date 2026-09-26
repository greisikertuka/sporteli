"""Indicator endpoints (contract §7), mounted under /api/v1 by app.main.

- GET  /indicators?pack=core_kpi            → IndicatorBoard
- GET  /indicators/{code}                   → Passport
- GET  /indicators/{code}/lineage?limit=50  → LineageRows
- GET  /definitions/population_basis        → current pin and the per-capita values
- POST /definitions/population_basis        → pin the population basis
- GET  /coverage?pack=al_smp                → Coverage (SMP 2024 Annex A)
- GET  /export/core_kpi.xlsx                → workbook with a visible "Burimi" column
- GET  /open-data/indicators.csv            → computable indicators as CSV (CC BY 4.0 header)
"""

from __future__ import annotations

from typing import Annotated, Literal

import duckdb
from fastapi import APIRouter, Depends, Query, Response

from app.indicators import coverage as cov
from app.indicators import export as exp
from app.indicators import service as svc
from app.indicators.models import (
    BasisPinIn,
    BasisPinOut,
    CoverageOut,
    IndicatorBoard,
    LineageRowsOut,
    PassportOut,
)
from app.meta.errors import api_error
from app.warehouse.db import get_cursor

router = APIRouter(tags=["indicators"])

Cursor = Annotated[duckdb.DuckDBPyConnection, Depends(get_cursor)]
Locale = Literal["sq", "en"]


def _unknown_pack(pack: str):
    return api_error(
        404,
        "unknown_pack",
        f"Paketa e treguesve «{pack}» nuk ekziston.",
        f"Indicator pack “{pack}” does not exist.",
    )


def _unknown_indicator(code: str):
    return api_error(
        404,
        "unknown_indicator",
        f"Treguesi «{code}» nuk ekziston në këtë paketë.",
        f"Indicator “{code}” does not exist in this pack.",
    )


@router.get("/indicators", response_model=IndicatorBoard)
def get_board(con: Cursor, pack: str = "core_kpi") -> dict:
    try:
        return svc.board(con, pack)
    except KeyError as exc:
        raise _unknown_pack(pack) from exc


@router.get("/indicators/{code}", response_model=PassportOut)
def get_passport(code: str, con: Cursor, pack: str = "core_kpi") -> dict:
    code = code.strip().upper()
    try:
        svc._load_pack(pack)
    except KeyError as exc:
        raise _unknown_pack(pack) from exc
    try:
        e = svc.evaluate_one(con, code, pack)
    except KeyError as exc:
        raise _unknown_indicator(code) from exc
    return svc.passport_detail(e)


@router.get("/indicators/{code}/lineage", response_model=LineageRowsOut)
def get_lineage(
    code: str,
    con: Cursor,
    limit: Annotated[int, Query(ge=1, le=1000)] = 50,
    pack: str = "core_kpi",
) -> dict:
    code = code.strip().upper()
    try:
        svc._load_pack(pack)
    except KeyError as exc:
        raise _unknown_pack(pack) from exc
    try:
        return svc.lineage_rows(con, code, limit, pack)
    except KeyError as exc:
        raise _unknown_indicator(code) from exc


@router.get("/definitions/population_basis", response_model=BasisPinOut)
def get_population_basis(con: Cursor) -> dict:
    return svc.basis_response(con)


@router.post("/definitions/population_basis", response_model=BasisPinOut)
def post_population_basis(body: BasisPinIn, con: Cursor) -> dict:
    try:
        svc.pin_population_basis(con, body.value, body.reason)
    except ValueError as exc:
        raise api_error(
            422,
            "invalid_basis",
            f"Baza e popullsisë «{body.value}» nuk njihet. Zgjidhni census_2023 ose "
            "civil_registry.",
            f"Population basis “{body.value}” is not recognised. Choose census_2023 or "
            "civil_registry.",
        ) from exc
    return svc.basis_response(con)


@router.get("/coverage", response_model=CoverageOut)
def get_coverage(con: Cursor, pack: str = "al_smp") -> dict:
    try:
        return cov.coverage(con, pack)
    except KeyError as exc:
        raise api_error(
            404,
            "unknown_pack",
            f"Paketa e mbulimit «{pack}» nuk ekziston.",
            f"Coverage pack “{pack}” does not exist.",
        ) from exc


def _download_headers(filename: str) -> dict[str, str]:
    return {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Access-Control-Expose-Headers": "Content-Disposition, X-License, X-Synthetic-Data, Link",
        "Cache-Control": "no-store",
    }


@router.get(
    "/export/core_kpi.xlsx",
    response_class=Response,
    responses={200: {"content": {exp.XLSX_MEDIA_TYPE: {}}}},
)
def export_core_kpi(con: Cursor, locale: Locale = "sq") -> Response:
    evaluated = svc.evaluate_pack(con, "core_kpi")
    content = exp.build_xlsx(evaluated, con, locale)
    headers = _download_headers(exp.xlsx_filename(evaluated, locale))
    headers["X-Synthetic-Data"] = str(
        any(s["synthetic"] for e in evaluated for s in e.sources)
    ).lower()
    return Response(content=content, media_type=exp.XLSX_MEDIA_TYPE, headers=headers)


@router.get(
    "/open-data/indicators.csv",
    response_class=Response,
    responses={200: {"content": {"text/csv": {}}}},
)
def open_data_csv(con: Cursor) -> Response:
    evaluated = svc.evaluate_pack(con, "core_kpi")
    content = exp.build_open_data_csv(evaluated)
    headers = _download_headers("indicators.csv")
    headers["Content-Disposition"] = 'inline; filename="indicators.csv"'
    headers["X-License"] = "CC-BY-4.0"
    headers["Link"] = f'<{exp.LICENSE_URL}>; rel="license"'
    headers["X-Synthetic-Data"] = str(
        any(s["synthetic"] for e in evaluated for s in e.sources)
    ).lower()
    return Response(content=content, media_type=exp.CSV_MEDIA_TYPE, headers=headers)

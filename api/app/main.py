from typing import Annotated

import duckdb
from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.warehouse.db import get_connection

api = APIRouter(prefix="/api/v1")


@api.get("/health", tags=["system"])
def health(con: Annotated[duckdb.DuckDBPyConnection, Depends(get_connection)]) -> dict:
    settings = get_settings()
    try:
        db_ok = con.execute("select 1").fetchone()[0] == 1
    except duckdb.Error:
        db_ok = False
    return {
        "status": "ok",
        "db": db_ok,
        "llm": bool(settings.anthropic_api_key),
        "version": settings.app_version,
    }


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Elbasan Pulse API",
        version=settings.app_version,
        description="Unified municipal data, KPIs and decision support.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api)
    return app


app = create_app()

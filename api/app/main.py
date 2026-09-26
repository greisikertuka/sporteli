from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.copilot.router import router as copilot_router
from app.indicators.router import router as indicators_router
from app.ingest.router import router as ingest_router
from app.llm.client import get_llm
from app.meta.errors import install_error_handlers
from app.meta.router import router as meta_router
from app.warehouse.db import close_db, get_db

API_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    get_db()  # open the process-wide connection and create the schema
    get_llm()  # restore LLM spend from the call log
    try:
        yield
    finally:
        close_db()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Sportel API",
        version=settings.app_version,
        description=(
            "Sportel — Raporto një herë, provo çdo numër (Report once, prove every number). "
            "Municipal exports in, proven indicators out."
        ),
        lifespan=lifespan,
    )
    install_error_handlers(app)  # before CORS, so CORS headers wrap every error response
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    for router in (meta_router, ingest_router, indicators_router, copilot_router):
        app.include_router(router, prefix=API_PREFIX)
    return app


app = create_app()

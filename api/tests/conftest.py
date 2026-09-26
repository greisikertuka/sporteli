import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.llm.client import reset_llm
from app.warehouse.db import close_db


def _reset_singletons() -> None:
    close_db()
    reset_llm()
    get_settings.cache_clear()


@pytest.fixture
def settings_env(tmp_path, monkeypatch):
    monkeypatch.setenv("DUCKDB_PATH", str(tmp_path / "test.duckdb"))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    _reset_singletons()
    yield
    _reset_singletons()


@pytest.fixture
def db(settings_env):
    """The process-wide connection on a fresh temp database (schema created)."""
    from app.warehouse.db import get_db

    return get_db()


@pytest.fixture
def client(settings_env):
    from app.main import create_app

    with TestClient(create_app()) as c:
        yield c

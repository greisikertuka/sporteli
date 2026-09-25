import pytest
from fastapi.testclient import TestClient

from app.config import get_settings


@pytest.fixture
def settings_env(tmp_path, monkeypatch):
    monkeypatch.setenv("DUCKDB_PATH", str(tmp_path / "test.duckdb"))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def client(settings_env):
    from app.main import create_app

    with TestClient(create_app()) as c:
        yield c

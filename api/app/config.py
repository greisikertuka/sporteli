import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

API_DIR = Path(__file__).resolve().parents[1]
"""The `api/` directory. Relative paths in settings resolve against it, not the CWD."""


def _resolve(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else API_DIR / p


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_version: str = "0.1.0"
    anthropic_api_key: str | None = None
    duckdb_path: str = "data/pulse.duckdb"
    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:3000",
        "http://localhost:3100",
    ]
    llm_budget_usd: float = 20.0
    demo_reset_enabled: bool = True
    samples_dir: str = "samples"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_origins(cls, value: Any) -> Any:
        """Accept a JSON list (`["http://a","http://b"]`) or a comma string (`http://a,http://b`)."""
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return []
            if text.startswith("["):
                return [str(v).strip() for v in json.loads(text) if str(v).strip()]
            return [part.strip() for part in text.split(",") if part.strip()]
        return value

    @property
    def duckdb_file(self) -> str:
        """DuckDB path resolved against `api/` (":memory:" is passed through)."""
        if self.duckdb_path == ":memory:":
            return self.duckdb_path
        return str(_resolve(self.duckdb_path))

    @property
    def samples_path(self) -> Path:
        """Absolute path of the server-side sample files directory."""
        return _resolve(self.samples_dir)


@lru_cache
def get_settings() -> Settings:
    return Settings()

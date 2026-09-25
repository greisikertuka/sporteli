from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_version: str = "0.1.0"
    anthropic_api_key: str | None = None
    duckdb_path: str = "data/pulse.duckdb"
    cors_origins: list[str] = ["http://localhost:3000"]
    llm_budget_usd: float = 20.0


@lru_cache
def get_settings() -> Settings:
    return Settings()

"""Application configuration, loaded from environment (12-factor)."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central settings object. See `.env.example` for keys."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "dev"
    app_name: str = "ApexOS"
    api_v1_prefix: str = "/api/v1"

    database_url: str = "postgresql+psycopg://apex:apex@localhost:5432/apexos"

    cors_origins: str = "http://localhost:3000"

    # Dev auth: which seeded user the API acts as when no Clerk session is present.
    dev_actor_email: str = "founder@apexsupply.example"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_dev(self) -> bool:
        return self.app_env.lower() in {"dev", "development", "local"}


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()


settings = get_settings()

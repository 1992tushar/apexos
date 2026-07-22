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

    # Document storage (Phase B). Backend is "r2" only when all R2_* creds are set;
    # otherwise we fall back to local disk under `documents_local_dir` (gitignored)
    # so the app runs locally without cloud credentials.
    documents_local_dir: str = "var/documents"
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket: str = ""

    @property
    def documents_backend(self) -> str:
        """'r2' when all Cloudflare R2 creds are configured, else 'local'."""
        if all(
            [self.r2_account_id, self.r2_access_key_id, self.r2_secret_access_key, self.r2_bucket]
        ):
            return "r2"
        return "local"

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

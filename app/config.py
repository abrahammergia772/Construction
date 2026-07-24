"""Runtime configuration. Secrets stay in environment variables, never in the browser."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "ConstructrAI"
    app_url: str = "http://127.0.0.1:8000"
    supabase_url: str | None = None
    supabase_anon_key: str | None = None
    supabase_service_role_key: str | None = None
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    cors_origins: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip().rstrip("/") for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def supabase_ready(self) -> bool:
        return bool(self.supabase_url and self.supabase_anon_key and self.supabase_service_role_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()

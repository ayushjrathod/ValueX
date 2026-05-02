from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv



APP_ENVS: tuple[str] = ("development", "production", "test")
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"


class ConfigError(RuntimeError):
    """Raised when environment configuration is missing or invalid."""


@dataclass(frozen=True, slots=True)
class Settings:
    app_env: str
    openai_api_key: str
    openai_model: str
    database_url: str | None
    pgvector_database_url: str | None
    redis_url: str | None

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_test(self) -> bool:
        return self.app_env == "test"

    def require_openai_api_key(self) -> str:
        if not self.openai_api_key:
            raise ConfigError("OPENAI_API_KEY is required for LLM-backed features.")
        return self.openai_api_key


def load_environment(env_file: str | Path | None = None) -> None:
    """
    Load environment variables from .env without overriding real environment.

    Real environment variables should win in production and CI. The local .env
    file is only a convenience for development.
    """
    dotenv_path = Path(env_file) if env_file else _project_root() / ".env"
    load_dotenv(dotenv_path=dotenv_path, override=False)


def get_settings(env_file: str | Path | None = None) -> Settings:
    load_environment(env_file)

    app_env_value = (os.getenv("APP_ENV") or "development").strip().lower()
    if app_env_value not in APP_ENVS:
        allowed = ", ".join(APP_ENVS)
        raise ConfigError(f"APP_ENV must be one of: {allowed}. Got {app_env_value!r}.")

    openai_api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    openai_model = (os.getenv("OPENAI_MODEL") or DEFAULT_OPENAI_MODEL).strip()
    if not openai_model:
        raise ConfigError("OPENAI_MODEL cannot be blank.")

    database_url = (os.getenv("DATABASE_URL") or "").strip() or None
    if database_url:
        parsed = urlparse(database_url)
        if parsed.scheme not in ("postgresql", "postgres") or not parsed.netloc:
            raise ConfigError("DATABASE_URL must be a valid PostgreSQL URL.")

    pgvector_database_url = (os.getenv("PGVECTOR_DATABASE_URL") or "").strip() or None
    if pgvector_database_url:
        parsed = urlparse(pgvector_database_url)
        if parsed.scheme not in ("postgresql", "postgres") or not parsed.netloc:
            raise ConfigError("PGVECTOR_DATABASE_URL must be a valid PostgreSQL URL.")

    redis_url = (os.getenv("REDIS_URL") or "").strip() or None
    if redis_url:
        parsed = urlparse(redis_url)
        if parsed.scheme not in ("redis", "rediss") or not parsed.netloc:
            raise ConfigError("REDIS_URL must be a valid Redis URL.")

    settings = Settings(
        app_env=app_env_value,
        openai_api_key=openai_api_key,
        openai_model=openai_model,
        database_url=database_url,
        pgvector_database_url=pgvector_database_url,
        redis_url=redis_url,
    )

    if settings.is_production and not settings.openai_api_key:
        raise ConfigError("OPENAI_API_KEY must be set when APP_ENV=production.")

    return settings


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]

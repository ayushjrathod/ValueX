from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# APP_ENV must be one of these (see _normalize_app_env).
APP_ENVS: tuple[str, ...] = ("development", "production", "test")

# Defaults when the matching env var is unset (field names are the env keys, uppercased).
OPENAI_MODEL = "gpt-4o-mini"
E2E_WARN_THRESHOLD_S = 6.0
COST_BUDGET_USD = 0.05
CLASSIFIER_TEMPERATURE = 0.1
PORTFOLIO_MAX_TOOL_ROUNDS = 5
PORTFOLIO_TOOL_TEMPERATURE = 0.2
PORTFOLIO_OBSERVATION_TEMPERATURE = 0.4
PORTFOLIO_RECENT_HISTORY_TURNS = 4
SESSION_MAX_TURNS = 10
SESSION_TTL_SECONDS = 3600
SAFETY_BLOCK_THRESHOLD = 0.58
MARKET_DATA_MAX_WORKERS = 10
API_PORT = 8000

# USD per 1M tokens; used by request cost estimates (see tracking.estimate_cost).
MODEL_PRICING_USD_PER_1M_TOKENS: dict[str, dict[str, float]] = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4.1": {"input": 2.00, "output": 8.00},
}

# One "turn" in session history = user message + assistant message.
SESSION_MESSAGES_PER_TURN = 2

# Portfolio concentration flags (% weight in largest / top-N positions).
TOP_HOLDINGS_COUNT = 3
HIGH_CONCENTRATION_THRESHOLD_PCT = 50.0
WARN_CONCENTRATION_THRESHOLD_PCT = 30.0

def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


class ConfigError(RuntimeError):
    """Invalid or missing environment configuration."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_project_root() / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    app_env: str = "development"
    llm: str = "openai"
    google_cloud_project: str = ""
    google_cloud_region: str = "global"
    gemini_model_id: str = "gemini-1.5-flash"
    openai_api_key: str = ""
    openai_model: str = OPENAI_MODEL
    e2e_warn_threshold_s: float = E2E_WARN_THRESHOLD_S
    cost_budget_usd: float = COST_BUDGET_USD
    classifier_temperature: float = CLASSIFIER_TEMPERATURE
    portfolio_max_tool_rounds: int = PORTFOLIO_MAX_TOOL_ROUNDS
    portfolio_tool_temperature: float = PORTFOLIO_TOOL_TEMPERATURE
    portfolio_observation_temperature: float = PORTFOLIO_OBSERVATION_TEMPERATURE
    portfolio_recent_history_turns: int = PORTFOLIO_RECENT_HISTORY_TURNS
    session_max_turns: int = SESSION_MAX_TURNS
    session_ttl_seconds: int = SESSION_TTL_SECONDS
    safety_block_threshold: float = SAFETY_BLOCK_THRESHOLD
    market_data_max_workers: int = MARKET_DATA_MAX_WORKERS
    api_port: int = API_PORT

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

    @field_validator("llm", mode="before")
    @classmethod
    def _normalize_llm(cls, value: object) -> str:
        llm = str(value or "openai").strip().lower()
        if llm == "gemini":
            llm = "gcp"
        if llm not in ("openai", "gcp"):
            raise ValueError("LLM must be one of: openai, gcp, gemini.")
        return llm

    @field_validator("app_env", mode="before")
    @classmethod
    def _normalize_app_env(cls, value: object) -> str:
        app_env = str(value or "development").strip().lower()
        if app_env not in APP_ENVS:
            allowed = ", ".join(APP_ENVS)
            raise ValueError(f"APP_ENV must be one of: {allowed}. Got {app_env!r}.")
        return app_env

    @field_validator("openai_model", mode="before")
    @classmethod
    def _normalize_openai_model(cls, value: object) -> str:
        model = str(value or OPENAI_MODEL).strip()
        if not model:
            raise ValueError("OPENAI_MODEL cannot be blank.")
        return model

    @field_validator("openai_api_key", mode="before")
    @classmethod
    def _normalize_openai_api_key(cls, value: object) -> str:
        return str(value or "").strip()

    @model_validator(mode="after")
    def _validate_production_requirements(self) -> Settings:
        if self.is_production and not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY must be set when APP_ENV=production.")
        return self


def get_settings(env_file: str | Path | None = None) -> Settings:
    """Load settings; *env_file* overrides the project `.env` path (e.g. in tests)."""
    try:
        if env_file is not None:
            return Settings(_env_file=Path(env_file))
        return Settings()
    except ValidationError as exc:
        raise ConfigError(str(exc)) from exc


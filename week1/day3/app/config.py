"""
app/config.py
=============
Single source of truth for runtime configuration.

Rules:
  - Everything that varies between local / staging / prod lives here.
  - Everything secret (API keys) lives in environment variables, never in code.
  - In development, a `.env` file at the repo root is read automatically.
  - In production, real env vars override anything in `.env`.

Anywhere else in the codebase, you import the singleton:
    from app.config import settings
You never read os.environ directly. One place to look, one place to change.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- App identity ----------------------------------------------------
    app_name: str = "research-assistant"
    environment: Literal["dev", "staging", "prod"] = "dev"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # --- LLM provider (Gemini) ------------------------------------------
    # SecretStr means accidental logging prints `**********` instead of the key.
    gemini_api_key: SecretStr = Field(
        ..., description="Google AI Studio API key (Gemini). Required."
    )
    default_model: str = "gemini-2.0-flash"
    default_max_tokens: int = 1024
    default_temperature: float = 0.7

    request_timeout_seconds: float = 60.0


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()

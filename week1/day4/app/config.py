"""
Centralised configuration. The senior-engineer rule from Day 2 still holds:
config is loaded ONCE, here, from the environment, and imported everywhere.
Never read os.environ scattered across the codebase, never hardcode a key.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Gemini ---
    gemini_api_key: str
    # A fast/cheap model is the right default for an extraction endpoint.
    # Synthesis/chat can override per-request.
    gemini_model: str = "gemini-2.5-flash"

    # --- Timeouts ---
    # The SDK's transport timeout. NOTE: google-genai expects MILLISECONDS here.
    # This is the inner layer — it fires inside the HTTP client.
    sdk_timeout_ms: int = 30_000  # 30 seconds, expressed in ms

    # The outer, request-level timeout enforced by asyncio.wait_for, in SECONDS.
    # Deliberately a touch LONGER than the SDK timeout so that, in the normal
    # case, the SDK's own (cleaner) timeout fires first. The outer one is the
    # safety net for when the SDK timeout fails to fire — e.g. the call is stuck
    # somewhere the SDK isn't watching.
    request_timeout_s: float = 35.0

    # --- Retry policy ---
    retry_max_attempts: int = 4
    retry_base_delay_s: float = 1.0
    retry_max_delay_s: float = 8.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
"""
app/clients/anthropic.py
========================
Holds the AsyncAnthropic client. One per process.

Why a wrapper file at all (rather than importing AsyncAnthropic where needed)?
  1. Initialization (API key, timeout, transport) lives in ONE place.
  2. When we add retries/middleware/observability in week 5, we change it here
     and nothing else needs to move.
  3. Tests can inject a fake client by overriding get_anthropic_client().
"""

from functools import lru_cache

from anthropic import AsyncAnthropic

from app.config import settings


@lru_cache
def get_anthropic_client() -> AsyncAnthropic:
    """Return the process-wide AsyncAnthropic client.

    lru_cache here is the simple form of dependency injection: the first call
    builds the client, every subsequent call returns the same instance. In
    tests we override this function with a fake; the app code doesn't change.
    """
    return AsyncAnthropic(
        api_key=settings.anthropic_api_key.get_secret_value(),
        timeout=settings.request_timeout_seconds,
        # max_retries=0 — we'll add our own retry policy in week 1 day 4.
        # Leaving the SDK default for now keeps behavior predictable.
    )
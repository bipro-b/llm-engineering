"""
Retry policy for LLM calls.

WHY THIS LOOKS DIFFERENT FROM THE ANTHROPIC VERSION
---------------------------------------------------
Anthropic's SDK hands you tidy exception classes (RateLimitError,
InternalServerError, APIConnectionError, ...) and you retry "on those classes".
Gemini's google-genai SDK does NOT. It raises:

    google.genai.errors.ClientError   -> HTTP 4xx, carries .code
    google.genai.errors.ServerError   -> HTTP 5xx, carries .code
    google.genai.errors.APIError       -> base class, carries .code

...plus ordinary network errors (httpx.ConnectError / TimeoutException) when the
request never reaches Google at all.

So we can't retry "on RateLimitError" — there is no such class. We retry on
SEMANTICS: "is this failure transient?" A status code answers that question
regardless of which SDK threw it. This is the more correct mental model anyway:
retry policy is about whether re-sending the identical request could succeed,
not about exception taxonomy.

    RETRYABLE      : 408, 429, 500, 502, 503, 504  + raw connection errors
    NOT RETRYABLE  : 400 (bad request), 401/403 (auth), 404 (no such model), ...
"""
from __future__ import annotations

import httpx
from google.genai import errors as genai_errors
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.config import get_settings

# Status codes where re-sending the SAME request might succeed.
RETRYABLE_STATUS_CODES = frozenset({408, 429, 500, 502, 503, 504})

# Network-level errors: the request never reached Google, so it's worth a retry.
RETRYABLE_NETWORK_ERRORS = (
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.ReadTimeout,
    httpx.RemoteProtocolError,
)


def _status_of(exc: BaseException) -> int | None:
    """Best-effort extraction of an HTTP status from a Gemini SDK error."""
    code = getattr(exc, "code", None)
    if isinstance(code, int):
        return code
    # Some SDK versions nest it under .response_json or .status — be defensive.
    status = getattr(exc, "status_code", None)
    return status if isinstance(status, int) else None


def is_retryable(exc: BaseException) -> bool:
    """The single source of truth for 'should we retry this exception?'"""
    if isinstance(exc, RETRYABLE_NETWORK_ERRORS):
        return True
    if isinstance(exc, genai_errors.APIError):
        status = _status_of(exc)
        # If we can't read a status, be conservative: a ServerError (5xx) is
        # transient by definition; a ClientError (4xx) is not.
        if status is None:
            return isinstance(exc, genai_errors.ServerError)
        return status in RETRYABLE_STATUS_CODES
    return False


def with_llm_retry(fn):
    """
    Decorator: retry an async LLM call on TRANSIENT failures only.

    - exponential backoff with jitter (tenacity's wait_exponential_jitter spreads
      the herd so 500 simultaneously-failed requests don't stampede in lockstep)
    - capped attempts (fail loudly rather than hang forever)
    - NEVER retries 400/401/403/404 — those re-send an identical broken request
    """
    settings = get_settings()
    return retry(
        retry=retry_if_exception(is_retryable),
        wait=wait_exponential_jitter(
            initial=settings.retry_base_delay_s,
            max=settings.retry_max_delay_s,
        ),
        stop=stop_after_attempt(settings.retry_max_attempts),
        reraise=True,  # surface the real error after exhausting attempts
    )(fn)
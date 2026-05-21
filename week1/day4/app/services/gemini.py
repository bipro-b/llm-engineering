"""
The Gemini service. This is where the three Day-4 concepts converge:

  1. Structured output  -> response_schema (a Pydantic model) constrains generation
  2. Retries            -> the transient-failure call is wrapped by with_llm_retry
  3. Timeouts (x2)      -> inner SDK timeout (ms!) + outer asyncio.wait_for (s)

Plus the self-correcting loop: validate on the way out, and on failure retry ONCE
with the validation error fed back to the model.
"""
from __future__ import annotations

import asyncio
from typing import Type, TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel, ValidationError

from app.config import get_settings
from app.services.retry import with_llm_retry

T = TypeVar("T", bound=BaseModel)

_settings = get_settings()

# One shared client. The SDK timeout lives in HttpOptions.
# CRITICAL: google-genai expresses this timeout in MILLISECONDS. Pass 30 and you
# get a 30ms timeout that fails almost instantly. We multiply seconds->ms here so
# the config can stay in human-readable units everywhere else.
_client = genai.Client(
    api_key=_settings.gemini_api_key,
    http_options=types.HttpOptions(timeout=_settings.sdk_timeout_ms),
)


@with_llm_retry
async def _generate(*, model: str, contents: str, schema: Type[BaseModel]) -> str:
    """
    One raw, schema-constrained generation call.

    Wrapped by with_llm_retry, so a 429/5xx/connection error here triggers
    backoff-with-jitter. A 400/401 does NOT — it raises straight through.

    Returns the model's raw JSON text; parsing/validation happens one layer up so
    that a *validation* failure (a different kind of problem) is handled separately
    from a *transport* failure.
    """
    response = await _client.aio.models.generate_content(
        model=model,
        contents=contents,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=schema,
            temperature=0,  # extraction wants determinism, not creativity
        ),
    )
    return response.text


async def extract(
    *,
    text: str,
    schema: Type[T],
    model: str | None = None,
) -> T:
    """
    Extract `text` into an instance of `schema`.

    Belt and suspenders:
      - response_schema constrains generation (fewer malformed outputs)
      - we still validate with Pydantic on return
      - if validation fails, we retry ONCE, feeding the error back to the model

    Both attempts run inside an OUTER asyncio.wait_for timeout (seconds) — the
    safety net for when the inner SDK timeout (ms) fails to fire.
    """
    model = model or _settings.gemini_model

    base_prompt = (
        "Extract the requested fields from the text below. "
        "Return ONLY data that matches the schema.\n\nTEXT:\n" + text
    )

    async def _attempt(prompt: str) -> T:
        raw = await _generate(model=model, contents=prompt, schema=schema)
        # Validate on the way out. response_schema makes this *usually* pass —
        # but truncation (hit max tokens) or a semantically-wrong value can still
        # break it, which is exactly the long tail we're guarding against.
        return schema.model_validate_json(raw)

    async def _run() -> T:
        try:
            return await _attempt(base_prompt)
        except ValidationError as first_error:
            # THE self-correcting retry. Hand the model its own mistake and the
            # exact complaint. This single trick fixes most edge cases.
            correction_prompt = (
                base_prompt
                + "\n\nYour previous response FAILED validation with this error:\n"
                + str(first_error)
                + "\nReturn corrected JSON that satisfies the schema."
            )
            return await _attempt(correction_prompt)

    # OUTER timeout layer. If the whole thing — including retry sleeps — exceeds
    # the budget, give up regardless of where it's stuck.
    return await asyncio.wait_for(_run(), timeout=_settings.request_timeout_s)
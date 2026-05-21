"""
app/clients/gemini.py
=====================
Gemini adapter. Implements the LLMProvider protocol with both chat()
(single-shot) and stream() (token-by-token).

Reasoning-token note: the 2.5 family allocates internal "thinking" tokens
from your max_output_tokens budget before producing visible output. For a
plain /chat we disable thinking (thinking_budget=0) so the budget all goes
to visible content. We will re-enable thinking in week 3 for agent steps
that benefit from deeper reasoning.

Cancellation note: the SDK exposes streaming via an *async iterator*.
Awaiting it inside an `async for` is the canonical way to consume tokens.
When our generator is cancelled (caller breaks out, request disconnects),
Python propagates `GeneratorExit` / `CancelledError` into the SDK iterator;
the SDK in turn closes its HTTP connection. That is what tells Google to
*stop generating* -- not merely "we stopped listening." Critical for cost.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import AsyncIterator

from google import genai
from google.genai import types as gtypes

from app.config import settings
from app.schemas.chat import ChatRequest, ChatResponse, Usage
from app.schemas.stream import StreamDelta, StreamEvent, StreamUsage

logger = logging.getLogger(__name__)

_ROLE_TO_GEMINI = {"user": "user", "assistant": "model"}


@lru_cache
def _build_client() -> genai.Client:
    return genai.Client(api_key=settings.gemini_api_key.get_secret_value())


def _build_contents(req: ChatRequest) -> list[gtypes.Content]:
    """Translate our messages to Gemini's `contents` shape (role + parts)."""
    return [
        gtypes.Content(
            role=_ROLE_TO_GEMINI[m.role],
            parts=[gtypes.Part(text=m.content)],
        )
        for m in req.messages
    ]


def _build_config(req: ChatRequest) -> gtypes.GenerateContentConfig:
    """Translate our sampling params + system prompt to Gemini's config object."""
    return gtypes.GenerateContentConfig(
        temperature=req.temperature,
        max_output_tokens=req.max_tokens,
        system_instruction=req.system,
        # Disable reasoning. Re-enable per-call in week 3 for agent steps.
        thinking_config=gtypes.ThinkingConfig(thinking_budget=0),
    )


class GeminiProvider:
    """Adapter: domain types outside, Gemini SDK inside."""

    def __init__(self, client: genai.Client | None = None) -> None:
        self._client = client or _build_client()

    # --- Single-shot ----------------------------------------------------

    async def chat(self, req: ChatRequest) -> ChatResponse:
        model = req.model or settings.default_model
        contents = _build_contents(req)
        config = _build_config(req)

        logger.info("gemini.chat start", extra={"model": model, "n_messages": len(contents)})

        response = await self._client.aio.models.generate_content(
            model=model, contents=contents, config=config,
        )

        text = _extract_text(response)
        if not text:
            raise RuntimeError(
                f"Gemini returned no text. finish_reason="
                f"{_finish_reason(response)!r} raw={response!r}"
            )

        usage = response.usage_metadata
        logger.info(
            "gemini.chat done",
            extra={
                "model": model,
                "input_tokens": usage.prompt_token_count if usage else None,
                "output_tokens": usage.candidates_token_count if usage else None,
                "finish_reason": _finish_reason(response),
            },
        )

        return ChatResponse(
            model=model,
            content=text,
            stop_reason=_finish_reason(response),
            usage=Usage(
                input_tokens=(usage.prompt_token_count if usage else 0) or 0,
                output_tokens=(usage.candidates_token_count if usage else 0) or 0,
            ),
        )

    # --- Streaming ------------------------------------------------------

    async def stream(self, req: ChatRequest) -> AsyncIterator[StreamEvent]:
        """Yield StreamDelta events as tokens arrive, plus one StreamUsage at the end.

        We track final usage by reading `usage_metadata` from whichever chunk
        carries it. Gemini's stream emits usage on (typically) the last chunk;
        we keep the latest non-null value and emit one StreamUsage at the end.
        """
        model = req.model or settings.default_model
        contents = _build_contents(req)
        config = _build_config(req)

        logger.info("gemini.stream start", extra={"model": model, "n_messages": len(contents)})

        last_usage: gtypes.GenerateContentResponseUsageMetadata | None = None
        chunk_count = 0

        # `generate_content_stream` returns an async iterator of partial
        # GenerateContentResponse objects, each with its own .candidates and
        # possibly its own .usage_metadata.
        stream = await self._client.aio.models.generate_content_stream(
            model=model, contents=contents, config=config,
        )

        try:
            async for chunk in stream:
                # Each chunk may have text on its first candidate's first part.
                text = _extract_text(chunk)
                if text:
                    chunk_count += 1
                    yield StreamDelta(text=text)
                # Usage typically arrives on a final chunk. Keep the latest.
                if getattr(chunk, "usage_metadata", None):
                    last_usage = chunk.usage_metadata
        finally:
            # If our consumer breaks early (disconnect / cancel), Python
            # raises GeneratorExit here. The `finally` is the place to emit
            # final usage and log -- but we MUST NOT yield from a finally
            # during GeneratorExit (that re-raises RuntimeError). So we only
            # yield usage on the normal-exit path; we always log.
            logger.info(
                "gemini.stream done",
                extra={
                    "model": model,
                    "chunks": chunk_count,
                    "input_tokens": last_usage.prompt_token_count if last_usage else None,
                    "output_tokens": last_usage.candidates_token_count if last_usage else None,
                },
            )

        # Reached only on normal completion (not on GeneratorExit).
        if last_usage is not None:
            yield StreamUsage(
                input_tokens=last_usage.prompt_token_count or 0,
                output_tokens=last_usage.candidates_token_count or 0,
            )


# --- helpers ---------------------------------------------------------------

def _extract_text(response: gtypes.GenerateContentResponse) -> str:
    """Pull text from the first candidate's first text part.

    `response.text` raises on safety-blocked or empty responses; we walk the
    structure ourselves so streaming chunks with no text don't crash us.
    """
    if not getattr(response, "candidates", None):
        return ""
    parts = response.candidates[0].content.parts or []
    return "".join(getattr(p, "text", "") or "" for p in parts)


def _finish_reason(response: gtypes.GenerateContentResponse) -> str | None:
    if not getattr(response, "candidates", None):
        return None
    fr = response.candidates[0].finish_reason
    return fr.name if fr else None


@lru_cache
def get_provider() -> GeminiProvider:
    return GeminiProvider()
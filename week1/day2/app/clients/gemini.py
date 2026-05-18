"""
app/clients/gemini.py
=====================
Gemini adapter. Implements the LLMProvider protocol.

Note on Gemini 2.5 family: these are reasoning models that allocate
internal "thinking" tokens from your max_output_tokens budget before
producing visible output. For a basic /chat endpoint we disable thinking
(thinking_budget=0) so all the budget goes to visible content. When we
build agents in week 3, we'll re-enable thinking on the steps that
benefit from deeper reasoning (planning, multi-hop synthesis).
"""

from __future__ import annotations

import logging
from functools import lru_cache

from google import genai
from google.genai import types as gtypes

from app.config import settings
from app.schemas.chat import ChatRequest, ChatResponse, Usage

logger = logging.getLogger(__name__)

_ROLE_TO_GEMINI = {"user": "user", "assistant": "model"}


@lru_cache
def _build_client() -> genai.Client:
    return genai.Client(api_key=settings.gemini_api_key.get_secret_value())


class GeminiProvider:
    """Adapter: domain types outside, Gemini SDK inside."""

    def __init__(self, client: genai.Client | None = None) -> None:
        self._client = client or _build_client()

    async def chat(self, req: ChatRequest) -> ChatResponse:
        model = req.model or settings.default_model

        contents: list[gtypes.Content] = [
            gtypes.Content(
                role=_ROLE_TO_GEMINI[m.role],
                parts=[gtypes.Part(text=m.content)],
            )
            for m in req.messages
        ]

        config = gtypes.GenerateContentConfig(
            temperature=req.temperature,
            max_output_tokens=req.max_tokens,
            system_instruction=req.system,
            # Disable reasoning tokens. On 2.5-family models, thinking eats
            # the output budget. We don't need it for a plain /chat endpoint.
            # Harmless on models that don't support thinking (SDK ignores it).
            thinking_config=gtypes.ThinkingConfig(thinking_budget=0),
        )

        logger.info(
            "gemini.chat start",
            extra={"model": model, "n_messages": len(contents)},
        )

        response = await self._client.aio.models.generate_content(
            model=model,
            contents=contents,
            config=config,
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


def _extract_text(response: gtypes.GenerateContentResponse) -> str:
    if not response.candidates:
        return ""
    parts = response.candidates[0].content.parts or []
    return "".join(getattr(p, "text", "") or "" for p in parts)


def _finish_reason(response: gtypes.GenerateContentResponse) -> str | None:
    if not response.candidates:
        return None
    fr = response.candidates[0].finish_reason
    return fr.name if fr else None


@lru_cache
def get_provider() -> GeminiProvider:
    return GeminiProvider()
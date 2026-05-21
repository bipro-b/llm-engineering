"""
app/services/llm.py
===================
Business logic for talking to an LLM -- provider-agnostic.

The service depends on `LLMProvider` (a Protocol). That means swapping
Gemini for Anthropic / OpenAI / Groq later is a new file in `clients/`,
not a refactor of routes or services.

Today the methods are thin pass-throughs. They are the right hook point
for retries (day 4), cost tracking (day 4), tracing (week 5), and rate
limiting (week 6).
"""

import logging
from typing import AsyncIterator

from app.clients.base import LLMProvider
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.stream import StreamEvent

logger = logging.getLogger(__name__)


class LLMService:
    def __init__(self, provider: LLMProvider):
        self._provider = provider

    async def chat(self, req: ChatRequest) -> ChatResponse:
        logger.info(
            "llm_service.chat",
            extra={"model": req.model, "n_messages": len(req.messages)},
        )
        return await self._provider.chat(req)

    def stream(self, req: ChatRequest) -> AsyncIterator[StreamEvent]:
        """Pass-through to the provider's streaming generator.

        Note: this is NOT an async generator itself (no `async def`, no yield).
        It returns the provider's iterator directly. That keeps cancellation
        semantics clean -- when the caller stops iterating, the cancellation
        propagates into the provider's generator (and thus the SDK) directly.
        """
        logger.info(
            "llm_service.stream",
            extra={"model": req.model, "n_messages": len(req.messages)},
        )
        return self._provider.stream(req)
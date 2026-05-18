"""
app/services/llm.py
===================
Business logic for talking to an LLM — provider-agnostic.

The architectural shift from yesterday: this service used to depend on
`AsyncAnthropic`. Now it depends on `LLMProvider` (a Protocol).

That means:
  - Swapping Gemini for Anthropic / OpenAI / Groq later = new clients/ file.
  - This service does not change.
  - Routes do not change.
  - Schemas do not change.
  - Tests need only a fake that satisfies the Protocol.

This pattern is called *dependency inversion*: high-level code (the service)
doesn't depend on low-level code (the SDK). Both depend on an abstraction
(the Protocol). It's the foundation of the model-router pattern we'll add
properly in week 6.
"""

import logging

from app.clients.base import LLMProvider
from app.schemas.chat import ChatRequest, ChatResponse

logger = logging.getLogger(__name__)


class LLMService:
    """Domain service that orchestrates LLM calls.

    Right now this is a thin pass-through, but in coming days it will pick
    up: retries with backoff (day 4), cost tracking (day 4), structured
    output handling (day 3), and observability hooks (week 5). All of that
    belongs at this layer, not in the provider adapter.
    """

    def __init__(self, provider: LLMProvider):
        self._provider = provider

    async def chat(self, req: ChatRequest) -> ChatResponse:
        logger.info(
            "llm_service.chat",
            extra={"model": req.model, "n_messages": len(req.messages)},
        )
        return await self._provider.chat(req)
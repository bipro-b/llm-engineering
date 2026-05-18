"""
app/clients/base.py
===================
The provider-agnostic interface.

`LLMProvider` is a Protocol: Python's structural typing equivalent of an
interface. Any class that has an async `chat` method with this signature
*is* an LLMProvider — no inheritance required.

This is the seam that decouples our service from any particular SDK.
The service depends on this Protocol, not on Anthropic or Gemini directly.
Adding a new provider = writing a new file in `clients/`. Nothing else moves.
"""

from typing import Protocol

from app.schemas.chat import ChatRequest, ChatResponse


class LLMProvider(Protocol):
    """Anything that can take a ChatRequest and return a ChatResponse."""

    async def chat(self, req: ChatRequest) -> ChatResponse:
        """Send a chat request and return a typed response.

        Implementations are responsible for:
          - translating our domain types to whatever the SDK expects,
          - calling the SDK asynchronously (never blocking the event loop),
          - translating the SDK response back to our ChatResponse type,
          - letting SDK-specific exceptions propagate (the route layer
            translates them into HTTP errors).
        """
        ...
"""
app/clients/base.py
===================
The provider-agnostic interface.

`LLMProvider` is a Protocol: any class with `chat` and `stream` methods
matching this signature *is* an LLMProvider — no inheritance required.
"""

from typing import AsyncIterator, Protocol

from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.stream import StreamEvent


class LLMProvider(Protocol):
    async def chat(self, req: ChatRequest) -> ChatResponse: ...

    async def stream(self, req: ChatRequest) -> AsyncIterator[StreamEvent]: ...

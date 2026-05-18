"""
app/schemas/chat.py
===================
Pydantic models for /chat. These are the *contract* between client and server.

Two principles:
  1. Validate at the edge. Inside the app we operate on typed objects, not dicts.
  2. Make invalid states unrepresentable. If `temperature` must be in [0, 1],
     the type system enforces that — your handler can't be reached with bad input.
"""

from typing import Literal

from pydantic import BaseModel, Field


class Message(BaseModel):
    """One turn in a conversation."""
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=100_000)


class ChatRequest(BaseModel):
    """Body of POST /chat."""
    messages: list[Message] = Field(..., min_length=1, max_length=200)
    model: str | None = None             # falls back to settings.default_model
    temperature: float = Field(0.7, ge=0.0, le=1.0)
    max_tokens: int = Field(1024, ge=1, le=8192)
    system: str | None = Field(None, max_length=20_000)


class Usage(BaseModel):
    """Token accounting — we return this so callers can track cost."""
    input_tokens: int
    output_tokens: int


class ChatResponse(BaseModel):
    """Body of the 200 response from /chat."""
    model: str
    content: str
    stop_reason: str | None
    usage: Usage
"""
app/schemas/chat.py
===================
Pydantic models for /chat. These are the *contract* between client and server.
"""

from typing import Literal

from pydantic import BaseModel, Field


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=100_000)


class ChatRequest(BaseModel):
    messages: list[Message] = Field(..., min_length=1, max_length=200)
    model: str | None = None
    temperature: float = Field(0.7, ge=0.0, le=1.0)
    max_tokens: int = Field(1024, ge=1, le=8192)
    system: str | None = Field(None, max_length=20_000)


class Usage(BaseModel):
    input_tokens: int
    output_tokens: int


class ChatResponse(BaseModel):
    model: str
    content: str
    stop_reason: str | None
    usage: Usage

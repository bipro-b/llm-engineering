"""
app/schemas/stream.py
=====================
Typed events that flow over the streaming pipeline.

We use a discriminated union on the `type` field. Inside the app every event
is a typed Pydantic model; only at the SSE boundary do we serialize them to
JSON strings. This means the streaming code does not pass dicts around -
it passes typed events, and the type checker can verify shape correctness.
"""

from typing import Literal

from pydantic import BaseModel, Field


class StreamDelta(BaseModel):
    """One chunk of generated text."""
    type: Literal["delta"] = "delta"
    text: str


class StreamUsage(BaseModel):
    """Token accounting. Emitted exactly once, at end of stream, before [DONE]."""
    type: Literal["usage"] = "usage"
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)


class StreamError(BaseModel):
    """Something went wrong upstream. Emitted in-stream so the client knows."""
    type: Literal["error"] = "error"
    message: str
    # 'upstream' = LLM API failed; 'internal' = our code; 'cancelled' = client left.
    kind: Literal["upstream", "internal", "cancelled"] = "upstream"


# The union type the rest of the app uses.
StreamEvent = StreamDelta | StreamUsage | StreamError
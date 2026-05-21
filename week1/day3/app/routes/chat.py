"""
app/routes/chat.py
==================
HTTP layer for /chat (single-shot) and /chat/stream (SSE streaming).

The route is intentionally thin: parse the request, hand off to the service,
adapt the response to HTTP. Logic belongs in services, not here.

SSE notes (read once, then internalize):
  - Wire format: each event is `data: <json>\\n\\n`. Blank line separates events.
  - Content-Type MUST be `text/event-stream`.
  - Cache-Control MUST be `no-cache` so intermediaries don't buffer.
  - `X-Accel-Buffering: no` is for nginx; without it, nginx buffers up to 4KB
    before flushing, which kills the per-token feel in production.
  - We send `[DONE]` as a final sentinel (a convention from OpenAI). Clients
    use it to distinguish a clean end from a connection drop.
  - We check `request.is_disconnected()` once per chunk. When the client
    leaves, we stop iterating, which propagates cancellation into the
    provider's generator, which closes the SDK's HTTP stream, which tells
    Google to stop generating tokens we won't bill our user for.
"""

import json
import logging
from typing import Annotated, AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from google.genai import errors as gerrors

from app.clients.gemini import get_provider
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.stream import StreamError, StreamEvent
from app.services.llm import LLMService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


def get_llm_service() -> LLMService:
    """FastAPI dependency. Tests override this with a fake."""
    return LLMService(provider=get_provider())


# --- /chat (single-shot, unchanged from day 2) ----------------------------

@router.post("", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    svc: Annotated[LLMService, Depends(get_llm_service)],
) -> ChatResponse:
    try:
        return await svc.chat(req)
    except gerrors.APIError as e:
        upstream_status = getattr(e, "code", None) or 502
        out_status = upstream_status if 400 <= upstream_status < 500 else 502
        raise HTTPException(status_code=out_status, detail=f"Upstream error: {e}")
    except TimeoutError as e:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"Upstream timeout: {e}",
        )


# --- /chat/stream (SSE) --------------------------------------------------

# Headers required for SSE to behave correctly through every HTTP intermediary.
_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    # nginx-specific: disable response buffering so chunks flush immediately.
    # Harmless on other proxies.
    "X-Accel-Buffering": "no",
}


def _sse_pack(payload: str) -> bytes:
    """Encode a payload string as a single SSE event.

    The exact wire shape is:    data: <payload>\\n\\n
    Note the TWO newlines -- the blank line is the event terminator.
    Without it, the client sees no events even though bytes are flowing.
    """
    return f"data: {payload}\n\n".encode("utf-8")


async def _sse_event_stream(
    request: Request,
    events: AsyncIterator[StreamEvent],
) -> AsyncIterator[bytes]:
    """Adapt our typed StreamEvents to the SSE wire format, with disconnect handling.

    This generator is what FastAPI's StreamingResponse iterates. Returning
    an `async generator` is critical -- a plain generator would block the
    event loop on every yield.
    """
    try:
        async for event in events:
            # Disconnect check between events. If the client closed the
            # connection, stop iterating. Breaking out of this loop causes
            # `events` (the provider's async generator) to be garbage-collected,
            # which raises GeneratorExit inside it, which causes the SDK's HTTP
            # stream to close, which tells Google to stop generating.
            if await request.is_disconnected():
                logger.info("sse: client disconnected, cancelling upstream")
                break

            # Pydantic's model_dump_json gives us a compact JSON string with
            # the discriminator field intact. The client uses `event.type` to
            # dispatch.
            yield _sse_pack(event.model_dump_json())

    except gerrors.APIError as e:
        # Upstream error mid-stream. Emit an `error` event so the client
        # can render a useful message, then end.
        logger.warning("sse: upstream error", exc_info=True)
        err = StreamError(message=str(e), kind="upstream")
        yield _sse_pack(err.model_dump_json())
    except Exception as e:  # noqa: BLE001
        # Anything else is internal. Don't leak the traceback to the client;
        # log it server-side, send a generic message.
        logger.exception("sse: internal error")
        err = StreamError(message=f"internal: {type(e).__name__}", kind="internal")
        yield _sse_pack(err.model_dump_json())
    finally:
        # Final sentinel. Even on disconnect we attempt to emit it; if the
        # socket is already gone, the bytes silently fail to send (Starlette
        # absorbs the BrokenPipeError).
        yield _sse_pack("[DONE]")


@router.post("/stream")
async def chat_stream(
    req: ChatRequest,
    request: Request,
    svc: Annotated[LLMService, Depends(get_llm_service)],
) -> StreamingResponse:
    """SSE endpoint. Streams chunks of generated text as they arrive."""
    # Build the provider's typed stream. We do NOT iterate it here -- we
    # hand it to `_sse_event_stream`, which is what `StreamingResponse`
    # consumes. The iteration only starts when FastAPI begins writing.
    events = svc.stream(req)

    return StreamingResponse(
        _sse_event_stream(request, events),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )
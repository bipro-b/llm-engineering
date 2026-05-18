"""
app/routes/chat.py
==================
The HTTP layer for /chat. Deliberately thin.

The route's job: parse the request (Pydantic does it), hand it to the service,
return the result. Logic belongs in the service, not here. If you find yourself
writing if/else for business reasons in a route file, stop and move it.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from google.genai import errors as gerrors

from week1.day2.app.clients.gemini import get_provider
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.llm import LLMService

router = APIRouter(prefix="/chat", tags=["chat"])


def get_llm_service() -> LLMService:
    """FastAPI dependency: build a service backed by the current provider.

    This is the seam tests use to inject a fake LLM. In test code:
        app.dependency_overrides[get_llm_service] = lambda: FakeLLM()

    To swap providers in production, change the import above (e.g. to
    `from app.clients.anthropic import get_provider`). Nothing else moves.
    """
    return LLMService(provider=get_provider())


@router.post("", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    svc: Annotated[LLMService, Depends(get_llm_service)],
) -> ChatResponse:
    try:
        return await svc.chat(req)
    except gerrors.APIError as e:
        # Gemini's SDK raises APIError (and subclasses like ClientError,
        # ServerError) for non-2xx responses. `code` holds the HTTP status.
        upstream_status = getattr(e, "code", None) or 502
        # Pass 4xx through (our request was bad), surface 5xx as 502 (bad gateway).
        out_status = upstream_status if 400 <= upstream_status < 500 else 502
        raise HTTPException(
            status_code=out_status,
            detail=f"Upstream error: {e}",
        )
    except TimeoutError as e:
        # Asyncio-level timeout (e.g. via asyncio.wait_for) maps to 504.
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"Upstream timeout: {e}",
        )
"""
/extract endpoint.

The route's job is thin: validate the request, call the service, and translate
failures into HONEST HTTP status codes. A timeout is 504, an upstream auth
failure is 502 (the upstream is misconfigured, not the caller), a bad request
is 400. Never collapse everything into a generic 500 — the status code is how
the caller knows whether retrying is worth it.
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException
from google.genai import errors as genai_errors
from pydantic import BaseModel, Field

from app.services.gemini import extract
from app.services.retry import RETRYABLE_STATUS_CODES

router = APIRouter()


# --- The schema we want to extract INTO. In a real app this would be selectable;
# here we hardcode a "contact card" as a concrete, testable example. ---
class Contact(BaseModel):
    name: str = Field(description="Full name of the person.")
    email: str | None = Field(default=None, description="Email if present.")
    company: str | None = Field(default=None, description="Employer if present.")
    role: str | None = Field(default=None, description="Job title if present.")


class ExtractRequest(BaseModel):
    text: str = Field(min_length=1, description="Raw text to extract from.")
    model: str | None = Field(default=None, description="Override the model.")


@router.post("/extract", response_model=Contact)
async def extract_endpoint(req: ExtractRequest) -> Contact:
    try:
        return await extract(text=req.text, schema=Contact, model=req.model)

    except asyncio.TimeoutError:
        # The outer wait_for fired. The call took too long.
        raise HTTPException(status_code=504, detail="LLM call timed out.")

    except genai_errors.APIError as exc:
        code = getattr(exc, "code", None)
        if code in RETRYABLE_STATUS_CODES:
            # We already retried and still failed — the upstream is degraded.
            raise HTTPException(status_code=502, detail="LLM upstream unavailable.")
        if code in (401, 403):
            # OUR key/permission is wrong. That's a server misconfiguration, not
            # the caller's fault — 502, not 401, so we don't blame the client.
            raise HTTPException(status_code=502, detail="LLM auth misconfigured.")
        if code == 400:
            raise HTTPException(status_code=400, detail="Bad request to LLM.")
        raise HTTPException(status_code=502, detail="LLM error.")
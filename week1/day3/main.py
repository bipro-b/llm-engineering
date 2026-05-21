"""
app/main.py
===========
FastAPI application entry point.

Run locally:
    python -m uvicorn app.main:app --reload --port 8000

Then open http://localhost:8000/ to see the streaming demo page.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.routes.chat import router as chat_router


def _configure_logging() -> None:
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    _configure_logging()
    logger = logging.getLogger(__name__)
    logger.info("starting %s in %s mode", settings.app_name, settings.environment)
    yield
    logger.info("shutdown complete")


app = FastAPI(title=settings.app_name, version="0.2.0", lifespan=lifespan)

# Static files for the demo page.
_static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=_static_dir), name="static")

app.include_router(chat_router)


@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    """Send people to the streaming demo by default."""
    return RedirectResponse(url="/static/index.html")


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
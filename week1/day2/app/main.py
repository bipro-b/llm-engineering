"""
app/main.py
===========
FastAPI application entry point.

Run locally:
    uvicorn app.main:app --reload --port 8000

In production we'd run with multiple workers (e.g. uvicorn --workers 4 or
gunicorn -k uvicorn.workers.UvicornWorker), but for development --reload
gives us hot-reload on file changes.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.routes.chat import router as chat_router


def _configure_logging() -> None:
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Runs once at startup, once at shutdown.

    Right now we just configure logging, but this is where in week 6 we'll
    open DB connection pools, warm caches, and gracefully close them.
    """
    _configure_logging()
    logger = logging.getLogger(__name__)
    logger.info(
        "starting %s in %s mode", settings.app_name, settings.environment
    )
    yield
    logger.info("shutdown complete")


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(chat_router)


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    """Liveness probe. Required for any real deployment in week 6."""
    return {"status": "ok"}
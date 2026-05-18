# syntax=docker/dockerfile:1.7
# ------------------------------------------------------------------
# Stage 1 — build dependencies into a virtualenv with uv.
# uv is dramatically faster than pip; the cache mount keeps repeat builds quick.
# ------------------------------------------------------------------
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

# Install uv from its official image without curl/build tools bloat.
COPY --from=ghcr.io/astral-sh/uv:0.4 /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml ./
# Resolve and install into /app/.venv so the final stage can copy it whole.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv venv /app/.venv && \
    uv pip install --python /app/.venv/bin/python -e .

# ------------------------------------------------------------------
# Stage 2 — runtime. Slim, no build tools, non-root user.
# ------------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

RUN groupadd -r app && useradd -r -g app -d /app -s /sbin/nologin app

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY app ./app

USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; \
      sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).status==200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
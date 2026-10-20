# syntax=docker/dockerfile:1
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /workspace

RUN uv venv /app/venv

COPY apps/worker/requirements.txt ./
RUN uv pip install -r requirements.txt --python /app/venv/bin/python

COPY apps/worker/src/worker /app/src/worker
COPY packages/studio_core/src/studio_core /app/src/studio_core
COPY packages/studio_providers/src/studio_providers /app/src/studio_providers
COPY packages/studio_media/src/studio_media /app/src/studio_media

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 1000 studio
USER studio
WORKDIR /app

COPY --from=builder /app/venv /app/venv
COPY --from=builder /app/src /app/src

ENV PATH="/app/venv/bin:$PATH"
ENV PYTHONPATH="/app/src"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import worker; print('ok')"

CMD ["arq", "worker.main.WorkerSettings"]

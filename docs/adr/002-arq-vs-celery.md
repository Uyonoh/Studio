# ADR-002: Background Worker Selection: ARQ over Celery

**Status:** Accepted  
**Date:** 2026-10-18  
**Decision makers:** Engineering team  

## Context

Our application tier is built with Python 3.12+, FastAPI, and `asyncpg` to deliver non-blocking I/O across database operations and external HTTP calls. The worker tier needs to handle:
- Claiming and executing generation jobs (`run_generation`).
- Fetching and saving generated media (`finalize_generation`).
- Best-effort cancellation requests (`cancel_generation`).
- Periodic safety net scanning (`reconcile_jobs` cron).

We evaluated task queue systems for Python, primarily comparing **ARQ** with **Celery**.

## Decision

We chose **ARQ** (backed by Redis) as our task queue and background worker runtime.

### Rationale

1. **Native `asyncio` Architecture:**
   - ARQ is designed from the ground up for Python's `asyncio`. Tasks are standard `async def` coroutines sharing the process event loop.
   - Celery's core was designed around prefork and threading. While it offers eventlet/gevent pools and experimental asyncio wrappers, integrating async libraries like `asyncpg` and `httpx` inside Celery worker tasks has historically led to thread/event loop mismatches, complex monkey patching, and subtle deadlocks.

2. **Lightweight Footprint and Minimal Dependencies:**
   - ARQ is lightweight (~1,000 lines of clean Python) and depends directly on `redis-py` (async client).
   - Celery pulls in a heavy dependency tree (`kombu`, `billiard`, `amqp`, `vine`, `click`), increasing container image size and startup latency.

3. **Shared Resource Context:**
   - ARQ provides a straightforward `ctx: dict[str, Any]` passed to every task, populated during worker `startup`. This cleanly holds long-lived async connection pools (`asyncpg.Pool`, Redis connection pool) without thread-local hacks or global singletons.

4. **Built-in Cron Scheduling:**
   - ARQ includes cron job scheduling (`arq.cron.cron`) running directly in the worker process. This eliminates the need to run and monitor a separate scheduler daemon (like `celery-beat`), reducing infrastructure complexity and deployment cost on Render.

5. **Deterministic Enqueue Deduplication:**
   - ARQ natively supports deduplicated job submission via `_job_id=str(job_id)`. Re-enqueuing an existing job ID is a no-op if the job is already queued or active, preventing duplicate worker execution.

## Consequences

### Positive
- **Unified Async Stack:** API and Worker share identical programming paradigms, typing, database helpers (`studio_core`), and HTTP clients (`httpx.AsyncClient`).
- **Resource Efficiency:** Low memory overhead per worker process, making single-instance staging and small production containers fast and inexpensive.
- **Operational Simplicity:** Only Redis and worker container required; no AMQP broker (RabbitMQ) or auxiliary beat daemon.

### Negative / Trade-offs
- **Advanced Workflow Features:** ARQ does not include native workflow primitives (canvas, chords, chains, DAGs). Since our jobs are single-step tasks governed by PostgreSQL state, this is not needed for MVP.
- **Scale-up Path:** If workflow DAG orchestration or multi-hour workflows are needed later (e.g. distributed video stitching pipelines), we will adopt Temporal or SQS/Cloud Tasks. Because PostgreSQL is the authoritative state machine (ADR-001), replacing the queue transport layer will not affect core business logic.

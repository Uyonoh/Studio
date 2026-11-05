# ADR-001: PostgreSQL as Authoritative Job Source of Truth

**Status:** Accepted  
**Date:** 2026-10-15  
**Decision makers:** Engineering team  

## Context

AI generation workflows (text-to-image, text-to-video, image-to-video) are asynchronous, multi-step, and potentially long-running (from seconds up to tens of minutes). During job execution, many failure modes can occur:
- Workers may crash or be terminated mid-job (OOM, deployment rollout, host failure).
- Webhooks from external inference providers (Replicate, Fal.ai) can arrive out-of-order, be duplicated, or be dropped entirely due to transient network failures.
- In-memory message brokers (such as Redis) can restart or evict keys under memory pressure.
- Users can concurrently request job cancellation or retry while workers are submitting or finalizing.

In many task systems, the queue or distributed task broker holds the authoritative job status. We needed to decide where the canonical source of truth for generation lifecycle, state transitions, and asset lineage should reside.

## Decision

We make **PostgreSQL (`generation_jobs`) the sole authoritative source of truth** for all generation job state, lineage, and credit accounting. Queues (Redis via ARQ) serve strictly as an ephemeral transport mechanism for job dispatch notifications.

### Core Architectural Mechanics

1. **Queue as Transport Only:**
   - The API enqueues only `job_id` references: `enqueue(queue, "run_generation", job_id)`.
   - The queue payload contains no mutable domain state.
   - Enqueue operations use deterministic task IDs (`_job_id=str(job_id)`) to deduplicate redundant enqueue attempts.

2. **Guarded Atomic State Transitions:**
   - Every state transition is executed with strict optimistic concurrency guards in SQL:
     ```sql
     UPDATE generation_jobs
     SET status = $new_status, updated_at = NOW()
     WHERE id = $job_id AND status = $expected_current_status
     RETURNING id;
     ```
   - If zero rows are updated, the transition is rejected (e.g. if a job was already canceled by the user, or claimed by another worker).

3. **Reconciler as the Safety Net:**
   - A background cron task (`reconcile_jobs`) periodically scans `generation_jobs` using `SELECT ... FOR UPDATE SKIP LOCKED`.
   - It identifies stuck `queued`, `submitting`, `running`, or `finalizing` jobs based on timestamps (`heartbeat_at`, `started_at`, timeout policies) and automatically recovers or fails them with credit refunds without querying Redis.

4. **Realtime Push Direct from Database:**
   - Supabase Realtime listens to PostgreSQL WAL (`postgres_changes` on `generation_jobs`) and pushes row updates directly to browser clients, eliminating the need for a separate WebSocket publish layer in the worker or API.

5. **Financial & Data Lineage Integrity:**
   - Credit reservations, refunds, and finalizations are bound to the `credit_ledger` and `generation_jobs` via relational integrity and transactions, ensuring no double-spend or orphaned deductions.

## Consequences

### Positive
- **Fault-tolerant and self-healing:** A total Redis flush or restart causes no permanent data loss; the reconciler inspects PostgreSQL and re-enqueues or recovers pending tasks.
- **Strict auditability:** All historical job states, transitions, timestamps, error codes, and provider IDs remain permanently queryable for support and analytics.
- **Row-Level Security (RLS):** Supabase RLS enforces workspace isolation directly on the job table, preventing cross-tenant leakage at the storage and query level.
- **Simplified worker logic:** Workers never coordinate peer status; they query and update Postgres atomically.

### Negative / Trade-offs
- **Postgres write throughput:** Frequent status updates and heartbeats write to the primary database. For the MVP and foreseeable scale (hundreds of concurrent jobs), this overhead is negligible, especially with connection pooling.
- **Index requirements:** Requires composite indexes on `(status, created_at)` and `(status, heartbeat_at)` to keep reconciler scans fast and non-blocking.

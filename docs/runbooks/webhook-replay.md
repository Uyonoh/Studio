# Runbook: Webhook Ingestion, Idempotency, and Replay

This runbook covers the webhook ingestion lifecycle, signature verification, duplicate handling, and procedures for manually replaying or recovering missed provider webhooks.

---

## 1. Webhook Lifecycle and Architecture

When a generation job is submitted, the worker configures the upstream provider's completion callback URL:
```
https://api.<domain>/internal/webhooks/{provider}/{job_id}?token={token}
```

### Security Layers
1. **Per-Job HMAC Token (`token`):** Derived from `HMAC-SHA256(WEBHOOK_SIGNING_SECRET, str(job_id))`. Verified using constant-time comparison (`hmac.compare_digest`). Prevents token reuse across jobs.
2. **Provider Signature Verification:** The raw payload and headers are passed to the provider adapter's `verify_webhook(headers, body)` method (e.g. Svix signing for Replicate, Fal webhook signature headers).

### Processing Steps
1. Validates HMAC token and provider signature (returns `401 Unauthorized` if invalid).
2. Appends raw payload to `public.job_events` (`type = 'webhook'`).
3. If the job is in `running` status, enqueues `finalize_generation` to the ARQ Redis queue.
4. If the job is already terminal (`succeeded`, `failed`, or `canceled`), logs the event and returns `200 OK` as an idempotent no-op.

---

## 2. Idempotency Guarantees

Provider webhooks may be delivered multiple times (e.g. provider retry logic on network timeouts). The pipeline is idempotent at every stage:
- **Queue Deduplication:** Finalization tasks are enqueued with `_job_id=f"finalize:{job_id}"`. Duplicate deliveries within the ARQ window are ignored by Redis.
- **State Machine Guard:** `finalize_generation` executes a guarded SQL update (`UPDATE generation_jobs ... WHERE status = 'running'`). Subsequent invocations find the job in `finalizing` or `succeeded` and exit cleanly.
- **Deterministic Asset Keys:** Output assets are assigned deterministic UUIDs (e.g. `UUIDv5(job_id, output_index)`). If finalization re-runs, existing storage paths and asset records are reused without creating duplicates.

---

## 3. Diagnosing Missed Webhooks

A webhook may be missed if:
- The provider experienced egress network issues.
- The API was temporarily restarting or unreachable.
- The webhook URL had an expired or misconfigured DNS/SSL endpoint.

### Identifying Jobs with Missed Webhooks

Check for jobs that have been in `running` state for longer than their expected duration without a recorded `webhook` event:

```sql
SELECT
  j.id,
  j.workspace_id,
  j.provider_job_id,
  j.status,
  j.started_at,
  NOW() - j.started_at AS running_time,
  count(e.id) FILTER (WHERE e.type = 'webhook') AS webhook_events_count
FROM public.generation_jobs j
LEFT JOIN public.job_events e ON e.job_id = j.id
WHERE j.status = 'running'
  AND j.started_at < NOW() - INTERVAL '3 minutes'
GROUP BY j.id
ORDER BY j.started_at ASC;
```

---

## 4. Replay and Recovery Procedures

### Option A: Automatic Recovery via Reconciler (Default)

You do **not** need to manually replay webhooks in most cases. The worker's `reconcile_jobs` cron runs every 60 seconds:
- For any `running` job older than `min_poll_age`, the reconciler calls the provider adapter's `get_status(provider_job_id)` API.
- If the provider reports the job is complete, the reconciler automatically enqueues `finalize_generation`.
- This self-healing mechanism recovers lost webhooks without operator intervention.

### Option B: Triggering Finalize Directly via Python

If you need to immediately trigger finalization without waiting for the reconciler:

```bash
uv run python -c "
import asyncio, uuid
from arq import create_pool
from arq.connections import RedisSettings
from studio_core.settings import get_settings

async def trigger_finalize(job_id_str):
    settings = get_settings()
    pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    await pool.enqueue_job('finalize_generation', uuid.UUID(job_id_str))
    print(f'Triggered finalize_generation for {job_id_str}')

asyncio.run(trigger_finalize('<JOB_UUID>'))
"
```

### Option C: Manual HTTP Webhook Replay via `curl`

To manually simulate or replay a provider webhook to the API endpoint:

1. Calculate the job's HMAC token:
   ```bash
   uv run python -c "
   import hmac, hashlib
   from studio_core.settings import get_settings
   settings = get_settings()
   token = hmac.new(settings.webhook_signing_secret.encode(), b'<JOB_UUID>', hashlib.sha256).hexdigest()
   print('Token:', token)
   "
   ```

2. Replay with `curl` (note: for real providers, use Option B unless you have the original provider signature headers, or run with `fake` provider in staging):
   ```bash
   curl -X POST \
     "https://api.<domain>/internal/webhooks/fake/<JOB_UUID>?token=<CALCULATED_TOKEN>" \
     -H "Content-Type: application/json" \
     -d '{"status": "succeeded", "output": ["https://storage.googleapis.com/..."]}'
   ```

3. Verify:
   ```sql
   SELECT id, status, completed_at FROM public.generation_jobs WHERE id = '<JOB_UUID>';
   SELECT id, storage_path, kind FROM public.assets WHERE source_job_id = '<JOB_UUID>';
   ```

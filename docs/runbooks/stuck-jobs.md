# Runbook: Investigating and Resolving Stuck Jobs

This runbook describes how to detect, diagnose, and resolve generation jobs that appear stuck in an active state (`queued`, `submitting`, `running`, or `finalizing`).

---

## 1. Job Lifecycle and Automatic Reconciler

Generation jobs follow the state machine defined in [TDD §5.2](../design.md):

```
queued ───► submitting ───► running ───► finalizing ───► succeeded
  │              │             │              │
  ▼              ▼             ▼              ▼
failed        failed        failed         failed
(refund)      (refund)      (refund)       (refund)
```

The background worker runs `reconcile_jobs` every 60 seconds. The reconciler automatically handles:
- **`queued` > 2 minutes** without an active Redis task: Re-enqueues the job.
- **`submitting` with stale heartbeat (> 3 minutes)**: Increments `attempt`, re-enqueues, or marks `failed` with credits refunded if `attempt >= max_attempts`.
- **`running` older than timeout (image 10 min, video 30 min)**: Calls provider cancel, marks `failed` (`error_code = 'TIMEOUT'`), and refunds credits.
- **`finalizing` with stale heartbeat (> 5 minutes)**: Re-enqueues finalization.

If a job remains stuck, either the worker process is down, Redis connection is interrupted, or the external provider failed to notify our webhook and polling timed out.

---

## 2. Detection & Diagnosis

### Check Admin Stats
Admins can check overall system health using the admin endpoint:
```bash
curl -H "Authorization: Bearer <ADMIN_JWT>" https://api.<domain>/v1/admin/stats
```
Inspect `active_jobs_count`, `queue_depth`, and `stuck_candidates`.

### Query Stuck Jobs Directly (PostgreSQL)

Connect to the database via `psql` or the Supabase SQL editor:

```sql
-- Find active jobs with no heartbeat in the last 5 minutes
SELECT
  id,
  workspace_id,
  project_id,
  status,
  task_type,
  attempt,
  max_attempts,
  provider_job_id,
  queued_at,
  started_at,
  heartbeat_at,
  NOW() - coalesce(heartbeat_at, started_at, queued_at) AS inactive_duration
FROM public.generation_jobs
WHERE status IN ('queued', 'submitting', 'running', 'finalizing')
  AND coalesce(heartbeat_at, started_at, queued_at) < NOW() - INTERVAL '5 minutes'
ORDER BY queued_at ASC;
```

### Inspect Job Events and Error Logs

```sql
-- Inspect recent lifecycle events for a specific stuck job
SELECT id, type, from_status, to_status, payload, created_at
FROM public.job_events
WHERE job_id = '<JOB_UUID>'
ORDER BY id ASC;
```

Check worker logs in Render or local console:
```bash
# Render CLI or dashboard logs
render logs --service studio-worker --tail 200
```
Search for the `job_id` or look for `heartbeat` or timeout entries.

---

## 3. Resolution Procedures

### Procedure A: Verify and Restart the Worker

If many jobs are stuck in `queued` or `submitting`, verify the worker health:
1. Check the Render dashboard for `studio-worker`. Verify the container is running and not crash-looping with OOM.
2. Verify Redis connectivity:
   ```bash
   redis-cli -u $REDIS_URL ping
   # Should return PONG
   ```
3. Restarting the worker triggers an immediate startup reconciliation pass that scans all active jobs.

### Procedure B: Force Re-enqueuing via Python

If the worker is healthy but a specific job's queue message was lost:
```bash
# From an operational shell or one-off script
uv run python -c "
import asyncio, uuid
from arq import create_pool
from arq.connections import RedisSettings
from studio_core.settings import get_settings

async def re_enqueue(job_id_str):
    settings = get_settings()
    pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    await pool.enqueue_job('run_generation', uuid.UUID(job_id_str), _job_id=job_id_str)
    print(f'Re-enqueued job {job_id_str}')

asyncio.run(re_enqueue('<JOB_UUID>'))
"
```

### Procedure C: Manually Fail and Refund a Stuck Job

If the external provider is unresponsive, the model timed out, or a user requires immediate resolution, safely transition the job to `failed` and refund the reserved credits:

```sql
BEGIN;

-- 1. Atomically transition job to failed
UPDATE public.generation_jobs
SET
  status = 'failed',
  error_code = 'OPERATOR_TERMINATED',
  error_message = 'Job terminated and refunded manually by operator',
  completed_at = NOW(),
  updated_at = NOW()
WHERE id = '<JOB_UUID>'
  AND status IN ('queued', 'submitting', 'running', 'finalizing');

-- 2. Issue credit refund if cost_credits > 0 and not already refunded
INSERT INTO public.credit_ledger (workspace_id, job_id, delta, reason)
SELECT
  j.workspace_id,
  j.id,
  j.cost_credits,
  'refund'
FROM public.generation_jobs j
WHERE j.id = '<JOB_UUID>'
  AND j.cost_credits > 0
  AND NOT EXISTS (
    SELECT 1 FROM public.credit_ledger l
    WHERE l.job_id = j.id AND l.reason = 'refund'
  );

-- 3. Log event
INSERT INTO public.job_events (job_id, type, from_status, to_status, payload)
VALUES (
  '<JOB_UUID>',
  'state_change',
  'running',
  'failed',
  '{"reason": "manual_operator_refund"}'::jsonb
);

COMMIT;
```

---

## 4. Verification

1. Confirm the job status is `failed` and `completed_at` is populated.
2. Confirm Supabase Realtime broadcasted the update to the UI.
3. Check `SELECT * FROM workspace_credit_balance WHERE workspace_id = '<WORKSPACE_UUID>'` to ensure the credits returned to the workspace.

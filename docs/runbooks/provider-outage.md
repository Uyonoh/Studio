# Runbook: Provider Outage and Model Disablement

This runbook describes how to handle upstream outages from external inference providers (Replicate, Fal.ai) by disabling providers or individual models via database flags, directing users to redundant providers, and restoring service once the incident is resolved.

---

## 1. Overview and Detection

AI Content Studio relies on external GPU providers to perform inference. During upstream disruptions:
- Workers may encounter HTTP 500/502/503/504, connection timeouts, or elevated rate limits (`429`).
- Reconciler and worker tasks retry transient errors with exponential backoff up to `max_attempts`.
- If an outage is sustained, jobs fail and trigger automatic credit refunds.

### Indicators of an Outage

1. **Sentry Alerts:** High failure rate alerts firing on `studio-worker` tagging `provider: replicate` or `provider: fal`.
2. **Admin Dashboard / Stats:**
   ```bash
   curl -H "Authorization: Bearer <ADMIN_JWT>" https://api.<domain>/v1/admin/stats
   ```
   Check `provider_error_rates` and recent failures grouped by provider.
3. **Provider Status Pages:**
   - Replicate: [status.replicate.com](https://status.replicate.com)
   - Fal.ai: [status.fal.ai](https://status.fal.ai)

---

## 2. Mitigation: Disabling via Database Flags

Disabling a provider or a model does **not** require a redeploy or code change. The database flags take effect immediately:

- `GET /v1/models` only returns models where `enabled = true` and whose parent provider has `enabled = true`.
- The frontend composer dynamically hides disabled models from the UI.
- Direct API submission against a disabled model is rejected with `400 Bad Request` (`MODEL_DISABLED`).

### Option A: Disable an Entire Provider

To immediately stop all new jobs from routing to a failing provider (e.g. Replicate):

```sql
-- Disable the provider
UPDATE public.providers
SET enabled = false
WHERE id = 'replicate';

-- Verify current provider status
SELECT id, name, enabled FROM public.providers;
```

### Option B: Disable a Single Broken Model

If only one specific model is failing (e.g. a broken weight checkpoint or upstream version issue) while other models on that provider work:

```sql
-- Disable a specific model by slug
UPDATE public.models
SET enabled = false
WHERE slug = 'replicate-flux-schnell';

-- Verify disabled models
SELECT slug, provider_id, display_name, enabled
FROM public.models
WHERE enabled = false;
```

---

## 3. Provider Redundancy

The system is designed with multi-provider redundancy across core task types (see [ADR-003](003-initial-models.md)):

| Task Type | Primary Model | Redundant Fallback |
|---|---|---|
| Text → Image | `replicate-flux-schnell` (Replicate) | `fal-flux-schnell` (Fal.ai) |
| Text → Video | `replicate-minimax-video` (Replicate) | `fal-kling-t2v` (Fal.ai) |
| Image → Video | `replicate-minimax-i2v` (Replicate) | `fal-kling-i2v` (Fal.ai) |

When Replicate is disabled, the frontend composer automatically reflects available Fal.ai models for the same task types.

---

## 4. Handling In-Flight Jobs

Jobs already submitted to the provider before it was disabled will continue until they succeed, fail, or time out:
- If the provider never returns a webhook, the worker's polling fallback and reconciler (`reconcile_jobs`) will terminate the job after the task timeout (image: 10m, video: 30m).
- When a job terminates with failure, the user's reserved credits are automatically refunded.
- To immediately clean up and refund active jobs belonging to the failing provider, use [Runbook: Stuck Jobs](stuck-jobs.md#procedure-c-manually-fail-and-refund-a-stuck-job).

---

## 5. Recovery and Re-enabling

Once the provider's status page reports operational recovery:

1. **Run a Smoke Test:**
   Execute a single generation against the provider using the manual smoke script:
   ```bash
   uv run python scripts/smoke_provider.py replicate
   # or
   uv run python scripts/smoke_provider.py fal
   ```

2. **Re-enable Provider and Models:**
   ```sql
   -- Re-enable provider
   UPDATE public.providers
   SET enabled = true
   WHERE id = 'replicate';

   -- Re-enable models
   UPDATE public.models
   SET enabled = true
   WHERE provider_id = 'replicate';
   ```

3. **Verify API Output:**
   ```bash
   curl https://api.<domain>/v1/models
   ```
   Confirm the recovered models appear with `enabled = true`.

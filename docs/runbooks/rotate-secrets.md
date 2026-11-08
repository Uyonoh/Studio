# Runbook: Secrets Rotation Procedure

This runbook outlines the step-by-step procedures to rotate credentials and secrets across Supabase, Render, Vercel, and AI providers with minimal operational disruption.

---

## 1. Secrets Inventory & Locations

| Secret | Service(s) | Storage Location | Impact of Rotation |
|---|---|---|---|
| `REPLICATE_API_TOKEN` | API, Worker | Render `studio-providers` group | Provider API calls |
| `REPLICATE_WEBHOOK_SECRET` | API, Worker | Render `studio-providers` group | Webhook signature verification |
| `FAL_KEY` | API, Worker | Render `studio-providers` group | Fal API submissions |
| `WEBHOOK_SIGNING_SECRET` | API, Worker | Render `studio-shared` group | Per-job webhook token HMACs |
| `DATABASE_URL` | API, Worker | Render `studio-api`, `studio-worker` | Postgres connectivity |
| `REDIS_URL` | API, Worker | Render Key Value link (`fromService`) | Queue transport and rate limiter |
| `SUPABASE_SERVICE_ROLE_KEY` | API, Worker | Render `studio-shared` group | Admin DB/storage bypass |
| `SUPABASE_ANON_KEY` | Web, API | Render `studio-shared`, Vercel env | Frontend Supabase client |
| `SUPABASE_JWT_SECRET` | API | Render `studio-api` | JWT token validation |
| `SENTRY_DSN` | API, Worker, Web | Render, Vercel env | Error tracking telemetry |

---

## 2. Rotating AI Provider Keys

### Replicate API Token (`REPLICATE_API_TOKEN`)

1. Go to [replicate.com/account/api-tokens](https://replicate.com/account/api-tokens).
2. Create a new token with a descriptive label (e.g. `studio-prod-2026-11`). **Do not delete the old token yet.**
3. In Render Dashboard:
   - Navigate to **Environment Groups** → `studio-providers`.
   - Update `REPLICATE_API_TOKEN` to the new token value.
   - Save changes (triggers rolling redeployment for both `studio-api` and `studio-worker`).
4. Monitor worker logs to verify successful job submissions.
5. In Replicate dashboard, revoke the old token.

### Fal.ai API Key (`FAL_KEY`)

1. Go to [fal.ai/dashboard/keys](https://fal.ai/dashboard/keys).
2. Create a new Key. Keep the previous key active.
3. Update `FAL_KEY` in Render `studio-providers` environment group.
4. Verify by running `scripts/smoke_provider.py fal`.
5. Revoke the old key on Fal.ai.

---

## 3. Rotating Webhook Secrets

### `WEBHOOK_SIGNING_SECRET`

`WEBHOOK_SIGNING_SECRET` is used to derive HMAC tokens for provider callbacks.

1. Generate a secure 32+ character random string:
   ```bash
   openssl rand -hex 32
   ```
2. Schedule rotation during a low-traffic window (jobs in-flight that were submitted under the previous secret will fail webhook token validation if finalized after restart; reconciler polling will recover them).
3. Update `WEBHOOK_SIGNING_SECRET` in the `studio-shared` group on Render.
4. Restart `studio-api` and `studio-worker`.

---

## 4. Rotating Database and Supabase Credentials

### Database Password (`DATABASE_URL`)

1. In Supabase Dashboard: **Project Settings** → **Database** → **Database password** → **Reset password**.
2. Note the new pooler URL and direct connection URL:
   - API: Transaction pooler URL (port 6543).
   - Worker: Direct database connection URL (port 5432).
3. In Render Dashboard:
   - Update `DATABASE_URL` on `studio-api`.
   - Update `DATABASE_URL` on `studio-worker`.
4. Deploy both services.
5. Verify `/readyz` returns 200 on `studio-api`.

### Supabase JWT Secret (`SUPABASE_JWT_SECRET`)

1. In Supabase Dashboard: **Project Settings** → **API** → **JWT Settings** → **Generate new secret**.
   *(Caution: Invalidates existing user sessions; users will need to re-login).*
2. Update `SUPABASE_JWT_SECRET` in Render `studio-api`.
3. If anon/service-role keys were rotated:
   - Update `SUPABASE_ANON_KEY` in Vercel project environment variables and redeploy web app.
   - Update `SUPABASE_SERVICE_ROLE_KEY` in Render `studio-shared` group.

---

## 5. Verification Checklist

After rotating any secret:
- [ ] API health checks pass (`curl https://api.<domain>/readyz` returns HTTP 200).
- [ ] Worker container is running and not crash looping.
- [ ] Run automated smoke script against staging:
      ```bash
      ./scripts/smoke_staging.sh
      ```
- [ ] Verify test generation completes end-to-end and asset renders in web app.

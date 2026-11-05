# Deployment runbook (Render + Vercel + Supabase)

This runbook describes how the staging and production environments are
provisioned. The Render Blueprint is `infra/render.yaml`; the web app deploys to
Vercel from `apps/web`. Supabase provides Postgres, Auth, and Storage.

## 1. Topology

| Component | Platform | Source | Notes |
| --- | --- | --- | --- |
| API | Render web service (`studio-api`) | `apps/api/Dockerfile` | Health check `/readyz`, 1 instance, autoscaling off. |
| Worker | Render background worker (`studio-worker`) | `apps/worker/Dockerfile` | ARQ cron runs the reconciler every minute. |
| Queue | Render Key Value (`studio-redis`) | managed | `noeviction`; internal access only. |
| Database / Auth / Storage | Supabase | `supabase/migrations` | Migrations applied from CI, not the API. |
| Web | Vercel | `apps/web` | Next.js 14, root directory `apps/web`. |

The worker runs `reconcile_jobs` via ARQ's cron scheduler, so no separate cron
service is required. Do **not** run a second worker with cron enabled against
the same queue unless `unique=True` is removed; the current job is unique and
idempotent, but duplicate reconcilers add noise.

## 2. Supabase setup

1. Create the project and record the project URL, anon key, service-role key,
   and JWT secret.
2. Apply migrations from the repository root:

   ```bash
   supabase link --project-ref <ref>
   supabase db push
   ```

3. Seed providers/models with `supabase/migrations/0004_models_seed.sql` and
   `0005_google_models_seed.sql` (included in `db push`).
4. Create the `media` storage bucket (public read is not required; the API
   issues signed URLs).
5. Create at least one test user and one workspace/project for the smoke test.

### Connection pooler

Use the Supabase **connection pooler in transaction mode** for the API:

- API `DATABASE_URL`: `postgresql://postgres.<ref>:<password>@<region>.pooler.supabase.com:6543/postgres`
- Worker `DATABASE_URL`: direct connection on port `5432`
  (`postgresql://postgres:<password>@db.<ref>.supabase.co:5432/postgres`)
- Migrations: direct connection, run from CI or a developer machine.

The API opens a small asyncpg pool per process. If connection counts grow,
raise the pooler pool size or add API instances; do not point the API at the
direct connection. The worker keeps long-lived connections and uses session
state, so the transaction pooler is not suitable there.

`studio_core.db.create_pool` detects port `6543` and sets
`statement_cache_size=0` automatically. Transaction-mode pooling can hand each
statement to a different backend, so asyncpg's named prepared statements are
unsafe there; direct and session-mode connections keep the default cache.

## 3. Render Blueprint

1. Push the repository to GitHub.
2. In Render: **New → Blueprint**, select the repository and the branch, and
   point the Blueprint path at `infra/render.yaml`.
3. Render creates `studio-api`, `studio-worker`, and `studio-redis`, and prompts
   for every `sync: false` variable.
4. Fill in the values:

   | Group | Variable | Value |
   | --- | --- | --- |
   | shared | `SUPABASE_URL` | `https://<ref>.supabase.co` |
   | shared | `SUPABASE_ANON_KEY` | Supabase anon key |
   | shared | `SUPABASE_SERVICE_ROLE_KEY` | Supabase service-role key (API/worker only) |
   | shared | `SUPABASE_JWT_SECRET` | Supabase JWT secret |
   | shared | `WEBHOOK_SIGNING_SECRET` | 32+ random bytes |
   | shared | `PUBLIC_API_URL` | `https://studio-api.onrender.com` (after first deploy) |
   | shared | `SENTRY_DSN` | API/worker Sentry DSN (optional) |
   | shared | `SENTRY_RELEASE` | Deployed git SHA (optional) |
   | shared | `ADMIN_USER_IDS` | Comma-separated Supabase user IDs for `/v1/admin/stats` |
   | api | `DATABASE_URL` | Supabase pooler URL (port 6543) |
   | worker | `DATABASE_URL` | Direct Supabase URL (port 5432) |
   | providers | `REPLICATE_API_TOKEN` | Replicate token |
   | providers | `REPLICATE_WEBHOOK_SECRET` | Replicate webhook signing secret |
   | providers | `FAL_KEY` | fal.ai key |
   | providers | `GEMINI_API_KEY` | Google AI key |

5. `REDIS_URL` is injected automatically from the `studio-redis` service.
6. Deploy. The API is ready when `GET https://studio-api.onrender.com/readyz`
   returns `200` with `{"status":"ok","checks":{"db":"ok","redis":"ok"}}`.
7. Confirm the worker logs `Starting ARQ Worker`, `Database pool opened`, and
   `Redis pool opened`. Enqueue a generation from the web app and verify the
   worker transitions it to `succeeded`.

The Blueprint intentionally sets `autoDeployTrigger: 'off'` and one instance per
service. Enable auto-deploy or more instances only after the CI pipeline in
T7.4 is in place.

### Render notes

- Build context is the repository root; the Dockerfiles copy `apps/*` and
  `packages/*` sources.
- The Docker images install ffmpeg and run as the non-root `studio` user.
- The API image exposes `/healthz` for liveness and `/readyz` for readiness.
  Render uses `/readyz` as the health check path.
- The worker has no HTTP port; Render treats the process as healthy while it is
  running. Its Docker `HEALTHCHECK` imports the worker package.
- The API webhook URL is `PUBLIC_API_URL` + `/internal/webhooks/...`; provider
  dashboards must point at the same host.

## 4. Vercel setup

1. Import the repository into Vercel.
2. Set **Root Directory** to `apps/web`.
3. Framework preset: **Next.js**. `apps/web/vercel.json` sets the build command;
   leave the dashboard overrides empty. Vercel detects the pnpm workspace and
   installs from the repository root. The build compiles `@studio/api-client`
   first because the web app imports its generated `dist/` output, which is not
   committed.
4. Add environment variables for **Production** and **Preview**:

   | Variable | Value |
   | --- | --- |
   | `NEXT_PUBLIC_SUPABASE_URL` | Supabase project URL |
   | `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase anon key |
   | `NEXT_PUBLIC_API_URL` | Render API URL, e.g. `https://studio-api.onrender.com` |
   | `NEXT_PUBLIC_SENTRY_DSN` | Web Sentry DSN (optional) |
   | `NEXT_PUBLIC_SENTRY_ENVIRONMENT` | `staging` or `production` |
   | `NEXT_PUBLIC_SENTRY_RELEASE` | `VERCEL_GIT_COMMIT_SHA` (optional) |
   | `NEXT_PUBLIC_SENTRY_TRACES_SAMPLE_RATE` | `0.1` |

5. In Supabase Auth, add the Vercel domain (and preview wildcard) to the
   allowed redirect URLs, e.g. `https://studio.vercel.app/auth/callback`.
6. Deploy and open the app. The browser uses the anon key only; the
   service-role key must never appear in `NEXT_PUBLIC_*` variables or client
   code.

## 5. Smoke test

`scripts/smoke_staging.sh` checks the deployed stack without requiring local
infrastructure:

```bash
API_BASE_URL=https://studio-api.onrender.com \
WEB_BASE_URL=https://studio.vercel.app \
bash scripts/smoke_staging.sh
```

It verifies:

- API `/healthz` returns `200`.
- API `/readyz` returns `200` with both `db` and `redis` checks `ok`.
- The web root responds (200/3xx) and is not an error page.

With a real user token and a project, it also submits a generation and polls
until it reaches a terminal state:

```bash
API_BASE_URL=https://studio-api.onrender.com \
WEB_BASE_URL=https://studio.vercel.app \
SMOKE_USER_TOKEN="<supabase access token>" \
SMOKE_PROJECT_ID="<project uuid>" \
SMOKE_MODEL="img-fast-v1" \
SMOKE_TASK_TYPE="text_to_image" \
SMOKE_PROMPT="a red apple on a table" \
bash scripts/smoke_staging.sh
```

The generation leg requires a working provider token and the worker running.
The script exits non-zero on failure, so CI can gate a deploy on it.

## 6. Rollback

1. **Render:** redeploy the previous image/commit from the service's **Deploys**
   tab, or revert the commit and redeploy. The Blueprint is declarative; a
   revert changes both services on the next deploy.
2. **Vercel:** promote the previous deployment to Production from the
   **Deployments** tab.
3. **Database:** migrations are expand → migrate → contract. A code rollback
   must remain compatible with the current schema; do not contract columns in
   the same release as the code that stops using them.
4. **Redis:** the queue is ephemeral for in-flight jobs. If Redis is replaced,
   the reconciler marks abandoned running jobs as failed and refunds credits;
   re-submit any user-facing work.
5. After rollback, re-run the smoke test and confirm `/readyz` is green.

## 7. Environment promotion

| Environment | Render | Vercel | Supabase |
| --- | --- | --- | --- |
| Staging | `studio-api` / `studio-worker` | Preview or staging domain | Staging project |
| Production | separate Blueprint/env group | Production domain | Production project |

Keep separate Supabase projects and provider tokens for staging and
production. Never share the service-role key or webhook secret between
environments.

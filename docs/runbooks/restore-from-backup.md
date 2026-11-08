# Runbook: Disaster Recovery and Database Restore

This runbook covers how to restore the AI Content Studio database and media storage from Supabase backups in the event of catastrophic data corruption, accidental deletion, or infrastructure failure.

---

## 1. Backup Strategy Overview

1. **PostgreSQL Database:**
   - **Production:** Supabase Point-in-Time Recovery (PITR) enabled. Continuous physical WAL archiving allows restoration to any second within the retention window (7 to 30 days).
   - **Staging / Snapshots:** Daily logical snapshots taken via Supabase automated backups, plus pre-migration logical dumps via `pg_dump`.
2. **Object Storage (`media` bucket):**
   - Assets are stored in Supabase Storage (`media/{workspace}/{project}/{asset_id}/original.{ext}`).
   - Storage objects are immutable once written; thumbnails and posters are derived and can be regenerated if necessary.
3. **Queue State (Redis):**
   - Redis is ephemeral transport. Because PostgreSQL is the sole source of truth (see [ADR-001](../adr/001-postgres-job-source-of-truth.md)), recovering the database automatically recovers the queue state via the worker's startup reconciler.

---

## 2. Point-in-Time Recovery (PITR) Procedure

If data corruption occurred at a known timestamp:

1. **Identify Target Time:**
   Determine the exact target time `T_target` (in UTC) immediately prior to the incident.
2. **Initiate PITR in Supabase:**
   - Go to **Supabase Dashboard** → **Project Settings** → **Database** → **Backups**.
   - Select **Point in Time**.
   - Enter the target UTC timestamp and click **Start Recovery**.
   *(Note: Supabase provisions a cloned or restored instance with the target state).*
3. **Update Connection String:**
   If restoration created a new project reference:
   - Note the new database credentials and connection pooler string.
   - Update `DATABASE_URL` in Render environment groups (`studio-api`, `studio-worker`).
   - Update `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` if project ref changed.

---

## 3. Restoring from a Logical Snapshot (`pg_dump`)

To restore from a manual `.sql` dump file:

1. **Place Services in Maintenance:**
   Temporarily scale `studio-api` and `studio-worker` to 0 instances in Render to prevent concurrent writes.
2. **Restore Database:**
   ```bash
   # Connect directly to the target Supabase database instance
   psql -h db.<ref>.supabase.co -U postgres -d postgres -f backup_snapshot.sql
   ```
3. **Verify Migrations:**
   Ensure all committed schema migrations are up to date:
   ```bash
   supabase db push
   ```

---

## 4. Post-Restore Reconciliation & Verification

1. **Restart Worker & API:**
   Scale `studio-api` and `studio-worker` back to active instances in Render.
2. **Automatic Startup Reconciliation:**
   On startup, the worker executes `startup()`, which triggers an immediate `reconcile_jobs` pass:
   - Any jobs that were `submitting`, `running`, or `finalizing` during the restored state will have their provider status checked.
   - Terminal jobs will finalize or refund.
   - Redis queue items will be re-enqueued as needed.
3. **Data Integrity Checks:**
   Run the following verification queries:
   ```sql
   -- Check table counts
   SELECT 'workspaces' AS entity, count(*) FROM public.workspaces
   UNION ALL
   SELECT 'generation_jobs', count(*) FROM public.generation_jobs
   UNION ALL
   SELECT 'assets', count(*) FROM public.assets
   UNION ALL
   SELECT 'credit_ledger', count(*) FROM public.credit_ledger;

   -- Check credit balance sanity
   SELECT workspace_id, balance FROM public.workspace_credit_balance LIMIT 10;
   ```
4. **Storage Asset Verification:**
   Verify that recent assets can be retrieved and have valid signed URLs:
   ```bash
   curl -H "Authorization: Bearer <JWT>" https://api.<domain>/v1/assets/<RECENT_ASSET_UUID>
   ```
5. **Run Smoke Test:**
   ```bash
   ./scripts/smoke_staging.sh
   ```

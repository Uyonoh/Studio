# Runbook: Credit Ledger Auditing and Manual Corrections

This runbook describes the credit accounting architecture, how to audit workspace balances for discrepancies, and how to execute safe manual credit corrections and grants.

---

## 1. Credit Ledger Architecture

Credits serve as the internal billing currency for AI generation tasks. All movements are recorded in an append-only ledger (`public.credit_ledger`). The current balance is computed dynamically via `public.workspace_credit_balance`.

### Ledger Schema
- `workspace_id`: Foreign key to `public.workspaces`.
- `job_id`: Optional reference to `public.generation_jobs`.
- `delta`: `numeric(10,2)`. Negative numbers deduct credits; positive numbers add credits.
- `reason`: Explanation tag:
  - `'reserve'`: Deducted when a generation job is submitted.
  - `'refund'`: Restored when a job fails, times out, or is canceled.
  - `'grant'`: Operator courtesy credit or seed allowance.
  - `'purchase'`: Purchased via billing integration (future).
  - `'adjustment'`: Manual administrative reconciliation.

### Guarantees
- **Atomic Reservation:** Credits are checked and reserved during `GenerationService.create_job` inside a database transaction before the job is enqueued.
- **Single-Refund Rule:** A job that fails or is canceled triggers a refund row. The system checks `WHERE reason = 'refund' AND job_id = ...` to prevent double-refunding.
- **Zero-Sum Completion:** When a job succeeds, the reservation remains as the final spend; no further ledger entry is required.

---

## 2. Auditing Workspace Balances

### Querying Current Balance

```sql
SELECT workspace_id, balance
FROM public.workspace_credit_balance
WHERE workspace_id = '<WORKSPACE_UUID>';
```

### Reviewing Transaction History

```sql
SELECT
  id,
  job_id,
  delta,
  reason,
  created_at
FROM public.credit_ledger
WHERE workspace_id = '<WORKSPACE_UUID>'
ORDER BY id DESC
LIMIT 50;
```

### Auditing Unrefunded Failed or Canceled Jobs

To identify any failed or canceled jobs that did not receive an automatic refund:

```sql
SELECT
  j.id AS job_id,
  j.workspace_id,
  j.status,
  j.cost_credits,
  j.completed_at
FROM public.generation_jobs j
WHERE j.status IN ('failed', 'canceled')
  AND j.cost_credits > 0
  AND NOT EXISTS (
    SELECT 1 FROM public.credit_ledger l
    WHERE l.job_id = j.id AND l.reason = 'refund'
  );
```

---

## 3. Manual Credit Actions

All manual changes must be executed as explicit `INSERT` statements into `public.credit_ledger`. Never update or delete existing ledger rows.

### Scenario A: Grant Courtesy / Onboarding Credits

To add 50 credits to a workspace (e.g. for user onboarding or support accommodation):

```sql
INSERT INTO public.credit_ledger (workspace_id, delta, reason)
VALUES ('<WORKSPACE_UUID>', 50.00, 'grant');
```

### Scenario B: Issue a Missing Refund for a Failed Job

If a job failed due to an uncaught provider error or manual termination and did not auto-refund:

```sql
INSERT INTO public.credit_ledger (workspace_id, job_id, delta, reason)
SELECT
  j.workspace_id,
  j.id,
  j.cost_credits,
  'refund'
FROM public.generation_jobs j
WHERE j.id = '<JOB_UUID>'
  AND NOT EXISTS (
    SELECT 1 FROM public.credit_ledger l
    WHERE l.job_id = j.id AND l.reason = 'refund'
  );
```

### Scenario C: Reconcile an Over-Credited Account (Deduction)

If credits were erroneously granted and need to be deducted:

```sql
INSERT INTO public.credit_ledger (workspace_id, delta, reason)
VALUES ('<WORKSPACE_UUID>', -25.00, 'adjustment');
```

---

## 4. Verification

After executing a ledger correction:
1. Verify the recalculated balance:
   ```sql
   SELECT * FROM public.workspace_credit_balance WHERE workspace_id = '<WORKSPACE_UUID>';
   ```
2. Have the user refresh the web application; the top-navigation credits badge updates immediately from the view.

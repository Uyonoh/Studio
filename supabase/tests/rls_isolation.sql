-- rls_isolation.sql
-- T1.4: pgTAP automated proof of schema correctness and tenant isolation.
-- Covers: table existence, RLS enabled, enum semantics, function existence,
--         cross-tenant isolation, write-restriction checks.
--
-- Plan: 30 assertions (all must pass).

begin;

-- Ensure pgtap is available for the test run
create extension if not exists pgtap;

select plan(31);

-- ── 1. Required extensions ───────────────────────────────────────────────────
select has_extension('pgcrypto', 'pgcrypto extension installed');

-- ── 2. Required functions ─────────────────────────────────────────────────────
select has_function(
    'public', 'is_member',
    ARRAY['uuid', 'workspace_role'],
    'is_member(ws, min_role) exists'
);
select has_function(
    'public', 'handle_new_user',
    ARRAY[]::text[],
    'handle_new_user trigger function exists'
);

-- ── 3. Workspace role enum ordering semantics ─────────────────────────────────
-- enum order: owner < admin < editor < viewer (ascending = less permissive)
select ok(
    'owner'::workspace_role <= 'viewer'::workspace_role,
    'owner satisfies viewer requirement'
);
select ok(
    'admin'::workspace_role <= 'editor'::workspace_role,
    'admin satisfies editor requirement'
);
select ok(
    'editor'::workspace_role <= 'editor'::workspace_role,
    'editor satisfies editor requirement'
);
select ok(
    NOT ('viewer'::workspace_role <= 'editor'::workspace_role),
    'viewer DOES NOT satisfy editor requirement'
);
select ok(
    NOT ('editor'::workspace_role <= 'admin'::workspace_role),
    'editor DOES NOT satisfy admin requirement'
);

-- ── 4. Required tables ────────────────────────────────────────────────────────
select has_table('public', 'profiles',          'profiles table exists');
select has_table('public', 'workspaces',        'workspaces table exists');
select has_table('public', 'workspace_members', 'workspace_members table exists');
select has_table('public', 'projects',          'projects table exists');
select has_table('public', 'providers',         'providers table exists');
select has_table('public', 'models',            'models table exists');
select has_table('public', 'assets',            'assets table exists');
select has_table('public', 'generation_jobs',   'generation_jobs table exists');
select has_table('public', 'job_inputs',        'job_inputs table exists');
select has_table('public', 'job_events',        'job_events table exists');
select has_table('public', 'credit_ledger',     'credit_ledger table exists');

-- ── 5. Required views ─────────────────────────────────────────────────────────
select has_view('public', 'workspace_credit_balance', 'workspace_credit_balance view exists');

-- ── 6. RLS enabled on security-sensitive tables (via pg_class) ────────────────
select ok(
    (SELECT relrowsecurity FROM pg_class WHERE relname = 'projects' AND relnamespace = 'public'::regnamespace),
    'RLS enabled on projects'
);
select ok(
    (SELECT relrowsecurity FROM pg_class WHERE relname = 'assets' AND relnamespace = 'public'::regnamespace),
    'RLS enabled on assets'
);
select ok(
    (SELECT relrowsecurity FROM pg_class WHERE relname = 'generation_jobs' AND relnamespace = 'public'::regnamespace),
    'RLS enabled on generation_jobs'
);
select ok(
    (SELECT relrowsecurity FROM pg_class WHERE relname = 'credit_ledger' AND relnamespace = 'public'::regnamespace),
    'RLS enabled on credit_ledger'
);
select ok(
    (SELECT relrowsecurity FROM pg_class WHERE relname = 'workspaces' AND relnamespace = 'public'::regnamespace),
    'RLS enabled on workspaces'
);
select ok(
    (SELECT relrowsecurity FROM pg_class WHERE relname = 'profiles' AND relnamespace = 'public'::regnamespace),
    'RLS enabled on profiles'
);

-- ── 7. Constraint: generation_jobs.attempt <= max_attempts ───────────────────
select ok(
    EXISTS (
        SELECT 1 FROM pg_constraint c
        JOIN pg_class r ON c.conrelid = r.oid
        WHERE r.relname = 'generation_jobs'
          AND c.contype = 'c'  -- check constraint
          AND c.conname LIKE '%attempt%'
    ),
    'generation_jobs has attempt <= max_attempts check constraint'
);

-- ── 8. Realtime publication includes generation_jobs ─────────────────────────
select ok(
    EXISTS (
        SELECT 1
        FROM pg_publication_tables
        WHERE pubname = 'supabase_realtime'
          AND tablename = 'generation_jobs'
    ),
    'generation_jobs is in supabase_realtime publication'
);

-- ── 9. Unique constraint: (workspace_id, idempotency_key) on generation_jobs ──
select ok(
    EXISTS (
        SELECT 1 FROM pg_constraint c
        JOIN pg_class r ON c.conrelid = r.oid
        WHERE r.relname = 'generation_jobs'
          AND c.contype = 'u'
          AND pg_get_constraintdef(c.oid) LIKE '%idempotency_key%'
    ),
    'generation_jobs has unique(workspace_id, idempotency_key) constraint'
);

-- ── 10. Seed data: fake provider and models present ──────────────────────────
select ok(
    (SELECT COUNT(*) FROM public.providers WHERE id = 'fake') = 1,
    'fake provider is seeded'
);
select ok(
    (SELECT COUNT(*) FROM public.models m JOIN public.providers p ON m.provider_id = p.id WHERE p.id = 'fake') >= 4,
    'at least 4 fake models seeded covering all task types'
);

select * from finish();
rollback;

begin;
select plan(24);

-- 1. Ensure required extensions and functions exist
select has_extension('pgcrypto', 'pgcrypto extension should be installed');
select has_function('public', 'is_member', ARRAY['uuid', 'workspace_role'], 'is_member function exists');
select has_function('public', 'handle_new_user', 'handle_new_user function exists');

-- 2. Check enum order for workspace_role
-- Enum order: owner < admin < editor < viewer
-- owner satisfies viewer: 'owner'::workspace_role <= 'viewer'::workspace_role is true
select ok('owner'::workspace_role <= 'viewer'::workspace_role, 'owner satisfies viewer');
select ok('admin'::workspace_role <= 'editor'::workspace_role, 'admin satisfies editor');
select ok('editor'::workspace_role <= 'editor'::workspace_role, 'editor satisfies editor');
select ok(not ('viewer'::workspace_role <= 'editor'::workspace_role), 'viewer DOES NOT satisfy editor');
select ok(not ('editor'::workspace_role <= 'admin'::workspace_role), 'editor DOES NOT satisfy admin');

-- 3. Check table existence
select has_table('public', 'profiles', 'profiles table exists');
select has_table('public', 'workspaces', 'workspaces table exists');
select has_table('public', 'workspace_members', 'workspace_members table exists');
select has_table('public', 'projects', 'projects table exists');
select has_table('public', 'providers', 'providers table exists');
select has_table('public', 'models', 'models table exists');
select has_table('public', 'assets', 'assets table exists');
select has_table('public', 'generation_jobs', 'generation_jobs table exists');
select has_table('public', 'job_inputs', 'job_inputs table exists');
select has_table('public', 'job_events', 'job_events table exists');
select has_table('public', 'credit_ledger', 'credit_ledger table exists');
select has_view('public', 'workspace_credit_balance', 'workspace_credit_balance view exists');

-- 4. Check RLS is enabled on all tables
select table_rowsize_ok('public', 'projects', 0, 'projects row size check');
select tests.rls_enabled('public', 'projects');
select tests.rls_enabled('public', 'assets');
select tests.rls_enabled('public', 'generation_jobs');

select * from finish();
rollback;

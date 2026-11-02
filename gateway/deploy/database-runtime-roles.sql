-- Apply as gpu_control_migrate after migrations, then after each migration.
-- Login roles must be distinct, NOINHERIT, non-superuser, with no incoming or
-- outgoing memberships. Provision passwords out of band; never put them here.
-- This allowlist matches the current schema v10 and its OAuth tables.
BEGIN;

DO $$ BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_auth_members m
    JOIN pg_roles member_role ON member_role.oid = m.member
    JOIN pg_roles granted_role ON granted_role.oid = m.roleid
    WHERE member_role.rolname IN ('gpu_control_api', 'gpu_control_worker', 'gpu_control_migrate')
       OR granted_role.rolname IN ('gpu_control_api', 'gpu_control_worker', 'gpu_control_migrate')
  ) THEN
    RAISE EXCEPTION 'runtime database roles must not have incoming or outgoing memberships';
  END IF;
END $$;

REVOKE ALL ON TABLE
  public.gateway_schema_version,
  public.gateway_runs_v1,
  public.gateway_control_v1,
  public.gateway_oauth_admin_v1,
  public.gateway_oauth_login_guard_v1,
  public.gateway_oauth_login_source_buckets_v1,
  public.gateway_oauth_login_budget_v1,
  public.gateway_oauth_bootstrap_v1,
  public.gateway_oauth_sessions_v1,
  public.gateway_oauth_clients_v1,
  public.gateway_oauth_codes_v1,
  public.gateway_oauth_tokens_v1
FROM PUBLIC;

REVOKE ALL ON TABLE
  public.gateway_schema_version,
  public.gateway_runs_v1,
  public.gateway_control_v1,
  public.gateway_oauth_admin_v1,
  public.gateway_oauth_login_guard_v1,
  public.gateway_oauth_login_source_buckets_v1,
  public.gateway_oauth_login_budget_v1,
  public.gateway_oauth_bootstrap_v1,
  public.gateway_oauth_sessions_v1,
  public.gateway_oauth_clients_v1,
  public.gateway_oauth_codes_v1,
  public.gateway_oauth_tokens_v1
FROM gpu_control_api, gpu_control_worker;

-- Table-level revocation does not remove existing column UPDATE grants.
REVOKE UPDATE (id, owner, idempotency_key, request_hash, fingerprint, plan,
  state, created_at, started_at, approved_until, approval_id, handle, result,
  error, lease_until, lease_token, cancel_requested, slot_reserved,
  record_version, cleanup_state, finished_at, result_manifest, admission,
  attempt, submission_intent, last_observed_at)
ON TABLE public.gateway_runs_v1 FROM PUBLIC, gpu_control_api, gpu_control_worker;
REVOKE UPDATE (id, active_count, worker_seen_at, supervisor_seen_at)
ON TABLE public.gateway_control_v1 FROM PUBLIC, gpu_control_api, gpu_control_worker;

REVOKE CREATE ON SCHEMA public FROM PUBLIC, gpu_control_api, gpu_control_worker;
GRANT USAGE ON SCHEMA public TO gpu_control_api, gpu_control_worker, gpu_control_migrate;
GRANT CREATE ON SCHEMA public TO gpu_control_migrate;

GRANT SELECT, INSERT ON TABLE public.gateway_runs_v1 TO gpu_control_api;
GRANT UPDATE (state, approval_id, approved_until, slot_reserved, cancel_requested)
  ON TABLE public.gateway_runs_v1 TO gpu_control_api;
GRANT SELECT ON TABLE public.gateway_control_v1 TO gpu_control_api;
GRANT UPDATE (active_count) ON TABLE public.gateway_control_v1 TO gpu_control_api;

-- Workers observe and advance leased records, but do not create or delete runs
-- or control state. Keep destructive record operations with the API/migration
-- boundary rather than the Docker-authorized worker process.
GRANT SELECT ON TABLE public.gateway_runs_v1, public.gateway_control_v1
TO gpu_control_worker;
GRANT UPDATE (state, started_at, handle, result, error, lease_until, lease_token,
  cleanup_state, finished_at, record_version, attempt, submission_intent,
  last_observed_at) ON TABLE public.gateway_runs_v1 TO gpu_control_worker;
GRANT UPDATE (worker_seen_at, supervisor_seen_at)
  ON TABLE public.gateway_control_v1 TO gpu_control_worker;

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE
  public.gateway_oauth_admin_v1,
  public.gateway_oauth_bootstrap_v1,
  public.gateway_oauth_sessions_v1,
  public.gateway_oauth_clients_v1,
  public.gateway_oauth_codes_v1,
  public.gateway_oauth_tokens_v1
TO gpu_control_api;

-- New login admission state is API-only. The obsolete account-wide guard stays
-- revoked so an accidentally running old API fails closed after the v10 role
-- grant script is applied.
GRANT SELECT, INSERT, UPDATE, DELETE
  ON TABLE public.gateway_oauth_login_source_buckets_v1 TO gpu_control_api;
GRANT SELECT, UPDATE
  ON TABLE public.gateway_oauth_login_budget_v1 TO gpu_control_api;

-- Version state is read-only to runtime processes; only the migration owner
-- advances it. Table ownership remains with gpu_control_migrate.
GRANT SELECT ON TABLE public.gateway_schema_version TO gpu_control_api, gpu_control_worker;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.gateway_schema_version TO gpu_control_migrate;

ALTER DEFAULT PRIVILEGES FOR ROLE gpu_control_migrate IN SCHEMA public
  REVOKE ALL ON TABLES FROM PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE gpu_control_migrate IN SCHEMA public
  REVOKE ALL ON TABLES FROM gpu_control_api, gpu_control_worker;
ALTER DEFAULT PRIVILEGES FOR ROLE gpu_control_migrate
  REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;

-- Re-application after PUBLIC EXECUTE was revoked must temporarily restore
-- the trusted migration owner's right to replace the function.
DO $$ BEGIN
  IF to_regprocedure('public.gpu_control_release_finished_slot(text,text)') IS NOT NULL THEN
    EXECUTE 'GRANT EXECUTE ON FUNCTION public.gpu_control_release_finished_slot(text,text) '
         || 'TO gpu_control_migrate';
  END IF;
END $$;

CREATE OR REPLACE FUNCTION public.gpu_control_release_finished_slot(
  p_run_id text, p_expected_lease_token text
) RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $function$
DECLARE
  current_token text;
  current_state text;
  reserved boolean;
BEGIN
  PERFORM id FROM public.gateway_control_v1 WHERE id = 1 FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Gateway control row is missing' USING ERRCODE = '55000';
  END IF;

  SELECT lease_token, state, slot_reserved
    INTO current_token, current_state, reserved
    FROM public.gateway_runs_v1 WHERE id = p_run_id FOR UPDATE;
  IF NOT FOUND OR p_expected_lease_token IS NULL OR p_expected_lease_token = '' OR
     current_token IS DISTINCT FROM p_expected_lease_token OR NOT reserved OR
     current_state NOT IN ('succeeded', 'failed', 'cancelled', 'expired') THEN
    RETURN FALSE;
  END IF;

  UPDATE public.gateway_control_v1
     SET active_count = active_count - 1
   WHERE id = 1 AND active_count > 0;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Gateway active-slot counter is inconsistent' USING ERRCODE = '55000';
  END IF;

  UPDATE public.gateway_runs_v1 SET slot_reserved = FALSE
   WHERE id = p_run_id AND lease_token = p_expected_lease_token AND slot_reserved = TRUE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Gateway run reservation changed during release' USING ERRCODE = '55000';
  END IF;
  RETURN TRUE;
END
$function$;
REVOKE ALL ON FUNCTION public.gpu_control_release_finished_slot(text, text)
  FROM PUBLIC, gpu_control_api, gpu_control_worker;
GRANT EXECUTE ON FUNCTION public.gpu_control_release_finished_slot(text, text)
  TO gpu_control_worker, gpu_control_migrate;

COMMIT;

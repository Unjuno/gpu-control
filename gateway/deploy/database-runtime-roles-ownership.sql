-- Existing-database upgrade only. Run as the current owner of every Gateway
-- tables and gateway SECURITY DEFINER functions (normally a DBA/superuser)
-- before migrations use gpu_control_migrate. Also use after a no-owner restore,
-- which otherwise makes the SECURITY DEFINER function owned by the restore admin.
-- Fresh databases need no transfer: schema objects are created by the migration role.
GRANT USAGE, CREATE ON SCHEMA public TO gpu_control_migrate;

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

DO $$ DECLARE relation_name text; BEGIN
  FOR relation_name IN
    SELECT tablename FROM pg_tables
    WHERE schemaname = 'public' AND tablename IN (
      'gateway_schema_version', 'gateway_runs_v1', 'gateway_control_v1',
      'gateway_oauth_admin_v1', 'gateway_oauth_login_guard_v1',
      'gateway_oauth_login_source_buckets_v1', 'gateway_oauth_login_budget_v1',
      'gateway_oauth_bootstrap_v1', 'gateway_oauth_sessions_v1',
      'gateway_oauth_clients_v1', 'gateway_oauth_codes_v1', 'gateway_oauth_tokens_v1',
      'gateway_provider_observations_v1', 'gateway_provider_account_leases_v1',
      'gateway_paid_authorizations_v1'
    )
  LOOP
    EXECUTE format('ALTER TABLE public.%I OWNER TO gpu_control_migrate', relation_name);
  END LOOP;
  FOR relation_name IN
    SELECT tablename FROM pg_tables
    WHERE schemaname = 'public' AND tablename IN (
      'gateway_provider_observations_v1', 'gateway_provider_account_leases_v1',
      'gateway_paid_authorizations_v1'
    )
  LOOP
    EXECUTE format('ALTER TABLE public.%I OWNER TO gpu_control_migrate', relation_name);
  END LOOP;
  IF to_regprocedure('public.gpu_control_release_finished_slot(text,text)') IS NOT NULL THEN
    EXECUTE 'ALTER FUNCTION public.gpu_control_release_finished_slot(text,text) '
         || 'OWNER TO gpu_control_migrate';
  END IF;
  IF to_regprocedure('public.gpu_control_lock_provider_observation(text)') IS NOT NULL THEN
    EXECUTE 'ALTER FUNCTION public.gpu_control_lock_provider_observation(text) '
         || 'OWNER TO gpu_control_migrate';
  END IF;
END $$;

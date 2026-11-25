-- Run once as the database owner before the first --init-db.
-- These roles have no login/password until provisioned out of band.
-- Use an environment-dedicated PostgreSQL cluster; role names are cluster-global.
BEGIN;
DO $$ BEGIN
  CREATE ROLE gpu_control_api NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
DO $$ BEGIN
  CREATE ROLE gpu_control_worker NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
DO $$ BEGIN
  CREATE ROLE gpu_control_migrate NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ DECLARE r record; BEGIN
  FOR r IN SELECT rolname, rolsuper, rolcreatedb, rolcreaterole, rolreplication,
                  rolbypassrls, rolinherit
           FROM pg_roles
           WHERE rolname IN ('gpu_control_api', 'gpu_control_worker', 'gpu_control_migrate')
  LOOP
    IF r.rolsuper OR r.rolcreatedb OR r.rolcreaterole OR r.rolreplication OR
       r.rolbypassrls OR r.rolinherit THEN
      RAISE EXCEPTION 'runtime role % has unsafe attributes', r.rolname;
    END IF;
  END LOOP;
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

REVOKE CREATE ON SCHEMA public FROM PUBLIC, gpu_control_api, gpu_control_worker;
GRANT USAGE, CREATE ON SCHEMA public TO gpu_control_migrate;
COMMIT;

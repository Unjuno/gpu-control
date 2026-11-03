"""PostgreSQL ACL regression: worker DB access cannot read owner OAuth state."""
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import pytest
from sqlalchemy import insert, inspect, select, text, update

from gpu_gateway.store import Store, control, runs


DEPLOY = Path(__file__).resolve().parents[1] / "deploy"
ROLE_NAMES = ("gpu_control_api", "gpu_control_worker", "gpu_control_migrate",
              "gpu_control_unpriv")


@pytest.mark.skipif(not os.environ.get("GATEWAY_TEST_DATABASE_URL"),
                    reason="requires the dedicated disposable PostgreSQL test database")
def test_postgresql_runtime_roles_enforce_api_worker_and_migration_boundaries():
    url = os.environ["GATEWAY_TEST_DATABASE_URL"]
    store = Store(url)
    assert store.engine.dialect.name == "postgresql"
    with store.engine.connect() as connection:
        if not connection.execute(text("SELECT current_setting('is_superuser') = 'on'")).scalar_one():
            pytest.skip("database-role DDL regression requires the disposable PostgreSQL superuser")
    store.initialize()
    with store.engine.begin() as connection:
        connection.exec_driver_sql((DEPLOY / "database-runtime-roles-bootstrap.sql").read_text().replace("%", "%%"))
        connection.exec_driver_sql("""DO $$ BEGIN
            CREATE ROLE gpu_control_unpriv NOLOGIN NOINHERIT NOSUPERUSER;
          EXCEPTION WHEN duplicate_object THEN NULL; END $$""")
        connection.exec_driver_sql("REVOKE gpu_control_worker FROM gpu_control_unpriv")
        connection.exec_driver_sql("REVOKE gpu_control_unpriv FROM gpu_control_worker")
        connection.exec_driver_sql((DEPLOY / "database-runtime-roles-ownership.sql").read_text().replace("%", "%%"))
        connection.execute(text("SET ROLE gpu_control_migrate"))
        connection.exec_driver_sql((DEPLOY / "database-runtime-roles.sql").read_text().replace("%", "%%"))

        checks = {
            "api_reads_oauth": "SELECT has_table_privilege('gpu_control_api', 'public.gateway_oauth_tokens_v1', 'SELECT')",
            "api_updates_oauth": "SELECT has_table_privilege('gpu_control_api', 'public.gateway_oauth_tokens_v1', 'UPDATE')",
            "api_reads_login_budget": "SELECT has_table_privilege('gpu_control_api', 'public.gateway_oauth_login_budget_v1', 'SELECT')",
            "api_updates_login_budget": "SELECT has_table_privilege('gpu_control_api', 'public.gateway_oauth_login_budget_v1', 'UPDATE')",
            "api_inserts_login_sources": "SELECT has_table_privilege('gpu_control_api', 'public.gateway_oauth_login_source_buckets_v1', 'INSERT')",
            "api_updates_legacy_login_guard": "SELECT has_table_privilege('gpu_control_api', 'public.gateway_oauth_login_guard_v1', 'UPDATE')",
            "api_inserts_runs": "SELECT has_table_privilege('gpu_control_api', 'public.gateway_runs_v1', 'INSERT')",
            "api_deletes_runs": "SELECT has_table_privilege('gpu_control_api', 'public.gateway_runs_v1', 'DELETE')",
            "api_updates_approval": "SELECT has_column_privilege('gpu_control_api', 'public.gateway_runs_v1', 'approved_until', 'UPDATE')",
            "api_updates_result": "SELECT has_column_privilege('gpu_control_api', 'public.gateway_runs_v1', 'result', 'UPDATE')",
            "api_updates_active_count": "SELECT has_column_privilege('gpu_control_api', 'public.gateway_control_v1', 'active_count', 'UPDATE')",
            "worker_reads_runs": "SELECT has_table_privilege('gpu_control_worker', 'public.gateway_runs_v1', 'SELECT')",
            "worker_table_update_runs": "SELECT has_table_privilege('gpu_control_worker', 'public.gateway_runs_v1', 'UPDATE')",
            "worker_updates_state": "SELECT has_column_privilege('gpu_control_worker', 'public.gateway_runs_v1', 'state', 'UPDATE')",
            "worker_updates_owner": "SELECT has_column_privilege('gpu_control_worker', 'public.gateway_runs_v1', 'owner', 'UPDATE')",
            "worker_updates_plan": "SELECT has_column_privilege('gpu_control_worker', 'public.gateway_runs_v1', 'plan', 'UPDATE')",
            "worker_updates_fingerprint": "SELECT has_column_privilege('gpu_control_worker', 'public.gateway_runs_v1', 'fingerprint', 'UPDATE')",
            "worker_updates_slot": "SELECT has_column_privilege('gpu_control_worker', 'public.gateway_runs_v1', 'slot_reserved', 'UPDATE')",
            "worker_updates_active_count": "SELECT has_column_privilege('gpu_control_worker', 'public.gateway_control_v1', 'active_count', 'UPDATE')",
            "worker_inserts_runs": "SELECT has_table_privilege('gpu_control_worker', 'public.gateway_runs_v1', 'INSERT')",
            "worker_deletes_runs": "SELECT has_table_privilege('gpu_control_worker', 'public.gateway_runs_v1', 'DELETE')",
            "worker_deletes_control": "SELECT has_table_privilege('gpu_control_worker', 'public.gateway_control_v1', 'DELETE')",
            "worker_reads_oauth": "SELECT has_table_privilege('gpu_control_worker', 'public.gateway_oauth_tokens_v1', 'SELECT')",
            "worker_inserts_oauth": "SELECT has_table_privilege('gpu_control_worker', 'public.gateway_oauth_tokens_v1', 'INSERT')",
            "worker_updates_oauth": "SELECT has_table_privilege('gpu_control_worker', 'public.gateway_oauth_tokens_v1', 'UPDATE')",
            "worker_deletes_oauth": "SELECT has_table_privilege('gpu_control_worker', 'public.gateway_oauth_tokens_v1', 'DELETE')",
            "worker_reads_login_budget": "SELECT has_table_privilege('gpu_control_worker', 'public.gateway_oauth_login_budget_v1', 'SELECT')",
            "worker_inserts_login_sources": "SELECT has_table_privilege('gpu_control_worker', 'public.gateway_oauth_login_source_buckets_v1', 'INSERT')",
            "api_creates_schema": "SELECT has_schema_privilege('gpu_control_api', 'public', 'CREATE')",
            "worker_creates_schema": "SELECT has_schema_privilege('gpu_control_worker', 'public', 'CREATE')",
            "unpriv_creates_schema": "SELECT has_schema_privilege('gpu_control_unpriv', 'public', 'CREATE')",
            "migrate_creates_schema": "SELECT has_schema_privilege('gpu_control_migrate', 'public', 'CREATE')",
            "unpriv_reads_oauth": "SELECT has_table_privilege('gpu_control_unpriv', 'public.gateway_oauth_tokens_v1', 'SELECT')",
            "worker_executes_release": "SELECT has_function_privilege('gpu_control_worker', 'public.gpu_control_release_finished_slot(text,text)', 'EXECUTE')",
            "api_locks_provider_observation": "SELECT has_function_privilege('gpu_control_api', 'public.gpu_control_lock_provider_observation(text)', 'EXECUTE')",
            "worker_locks_provider_observation": "SELECT has_function_privilege('gpu_control_worker', 'public.gpu_control_lock_provider_observation(text)', 'EXECUTE')",
            "unpriv_locks_provider_observation": "SELECT has_function_privilege('gpu_control_unpriv', 'public.gpu_control_lock_provider_observation(text)', 'EXECUTE')",
            "api_reads_provider_observations": "SELECT has_table_privilege('gpu_control_api', 'public.gateway_provider_observations_v1', 'SELECT')",
            "api_updates_provider_observations": "SELECT has_table_privilege('gpu_control_api', 'public.gateway_provider_observations_v1', 'UPDATE')",
            "worker_updates_provider_observation_payload": "SELECT has_column_privilege('gpu_control_worker', 'public.gateway_provider_observations_v1', 'envelope', 'UPDATE')",
            "worker_updates_provider_observation_key": "SELECT has_column_privilege('gpu_control_worker', 'public.gateway_provider_observations_v1', 'provider', 'UPDATE')",
            "api_reads_provider_leases": "SELECT has_table_privilege('gpu_control_api', 'public.gateway_provider_account_leases_v1', 'SELECT')",
            "worker_updates_provider_leases": "SELECT has_table_privilege('gpu_control_worker', 'public.gateway_provider_account_leases_v1', 'UPDATE')",
            "worker_updates_provider_scope": "SELECT has_column_privilege('gpu_control_worker', 'public.gateway_provider_account_leases_v1', 'account_scope', 'UPDATE')",
            "worker_deletes_provider_leases": "SELECT has_table_privilege('gpu_control_worker', 'public.gateway_provider_account_leases_v1', 'DELETE')",
            "worker_reads_paid_authorizations": "SELECT has_table_privilege('gpu_control_worker', 'public.gateway_paid_authorizations_v1', 'SELECT')",
            "worker_writes_paid_authorizations": "SELECT has_table_privilege('gpu_control_worker', 'public.gateway_paid_authorizations_v1', 'INSERT') OR has_table_privilege('gpu_control_worker', 'public.gateway_paid_authorizations_v1', 'UPDATE') OR has_table_privilege('gpu_control_worker', 'public.gateway_paid_authorizations_v1', 'DELETE')",
            "api_reads_paid_authorizations": "SELECT has_table_privilege('gpu_control_api', 'public.gateway_paid_authorizations_v1', 'SELECT')",
            "api_executes_release": "SELECT has_function_privilege('gpu_control_api', 'public.gpu_control_release_finished_slot(text,text)', 'EXECUTE')",
            "unpriv_executes_release": "SELECT has_function_privilege('gpu_control_unpriv', 'public.gpu_control_release_finished_slot(text,text)', 'EXECUTE')",
        }
        with store.engine.connect() as connection:
            observed = {name: connection.execute(text(query)).scalar_one()
                        for name, query in checks.items()}
        assert observed == {
            "api_reads_oauth": True,
            "api_updates_oauth": True,
            "api_reads_login_budget": True,
            "api_updates_login_budget": True,
            "api_inserts_login_sources": True,
            "api_updates_legacy_login_guard": False,
            "api_inserts_runs": True,
            "api_deletes_runs": False,
            "api_updates_approval": True,
            "api_updates_result": False,
            "api_updates_active_count": True,
            "worker_reads_runs": True,
            "worker_table_update_runs": False,
            "worker_updates_state": True,
            "worker_updates_owner": False,
            "worker_updates_plan": False,
            "worker_updates_fingerprint": False,
            "worker_updates_slot": False,
            "worker_updates_active_count": False,
            "worker_inserts_runs": False,
            "worker_deletes_runs": False,
            "worker_deletes_control": False,
            "worker_reads_oauth": False,
            "worker_inserts_oauth": False,
            "worker_updates_oauth": False,
            "worker_deletes_oauth": False,
            "worker_reads_login_budget": False,
            "worker_inserts_login_sources": False,
            "api_creates_schema": False,
            "worker_creates_schema": False,
            "unpriv_creates_schema": False,
            "migrate_creates_schema": True,
            "unpriv_reads_oauth": False,
            "worker_executes_release": True,
            "api_locks_provider_observation": True,
            "worker_locks_provider_observation": True,
            "unpriv_locks_provider_observation": False,
            "api_reads_provider_observations": True,
            "api_updates_provider_observations": False,
            "worker_updates_provider_observation_payload": True,
            "worker_updates_provider_observation_key": False,
            "api_reads_provider_leases": False,
            "worker_updates_provider_leases": True,
            "worker_updates_provider_scope": False,
            "worker_deletes_provider_leases": False,
            "worker_reads_paid_authorizations": True,
            "worker_writes_paid_authorizations": False,
            "api_reads_paid_authorizations": False,
            "api_executes_release": False,
            "unpriv_executes_release": False,
        }

        with store.engine.connect() as connection:
            role_state = connection.execute(text(
                "SELECT rolname, rolsuper, rolcreatedb, rolcreaterole, rolreplication, "
                "rolbypassrls, rolinherit FROM pg_roles WHERE rolname = ANY(:roles)"),
                {"roles": list(ROLE_NAMES[:-1])}).all()
            memberships = connection.execute(text(
                "SELECT count(*) FROM pg_auth_members m JOIN pg_roles member_role ON member_role.oid=m.member "
                "JOIN pg_roles granted_role ON granted_role.oid=m.roleid "
                "WHERE member_role.rolname = ANY(:roles) OR granted_role.rolname = ANY(:roles)"),
                {"roles": list(ROLE_NAMES[:-1])}).scalar_one()
        assert len(role_state) == 3
        assert all(not any(row[1:]) for row in role_state)
        assert memberships == 0

        bootstrap_sql = (DEPLOY / "database-runtime-roles-bootstrap.sql").read_text().replace("%", "%%")
        for grant in ("GRANT gpu_control_worker TO gpu_control_unpriv",
                      "GRANT gpu_control_unpriv TO gpu_control_worker"):
            with store.engine.begin() as connection:
                connection.exec_driver_sql(grant)
            with store.engine.connect() as connection:
                with pytest.raises(Exception):
                    connection.exec_driver_sql(bootstrap_sql)
                connection.rollback()
            with store.engine.begin() as connection:
                if grant.endswith("gpu_control_unpriv"):
                    connection.exec_driver_sql("REVOKE gpu_control_worker FROM gpu_control_unpriv")
                else:
                    connection.exec_driver_sql("REVOKE gpu_control_unpriv FROM gpu_control_worker")
        with store.engine.connect() as connection:
            owners = connection.execute(text(
                "SELECT count(*) FROM pg_tables WHERE schemaname='public' "
                "AND tablename LIKE 'gateway_%' AND tableowner='gpu_control_migrate'"
            )).scalar_one()
        assert owners >= 13

        run_id, lease_token = uuid4().hex, uuid4().hex
        with store.engine.begin() as connection:
            previous_active_count = connection.execute(select(control.c.active_count)).scalar_one()
            connection.execute(insert(runs).values(
                id=run_id, owner="role-test-" + uuid4().hex,
                idempotency_key="role-test-" + uuid4().hex,
                request_hash="1" * 64, fingerprint="2" * 64, plan={},
                state="succeeded", created_at=1, started_at=1, approved_until=0,
                approval_id="", handle=None, result={"ok": True}, error="",
                lease_until=1, lease_token=lease_token, cancel_requested=False,
                slot_reserved=True, record_version=2, cleanup_state="complete",
                finished_at=1, result_manifest=None, admission=None, attempt=1,
                submission_intent=None, last_observed_at=1))
            connection.execute(update(control).where(control.c.id == 1).values(
                active_count=control.c.active_count + 1))
        with store.engine.connect() as connection:
            connection.execute(text("SET ROLE gpu_control_worker"))
            assert connection.execute(text(
                "SELECT public.gpu_control_release_finished_slot(:run_id, :token)"),
                {"run_id": run_id, "token": "f" * 32}).scalar_one() is False
            connection.rollback()
        with store.engine.connect() as connection:
            connection.execute(text("SET ROLE gpu_control_worker"))
            assert connection.execute(text(
                "SELECT public.gpu_control_release_finished_slot(:run_id, :token)"),
                {"run_id": run_id, "token": lease_token}).scalar_one() is True
            connection.commit()
        with store.engine.connect() as connection:
            assert connection.execute(text(
                "SELECT slot_reserved FROM public.gateway_runs_v1 WHERE id=:run_id"),
                {"run_id": run_id}).scalar_one() is False
            assert connection.execute(text(
                "SELECT active_count FROM public.gateway_control_v1 WHERE id=1")).scalar_one() == previous_active_count
            connection.execute(text("SET ROLE gpu_control_worker"))
            assert connection.execute(text(
                "SELECT public.gpu_control_release_finished_slot(:run_id, :token)"),
                {"run_id": run_id, "token": lease_token}).scalar_one() is False
            with pytest.raises(Exception):
                connection.execute(text(
                    "UPDATE public.gateway_runs_v1 SET owner='forged' WHERE id=:run_id"),
                    {"run_id": run_id})
            connection.rollback()
        for statement in (
            "UPDATE public.gateway_control_v1 SET active_count=0 WHERE id=1",
            "UPDATE public.gateway_runs_v1 SET slot_reserved=FALSE WHERE id=:run_id",
        ):
            with store.engine.connect() as connection:
                connection.execute(text("SET ROLE gpu_control_worker"))
                with pytest.raises(Exception):
                    connection.execute(text(statement), {"run_id": run_id})
                connection.rollback()

        rollback_id, rollback_token = uuid4().hex, uuid4().hex
        with store.engine.begin() as connection:
            connection.execute(insert(runs).values(
                id=rollback_id, owner="role-test-" + uuid4().hex,
                idempotency_key="role-test-" + uuid4().hex,
                request_hash="3" * 64, fingerprint="4" * 64, plan={},
                state="failed", created_at=2, started_at=2, approved_until=0,
                approval_id="", handle=None, result=None, error="test",
                lease_until=2, lease_token=rollback_token, cancel_requested=False,
                slot_reserved=True, record_version=2, cleanup_state="complete",
                finished_at=2, result_manifest=None, admission=None, attempt=1,
                submission_intent=None, last_observed_at=2))
            connection.execute(update(control).where(control.c.id == 1).values(
                active_count=control.c.active_count + 1))
        with store.engine.connect() as connection:
            connection.execute(text("SET ROLE gpu_control_worker"))
            assert connection.execute(text(
                "SELECT public.gpu_control_release_finished_slot(:run_id, :token)"),
                {"run_id": rollback_id, "token": rollback_token}).scalar_one() is True
            connection.rollback()
        with store.engine.connect() as connection:
            assert connection.execute(text(
                "SELECT slot_reserved FROM public.gateway_runs_v1 WHERE id=:run_id"),
                {"run_id": rollback_id}).scalar_one() is True
            assert connection.execute(text(
                "SELECT active_count FROM public.gateway_control_v1 WHERE id=1")).scalar_one() == previous_active_count + 1
        with store.engine.connect() as connection:
            connection.execute(text("SET ROLE gpu_control_worker"))
            assert connection.execute(text(
                "SELECT public.gpu_control_release_finished_slot(:run_id, :token)"),
                {"run_id": rollback_id, "token": rollback_token}).scalar_one() is True
            connection.commit()
        with store.engine.connect() as connection:
            assert connection.execute(text(
                "SELECT active_count FROM public.gateway_control_v1 WHERE id=1")).scalar_one() == previous_active_count

        with store.engine.connect() as connection:
            connection.execute(text("SET ROLE gpu_control_worker"))
            assert connection.execute(text(
                "SELECT count(*) FROM public.gateway_runs_v1")).scalar_one() >= 0
            with pytest.raises(Exception):
                connection.execute(text("SELECT count(*) FROM public.gateway_oauth_tokens_v1"))
            connection.rollback()
    store.engine.dispose()


@pytest.mark.skipif(not os.environ.get("GATEWAY_TEST_DATABASE_URL"),
                    reason="requires the dedicated disposable PostgreSQL test database")
def test_check_db_is_read_only_and_reports_current_pr58_schema():
    url = os.environ["GATEWAY_TEST_DATABASE_URL"]
    store = Store(url)
    with store.engine.connect() as connection:
        connection.execute(text("SET ROLE gpu_control_migrate"))
        migration_inspector = inspect(connection)
        assert "gateway_schema_version" in migration_inspector.get_table_names()
        before = connection.execute(text(
            "SELECT version FROM public.gateway_schema_version WHERE id=1")).scalar_one()
        tables_before = set(migration_inspector.get_table_names())
        connection.rollback()
    env = dict(os.environ, GATEWAY_DATABASE_URL=url)
    result = subprocess.run([sys.executable, "-m", "gpu_gateway.worker", "--check-db"],
                            cwd=Path(__file__).resolve().parents[1], env=env,
                            capture_output=True, text=True, check=False, timeout=20)
    assert result.returncode == 0, result.stderr
    report = __import__("json").loads(result.stdout)
    assert report["read_only"] is True
    assert report["current_version"] == report["target_version"] == 14
    assert report["planned_versions"] == []
    with store.engine.connect() as connection:
        connection.execute(text("SET ROLE gpu_control_migrate"))
        after = connection.execute(text(
            "SELECT version FROM public.gateway_schema_version WHERE id=1")).scalar_one()
        tables_after = set(inspect(connection).get_table_names())
        connection.rollback()
    assert (before, tables_before) == (after, tables_after)
    store.engine.dispose()


@pytest.mark.skipif(not os.environ.get("GATEWAY_TEST_DATABASE_URL"),
                    reason="requires the dedicated disposable PostgreSQL test database")
def test_restore_ownership_reduces_security_definer_function_to_migration_role():
    """A no-owner dump restored by a DBA must not leave the function DBA-owned."""
    url = os.environ["GATEWAY_TEST_DATABASE_URL"]
    store = Store(url)
    assert store.engine.dialect.name == "postgresql"
    with store.engine.connect() as connection:
        if not connection.execute(text("SELECT current_setting('is_superuser') = 'on'")).scalar_one():
            pytest.skip("restore ownership regression requires the disposable PostgreSQL superuser")
    store.initialize()
    with store.engine.begin() as connection:
        connection.exec_driver_sql((DEPLOY / "database-runtime-roles-bootstrap.sql").read_text().replace("%", "%%"))
        connection.exec_driver_sql((DEPLOY / "database-runtime-roles-ownership.sql").read_text().replace("%", "%%"))
        connection.exec_driver_sql("SET ROLE gpu_control_migrate")
        connection.exec_driver_sql((DEPLOY / "database-runtime-roles.sql").read_text().replace("%", "%%"))
        connection.exec_driver_sql("RESET ROLE")

        # pg_restore --no-owner makes the restore connection the new owner.
        connection.exec_driver_sql(
            "ALTER FUNCTION public.gpu_control_release_finished_slot(text,text) OWNER TO CURRENT_USER")
        owner = connection.execute(text(
            "SELECT pg_get_userbyid(proowner) FROM pg_proc "
            "WHERE oid='public.gpu_control_release_finished_slot(text,text)'::regprocedure"
        )).scalar_one()
        assert owner != "gpu_control_migrate"

        connection.exec_driver_sql((DEPLOY / "database-runtime-roles-ownership.sql").read_text().replace("%", "%%"))
        owner = connection.execute(text(
            "SELECT pg_get_userbyid(proowner) FROM pg_proc "
            "WHERE oid='public.gpu_control_release_finished_slot(text,text)'::regprocedure"
        )).scalar_one()
        assert owner == "gpu_control_migrate"
        connection.exec_driver_sql(
            "ALTER FUNCTION public.gpu_control_lock_provider_observation(text) OWNER TO CURRENT_USER")
        observation_owner = connection.execute(text(
            "SELECT pg_get_userbyid(proowner) FROM pg_proc "
            "WHERE oid='public.gpu_control_lock_provider_observation(text)'::regprocedure"
        )).scalar_one()
        assert observation_owner != "gpu_control_migrate"
        connection.exec_driver_sql((DEPLOY / "database-runtime-roles-ownership.sql").read_text().replace("%", "%%"))
        observation_owner = connection.execute(text(
            "SELECT pg_get_userbyid(proowner) FROM pg_proc "
            "WHERE oid='public.gpu_control_lock_provider_observation(text)'::regprocedure"
        )).scalar_one()
        assert observation_owner == "gpu_control_migrate"

        connection.exec_driver_sql("SET ROLE gpu_control_migrate")
        connection.exec_driver_sql((DEPLOY / "database-runtime-roles.sql").read_text().replace("%", "%%"))
        assert connection.execute(text(
            "SELECT has_function_privilege('gpu_control_worker', "
            "'public.gpu_control_release_finished_slot(text,text)', 'EXECUTE')"
        )).scalar_one() is True
        assert connection.execute(text(
            "SELECT NOT EXISTS (SELECT 1 FROM aclexplode((SELECT proacl FROM pg_proc "
            "WHERE oid='public.gpu_control_release_finished_slot(text,text)'::regprocedure)) "
            "WHERE grantee=0 AND privilege_type='EXECUTE')"
        )).scalar_one() is True
        assert connection.execute(text(
            "SELECT NOT EXISTS (SELECT 1 FROM aclexplode((SELECT proacl FROM pg_proc "
            "WHERE oid='public.gpu_control_lock_provider_observation(text)'::regprocedure)) "
            "WHERE grantee=0 AND privilege_type='EXECUTE')"
        )).scalar_one() is True
    store.engine.dispose()

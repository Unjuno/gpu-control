"""PostgreSQL ACL regression: worker DB access cannot read owner OAuth state."""
from contextlib import contextmanager
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import pytest
from sqlalchemy import insert, inspect, select, text, update

from gpu_gateway.store import Store, control, runs
from gpu_gateway.config import Settings
from gpu_gateway.worker import Worker


DEPLOY = Path(__file__).resolve().parents[1] / "deploy"
ROLE_NAMES = ("gpu_control_api", "gpu_control_worker", "gpu_control_migrate",
              "gpu_control_unpriv")


@contextmanager
def _store_transactions_as_role(store, role):
    original = store.transaction

    @contextmanager
    def role_transaction():
        with store.engine.connect() as connection:
            transaction = connection.begin()
            connection.exec_driver_sql(f"SET LOCAL ROLE {role}")
            try:
                yield connection
                transaction.commit()
            except BaseException:
                transaction.rollback()
                raise

    store.transaction = role_transaction
    try:
        yield
    finally:
        store.transaction = original


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
        connection.exec_driver_sql(
            "GRANT UPDATE (account_scope) ON TABLE public.gateway_provider_account_leases_v1 "
            "TO gpu_control_worker")
        connection.exec_driver_sql(
            "GRANT UPDATE (envelope) ON TABLE public.gateway_provider_observations_v1 "
            "TO gpu_control_api")
        connection.exec_driver_sql(
            "GRANT UPDATE (envelope) ON TABLE public.gateway_paid_authorizations_v1 "
            "TO gpu_control_worker")
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
            "api_updates_provider_observation_envelope": "SELECT has_column_privilege('gpu_control_api', 'public.gateway_provider_observations_v1', 'envelope', 'UPDATE')",
            "worker_updates_provider_observation_payload": "SELECT has_column_privilege('gpu_control_worker', 'public.gateway_provider_observations_v1', 'envelope', 'UPDATE')",
            "worker_updates_provider_observation_key": "SELECT has_column_privilege('gpu_control_worker', 'public.gateway_provider_observations_v1', 'provider', 'UPDATE')",
            "api_reads_provider_leases": "SELECT has_table_privilege('gpu_control_api', 'public.gateway_provider_account_leases_v1', 'SELECT')",
            "worker_updates_provider_leases": "SELECT has_column_privilege('gpu_control_worker', 'public.gateway_provider_account_leases_v1', 'state', 'UPDATE')",
            "worker_updates_provider_scope": "SELECT has_column_privilege('gpu_control_worker', 'public.gateway_provider_account_leases_v1', 'account_scope', 'UPDATE')",
            "worker_deletes_provider_leases": "SELECT has_table_privilege('gpu_control_worker', 'public.gateway_provider_account_leases_v1', 'DELETE')",
            "worker_reads_paid_authorizations": "SELECT has_table_privilege('gpu_control_worker', 'public.gateway_paid_authorizations_v1', 'SELECT')",
            "worker_writes_paid_authorizations": "SELECT has_table_privilege('gpu_control_worker', 'public.gateway_paid_authorizations_v1', 'INSERT') OR has_table_privilege('gpu_control_worker', 'public.gateway_paid_authorizations_v1', 'UPDATE') OR has_table_privilege('gpu_control_worker', 'public.gateway_paid_authorizations_v1', 'DELETE')",
            "worker_updates_paid_authorization_envelope": "SELECT has_column_privilege('gpu_control_worker', 'public.gateway_paid_authorizations_v1', 'envelope', 'UPDATE')",
            "api_updates_paid_authorizations": "SELECT has_table_privilege('gpu_control_api', 'public.gateway_paid_authorizations_v1', 'UPDATE')",
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
            "api_updates_provider_observation_envelope": False,
            "worker_updates_provider_observation_payload": True,
            "worker_updates_provider_observation_key": False,
            "api_reads_provider_leases": False,
            "worker_updates_provider_leases": True,
            "worker_updates_provider_scope": False,
            "worker_deletes_provider_leases": False,
            "worker_reads_paid_authorizations": True,
            "worker_writes_paid_authorizations": False,
            "worker_updates_paid_authorization_envelope": False,
            "api_updates_paid_authorizations": False,
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
        for role, statement in (
            ("gpu_control_api", "UPDATE public.gateway_provider_observations_v1 SET envelope='{}'::jsonb WHERE false"),
            ("gpu_control_worker", "UPDATE public.gateway_provider_account_leases_v1 SET account_scope='x' WHERE false"),
            ("gpu_control_worker", "UPDATE public.gateway_paid_authorizations_v1 SET envelope='{}'::jsonb WHERE false"),
        ):
            with store.engine.connect() as connection:
                connection.execute(text(f"SET ROLE {role}"))
                with pytest.raises(Exception):
                    connection.execute(text(statement))
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
def test_postgresql_p5_store_paths_run_under_effective_api_and_worker_roles():
    """Exercise Store operations with PostgreSQL enforcing the runtime ACLs."""
    from hashlib import sha256
    from concurrent.futures import ThreadPoolExecutor
    from sqlalchemy.exc import DBAPIError

    from gpu_gateway.migrations import paid_authorizations, provider_account_leases, provider_observations
    from gpu_gateway.provider_evidence import _canonical

    url = os.environ["GATEWAY_TEST_DATABASE_URL"]
    store = Store(url)
    assert store.engine.dialect.name == "postgresql"
    with store.engine.connect() as connection:
        if not connection.execute(text("SELECT current_setting('is_superuser') = 'on'")).scalar_one():
            pytest.skip("runtime Store role regression requires the disposable PostgreSQL superuser")
    store.initialize()
    with store.engine.begin() as connection:
        connection.exec_driver_sql((DEPLOY / "database-runtime-roles-bootstrap.sql").read_text().replace("%", "%%"))
        connection.exec_driver_sql((DEPLOY / "database-runtime-roles-ownership.sql").read_text().replace("%", "%%"))
        connection.exec_driver_sql("SET ROLE gpu_control_migrate")
        connection.exec_driver_sql((DEPLOY / "database-runtime-roles.sql").read_text().replace("%", "%%"))

    def seed_run(*, run_id, token, owner, fingerprint, state, cancel=False,
                 approval_id="", approved_until=0, plan=None, attempt=0,
                 submission_intent=None, handle=None, slot_reserved=False,
                 cleanup_state="unknown", result=None):
        with store.engine.begin() as connection:
            connection.execute(insert(runs).values(
                id=run_id, owner=owner, idempotency_key="role-api-" + run_id,
                request_hash="1" * 64, fingerprint=fingerprint,
                plan=plan or {"schema_version": 2}, state=state,
                created_at=100, started_at=100, approved_until=approved_until,
                approval_id=approval_id, handle=handle, result=result, error="",
                lease_until=1000, lease_token=token, cancel_requested=cancel,
                slot_reserved=slot_reserved, record_version=2,
                cleanup_state=cleanup_state, finished_at=None,
                result_manifest=None, admission=None, attempt=attempt,
                submission_intent=submission_intent, last_observed_at=None,
            ))

    # Ordinary CPU/demo terminal completion must not write the protected slot
    # or counter columns directly from the worker role.
    cpu_run, cpu_token = uuid4().hex, uuid4().hex
    seed_run(run_id=cpu_run, token=cpu_token, owner="role-cpu-" + cpu_run,
             fingerprint="1" * 64, state="running", slot_reserved=True)
    with store.engine.begin() as connection:
        connection.execute(update(control).where(control.c.id == 1).values(
            active_count=control.c.active_count + 1))
    worker = Worker(store, Settings(), {}, clock=lambda: 200)
    with _store_transactions_as_role(store, "gpu_control_worker"):
        worker.finish({"id": cpu_run, "lease_token": cpu_token, "plan": {},
                       "fingerprint": "1" * 64}, "failed", error="role-test")
    assert store.read(cpu_run)["slot_reserved"] is False
    with store.engine.connect() as connection:
        assert connection.execute(select(control.c.active_count)).scalar_one() == 0

    # Provider cleanup: wrong provider identity leaves all state intact; valid
    # completion releases the account lease and slot once, through the helper.
    cleanup_run, cleanup_token = uuid4().hex, uuid4().hex
    owner, fingerprint, scope = "role-cleanup-" + cleanup_run, "2" * 64, "3" * 64
    core_fingerprint, authorization_id = "4" * 64, "role-paid-cleanup"
    challenge = {"template_id": "template-role", "name": "role-" + cleanup_run}
    seed_run(run_id=cleanup_run, token=cleanup_token, owner=owner,
             fingerprint=fingerprint, state="submitting")
    lease = store.reserve_provider_account_lease_with_submission_intent(
        provider="runpod", account_scope=scope, run_id=cleanup_run, owner=owner,
        plan_fingerprint=fingerprint, core_plan_fingerprint=core_fingerprint,
        authorization_id=authorization_id, run_lease_token=cleanup_token,
        attempt=1, request_challenge=challenge, now=110)
    assert lease is not None
    assert store.transition_provider_account_lease_for_run(
        account_scope=scope, run_id=cleanup_run, owner=owner,
        plan_fingerprint=fingerprint, lease_token=lease.lease_token,
        run_lease_token=cleanup_token, core_plan_fingerprint=core_fingerprint,
        authorization_id=authorization_id, expected_state="reserved",
        new_state="submitting", now=111)
    assert store.transition_provider_account_lease_for_run(
        account_scope=scope, run_id=cleanup_run, owner=owner,
        plan_fingerprint=fingerprint, lease_token=lease.lease_token,
        run_lease_token=cleanup_token, core_plan_fingerprint=core_fingerprint,
        authorization_id=authorization_id, expected_state="submitting",
        new_state="active", provider_job_id="role-pod", now=112)
    with store.engine.begin() as connection:
        run = connection.execute(select(runs).where(runs.c.id == cleanup_run)).mappings().one()
        connection.execute(update(runs).where(runs.c.id == cleanup_run).values(
            state="running", handle={"pod_id": "role-pod"}, slot_reserved=True,
            cleanup_state="pending", result={"schema_version": 2, "cleanup_state": "pending"},
            submission_intent=run["submission_intent"] | {"phase": "handle_persisted"},
        ))
        connection.execute(update(control).where(control.c.id == 1).values(
            active_count=control.c.active_count + 1))
    assert store.transition_provider_account_lease_for_run(
        account_scope=scope, run_id=cleanup_run, owner=owner,
        plan_fingerprint=fingerprint, lease_token=lease.lease_token,
        run_lease_token=cleanup_token, core_plan_fingerprint=core_fingerprint,
        authorization_id=authorization_id, expected_state="active",
        new_state="cleanup_pending", now=113)
    cleanup_kwargs = dict(
        account_scope=scope, run_id=cleanup_run, owner=owner,
        plan_fingerprint=fingerprint, lease_token=lease.lease_token,
        run_lease_token=cleanup_token, core_plan_fingerprint=core_fingerprint,
        authorization_id=authorization_id, provider_job_id="role-pod",
        cleanup_confirmed=True, state="succeeded",
        result={"schema_version": 2, "cleanup_state": "complete", "checks": []},
        error="", record_version=2, now=120,
    )
    with _store_transactions_as_role(store, "gpu_control_worker"):
        assert store.finish_run_after_provider_cleanup(
            **(cleanup_kwargs | {"provider_job_id": "wrong-pod"})) is False
        assert store.finish_run_after_provider_cleanup(**cleanup_kwargs) is True
        assert store.finish_run_after_provider_cleanup(**cleanup_kwargs) is False
    assert store.read(cleanup_run)["slot_reserved"] is False
    with store.engine.connect() as connection:
        assert connection.execute(select(provider_account_leases.c.state).where(
            provider_account_leases.c.account_scope == scope)).scalar_one() == "released"
        assert connection.execute(select(control.c.active_count)).scalar_one() == 0

    # Proven pre-submission abort uses the same role-limited slot release.
    abort_run, abort_token = uuid4().hex, uuid4().hex
    abort_owner, abort_fingerprint, abort_scope = "role-abort-" + abort_run, "5" * 64, "6" * 64
    abort_auth, abort_core = "role-paid-abort", "7" * 64
    seed_run(run_id=abort_run, token=abort_token, owner=abort_owner,
             fingerprint=abort_fingerprint, state="submitting")
    abort_lease = store.reserve_provider_account_lease_with_submission_intent(
        provider="runpod", account_scope=abort_scope, run_id=abort_run, owner=abort_owner,
        plan_fingerprint=abort_fingerprint, core_plan_fingerprint=abort_core,
        authorization_id=abort_auth, run_lease_token=abort_token,
        attempt=1, request_challenge={"template_id": "template-role", "name": "abort-" + abort_run},
        now=130)
    assert abort_lease is not None
    with store.engine.begin() as connection:
        connection.execute(update(runs).where(runs.c.id == abort_run).values(
            cancel_requested=True, slot_reserved=True))
        connection.execute(update(control).where(control.c.id == 1).values(
            active_count=control.c.active_count + 1))
    abort_kwargs = dict(
        account_scope=abort_scope, run_id=abort_run, owner=abort_owner,
        plan_fingerprint=abort_fingerprint, lease_token=abort_lease.lease_token,
        run_lease_token=abort_token, core_plan_fingerprint=abort_core,
        authorization_id=abort_auth, state="cancelled",
        result={"schema_version": 2, "cleanup_state": "not_required", "checks": []},
        error="cancelled_before_submit", record_version=2, now=140,
    )
    with _store_transactions_as_role(store, "gpu_control_worker"):
        assert store.finish_run_after_pre_submission_abort(**abort_kwargs) is True
        assert store.finish_run_after_pre_submission_abort(**abort_kwargs) is False
    assert store.read(abort_run)["slot_reserved"] is False
    with store.engine.connect() as connection:
        assert connection.execute(select(provider_account_leases.c.state).where(
            provider_account_leases.c.account_scope == abort_scope)).scalar_one() == "released"
        assert connection.execute(select(control.c.active_count)).scalar_one() == 0

    # API locks signed observation rows through the definer function. A second
    # publisher remains blocked until the API's transaction ends.
    observation = {"provider": "runpod", "version": 1,
                   "observed_at": 100, "expires_at": 300, "payload": {}}
    with store.engine.begin() as connection:
        connection.execute(insert(provider_observations).values(
            provider="runpod", version=1, observed_at=100, expires_at=300,
            envelope=observation,
            envelope_sha256=sha256(_canonical(observation)).hexdigest()))
    newer_observation = {"provider": "runpod", "version": 2,
                         "observed_at": 200, "expires_at": 400, "payload": {}}

    def publish_as_worker_with_timeout():
        with store.engine.connect() as writer:
            transaction = writer.begin()
            try:
                writer.exec_driver_sql("SET LOCAL ROLE gpu_control_worker")
                writer.exec_driver_sql("SET LOCAL lock_timeout = '300ms'")
                writer.execute(update(provider_observations).where(
                    provider_observations.c.provider == "runpod").values(
                        version=2, observed_at=200, expires_at=400,
                        envelope=newer_observation,
                        envelope_sha256=sha256(_canonical(newer_observation)).hexdigest()))
                transaction.rollback()
                return None
            except DBAPIError as exc:
                state = getattr(exc.orig, "sqlstate", None) or getattr(exc.orig, "pgcode", None)
                transaction.rollback()
                return state

    with ThreadPoolExecutor(max_workers=1) as pool:
        with _store_transactions_as_role(store, "gpu_control_api"):
            with store.transaction() as connection:
                assert store.read_provider_observation(
                    "runpod", connection=connection, lock=True) is not None
                future = pool.submit(publish_as_worker_with_timeout)
                assert future.result(timeout=5) == "55P03"
        with store.engine.begin() as writer:
            writer.exec_driver_sql("SET LOCAL ROLE gpu_control_worker")
            writer.execute(update(provider_observations).where(
                provider_observations.c.provider == "runpod").values(
                    version=2, observed_at=200, expires_at=400,
                    envelope=newer_observation,
                    envelope_sha256=sha256(_canonical(newer_observation)).hexdigest()))

    # The worker's paid-authorization reader locks the run for serialization,
    # but reads the authorization row with SELECT-only privileges.
    auth_run, auth_token = uuid4().hex, uuid4().hex
    auth_owner, auth_fingerprint, approval_id = "role-auth-" + uuid4().hex, "9" * 64, uuid4().hex
    envelope = {"authorization_id": "paid-role-1", "issuer": "issuer-role",
                "run_id": auth_run, "owner": auth_owner,
                "gateway_plan_fingerprint": auth_fingerprint, "expires_at": 500}
    encoded = __import__("json").dumps(envelope, ensure_ascii=True, sort_keys=True,
                                        separators=(",", ":"), allow_nan=False).encode("ascii")
    seed_run(run_id=auth_run, token=auth_token, owner=auth_owner,
             fingerprint=auth_fingerprint, state="approved", approval_id=approval_id,
             approved_until=450, plan={"schema_version": 2})
    with store.engine.begin() as connection:
        connection.execute(insert(paid_authorizations).values(
            run_id=auth_run, owner=auth_owner, plan_fingerprint=auth_fingerprint,
            approval_id=approval_id, authorization_id="paid-role-1", issuer="issuer-role",
            envelope=envelope, envelope_sha256=sha256(encoded).hexdigest(), created_at=100))
    with _store_transactions_as_role(store, "gpu_control_worker"):
        assert store.read_paid_authorization(
            run_id=auth_run, owner=auth_owner, plan_fingerprint=auth_fingerprint,
            approval_id=approval_id, now=200) is not None
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
    assert report["current_version"] == report["target_version"] == 15
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

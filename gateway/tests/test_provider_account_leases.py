from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from sqlalchemy import select

from gpu_gateway.migrations import SCHEMA_VERSION, migration_status, provider_account_leases
from gpu_gateway.store import Store, control, runs


def test_provider_account_lease_excludes_a_second_run_until_confirmed_release(tmp_path):
    store = Store(f"sqlite:///{tmp_path / 'provider-account-lease.db'}")
    store.initialize()
    scope = "a" * 64
    plan = "b" * 64
    first_run = uuid4().hex
    second_run = uuid4().hex

    lease = store.reserve_provider_account_lease(
        provider="runpod", account_scope=scope, run_id=first_run,
        owner="owner-a", plan_fingerprint=plan, core_plan_fingerprint="e" * 64, authorization_id="auth-test", now=100,
    )
    assert lease is not None
    assert lease.state == "reserved"
    assert len(lease.lease_token) == 64
    retry_lease = store.reserve_provider_account_lease(
        provider="runpod", account_scope=scope, run_id=first_run,
        owner="owner-a", plan_fingerprint=plan, core_plan_fingerprint="e" * 64, authorization_id="auth-test", now=100,
    )
    assert retry_lease is not None
    assert retry_lease.lease_token == lease.lease_token
    assert not store.transition_provider_account_lease(
        account_scope=scope, run_id=first_run, owner="owner-a",
        plan_fingerprint=plan, core_plan_fingerprint="e" * 64, authorization_id="auth-test", lease_token=lease.lease_token,
        expected_state="reserved", new_state="submitting", now=100,
    )
    assert not store.bind_provider_account_lease_challenge(
        account_scope=scope, run_id=first_run, owner="owner-a",
        plan_fingerprint=plan, core_plan_fingerprint="e" * 64,
        authorization_id="auth-test", lease_token=lease.lease_token,
        request_challenge={"spec": {"api_key": "must-not-persist"}}, now=100,
    )
    for key_name in ("GPU_CONTROL_COMPLETION_KEY_B64", "adapter_signing_key", "private_key_pem"):
        assert not store.bind_provider_account_lease_challenge(
            account_scope=scope, run_id=first_run, owner="owner-a",
            plan_fingerprint=plan, core_plan_fingerprint="e" * 64,
            authorization_id="auth-test", lease_token=lease.lease_token,
            request_challenge={"env": {key_name: "test-placeholder"}}, now=100,
        )
    assert not store.bind_provider_account_lease_challenge(
        account_scope=scope, run_id=first_run, owner="owner-a",
        plan_fingerprint=plan, core_plan_fingerprint="e" * 64,
        authorization_id="auth-test", lease_token=lease.lease_token,
        request_challenge={"env": ({"private_key": "test-placeholder"},)}, now=100,
    )
    deeply_nested = {"level": None}
    cursor = deeply_nested
    for _ in range(70):
        cursor["level"] = {"level": None}
        cursor = cursor["level"]
    cursor["completion_key"] = "test-placeholder"
    assert not store.bind_provider_account_lease_challenge(
        account_scope=scope, run_id=first_run, owner="owner-a",
        plan_fingerprint=plan, core_plan_fingerprint="e" * 64,
        authorization_id="auth-test", lease_token=lease.lease_token,
        request_challenge=deeply_nested, now=100,
    )
    assert store.bind_provider_account_lease_challenge(
        account_scope=scope, run_id=first_run, owner="owner-a",
        plan_fingerprint=plan, core_plan_fingerprint="e" * 64,
        authorization_id="auth-test", lease_token=lease.lease_token,
        request_challenge={"template_id": "gpu-template", "name": "run-" + first_run}, now=100,
    )
    assert store.transition_provider_account_lease(
        account_scope=scope, run_id=first_run, owner="owner-a",
        plan_fingerprint=plan, core_plan_fingerprint="e" * 64, authorization_id="auth-test", lease_token=lease.lease_token,
        expected_state="reserved", new_state="submitting", now=100,
    )
    assert not store.bind_provider_account_lease_challenge(
        account_scope=scope, run_id=first_run, owner="owner-a",
        plan_fingerprint=plan, core_plan_fingerprint="e" * 64,
        authorization_id="auth-test", lease_token=lease.lease_token,
        request_challenge={"template_id": "replacement"}, now=100,
    )
    assert not store.transition_provider_account_lease(
        account_scope=scope, run_id=first_run, owner="owner-a",
        plan_fingerprint=plan, core_plan_fingerprint="e" * 64, authorization_id="auth-test", lease_token=retry_lease.lease_token,
        expected_state="reserved", new_state="submitting", now=100,
    )
    assert store.reserve_provider_account_lease(
        provider="runpod", account_scope=scope, run_id=second_run,
        owner="owner-b", plan_fingerprint="c" * 64, core_plan_fingerprint="e" * 64, authorization_id="auth-test", now=101,
    ) is None

    assert store.transition_provider_account_lease(
        account_scope=scope, run_id=first_run, owner="owner-a",
        plan_fingerprint=plan, core_plan_fingerprint="e" * 64, authorization_id="auth-test", lease_token=lease.lease_token,
        expected_state="submitting", new_state="uncertain", now=102,
    )
    assert store.transition_provider_account_lease(
        account_scope=scope, run_id=first_run, owner="owner-a",
        plan_fingerprint=plan, core_plan_fingerprint="e" * 64, authorization_id="auth-test", lease_token=lease.lease_token,
        expected_state="uncertain", new_state="active",
        provider_job_id="pod-1", now=103,
    )
    assert not store.release_provider_account_lease(
        account_scope=scope, run_id=first_run, owner="owner-a",
        plan_fingerprint=plan, core_plan_fingerprint="e" * 64, authorization_id="auth-test", lease_token=lease.lease_token,
        provider_job_id="pod-1", cleanup_confirmed=False, now=104,
    )
    assert store.transition_provider_account_lease(
        account_scope=scope, run_id=first_run, owner="owner-a",
        plan_fingerprint=plan, core_plan_fingerprint="e" * 64, authorization_id="auth-test", lease_token=lease.lease_token,
        expected_state="active", new_state="cleanup_pending", now=105,
    )
    assert not store.release_provider_account_lease(
        account_scope=scope, run_id=first_run, owner="owner-a",
        plan_fingerprint=plan, core_plan_fingerprint="e" * 64, authorization_id="auth-test", lease_token=lease.lease_token,
        provider_job_id="pod-2", cleanup_confirmed=True, now=106,
    )
    assert store.release_provider_account_lease(
        account_scope=scope, run_id=first_run, owner="owner-a",
        plan_fingerprint=plan, core_plan_fingerprint="e" * 64, authorization_id="auth-test", lease_token=lease.lease_token,
        provider_job_id="pod-1", cleanup_confirmed=True, now=107,
    )

    next_lease = store.reserve_provider_account_lease(
        provider="runpod", account_scope=scope, run_id=second_run,
        owner="owner-b", plan_fingerprint="c" * 64, core_plan_fingerprint="e" * 64, authorization_id="auth-test", now=108,
    )
    assert next_lease is not None
    assert next_lease.run_id == second_run
    assert next_lease.lease_token != lease.lease_token
    store.engine.dispose()


def test_provider_account_lease_transition_rejects_stale_identity_and_state(tmp_path):
    store = Store(f"sqlite:///{tmp_path / 'provider-account-lease-fencing.db'}")
    store.initialize()
    scope = "d" * 64
    run_id = uuid4().hex
    lease = store.reserve_provider_account_lease(
        provider="runpod", account_scope=scope, run_id=run_id,
        owner="owner-a", plan_fingerprint="e" * 64, core_plan_fingerprint="e" * 64, authorization_id="auth-test", now=100,
    )
    assert lease is not None
    assert lease.state == "reserved"

    assert not store.transition_provider_account_lease(
        account_scope=scope, run_id=run_id, owner="owner-a",
        plan_fingerprint="f" * 64, core_plan_fingerprint="e" * 64, authorization_id="auth-test", lease_token=lease.lease_token,
        expected_state="submitting", new_state="active", now=101,
    )
    assert not store.transition_provider_account_lease(
        account_scope=scope, run_id=run_id, owner="owner-a",
        plan_fingerprint="e" * 64, core_plan_fingerprint="e" * 64, authorization_id="auth-test", lease_token="0" * 64,
        expected_state="submitting", new_state="active", now=101,
    )
    assert not store.transition_provider_account_lease(
        account_scope=scope, run_id=run_id, owner="owner-a",
        plan_fingerprint="e" * 64, core_plan_fingerprint="e" * 64, authorization_id="auth-test", lease_token=lease.lease_token,
        expected_state="active", new_state="cleanup_pending", now=101,
    )
    store.engine.dispose()


def test_provider_account_lease_schema_migrates_additively(tmp_path):
    store = Store(f"sqlite:///{tmp_path / 'provider-account-lease-migration.db'}")
    store.initialize()

    status = migration_status(store.engine)

    assert SCHEMA_VERSION == 13
    assert status["current_version"] == SCHEMA_VERSION
    assert status["migration_required"] is False
    with store.engine.connect() as connection:
        assert connection.exec_driver_sql(
            "SELECT count(*) FROM gateway_provider_account_leases_v1"
        ).scalar_one() == 0
        assert {column["name"] for column in __import__("sqlalchemy").inspect(connection).get_columns(
            "gateway_provider_account_leases_v1"
        )} >= {"core_plan_fingerprint", "authorization_id", "request_challenge",
              "request_challenge_sha256"}
    store.engine.dispose()


def test_provider_account_lease_v10_upgrades_without_losing_held_lease(tmp_path):
    from sqlalchemy import create_engine
    from gpu_gateway.migrations import migrate

    engine = create_engine(f"sqlite:///{tmp_path / 'provider-account-v10.db'}")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE gateway_schema_version (id INTEGER PRIMARY KEY, version INTEGER NOT NULL)"
        )
        connection.exec_driver_sql("INSERT INTO gateway_schema_version VALUES (1, 10)")
        connection.exec_driver_sql("""
            CREATE TABLE gateway_provider_account_leases_v1 (
                account_scope VARCHAR(64) PRIMARY KEY, provider VARCHAR(32) NOT NULL,
                run_id VARCHAR(40) NOT NULL UNIQUE, owner VARCHAR(128) NOT NULL,
                plan_fingerprint VARCHAR(64) NOT NULL, state VARCHAR(24) NOT NULL,
                lease_token VARCHAR(64) NOT NULL, provider_job_id VARCHAR(512),
                updated_at INTEGER NOT NULL
            )
        """)
        connection.exec_driver_sql("""
            INSERT INTO gateway_provider_account_leases_v1
            VALUES ('aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
                    'runpod', 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb', 'owner-a',
                    'cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc',
                    'uncertain', 'dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd',
                    NULL, 123)
        """)

    assert migrate(engine) == SCHEMA_VERSION
    with engine.connect() as connection:
        row = connection.exec_driver_sql(
            "SELECT state, run_id, updated_at, core_plan_fingerprint, authorization_id "
            "FROM gateway_provider_account_leases_v1"
        ).one()
        assert tuple(row) == ("uncertain", "b" * 32, 123, None, None)
    engine.dispose()


def test_provider_account_lease_serializes_independent_store_instances(tmp_path):
    database = tmp_path / "provider-account-lease-shared.db"
    stores = [Store(f"sqlite:///{database}") for _ in range(2)]
    for store in stores:
        store.initialize()
    scope = "f" * 64

    def reserve(index):
        return stores[index].reserve_provider_account_lease(
            provider="runpod", account_scope=scope, run_id=uuid4().hex,
            owner=f"owner-{index}", plan_fingerprint=str(index) * 64, core_plan_fingerprint="e" * 64, authorization_id="auth-test", now=200 + index,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(reserve, (0, 1)))

    assert sum(result is not None for result in results) == 1
    for store in stores:
        store.engine.dispose()


def test_provider_account_lease_rejects_mismatched_identity_after_insert_conflict(tmp_path):
    store = Store(f"sqlite:///{tmp_path / 'provider-account-lease-conflict.db'}")
    store.initialize()
    scope = "9" * 64
    run_id = uuid4().hex
    # Simulate another transaction winning the unique account-scope insert
    # after this reservation's initial empty read. PostgreSQL can reach this
    # naturally; the SQLite trigger makes the conflict path deterministic.
    with store.engine.begin() as connection:
        connection.exec_driver_sql(f"""
            CREATE TRIGGER competing_provider_lease
            BEFORE INSERT ON gateway_provider_account_leases_v1
            WHEN NEW.account_scope = '{scope}'
            BEGIN
                INSERT INTO gateway_provider_account_leases_v1
                (account_scope, provider, run_id, owner, plan_fingerprint, state,
                 lease_token, provider_job_id, updated_at)
                VALUES ('{scope}', 'runpod', '{run_id}', 'owner-a', '{'a' * 64}',
                        'submitting', '{'1' * 64}', NULL, 100);
                SELECT RAISE(IGNORE);
            END;
        """)

    lease = store.reserve_provider_account_lease(
        provider="runpod", account_scope=scope, run_id=run_id,
        owner="owner-a", plan_fingerprint="b" * 64, core_plan_fingerprint="e" * 64, authorization_id="auth-test", now=101,
    )

    assert lease is None
    store.engine.dispose()


def _queued_for_worker(store, *, run_id, owner, plan_fingerprint, run_lease_token):
    with store.transaction() as connection:
        connection.execute(runs.insert().values(
            id=run_id, owner=owner, idempotency_key="idem-" + run_id,
            request_hash="1" * 64, fingerprint=plan_fingerprint, plan={"schema_version": 2},
            state="submitting", created_at=100, started_at=100, approved_until=500,
            approval_id="approval-" + run_id, lease_until=220, lease_token=run_lease_token,
            attempt=0, submission_intent=None, handle=None,
        ))


def test_provider_account_reservation_and_submission_intent_commit_together(tmp_path):
    store = Store(f"sqlite:///{tmp_path / 'provider-account-intent-atomic.db'}")
    store.initialize()
    run_id, run_token = uuid4().hex, uuid4().hex
    fingerprint = "a" * 64
    challenge = {"name": "gpu-control-" + run_id, "template_id": "template-a"}
    _queued_for_worker(store, run_id=run_id, owner="owner-a", plan_fingerprint=fingerprint,
                       run_lease_token=run_token)

    lease = store.reserve_provider_account_lease_with_submission_intent(
        provider="runpod", account_scope="b" * 64, run_id=run_id, owner="owner-a",
        plan_fingerprint=fingerprint, core_plan_fingerprint="c" * 64,
        authorization_id="paid-auth-1", run_lease_token=run_token, attempt=1,
        request_challenge=challenge, now=110,
    )

    assert lease is not None and lease.state == "reserved"
    assert lease.request_challenge == challenge
    job = store.read(run_id)
    assert job["attempt"] == 1
    assert job["submission_intent"] == {
        "provider": "runpod", "owner": "owner-a", "run_id": run_id,
        "attempt": 1, "plan_fingerprint": fingerprint,
        "account_scope": "b" * 64, "core_plan_fingerprint": "c" * 64,
            "authorization_id": "paid-auth-1",
            "provider_challenge_sha256": store._provider_challenge_digest(challenge),
            "phase": "dispatching", "created_at": 110,
    }
    store.engine.dispose()


def test_non_runpod_submission_intent_is_rejected_after_cancel(tmp_path):
    store = Store(f"sqlite:///{tmp_path / 'cancel-before-submit.db'}")
    store.initialize()
    run_id, run_token = uuid4().hex, uuid4().hex
    fingerprint = "a" * 64
    _queued_for_worker(store, run_id=run_id, owner="owner-a", plan_fingerprint=fingerprint,
                       run_lease_token=run_token)
    with store.transaction() as connection:
        connection.execute(runs.update().where(runs.c.id == run_id).values(cancel_requested=True))

    intent = {"provider": "demo", "owner": "owner-a", "run_id": run_id,
              "attempt": 1, "plan_fingerprint": fingerprint,
              "phase": "dispatching", "created_at": 110}
    binding = dict(run_id=run_id, owner="owner-a", plan_fingerprint=fingerprint,
                   run_lease_token=run_token, attempt=1)
    assert not store.begin_submission(**binding, intent=intent | {"attempt": True})
    assert not store.begin_submission(**binding, intent=intent | {"provider": "demo;other"})
    assert not store.begin_submission(**binding, intent=intent | {"created_at": True})
    assert not store.begin_submission(
        **binding, intent=intent,
    )
    job = store.read(run_id)
    assert job["attempt"] == 0
    assert job["submission_intent"] is None
    store.engine.dispose()


def test_runpod_reservation_is_rejected_after_cancel(tmp_path):
    store = Store(f"sqlite:///{tmp_path / 'runpod-cancel-before-submit.db'}")
    store.initialize()
    run_id, run_token = uuid4().hex, uuid4().hex
    fingerprint = "a" * 64
    _queued_for_worker(store, run_id=run_id, owner="owner-a", plan_fingerprint=fingerprint,
                       run_lease_token=run_token)
    with store.transaction() as connection:
        connection.execute(runs.update().where(runs.c.id == run_id).values(cancel_requested=True))

    assert store.reserve_provider_account_lease_with_submission_intent(
        provider="runpod", account_scope="b" * 64, run_id=run_id, owner="owner-a",
        plan_fingerprint=fingerprint, core_plan_fingerprint="c" * 64,
        authorization_id="paid-auth-1", run_lease_token=run_token, attempt=1,
        request_challenge={"name": "gpu-control-" + run_id, "template_id": "template-a"}, now=110,
    ) is None
    assert store.read(run_id)["submission_intent"] is None
    store.engine.dispose()


def test_runpod_reserved_lease_is_released_if_cancel_wins_before_dispatch(tmp_path):
    store = Store(f"sqlite:///{tmp_path / 'runpod-cancel-after-reserve.db'}")
    store.initialize()
    run_id, run_token = uuid4().hex, uuid4().hex
    fingerprint = "a" * 64
    scope, core_fingerprint = "b" * 64, "c" * 64
    challenge = {"name": "gpu-control-" + run_id, "template_id": "template-a"}
    _queued_for_worker(store, run_id=run_id, owner="owner-a", plan_fingerprint=fingerprint,
                       run_lease_token=run_token)
    lease = store.reserve_provider_account_lease_with_submission_intent(
        provider="runpod", account_scope=scope, run_id=run_id, owner="owner-a",
        plan_fingerprint=fingerprint, core_plan_fingerprint=core_fingerprint,
        authorization_id="paid-auth-1", run_lease_token=run_token, attempt=1,
        request_challenge=challenge, now=110,
    )
    assert lease is not None
    with store.transaction() as connection:
        connection.execute(runs.update().where(runs.c.id == run_id).values(cancel_requested=True))

    transition = dict(
        account_scope=scope, run_id=run_id, owner="owner-a",
        plan_fingerprint=fingerprint, lease_token=lease.lease_token,
        run_lease_token=run_token, core_plan_fingerprint=core_fingerprint,
        authorization_id="paid-auth-1", expected_state="reserved",
    )
    assert not store.transition_provider_account_lease_for_run(
        **transition, new_state="submitting", now=120,
    )
    assert store.transition_provider_account_lease_for_run(
        **transition, new_state="released", now=120,
    )
    current_lease = store.read_provider_account_lease_for_run(
        run_id=run_id, owner="owner-a", plan_fingerprint=fingerprint,
        run_lease_token=run_token, now=121,
    )
    assert current_lease is None
    store.engine.dispose()


def test_provider_account_lease_recovery_read_is_bound_to_current_worker_claim(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'provider-account-lease-reload.db'}"
    store = Store(database_url)
    recovery_store = Store(database_url)
    store.initialize()
    run_id, first_worker_token = uuid4().hex, uuid4().hex
    fingerprint = "a" * 64
    challenge = {"name": "gpu-control-" + run_id, "template_id": "template-a"}
    _queued_for_worker(store, run_id=run_id, owner="owner-a", plan_fingerprint=fingerprint,
                       run_lease_token=first_worker_token)
    lease = store.reserve_provider_account_lease_with_submission_intent(
        provider="runpod", account_scope="b" * 64, run_id=run_id, owner="owner-a",
        plan_fingerprint=fingerprint, core_plan_fingerprint="c" * 64,
        authorization_id="paid-auth-1", run_lease_token=first_worker_token,
        attempt=1, request_challenge=challenge, now=110,
    )
    assert lease is not None

    loaded = recovery_store.read_provider_account_lease_for_run(
        run_id=run_id, owner="owner-a", plan_fingerprint=fingerprint,
        run_lease_token=first_worker_token, now=120,
    )
    assert loaded == lease
    assert loaded.request_challenge == challenge
    assert recovery_store.read_provider_account_lease_for_run(
        run_id=run_id, owner="other-owner", plan_fingerprint=fingerprint,
        run_lease_token=first_worker_token, now=120,
    ) is None
    assert recovery_store.read_provider_account_lease_for_run(
        run_id=run_id, owner="owner-a", plan_fingerprint="d" * 64,
        run_lease_token=first_worker_token, now=120,
    ) is None
    assert recovery_store.read_provider_account_lease_for_run(
        run_id=run_id, owner="owner-a", plan_fingerprint=fingerprint,
        run_lease_token=first_worker_token, now=220,
    ) is None

    successor_token = uuid4().hex
    with store.transaction() as connection:
        connection.execute(runs.update().where(runs.c.id == run_id).values(
            lease_token=successor_token, lease_until=320,
        ))
    assert recovery_store.read_provider_account_lease_for_run(
        run_id=run_id, owner="owner-a", plan_fingerprint=fingerprint,
        run_lease_token=first_worker_token, now=230,
    ) is None
    recovered = recovery_store.read_provider_account_lease_for_run(
        run_id=run_id, owner="owner-a", plan_fingerprint=fingerprint,
        run_lease_token=successor_token, now=230,
    )
    assert recovered == lease
    with store.transaction() as connection:
        row = connection.execute(select(runs.c.submission_intent).where(
            runs.c.id == run_id)).scalar_one()
        connection.execute(runs.update().where(runs.c.id == run_id).values(
            submission_intent=row | {"provider_challenge_sha256": "0" * 64},
        ))
    assert recovery_store.read_provider_account_lease_for_run(
        run_id=run_id, owner="owner-a", plan_fingerprint=fingerprint,
        run_lease_token=successor_token, now=230,
    ) is None
    recovery_store.engine.dispose()
    store.engine.dispose()


def test_provider_account_intent_conflict_rolls_back_both_records(tmp_path):
    store = Store(f"sqlite:///{tmp_path / 'provider-account-intent-conflict.db'}")
    store.initialize()
    scope = "d" * 64
    winner_id, winner_token = uuid4().hex, uuid4().hex
    loser_id, loser_token = uuid4().hex, uuid4().hex
    challenge = {"name": "same-account"}
    _queued_for_worker(store, run_id=winner_id, owner="winner", plan_fingerprint="e" * 64,
                       run_lease_token=winner_token)
    _queued_for_worker(store, run_id=loser_id, owner="loser", plan_fingerprint="f" * 64,
                       run_lease_token=loser_token)
    winner = store.reserve_provider_account_lease_with_submission_intent(
        provider="runpod", account_scope=scope, run_id=winner_id, owner="winner",
        plan_fingerprint="e" * 64, core_plan_fingerprint="1" * 64,
        authorization_id="paid-winner", run_lease_token=winner_token, attempt=1,
        request_challenge=challenge, now=110,
    )
    assert winner is not None

    loser = store.reserve_provider_account_lease_with_submission_intent(
        provider="runpod", account_scope=scope, run_id=loser_id, owner="loser",
        plan_fingerprint="f" * 64, core_plan_fingerprint="2" * 64,
        authorization_id="paid-loser", run_lease_token=loser_token, attempt=1,
        request_challenge=challenge, now=111,
    )

    assert loser is None
    assert store.read(loser_id)["submission_intent"] is None
    assert store.read(loser_id)["attempt"] == 0
    store.engine.dispose()


def test_provider_account_intent_rejects_stale_worker_token_without_lease(tmp_path):
    store = Store(f"sqlite:///{tmp_path / 'provider-account-intent-stale.db'}")
    store.initialize()
    run_id, run_token = uuid4().hex, uuid4().hex
    fingerprint = "a" * 64
    _queued_for_worker(store, run_id=run_id, owner="owner-a", plan_fingerprint=fingerprint,
                       run_lease_token=run_token)

    lease = store.reserve_provider_account_lease_with_submission_intent(
        provider="runpod", account_scope="b" * 64, run_id=run_id, owner="owner-a",
        plan_fingerprint=fingerprint, core_plan_fingerprint="c" * 64,
        authorization_id="paid-auth-1", run_lease_token=uuid4().hex, attempt=1,
        request_challenge={"name": "run"}, now=110,
    )

    assert lease is None
    assert store.read(run_id)["submission_intent"] is None
    with store.engine.connect() as connection:
        assert connection.exec_driver_sql(
            "SELECT count(*) FROM gateway_provider_account_leases_v1"
        ).scalar_one() == 0
    store.engine.dispose()


def test_provider_account_intent_competition_has_one_commit_across_store_instances(tmp_path):
    database = tmp_path / "provider-account-intent-race.db"
    stores = [Store(f"sqlite:///{database}") for _ in range(2)]
    for store in stores:
        store.initialize()
    candidates = [(uuid4().hex, uuid4().hex), (uuid4().hex, uuid4().hex)]
    for index, (run_id, token) in enumerate(candidates):
        _queued_for_worker(stores[index], run_id=run_id, owner=f"owner-{index}",
                           plan_fingerprint=str(index + 1) * 64, run_lease_token=token)
    barrier = Barrier(2)

    def reserve(index):
        run_id, token = candidates[index]
        barrier.wait(timeout=5)
        return stores[index].reserve_provider_account_lease_with_submission_intent(
            provider="runpod", account_scope="9" * 64, run_id=run_id,
            owner=f"owner-{index}", plan_fingerprint=str(index + 1) * 64,
            core_plan_fingerprint="a" * 64, authorization_id=f"auth-{index}",
            run_lease_token=token, attempt=1,
            request_challenge={"name": f"run-{run_id}"}, now=200 + index,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        leases = list(pool.map(reserve, (0, 1)))

    assert sum(lease is not None for lease in leases) == 1
    committed_runs = [store.read(run_id) for store, (run_id, _) in zip(stores, candidates)]
    assert sum(run["submission_intent"] is not None for run in committed_runs) == 1
    assert sum(run["attempt"] == 1 for run in committed_runs) == 1
    for store in stores:
        store.engine.dispose()


def test_provider_lease_transition_requires_current_worker_claim(tmp_path):
    store = Store(f"sqlite:///{tmp_path / 'provider-account-lease-worker-fence.db'}")
    store.initialize()
    run_id, first_token = uuid4().hex, uuid4().hex
    fingerprint = "a" * 64
    scope = "b" * 64
    challenge = {"template_id": "template-a", "name": "gpu-control-" + run_id}
    _queued_for_worker(store, run_id=run_id, owner="owner-a", plan_fingerprint=fingerprint,
                       run_lease_token=first_token)
    lease = store.reserve_provider_account_lease_with_submission_intent(
        provider="runpod", account_scope=scope, run_id=run_id, owner="owner-a",
        plan_fingerprint=fingerprint, core_plan_fingerprint="c" * 64,
        authorization_id="paid-auth-1", run_lease_token=first_token,
        attempt=1, request_challenge=challenge, now=110,
    )
    assert lease is not None

    assert store.transition_provider_account_lease_for_run(
        account_scope=scope, run_id=run_id, owner="owner-a", plan_fingerprint=fingerprint,
        lease_token=lease.lease_token, run_lease_token=first_token,
        core_plan_fingerprint="c" * 64, authorization_id="paid-auth-1",
        expected_state="reserved", new_state="submitting", now=120,
    )

    successor_token = uuid4().hex
    with store.transaction() as connection:
        connection.execute(runs.update().where(runs.c.id == run_id).values(
            lease_token=successor_token, lease_until=300,
        ))
    assert not store.transition_provider_account_lease_for_run(
        account_scope=scope, run_id=run_id, owner="owner-a", plan_fingerprint=fingerprint,
        lease_token=lease.lease_token, run_lease_token=first_token,
        core_plan_fingerprint="c" * 64, authorization_id="paid-auth-1",
        expected_state="submitting", new_state="active", provider_job_id="pod-stale", now=130,
    )
    assert store.transition_provider_account_lease_for_run(
        account_scope=scope, run_id=run_id, owner="owner-a", plan_fingerprint=fingerprint,
        lease_token=lease.lease_token, run_lease_token=successor_token,
        core_plan_fingerprint="c" * 64, authorization_id="paid-auth-1",
        expected_state="submitting", new_state="uncertain", now=130,
    )
    loaded = store.read_provider_account_lease_for_run(
        run_id=run_id, owner="owner-a", plan_fingerprint=fingerprint,
        run_lease_token=successor_token, now=130,
    )
    assert loaded is not None and loaded.state == "uncertain"
    assert store.transition_provider_account_lease_for_run(
        account_scope=scope, run_id=run_id, owner="owner-a", plan_fingerprint=fingerprint,
        lease_token=lease.lease_token, run_lease_token=successor_token,
        core_plan_fingerprint="c" * 64, authorization_id="paid-auth-1",
        expected_state="uncertain", new_state="active", provider_job_id="pod-reconciled", now=140,
    )
    active = store.read_provider_account_lease_for_run(
        run_id=run_id, owner="owner-a", plan_fingerprint=fingerprint,
        run_lease_token=successor_token, now=140,
    )
    assert active is not None and active.state == "active"
    assert active.provider_job_id == "pod-reconciled"
    store.engine.dispose()


def test_provider_cleanup_release_and_terminal_run_commit_atomically(tmp_path):
    store = Store(f"sqlite:///{tmp_path / 'provider-account-cleanup-atomic.db'}")
    store.initialize()
    run_id, run_token = uuid4().hex, uuid4().hex
    scope, fingerprint = "b" * 64, "a" * 64
    challenge = {"template_id": "template-a", "name": "gpu-control-" + run_id}
    _queued_for_worker(store, run_id=run_id, owner="owner-a", plan_fingerprint=fingerprint,
                       run_lease_token=run_token)
    lease = store.reserve_provider_account_lease_with_submission_intent(
        provider="runpod", account_scope=scope, run_id=run_id, owner="owner-a",
        plan_fingerprint=fingerprint, core_plan_fingerprint="c" * 64,
        authorization_id="paid-auth-1", run_lease_token=run_token,
        attempt=1, request_challenge=challenge, now=110,
    )
    assert lease is not None
    assert store.transition_provider_account_lease_for_run(
        account_scope=scope, run_id=run_id, owner="owner-a", plan_fingerprint=fingerprint,
        lease_token=lease.lease_token, run_lease_token=run_token,
        core_plan_fingerprint="c" * 64, authorization_id="paid-auth-1",
        expected_state="reserved", new_state="submitting", now=115,
    )
    assert store.transition_provider_account_lease_for_run(
        account_scope=scope, run_id=run_id, owner="owner-a", plan_fingerprint=fingerprint,
        lease_token=lease.lease_token, run_lease_token=run_token,
        core_plan_fingerprint="c" * 64, authorization_id="paid-auth-1",
        expected_state="submitting", new_state="active", provider_job_id="pod-1", now=120,
    )
    with store.transaction() as connection:
        intent = store.read(run_id)["submission_intent"] | {"phase": "handle_persisted"}
        connection.execute(runs.update().where(runs.c.id == run_id).values(
            state="running", handle={"pod_id": "pod-1"}, submission_intent=intent,
            slot_reserved=True, cleanup_state="pending",
            result={"schema_version": 2, "cleanup_state": "pending", "checks": []},
        ))
        connection.execute(control.update().where(control.c.id == 1).values(active_count=1))
    assert store.transition_provider_account_lease_for_run(
        account_scope=scope, run_id=run_id, owner="owner-a", plan_fingerprint=fingerprint,
        lease_token=lease.lease_token, run_lease_token=run_token,
        core_plan_fingerprint="c" * 64, authorization_id="paid-auth-1",
        expected_state="active", new_state="cleanup_pending", now=125,
    )
    result = {"schema_version": 2, "cleanup_state": "complete", "checks": []}

    assert not store.finish_run_after_provider_cleanup(
        account_scope=scope, run_id=run_id, owner="owner-a", plan_fingerprint=fingerprint,
        lease_token=lease.lease_token, run_lease_token=run_token,
        core_plan_fingerprint="c" * 64, authorization_id="paid-auth-1",
        provider_job_id="pod-wrong", cleanup_confirmed=True,
        state="succeeded", result=result, error="", record_version=2, now=130,
    )
    assert not store.finish_run_after_provider_cleanup(
        account_scope=scope, run_id=run_id, owner="owner-a", plan_fingerprint=fingerprint,
        lease_token=lease.lease_token, run_lease_token=run_token,
        core_plan_fingerprint="c" * 64, authorization_id="paid-auth-1",
        provider_job_id="pod-1", cleanup_confirmed=False,
        state="succeeded", result=result, error="", record_version=2, now=130,
    )
    assert store.finish_run_after_provider_cleanup(
        account_scope=scope, run_id=run_id, owner="owner-a", plan_fingerprint=fingerprint,
        lease_token=lease.lease_token, run_lease_token=run_token,
        core_plan_fingerprint="c" * 64, authorization_id="paid-auth-1",
        provider_job_id="pod-1", cleanup_confirmed=True,
        state="succeeded", result=result, error="", record_version=2, now=130,
    )
    saved = store.read(run_id)
    assert saved["state"] == "succeeded"
    assert saved["cleanup_state"] == "complete"
    assert saved["slot_reserved"] is False
    assert saved["result"]["cleanup_state"] == "complete"
    with store.engine.connect() as connection:
        lease_state = connection.execute(select(provider_account_leases.c.state)).scalar_one()
        active_count = connection.execute(select(control.c.active_count)).scalar_one()
    assert lease_state == "released"
    assert active_count == 0
    store.engine.dispose()

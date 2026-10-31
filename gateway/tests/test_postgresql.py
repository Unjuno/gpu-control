"""Run against the dedicated ephemeral PostgreSQL service in gateway CI."""
import os
import threading
import hashlib
import time
from multiprocessing import get_context
from queue import Empty
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect, select, text, update
from sqlalchemy.engine import make_url

from gpu_gateway.config import Settings, Workload
from gpu_gateway.service import ExperimentService, GatewayError, Prepare, Principal
from gpu_gateway.store import Store, control, runs
from gpu_gateway.migrations import SCHEMA_VERSION, migrate, migration_status, schema_version
from gpu_gateway.worker import Worker
from gpu_gateway.backends import DemoBackend
from gpu_gateway.local_oauth import LocalOAuth, oauth_clients, oauth_tokens

from test_migrations import _legacy_v1


def _reserve_provider_account_intent_process(url, barrier, result_queue, *, index,
                                             account_scope, run_id, owner,
                                             plan_fingerprint, core_plan_fingerprint,
                                             authorization_id, run_lease_token):
    """Compete through separate processes/connections against shared PostgreSQL."""
    store = Store(url)
    try:
        barrier.wait(timeout=20)
        lease = store.reserve_provider_account_lease_with_submission_intent(
            provider="runpod", account_scope=account_scope, run_id=run_id,
            owner=owner, plan_fingerprint=plan_fingerprint,
            core_plan_fingerprint=core_plan_fingerprint,
            authorization_id=authorization_id,
            run_lease_token=run_lease_token, attempt=1,
            request_challenge={"name": "gpu-control-" + run_id,
                               "template_id": "template-test"},
            now=2_000_000_000 + index,
        )
        reloaded = store.read_provider_account_lease_for_run(
            run_id=run_id, owner=owner, plan_fingerprint=plan_fingerprint,
            run_lease_token=run_lease_token, now=2_000_000_000 + index,
        )
        result_queue.put((index, lease is not None, reloaded is not None,
                          bool(lease and reloaded and lease.lease_token == reloaded.lease_token)))
    except BaseException as error:
        result_queue.put((index, False, type(error).__name__))
        raise
    finally:
        store.engine.dispose()


def test_postgres_parallel_admission_and_cross_process_state():
    url = os.environ.get('GATEWAY_TEST_DATABASE_URL')
    if not url:
        pytest.skip('requires a dedicated PostgreSQL test database')
    settings = Settings(database_url=url)
    store = Store(url); store.initialize()
    scopes = frozenset({'experiments:read','experiments:run','experiments:cancel'})
    owner = Principal(uuid4().hex, scopes, browser=True)
    service = ExperimentService(store, settings, {'demo':Workload(provider='demo')})
    request = Prepare(workload='demo', idempotency_key='postgres-test')
    with ThreadPoolExecutor(max_workers=8) as pool:
        jobs = list(pool.map(lambda _: service.prepare(owner, request), range(20)))
    assert len({job['id'] for job in jobs}) == 1
    job = jobs[0]; service.approve(owner, job['id'], job['fingerprint'])
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda _: service.submit(owner, job['id']), range(20)))
    with store.engine.connect() as c:
        assert c.execute(select(control.c.active_count)).scalar_one() == 1
    # A second engine represents a different process/cold Vercel instance.
    other = Store(url)
    assert other.read(job['id'])['state'] == 'queued'
    service.cancel(owner, job['id'])
    with other.engine.connect() as c:
        assert c.execute(select(control.c.active_count)).scalar_one() == 0
    other.engine.dispose(); store.engine.dispose()


def test_postgres_worker_lease_has_one_current_owner():
    url = os.environ.get('GATEWAY_TEST_DATABASE_URL')
    if not url:
        pytest.skip('requires a dedicated PostgreSQL test database')
    settings = Settings(database_url=url)
    store = Store(url); store.initialize()
    scopes = frozenset({'experiments:read', 'experiments:run', 'experiments:cancel'})
    owner = Principal(uuid4().hex, scopes, browser=True)
    service = ExperimentService(store, settings, {'demo': Workload(provider='demo')})
    prepared = service.prepare(owner, Prepare(workload='demo', idempotency_key='lease-' + uuid4().hex))
    service.approve(owner, prepared['id'], prepared['fingerprint'])
    service.submit(owner, prepared['id'])

    workers = [Worker(Store(url), settings, {'demo': DemoBackend()}) for _ in range(8)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        claims = list(pool.map(lambda worker: worker.claim(), workers))
    first_claims = [claim for claim in claims if claim is not None]
    assert len(first_claims) == 1
    stale = first_claims[0]

    # Simulate expiry while the previous process is paused after claiming.
    with store.transaction() as connection:
        connection.execute(update(runs).where(runs.c.id == prepared['id']).values(lease_until=0))
    replacement = workers[1].claim()
    assert replacement is not None
    assert replacement['lease_token'] != stale['lease_token']
    assert workers[0].update(stale, state='failed', result={'stale': True}) is False
    workers[0].finish(stale, 'failed', {'stale': True})
    saved = store.read(prepared['id'])
    assert saved['lease_token'] == replacement['lease_token']
    assert saved['result'] is None
    assert saved['state'] == 'submit_unknown'

    # The PostgreSQL service is shared by all tests in this module/run.
    # Release this synthetic in-flight reservation so test order cannot affect
    # later admission checks.
    with store.transaction() as connection:
        connection.execute(update(runs).where(runs.c.id == prepared['id']).values(
            state='cancelled', cancel_requested=True, slot_reserved=False, lease_until=0))
        connection.execute(update(control).where(control.c.id == 1).values(
            active_count=control.c.active_count - 1))

    for worker in workers:
        worker.store.engine.dispose()
    store.engine.dispose()


def test_postgres_provider_account_lease_and_run_intent_are_process_atomic():
    """Two worker processes must not split or duplicate one account reservation."""
    url = os.environ.get('GATEWAY_TEST_DATABASE_URL')
    if not url:
        pytest.skip('requires a dedicated PostgreSQL test database')

    store = Store(url)
    store.initialize()
    account_scope = uuid4().hex + uuid4().hex
    candidates = [(uuid4().hex, uuid4().hex) for _ in range(2)]
    fingerprints = [uuid4().hex + uuid4().hex for _ in candidates]
    owners = ["lease-process-" + uuid4().hex for _ in candidates]
    try:
        with store.transaction() as connection:
            for index, ((run_id, run_token), fingerprint, owner) in enumerate(
                    zip(candidates, fingerprints, owners)):
                connection.execute(runs.insert().values(
                    id=run_id, owner=owner, idempotency_key="lease-" + uuid4().hex,
                    request_hash="1" * 64, fingerprint=fingerprint,
                    plan={"schema_version": 2}, state="submitting", created_at=1,
                    started_at=1, approved_until=2_100_000_000,
                    approval_id="approval-" + uuid4().hex, lease_until=2_000_000_120,
                    lease_token=run_token, attempt=0, submission_intent=None,
                ))

        context = get_context("spawn")
        barrier = context.Barrier(2)
        result_queue = context.Queue()
        processes = []
        for index, ((run_id, run_token), fingerprint, owner) in enumerate(
                zip(candidates, fingerprints, owners)):
            process = context.Process(
                target=_reserve_provider_account_intent_process,
                kwargs={
                    "url": url, "barrier": barrier, "result_queue": result_queue,
                    "index": index, "account_scope": account_scope,
                    "run_id": run_id, "owner": owner,
                    "plan_fingerprint": fingerprint,
                    "core_plan_fingerprint": "c" * 64,
                    "authorization_id": "auth-" + str(index),
                    "run_lease_token": run_token,
                },
            )
            processes.append(process)
            process.start()

        results = []
        for _ in processes:
            try:
                results.append(result_queue.get(timeout=30))
            except Empty:
                break
        for process in processes:
            process.join(timeout=30)
        assert all(not process.is_alive() for process in processes)
        assert all(process.exitcode == 0 for process in processes)
        assert len(results) == 2 and all(len(result) == 4 for result in results)
        assert sum(won for _, won, _, _ in results) == 1
        assert all(reloaded == won and same_lease == won
                   for _, won, reloaded, same_lease in results)

        persisted = [store.read(run_id) for run_id, _ in candidates]
        assert sum(run["submission_intent"] is not None for run in persisted) == 1
        assert sum(run["attempt"] == 1 for run in persisted) == 1
        with store.engine.connect() as connection:
            lease = connection.execute(text(
                "SELECT run_id, state FROM gateway_provider_account_leases_v1 "
                "WHERE account_scope = :scope"
            ), {"scope": account_scope}).one()
        winner_id = next(run["id"] for run in persisted if run["submission_intent"] is not None)
        assert lease.run_id == winner_id and lease.state == "reserved"
    finally:
        with store.engine.begin() as connection:
            connection.execute(text(
                "DELETE FROM gateway_provider_account_leases_v1 WHERE account_scope = :scope"
            ), {"scope": account_scope})
            for run_id, _ in candidates:
                connection.execute(runs.delete().where(runs.c.id == run_id))
        store.engine.dispose()


def test_postgres_v4_to_current_additive_recovery_oauth_and_provider_evidence():
    url = os.environ.get('GATEWAY_TEST_DATABASE_URL')
    if not url:
        pytest.skip('requires a dedicated PostgreSQL test database')
    store = Store(url)
    store.initialize()
    worker_seen = int(time.time())
    with store.engine.begin() as connection:
        connection.execute(update(control).where(control.c.id == 1).values(worker_seen_at=worker_seen))
        connection.exec_driver_sql('ALTER TABLE gateway_control_v1 DROP COLUMN supervisor_seen_at')
        connection.exec_driver_sql('ALTER TABLE gateway_runs_v1 DROP COLUMN last_observed_at')
        connection.exec_driver_sql('ALTER TABLE gateway_oauth_tokens_v1 DROP COLUMN grant_id')
        connection.exec_driver_sql('DROP TABLE gateway_provider_observations_v1')
        connection.execute(update(schema_version).where(schema_version.c.id == 1).values(version=4))

    assert migrate(store.engine) == SCHEMA_VERSION
    with store.engine.connect() as connection:
        assert connection.execute(select(schema_version.c.version)).scalar_one() == SCHEMA_VERSION
        row = connection.execute(select(control.c.worker_seen_at, control.c.supervisor_seen_at)
                                 .where(control.c.id == 1)).one()
    assert row == (worker_seen, 0)
    with store.engine.connect() as connection:
        assert "last_observed_at" in {column["name"] for column in
                                       inspect(connection).get_columns("gateway_runs_v1")}
        assert "grant_id" in {column["name"] for column in
                              inspect(connection).get_columns("gateway_oauth_tokens_v1")}
        assert {column["name"] for column in
                inspect(connection).get_columns("gateway_provider_observations_v1")} == {
                    "provider", "version", "observed_at", "expires_at", "envelope", "envelope_sha256",
                }
    store.engine.dispose()


def test_postgres_v1_to_current_preserves_legacy_run_and_oauth_rows():
    """Exercise the complete production upgrade path from unversioned v1."""
    url = os.environ.get('GATEWAY_TEST_DATABASE_URL')
    if not url:
        pytest.skip('requires a dedicated PostgreSQL test database')

    admin = create_engine(url)
    schema = f"migration_{uuid4().hex}"
    with admin.begin() as connection:
        connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')

    scoped_url = make_url(url).set(query={
        **make_url(url).query,
        'options': f'-csearch_path={schema}',
    })
    engine = create_engine(scoped_url)
    try:
        _legacy_v1(engine)

        status = migration_status(engine)
        assert status["supported"] is True
        assert status["current_version"] == 1
        assert status["target_version"] == SCHEMA_VERSION
        assert status["migration_required"] is True
        assert status["planned_versions"] == list(range(2, SCHEMA_VERSION + 1))
        with engine.connect() as connection:
            assert "gateway_schema_version" not in inspect(connection).get_table_names()
            assert connection.execute(text(
                'SELECT token_hash FROM gateway_oauth_tokens_v1'
            )).scalar_one() == 'secret-hash'

        assert migrate(engine) == SCHEMA_VERSION
        assert migrate(engine) == SCHEMA_VERSION
        # Preserve the password when constructing the store's second engine.
        store = Store(scoped_url.render_as_string(hide_password=False))
        store.initialize()

        row = store.read('0123456789abcdef0123456789abcdef')
        assert row['owner'] == 'owner-a'
        assert row['idempotency_key'] == 'stable-key'
        assert row['fingerprint'] == 'plan-fingerprint'
        assert row['plan'] == {'schema_version': 1}
        assert row['handle'] == {'id': 'provider-id'}
        assert row['result'] == {'simulation': True}
        assert row['state'] == 'succeeded'
        assert row['cleanup_state'] == 'unknown'
        with engine.connect() as connection:
            assert connection.execute(text(
                'SELECT token_hash FROM gateway_oauth_tokens_v1'
            )).scalar_one() == 'secret-hash'
            assert connection.execute(select(schema_version.c.version)).scalar_one() == SCHEMA_VERSION
            assert 'grant_id' in {column['name'] for column in
                                  inspect(connection).get_columns('gateway_oauth_tokens_v1')}
            assert {column['name'] for column in
                    inspect(connection).get_columns('gateway_provider_observations_v1')} == {
                        'provider', 'version', 'observed_at', 'expires_at', 'envelope',
                        'envelope_sha256',
                    }
        store.engine.dispose()
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.exec_driver_sql(f'DROP SCHEMA "{schema}" CASCADE')
        admin.dispose()


def test_postgres_v8_oauth_client_migration_preserves_used_dcr_clients():
    url = os.environ.get('GATEWAY_TEST_DATABASE_URL')
    if not url:
        pytest.skip('requires a dedicated PostgreSQL test database')

    admin = create_engine(url)
    schema = f"oauth_migration_{uuid4().hex}"
    with admin.begin() as connection:
        connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
    scoped_url = make_url(url).set(query={
        **make_url(url).query,
        'options': f'-csearch_path={schema}',
    })
    store = Store(scoped_url.render_as_string(hide_password=False))
    try:
        store.initialize()
        client_id = "mcp_existing_postgres_client"
        with store.engine.begin() as connection:
            connection.execute(oauth_clients.insert().values(
                client_id=client_id,
                redirect_uris=["https://chatgpt.com/connector_platform_oauth_redirect"],
                client_name="Existing ChatGPT connection", created_at=1,
                expires_at=100, persistent=False,
            ))
            connection.execute(oauth_tokens.insert().values(
                token_hash="a" * 64, kind="refresh", client_id=client_id,
                subject="owner", scope="experiments:read offline_access",
                resource="https://gateway.example/mcp", expires_at=50,
                created_at=1, revoked=True, grant_id="b" * 64,
            ))
            connection.exec_driver_sql(
                'ALTER TABLE "gateway_oauth_clients_v1" DROP COLUMN "persistent"')
            connection.execute(schema_version.update().values(version=8))

        assert migrate(store.engine) == SCHEMA_VERSION
        with store.engine.connect() as connection:
            assert connection.execute(select(oauth_clients.c.persistent).where(
                oauth_clients.c.client_id == client_id
            )).scalar_one() is True
    finally:
        store.engine.dispose()
        with admin.begin() as connection:
            connection.exec_driver_sql(f'DROP SCHEMA "{schema}" CASCADE')
        admin.dispose()


def test_postgres_refresh_rotation_and_grant_revocation_race():
    url = os.environ.get('GATEWAY_TEST_DATABASE_URL')
    if not url:
        pytest.skip('requires a dedicated PostgreSQL test database')
    settings = Settings(database_url=url, public_url='https://gateway.example')
    store = Store(url)
    store.initialize()
    oauth = LocalOAuth(settings, store)
    client_id = oauth.register_client({
        'client_name': 'ChatGPT race ' + uuid4().hex,
        'redirect_uris': ['https://chatgpt.com/connector_platform_oauth_redirect'],
    })['client_id']
    initial = oauth._new_token_pair(
        client_id=client_id, subject='owner',
        scope='experiments:read offline_access', resource=settings.resource,
    )
    pair_entered = threading.Event()
    allow_pair_to_finish = threading.Event()
    errors = []
    refreshed = []
    original_new_pair = oauth._new_token_pair

    def pause_replacement_pair(**kwargs):
        pair_entered.set()
        if not allow_pair_to_finish.wait(timeout=10):
            raise TimeoutError('test did not release replacement token pair')
        return original_new_pair(**kwargs)

    oauth._new_token_pair = pause_replacement_pair

    def refresh():
        try:
            refreshed.append(oauth.token({
                'grant_type': 'refresh_token', 'client_id': client_id,
                'refresh_token': initial['refresh_token'], 'resource': settings.resource,
            }))
        except Exception as exc:
            errors.append(exc)

    def revoke():
        try:
            oauth.revoke({'client_id': client_id, 'token': initial['refresh_token']})
        except Exception as exc:
            errors.append(exc)

    refresh_thread = threading.Thread(target=refresh, name='postgres-oauth-refresh')
    refresh_thread.start()
    assert pair_entered.wait(timeout=10)
    revoke_started = threading.Event()

    def revoke_with_signal():
        revoke_started.set()
        revoke()

    revoke_thread = threading.Thread(target=revoke_with_signal, name='postgres-oauth-revoke')
    revoke_thread.start()
    assert revoke_started.wait(timeout=5)
    # Let the revoke query reach the row lock while the refresh transaction is
    # paused after consuming the old token but before writing replacement rows.
    time.sleep(0.1)
    allow_pair_to_finish.set()
    refresh_thread.join(timeout=10)
    revoke_thread.join(timeout=10)
    assert not refresh_thread.is_alive() and not revoke_thread.is_alive()
    assert not errors
    assert len(refreshed) == 1

    token_hashes = [hashlib.sha256(value.encode()).hexdigest() for value in (
        initial['refresh_token'], refreshed[0]['access_token'], refreshed[0]['refresh_token'],
    )]
    with store.engine.connect() as connection:
        revoked = connection.execute(select(oauth_tokens.c.revoked).where(
            oauth_tokens.c.token_hash.in_(token_hashes)
        )).scalars().all()
    assert len(revoked) == 3 and all(revoked)
    store.engine.dispose()


def test_postgres_refresh_token_can_only_be_consumed_once_concurrently():
    url = os.environ.get('GATEWAY_TEST_DATABASE_URL')
    if not url:
        pytest.skip('requires a dedicated PostgreSQL test database')
    settings = Settings(database_url=url)
    store = Store(url); store.initialize()
    oauth = LocalOAuth(settings, store)
    registered = oauth.register_client({
        'client_name': 'refresh-race-' + uuid4().hex,
        'redirect_uris': ['https://chatgpt.com/connector_platform_oauth_redirect'],
    })
    client_id = registered['client_id']
    original = oauth._new_token_pair(
        client_id=client_id, subject='owner',
        scope='experiments:read offline_access', resource=settings.resource,
    )
    barrier = threading.Barrier(2)

    def refresh_once():
        barrier.wait(timeout=10)
        try:
            return ('success', oauth.token({
                'grant_type': 'refresh_token', 'client_id': client_id,
                'refresh_token': original['refresh_token'], 'resource': settings.resource,
            }))
        except GatewayError as error:
            return ('error', error.code)

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(lambda _: refresh_once(), range(2)))
        successes = [value for status, value in outcomes if status == 'success']
        errors = [value for status, value in outcomes if status == 'error']
        assert len(successes) == 1
        assert errors == ['invalid_grant']
        with store.engine.connect() as connection:
            rows = connection.execute(select(oauth_tokens.c.kind, oauth_tokens.c.revoked).where(
                oauth_tokens.c.client_id == client_id
            )).all()
        assert sorted((kind, revoked) for kind, revoked in rows) == [
            ('access', False), ('access', False), ('refresh', False), ('refresh', True),
        ]
    finally:
        store.engine.dispose()


def test_postgres_refresh_rotation_rolls_back_if_replacement_insert_fails(monkeypatch):
    url = os.environ.get('GATEWAY_TEST_DATABASE_URL')
    if not url:
        pytest.skip('requires a dedicated PostgreSQL test database')
    settings = Settings(database_url=url)
    store = Store(url); store.initialize()
    oauth = LocalOAuth(settings, store)
    registered = oauth.register_client({
        'client_name': 'refresh-rollback-' + uuid4().hex,
        'redirect_uris': ['https://chatgpt.com/connector_platform_oauth_redirect'],
    })
    client_id = registered['client_id']
    original = oauth._new_token_pair(
        client_id=client_id, subject='owner',
        scope='experiments:read offline_access', resource=settings.resource,
    )
    real_insert = oauth._insert_token

    def fail_replacement_refresh(connection, raw, **kwargs):
        if kwargs['kind'] == 'refresh':
            raise RuntimeError('injected PostgreSQL refresh insert failure')
        return real_insert(connection, raw, **kwargs)

    monkeypatch.setattr(oauth, '_insert_token', fail_replacement_refresh)
    try:
        with pytest.raises(RuntimeError, match='injected PostgreSQL refresh insert failure'):
            oauth.token({
                'grant_type': 'refresh_token', 'client_id': client_id,
                'refresh_token': original['refresh_token'], 'resource': settings.resource,
            })

        with store.engine.connect() as connection:
            rows = connection.execute(select(oauth_tokens.c.kind, oauth_tokens.c.revoked).where(
                oauth_tokens.c.client_id == client_id
            )).all()
        assert sorted((kind, revoked) for kind, revoked in rows) == [
            ('access', False), ('refresh', False),
        ]

        monkeypatch.setattr(oauth, '_insert_token', real_insert)
        rotated = oauth.token({
            'grant_type': 'refresh_token', 'client_id': client_id,
            'refresh_token': original['refresh_token'], 'resource': settings.resource,
        })
        assert rotated['refresh_token'] != original['refresh_token']
    finally:
        store.engine.dispose()


def test_postgres_v4_to_current_additive_recovery_oauth_and_provider_evidence():
    url = os.environ.get('GATEWAY_TEST_DATABASE_URL')
    if not url:
        pytest.skip('requires a dedicated PostgreSQL test database')
    store = Store(url)
    store.initialize()
    worker_seen = int(time.time())
    with store.engine.begin() as connection:
        connection.execute(update(control).where(control.c.id == 1).values(worker_seen_at=worker_seen))
        connection.exec_driver_sql('ALTER TABLE gateway_control_v1 DROP COLUMN supervisor_seen_at')
        connection.exec_driver_sql('ALTER TABLE gateway_runs_v1 DROP COLUMN last_observed_at')
        connection.exec_driver_sql('ALTER TABLE gateway_oauth_tokens_v1 DROP COLUMN grant_id')
        connection.exec_driver_sql('DROP TABLE gateway_provider_observations_v1')
        connection.execute(update(schema_version).where(schema_version.c.id == 1).values(version=4))

    assert migrate(store.engine) == SCHEMA_VERSION
    with store.engine.connect() as connection:
        assert connection.execute(select(schema_version.c.version)).scalar_one() == SCHEMA_VERSION
        row = connection.execute(select(control.c.worker_seen_at, control.c.supervisor_seen_at)
                                 .where(control.c.id == 1)).one()
    assert row == (worker_seen, 0)
    with store.engine.connect() as connection:
        assert "last_observed_at" in {column["name"] for column in
                                       inspect(connection).get_columns("gateway_runs_v1")}
        assert "grant_id" in {column["name"] for column in
                              inspect(connection).get_columns("gateway_oauth_tokens_v1")}
        assert {column["name"] for column in
                inspect(connection).get_columns("gateway_provider_observations_v1")} == {
                    "provider", "version", "observed_at", "expires_at", "envelope", "envelope_sha256",
                }
    store.engine.dispose()


def test_postgres_v1_to_current_preserves_legacy_run_and_oauth_rows():
    """Exercise the complete production upgrade path from unversioned v1."""
    url = os.environ.get('GATEWAY_TEST_DATABASE_URL')
    if not url:
        pytest.skip('requires a dedicated PostgreSQL test database')

    admin = create_engine(url)
    schema = f"migration_{uuid4().hex}"
    with admin.begin() as connection:
        connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')

    scoped_url = make_url(url).set(query={
        **make_url(url).query,
        'options': f'-csearch_path={schema}',
    })
    engine = create_engine(scoped_url)
    try:
        _legacy_v1(engine)

        status = migration_status(engine)
        assert status["supported"] is True
        assert status["current_version"] == 1
        assert status["target_version"] == SCHEMA_VERSION
        assert status["migration_required"] is True
        assert status["planned_versions"] == list(range(2, SCHEMA_VERSION + 1))
        with engine.connect() as connection:
            assert "gateway_schema_version" not in inspect(connection).get_table_names()
            assert connection.execute(text(
                'SELECT token_hash FROM gateway_oauth_tokens_v1'
            )).scalar_one() == 'secret-hash'

        assert migrate(engine) == SCHEMA_VERSION
        assert migrate(engine) == SCHEMA_VERSION
        # Preserve the password when constructing the store's second engine.
        store = Store(scoped_url.render_as_string(hide_password=False))
        store.initialize()

        row = store.read('0123456789abcdef0123456789abcdef')
        assert row['owner'] == 'owner-a'
        assert row['idempotency_key'] == 'stable-key'
        assert row['fingerprint'] == 'plan-fingerprint'
        assert row['plan'] == {'schema_version': 1}
        assert row['handle'] == {'id': 'provider-id'}
        assert row['result'] == {'simulation': True}
        assert row['state'] == 'succeeded'
        assert row['cleanup_state'] == 'unknown'
        with engine.connect() as connection:
            assert connection.execute(text(
                'SELECT token_hash FROM gateway_oauth_tokens_v1'
            )).scalar_one() == 'secret-hash'
            assert connection.execute(select(schema_version.c.version)).scalar_one() == SCHEMA_VERSION
            assert 'grant_id' in {column['name'] for column in
                                  inspect(connection).get_columns('gateway_oauth_tokens_v1')}
            assert {column['name'] for column in
                    inspect(connection).get_columns('gateway_provider_observations_v1')} == {
                        'provider', 'version', 'observed_at', 'expires_at', 'envelope',
                        'envelope_sha256',
                    }
        store.engine.dispose()
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.exec_driver_sql(f'DROP SCHEMA "{schema}" CASCADE')
        admin.dispose()


def test_postgres_v8_oauth_client_migration_preserves_used_dcr_clients():
    url = os.environ.get('GATEWAY_TEST_DATABASE_URL')
    if not url:
        pytest.skip('requires a dedicated PostgreSQL test database')

    admin = create_engine(url)
    schema = f"oauth_migration_{uuid4().hex}"
    with admin.begin() as connection:
        connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
    scoped_url = make_url(url).set(query={
        **make_url(url).query,
        'options': f'-csearch_path={schema}',
    })
    store = Store(scoped_url.render_as_string(hide_password=False))
    try:
        store.initialize()
        client_id = "mcp_existing_postgres_client"
        with store.engine.begin() as connection:
            connection.execute(oauth_clients.insert().values(
                client_id=client_id,
                redirect_uris=["https://chatgpt.com/connector_platform_oauth_redirect"],
                client_name="Existing ChatGPT connection", created_at=1,
                expires_at=100, persistent=False,
            ))
            connection.execute(oauth_tokens.insert().values(
                token_hash="a" * 64, kind="refresh", client_id=client_id,
                subject="owner", scope="experiments:read offline_access",
                resource="https://gateway.example/mcp", expires_at=50,
                created_at=1, revoked=True, grant_id="b" * 64,
            ))
            connection.exec_driver_sql(
                'ALTER TABLE "gateway_oauth_clients_v1" DROP COLUMN "persistent"')
            connection.execute(schema_version.update().values(version=8))

        assert migrate(store.engine) == SCHEMA_VERSION
        with store.engine.connect() as connection:
            assert connection.execute(select(oauth_clients.c.persistent).where(
                oauth_clients.c.client_id == client_id
            )).scalar_one() is True
    finally:
        store.engine.dispose()
        with admin.begin() as connection:
            connection.exec_driver_sql(f'DROP SCHEMA "{schema}" CASCADE')
        admin.dispose()

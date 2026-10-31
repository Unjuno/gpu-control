"""Run against the dedicated ephemeral PostgreSQL service in gateway CI."""
import os
import time
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from sqlalchemy import select, update

from gpu_gateway.config import Settings, Workload
from gpu_gateway.service import ExperimentService, Prepare, Principal
from gpu_gateway.store import Store, control, runs
from gpu_gateway.worker import Worker
from gpu_gateway.backends import DemoBackend


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

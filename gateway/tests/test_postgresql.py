"""Run against the dedicated ephemeral PostgreSQL service in gateway CI."""
import os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from sqlalchemy import select

from gpu_gateway.config import Settings, Workload
from gpu_gateway.service import ExperimentService, Prepare, Principal
from gpu_gateway.store import Store, control
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

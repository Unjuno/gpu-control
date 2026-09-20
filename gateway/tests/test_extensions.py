from dataclasses import replace
from decimal import Decimal

import pytest
from sqlalchemy import select

from gpu_gateway.backends import DemoBackend
from gpu_gateway.config import Settings, Workload
from gpu_gateway.registry import ProviderRegistration, default_registry
from gpu_gateway.service import ExperimentService, Prepare
from gpu_gateway.store import control
from gpu_gateway.worker import Worker


def test_third_provider_needs_no_mcp_or_service_branch(system):
    registry = default_registry()
    registry['future_gpu'] = ProviderRegistration('future_gpu', 'test_only', lambda settings: True, lambda settings: DemoBackend())
    manifest = Workload(provider='future_gpu', quoted_usd_per_hour=Decimal('0.5'),
                        quote_reference='synthetic-test-only', quote_expires_at=system.clock() + 1000)
    service = ExperimentService(system.store, system.settings, {'future': manifest}, system.clock, registry=registry)
    job = service.prepare(system.owner, Prepare(workload='future', idempotency_key='future-test'))
    service.approve(system.browser, job['id'], job['fingerprint'])
    service.submit(system.owner, job['id'])
    worker = Worker(system.store, system.settings, {'future_gpu': DemoBackend()}, system.clock, registry=registry)
    worker.tick(); system.clock.advance(2); worker.tick()
    assert service.get(system.owner, job['id'])['state'] == 'succeeded'
    assert any(p['id'] == 'future_gpu' for p in service.integrations(system.owner)['providers'])


def test_list_is_bounded_summary_not_all_logs(system):
    job = system.service.prepare(system.owner, Prepare(workload='demo', idempotency_key='summary-test'))
    summary = system.service.list(system.owner)['experiments'][0]
    assert summary['id'] == job['id']
    assert 'result' not in summary and 'plan' not in summary


def test_external_schema_reference_rejected():
    with pytest.raises(ValueError):
        Workload(provider='demo', parameter_schema={'type':'object','additionalProperties':False,
                  'properties':{'x':{'$ref':'https://example.invalid/schema'}}})


@pytest.mark.parametrize('value', ['NaN', 'Infinity', '0', '-1'])
def test_invalid_operator_cost_limit(value):
    with pytest.raises(ValueError): Settings(max_job_cost_usd=Decimal(value)).validate()

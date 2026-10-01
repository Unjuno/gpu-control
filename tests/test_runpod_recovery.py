"""A restart must not require a new allocation permit to clean up an existing Pod."""
from dataclasses import replace
from datetime import timedelta

import pytest

from gpu_control.lifecycle import CleanupState, JobObservation, JobState, build_submission_receipt
from gpu_control.providers.runpod_v1_adapter import RunPodV1AdapterError
from test_runpod_v1_adapter import NOW, FakeV1Client, adapter, plan


def setup_recovery():  # type: ignore[no-untyped-def]
    value = plan()
    client = FakeV1Client(value)
    original = adapter(value, client, lambda: NOW)
    receipt = build_submission_receipt(value, provider_job_id='pod-123', submitted_at_utc=NOW)
    kwargs = dict(
        clock=lambda: NOW + timedelta(minutes=20),
        recovery_receipt=receipt,
        expected_recovery_receipt_fingerprint=receipt.fingerprint(),
    )
    return original, client, receipt, kwargs


def test_normal_reconstruction_still_rejects_expired_permit() -> None:
    original, client, receipt, kwargs = setup_recovery()
    with pytest.raises(RunPodV1AdapterError, match='expired'):
        replace(original, clock=kwargs['clock'])
    assert client.create_payloads == []


def test_recovery_observes_and_cleans_exact_pod_after_permit_and_price_expire() -> None:
    original, client, receipt, kwargs = setup_recovery()
    recovered = replace(original, **kwargs)
    assert recovered.observe(receipt).state is JobState.RUNNING
    terminal = JobObservation(
        provider=receipt.provider, provider_job_id=receipt.provider_job_id,
        plan_fingerprint=receipt.plan_fingerprint, state=JobState.TIMED_OUT,
        cleanup_state=CleanupState.NOT_STARTED,
        observed_at_utc=(NOW + timedelta(minutes=20)).isoformat(),
        status_reference='trusted-watchdog:deadline',
    )
    assert recovered.cleanup(receipt, terminal).cleanup_state is CleanupState.COMPLETED
    assert client.create_payloads == []


def test_recovery_mode_never_allows_submission_even_before_expiry() -> None:
    original, client, receipt, kwargs = setup_recovery()
    kwargs['clock'] = lambda: NOW + timedelta(seconds=1)
    recovered = replace(original, **kwargs)
    with pytest.raises(RunPodV1AdapterError, match='recovery-only'):
        recovered.submit(original.approved_plan)
    assert client.create_payloads == []
    assert len(client.list_responses) == 2  # No occupancy/network call either.


@pytest.mark.parametrize('change', ['missing-fingerprint', 'wrong-fingerprint', 'runtime', 'cost', 'future', 'plan'])
def test_recovery_rejects_untrusted_or_mismatched_receipts(change: str) -> None:
    original, client, receipt, kwargs = setup_recovery()
    if change == 'missing-fingerprint':
        kwargs['expected_recovery_receipt_fingerprint'] = None
    elif change == 'wrong-fingerprint':
        kwargs['expected_recovery_receipt_fingerprint'] = 'sha256:' + '0' * 64
    elif change == 'runtime':
        kwargs['recovery_receipt'] = replace(receipt, max_runtime_minutes=1)
    elif change == 'cost':
        kwargs['recovery_receipt'] = replace(receipt, max_cost_usd=receipt.max_cost_usd / 2)
    elif change == 'future':
        kwargs['clock'] = lambda: NOW - timedelta(seconds=1)
    elif change == 'plan':
        kwargs['recovery_receipt'] = replace(receipt, plan_fingerprint='sha256:' + '1' * 64)
    if change in {'runtime', 'cost', 'plan'}:
        kwargs['expected_recovery_receipt_fingerprint'] = kwargs['recovery_receipt'].fingerprint()
    with pytest.raises(RunPodV1AdapterError):
        replace(original, **kwargs)
    assert client.create_payloads == []


def test_recovery_cannot_observe_a_different_pod_with_same_plan() -> None:
    original, client, receipt, kwargs = setup_recovery()
    recovered = replace(original, **kwargs)
    with pytest.raises(RunPodV1AdapterError, match='exact recovery receipt'):
        recovered.observe(replace(receipt, provider_job_id='pod-other'))
    assert client.create_payloads == []


def test_reconciled_create_with_other_occupancy_is_compensated() -> None:
    from test_runpod_reconciliation import make_adapter
    value, launch, client, occupancy, inventory, runpod = make_adapter()
    occupancy.responses[1].append({'id': 'another-pod', 'status': 'RUNNING'})
    with pytest.raises(RunPodV1AdapterError, match='terminated'):
        runpod.submit(value)
    assert client.create_calls == 1
    assert client.terminate_calls == ['pod-123']


def test_inconsistent_reconciled_response_never_deletes_an_unrelated_pod() -> None:
    from test_runpod_reconciliation import make_adapter
    value, launch, client, occupancy, inventory, runpod = make_adapter()
    client.get_response['name'] = 'unrelated-execution'
    with pytest.raises(RunPodV1AdapterError, match='could not be reconciled'):
        runpod.submit(value)
    assert client.create_calls == 1
    assert client.terminate_calls == []

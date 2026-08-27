from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from gpu_control.execution import ApprovedExecutionPlan
from gpu_control.lifecycle import JobState
from gpu_control.providers.controller import cleanup_provider_job, observe_provider_job, submit_approved_plan
from gpu_control.providers.runpod_adapter import RunPodV2Adapter, RunPodV2AdapterError
from gpu_control.providers.runpod_occupancy import build_account_occupancy_evidence
from gpu_control.providers.runpod_pricing import RunPodCatalogPricingEvidence
from gpu_control.providers.runpod_v2 import (
    PublishedImageEvidence,
    RunPodV2Error,
    RunPodV2HttpError,
    RunPodV2TransportError,
    pod_name_for_plan,
)


DIGEST = "sha256:" + "a" * 64
SUBMITTED_AT = datetime(2026, 8, 22, 16, 1, tzinfo=timezone.utc)


def pricing() -> RunPodCatalogPricingEvidence:
    return RunPodCatalogPricingEvidence(
        gpu_profile="cheap-24gb",
        gpu_type_id="NVIDIA GeForce RTX 4090",
        cloud="SECURE",
        memory_gb=24,
        hourly_price_usd=Decimal("0.44"),
        availability="HIGH",
        verification_reference="runpod-v2-catalog:sha256:" + "c" * 64,
        verified_at_utc="2026-08-22T16:00:00Z",
        valid_until_utc="2026-08-22T16:03:00Z",
    )


def plan() -> ApprovedExecutionPlan:
    evidence = pricing()
    result = ApprovedExecutionPlan(
        provider="runpod",
        provider_resource_id=evidence.gpu_type_id,
        target_repo="example/model",
        target_sha="0123456789abcdef0123456789abcdef01234567",
        dockerfile_path="Dockerfile",
        image_digest=DIGEST,
        container_verification_reference="actions-run:100/container",
        gpu_profile=evidence.gpu_profile,
        gpu_count=1,
        max_runtime_minutes=15,
        max_cost_usd=Decimal("0.20"),
        verified_hourly_price_usd=evidence.hourly_price_usd,
        pricing_verification_reference=evidence.verification_reference,
        pricing_verified_at_utc=evidence.verified_at_utc,
        pricing_valid_until_utc=evidence.valid_until_utc,
        worst_case_cost_usd=Decimal("0.11"),
        authorization_reference="workflow_dispatch:100",
    )
    result.validate_shape()
    return result


def image(value: ApprovedExecutionPlan) -> PublishedImageEvidence:
    return PublishedImageEvidence(
        plan_fingerprint=value.fingerprint(),
        image_reference=f"ghcr.io/example/model@{DIGEST}",
        image_digest=DIGEST,
        verification_reference="registry-publish:100",
    )


def pod_payload(value: ApprovedExecutionPlan, *, status: str = "PROVISIONING", cost: float = 0.44):
    return {
        "id": "pod-123",
        "name": pod_name_for_plan(value),
        "image": image(value).image_reference,
        "gpu": {"id": value.provider_resource_id, "count": 1},
        "cloud": "SECURE",
        "cost": cost,
        "status": status,
    }


class FakeClient:
    def __init__(self, value: ApprovedExecutionPlan) -> None:
        self.value = value
        self.create_calls = 0
        self.get_calls = 0
        self.list_calls = 0
        self.terminate_calls: list[str] = []
        self.create_response = pod_payload(value)
        self.status_responses = [pod_payload(value, status="RUNNING")]
        self.list_responses: list[dict[str, object]] = []
        self.create_error: Exception | None = None
        self.terminate_error: Exception | None = None

    def create_pod(self, payload):  # type: ignore[no-untyped-def]
        self.create_calls += 1
        if self.create_error is not None:
            raise self.create_error
        return self.create_response

    def get_pod(self, pod_id):  # type: ignore[no-untyped-def]
        self.get_calls += 1
        response = self.status_responses.pop(0)
        assert response["id"] == pod_id
        return response

    def list_pods(self):  # type: ignore[no-untyped-def]
        self.list_calls += 1
        if not self.list_responses:
            raise AssertionError("unexpected List Pods call")
        return self.list_responses.pop(0)

    def terminate_pod(self, pod_id):  # type: ignore[no-untyped-def]
        self.terminate_calls.append(pod_id)
        if self.terminate_error is not None:
            raise self.terminate_error


class FakeOccupancyProbe:
    def __init__(self, value: ApprovedExecutionPlan) -> None:
        self.value = value
        self.calls = 0
        self.responses: list[list[dict[str, str]]] = [
            [],
            [{"id": "pod-123", "status": "PROVISIONING"}],
        ]

    def __call__(self, value: ApprovedExecutionPlan):
        assert value.fingerprint() == self.value.fingerprint()
        self.calls += 1
        pods = self.responses.pop(0)
        return build_account_occupancy_evidence(
            value,
            pods,
            checked_at_utc=SUBMITTED_AT,
            ttl_seconds=60,
        )


def adapter(value: ApprovedExecutionPlan | None = None) -> tuple[RunPodV2Adapter, FakeClient, FakeOccupancyProbe]:
    value = value or plan()
    client = FakeClient(value)
    occupancy = FakeOccupancyProbe(value)
    return (
        RunPodV2Adapter(
            client=client,  # type: ignore[arg-type]
            approved_plan=value,
            published_image=image(value),
            catalog_pricing=pricing(),
            occupancy_probe=occupancy,
            clock=lambda: SUBMITTED_AT + timedelta(seconds=1),
        ),
        client,
        occupancy,
    )


def test_adapter_crosses_existing_trusted_controller_and_cleans_up_failure() -> None:
    value = plan()
    runpod, client, occupancy = adapter(value)

    submitted = submit_approved_plan(
        runpod,
        value,
        expected_plan_fingerprint=value.fingerprint(),
        submitted_at_utc=SUBMITTED_AT,
    )
    assert submitted.receipt.provider_job_id == "pod-123"
    assert client.create_calls == 1
    assert occupancy.calls == 2

    running = observe_provider_job(
        runpod,
        submitted.receipt,
        observed_at_utc=datetime(2026, 8, 22, 16, 1, 10, tzinfo=timezone.utc),
        previous_observation=submitted.initial_observation,
    )
    assert running.state is JobState.RUNNING

    client.status_responses.append(pod_payload(value, status="ERROR"))
    failed = observe_provider_job(
        runpod,
        submitted.receipt,
        observed_at_utc=datetime(2026, 8, 22, 16, 1, 20, tzinfo=timezone.utc),
        previous_observation=running,
    )
    assert failed.state is JobState.FAILED

    finalized = cleanup_provider_job(
        runpod,
        submitted.receipt,
        failed,
        observed_at_utc=datetime(2026, 8, 22, 16, 1, 30, tzinfo=timezone.utc),
    )
    assert finalized.finalized is True
    assert client.terminate_calls == ["pod-123"]

    with pytest.raises(RunPodV2AdapterError, match="result collection is disabled"):
        runpod.collect_results(submitted.receipt, finalized)


def test_existing_non_terminated_pod_blocks_create_before_paid_allocation() -> None:
    value = plan()
    runpod, client, occupancy = adapter(value)
    occupancy.responses = [[{"id": "someone-else-pod", "status": "RUNNING"}]]

    with pytest.raises(RunPodV2AdapterError, match="account is busy"):
        runpod.submit(value)

    assert client.create_calls == 0
    assert occupancy.calls == 1


def test_competing_pod_appearing_during_create_terminates_new_pod() -> None:
    value = plan()
    runpod, client, occupancy = adapter(value)
    occupancy.responses = [
        [],
        [
            {"id": "pod-123", "status": "PROVISIONING"},
            {"id": "racing-pod", "status": "RUNNING"},
        ],
    ]

    with pytest.raises(RunPodV2AdapterError, match="was terminated"):
        runpod.submit(value)

    assert client.create_calls == 1
    assert client.terminate_calls == ["pod-123"]


def test_post_create_price_mismatch_triggers_immediate_compensating_termination() -> None:
    value = plan()
    runpod, client, _ = adapter(value)
    client.create_response = pod_payload(value, cost=0.45)

    with pytest.raises(RunPodV2AdapterError, match="was terminated"):
        runpod.submit(value)

    assert client.create_calls == 1
    assert client.terminate_calls == ["pod-123"]


def test_post_create_cloud_mismatch_triggers_compensating_termination() -> None:
    value = plan()
    runpod, client, _ = adapter(value)
    client.create_response = dict(pod_payload(value), cloud="COMMUNITY")

    with pytest.raises(RunPodV2AdapterError, match="was terminated"):
        runpod.submit(value)

    assert client.terminate_calls == ["pod-123"]


def test_compensating_termination_failure_is_visible() -> None:
    value = plan()
    runpod, client, _ = adapter(value)
    client.create_response = pod_payload(value, cost=0.45)
    client.terminate_error = RunPodV2Error("terminate failed")

    with pytest.raises(RunPodV2AdapterError, match="termination also failed"):
        runpod.submit(value)

    assert client.create_calls == 1
    assert client.terminate_calls == ["pod-123"]


def test_ambiguous_create_is_reconciled_without_second_post() -> None:
    value = plan()
    runpod, client, occupancy = adapter(value)
    client.create_error = RunPodV2TransportError("ambiguous")
    client.list_responses = [{"pods": [pod_payload(value)]}]

    submission = runpod.submit(value)

    assert submission.provider_job_id == "pod-123"
    assert occupancy.calls == 2
    assert client.create_calls == 1
    assert client.list_calls == 1
    assert client.terminate_calls == []


def test_ambiguous_create_with_no_unique_match_fails_closed_without_retry() -> None:
    value = plan()
    runpod, client, occupancy = adapter(value)
    client.create_error = RunPodV2TransportError("ambiguous")
    client.list_responses = [{"pods": []}]

    with pytest.raises(RunPodV2AdapterError, match="exactly one plan-named Pod"):
        runpod.submit(value)

    assert occupancy.calls == 1
    assert client.create_calls == 1
    assert client.list_calls == 1
    assert client.terminate_calls == []


def test_ambiguous_create_with_multiple_named_matches_fails_closed() -> None:
    value = plan()
    runpod, client, _ = adapter(value)
    client.create_error = RunPodV2TransportError("ambiguous")
    second = dict(pod_payload(value), id="pod-456")
    client.list_responses = [{"pods": [pod_payload(value), second]}]

    with pytest.raises(RunPodV2AdapterError, match="exactly one plan-named Pod"):
        runpod.submit(value)

    assert client.create_calls == 1
    assert client.list_calls == 1


def test_cleanup_404_requires_account_absence_reconciliation() -> None:
    value = plan()
    runpod, client, _ = adapter(value)
    submitted = submit_approved_plan(
        runpod,
        value,
        expected_plan_fingerprint=value.fingerprint(),
        submitted_at_utc=SUBMITTED_AT,
    )
    client.status_responses = [pod_payload(value, status="ERROR")]
    failed = observe_provider_job(
        runpod,
        submitted.receipt,
        observed_at_utc=SUBMITTED_AT + timedelta(seconds=10),
        previous_observation=submitted.initial_observation,
    )
    client.terminate_error = RunPodV2HttpError(404)
    client.list_responses = [{"pods": []}]

    finalized = cleanup_provider_job(
        runpod,
        submitted.receipt,
        failed,
        observed_at_utc=SUBMITTED_AT + timedelta(seconds=20),
    )

    assert finalized.finalized is True
    assert "already-absent-reconciled" in finalized.cleanup_reference
    assert client.list_calls == 1


def test_cleanup_404_is_not_success_when_pod_still_exists() -> None:
    value = plan()
    runpod, client, _ = adapter(value)
    submitted = submit_approved_plan(
        runpod,
        value,
        expected_plan_fingerprint=value.fingerprint(),
        submitted_at_utc=SUBMITTED_AT,
    )
    client.status_responses = [pod_payload(value, status="ERROR")]
    failed = observe_provider_job(
        runpod,
        submitted.receipt,
        observed_at_utc=SUBMITTED_AT + timedelta(seconds=10),
        previous_observation=submitted.initial_observation,
    )
    client.terminate_error = RunPodV2HttpError(404)
    client.list_responses = [{"pods": [pod_payload(value, status="ERROR")]}]

    with pytest.raises(RunPodV2AdapterError, match="still present"):
        cleanup_provider_job(
            runpod,
            submitted.receipt,
            failed,
            observed_at_utc=SUBMITTED_AT + timedelta(seconds=20),
        )


def test_different_plan_is_rejected_before_occupancy_or_create() -> None:
    value = plan()
    runpod, client, occupancy = adapter(value)
    changed = ApprovedExecutionPlan.from_dict(
        {**value.to_dict(), "authorization_reference": "workflow_dispatch:other"}
    )

    with pytest.raises(RunPodV2AdapterError, match="different approved plan"):
        runpod.submit(changed)

    assert occupancy.calls == 0
    assert client.create_calls == 0


def test_exited_status_remains_ambiguous_and_does_not_fake_success() -> None:
    value = plan()
    runpod, client, _ = adapter(value)
    submitted = submit_approved_plan(
        runpod,
        value,
        expected_plan_fingerprint=value.fingerprint(),
        submitted_at_utc=SUBMITTED_AT,
    )
    client.status_responses = [pod_payload(value, status="EXITED")]

    with pytest.raises(RunPodV2AdapterError, match="EXITED is ambiguous"):
        runpod.observe(submitted.receipt)

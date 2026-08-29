from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from gpu_control.completion import CompletionChallenge, execution_name_for
from gpu_control.execution import ApprovedExecutionPlan
from gpu_control.lifecycle import CleanupState, JobObservation, JobState, build_submission_receipt
from gpu_control.providers.controller import cleanup_provider_job, submit_approved_plan
from gpu_control.providers.runpod_adapter import RunPodV2Adapter, RunPodV2AdapterError
from gpu_control.providers.runpod_occupancy import build_account_occupancy_evidence
from gpu_control.providers.runpod_pricing import RunPodCatalogPricingEvidence
from gpu_control.providers.runpod_reconciliation import (
    RunPodPodInventoryEvidence,
    build_pod_inventory_evidence,
    cleanup_reconciled,
    reconcile_ambiguous_create,
)
from gpu_control.providers.runpod_v2 import PublishedImageEvidence, RunPodCompletionLaunch, RunPodV2Error


DIGEST = "sha256:" + "a" * 64
SECRET = bytes(range(32))
NOW = datetime(2026, 8, 28, 1, 0, tzinfo=timezone.utc)


def pricing() -> RunPodCatalogPricingEvidence:
    return RunPodCatalogPricingEvidence(
        gpu_profile="cheap-24gb",
        gpu_type_id="NVIDIA GeForce RTX 4090",
        cloud="SECURE",
        memory_gb=24,
        hourly_price_usd=Decimal("0.44"),
        availability="HIGH",
        verification_reference="runpod-v2-catalog:sha256:" + "c" * 64,
        verified_at_utc="2026-08-28T00:59:00Z",
        valid_until_utc="2026-08-28T01:04:00Z",
    )


def plan() -> ApprovedExecutionPlan:
    evidence = pricing()
    value = ApprovedExecutionPlan(
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
    value.validate_shape()
    return value


def image(value: ApprovedExecutionPlan) -> PublishedImageEvidence:
    return PublishedImageEvidence(
        plan_fingerprint=value.fingerprint(),
        image_reference=f"ghcr.io/example/model@{DIGEST}",
        image_digest=DIGEST,
        verification_reference="registry-publish:100",
    )


def completion(value: ApprovedExecutionPlan) -> RunPodCompletionLaunch:
    nonce = "b" * 64
    challenge = CompletionChallenge(
        key_id="paid-runpod-v2",
        nonce=nonce,
        plan_fingerprint=value.fingerprint(),
        execution_name=execution_name_for(value.fingerprint(), nonce),
        source_sha=value.target_sha,
        image_digest=value.image_digest,
    )
    return RunPodCompletionLaunch(challenge=challenge, secret_key=SECRET)


def pod_payload(
    value: ApprovedExecutionPlan,
    launch: RunPodCompletionLaunch,
    *,
    pod_id: str = "pod-123",
    status: str = "PROVISIONING",
    cost: float = 0.44,
):
    return {
        "id": pod_id,
        "name": launch.challenge.execution_name,
        "image": image(value).image_reference,
        "gpu": {"id": value.provider_resource_id, "count": 1},
        "cloud": "SECURE",
        "cost": cost,
        "status": status,
    }


def inventory(value: ApprovedExecutionPlan, pods: list[dict[str, object]]):  # type: ignore[no-untyped-def]
    return build_pod_inventory_evidence(
        value,
        {"pods": pods},
        checked_at_utc=NOW,
        ttl_seconds=60,
    )


def test_inventory_reconciliation_uses_exact_per_execution_name() -> None:
    value = plan()
    launch = completion(value)
    evidence = inventory(
        value,
        [
            {"id": "other", "name": "gpu-control-deadbeefdead-deadbeefdead", "status": "RUNNING"},
            {"id": "pod-123", "name": launch.challenge.execution_name, "status": "PROVISIONING"},
        ],
    )

    assert reconcile_ambiguous_create(evidence, value, launch.challenge, now_utc=NOW) == "pod-123"


def test_inventory_rejects_zero_multiple_and_terminated_create_matches() -> None:
    value = plan()
    launch = completion(value)

    with pytest.raises(RunPodV2Error, match="no exact"):
        reconcile_ambiguous_create(inventory(value, []), value, launch.challenge, now_utc=NOW)

    duplicate_name = [
        {"id": "pod-1", "name": launch.challenge.execution_name, "status": "RUNNING"},
        {"id": "pod-2", "name": launch.challenge.execution_name, "status": "RUNNING"},
    ]
    with pytest.raises(RunPodV2Error, match="multiple exact"):
        reconcile_ambiguous_create(inventory(value, duplicate_name), value, launch.challenge, now_utc=NOW)

    terminated = [{"id": "pod-1", "name": launch.challenge.execution_name, "status": "TERMINATED"}]
    with pytest.raises(RunPodV2Error, match="already terminated"):
        reconcile_ambiguous_create(inventory(value, terminated), value, launch.challenge, now_utc=NOW)


def test_inventory_is_bounded_and_rejects_duplicate_pod_ids() -> None:
    value = plan()
    many = [
        {"id": f"pod-{index}", "name": f"name-{index}", "status": "RUNNING"}
        for index in range(257)
    ]
    with pytest.raises(RunPodV2Error, match="bounded Pod count"):
        inventory(value, many)

    duplicates = [
        {"id": "pod-1", "name": "name-1", "status": "RUNNING"},
        {"id": "pod-1", "name": "name-2", "status": "RUNNING"},
    ]
    with pytest.raises(RunPodV2Error, match="duplicate Pod ids"):
        inventory(value, duplicates)


def test_reconstructed_inventory_revalidates_entry_shape_and_digest() -> None:
    value = plan()
    evidence = inventory(value, [{"id": "pod-1", "name": "name-1", "status": "RUNNING"}])

    tampered_entry = replace(evidence.pods[0], status="running")
    with pytest.raises(RunPodV2Error, match="canonical uppercase"):
        replace(evidence, pods=(tampered_entry,)).validate_against_plan(value, now_utc=NOW)

    with pytest.raises(RunPodV2Error, match="verification_reference"):
        replace(evidence, verification_reference="runpod-v2-pods:sha256:" + "f" * 64).validate_against_plan(
            value, now_utc=NOW
        )


def test_cleanup_reconciliation_requires_absent_or_terminated_exact_pod() -> None:
    value = plan()
    assert cleanup_reconciled(inventory(value, []), value, "pod-123", now_utc=NOW) is True
    terminated = [{"id": "pod-123", "name": "x", "status": "TERMINATED"}]
    assert cleanup_reconciled(inventory(value, terminated), value, "pod-123", now_utc=NOW) is True
    running = [{"id": "pod-123", "name": "x", "status": "RUNNING"}]
    assert cleanup_reconciled(inventory(value, running), value, "pod-123", now_utc=NOW) is False


class FakeClient:
    def __init__(self, value: ApprovedExecutionPlan, launch: RunPodCompletionLaunch) -> None:
        self.value = value
        self.launch = launch
        self.expected_create_name = launch.challenge.execution_name
        self.create_calls = 0
        self.get_calls = 0
        self.terminate_calls: list[str] = []
        self.create_error: Exception | None = RunPodV2Error("RunPod API could not be reached")
        self.get_response = pod_payload(value, launch)
        self.terminate_error: Exception | None = None

    def create_pod(self, payload):  # type: ignore[no-untyped-def]
        self.create_calls += 1
        assert payload["name"] == self.expected_create_name
        if self.create_error is not None:
            raise self.create_error
        return self.get_response

    def get_pod(self, pod_id):  # type: ignore[no-untyped-def]
        self.get_calls += 1
        assert pod_id == self.get_response["id"]
        return self.get_response

    def terminate_pod(self, pod_id):  # type: ignore[no-untyped-def]
        self.terminate_calls.append(pod_id)
        if self.terminate_error is not None:
            raise self.terminate_error


class OccupancyProbe:
    def __init__(self, value: ApprovedExecutionPlan) -> None:
        self.value = value
        self.responses: list[list[dict[str, str]]] = [
            [],
            [{"id": "pod-123", "status": "PROVISIONING"}],
        ]
        self.calls = 0

    def __call__(self, value: ApprovedExecutionPlan):  # type: ignore[no-untyped-def]
        assert value.fingerprint() == self.value.fingerprint()
        self.calls += 1
        return build_account_occupancy_evidence(
            value,
            self.responses.pop(0),
            checked_at_utc=NOW,
            ttl_seconds=60,
        )


class InventoryProbe:
    def __init__(self, value: ApprovedExecutionPlan, launch: RunPodCompletionLaunch) -> None:
        self.value = value
        self.launch = launch
        self.responses: list[list[dict[str, object]]] = [
            [{"id": "pod-123", "name": launch.challenge.execution_name, "status": "PROVISIONING"}]
        ]
        self.calls = 0

    def __call__(self, value: ApprovedExecutionPlan):  # type: ignore[no-untyped-def]
        assert value.fingerprint() == self.value.fingerprint()
        self.calls += 1
        return build_pod_inventory_evidence(
            value,
            {"pods": self.responses.pop(0)},
            checked_at_utc=NOW,
            ttl_seconds=60,
        )


def make_adapter(*, with_completion: bool = True):  # type: ignore[no-untyped-def]
    value = plan()
    launch = completion(value)
    client = FakeClient(value, launch)
    if not with_completion:
        client.expected_create_name = f"gpu-control-{value.fingerprint()[7:19]}"
    occupancy = OccupancyProbe(value)
    inventory_probe = InventoryProbe(value, launch)
    adapter = RunPodV2Adapter(
        client=client,  # type: ignore[arg-type]
        approved_plan=value,
        published_image=image(value),
        catalog_pricing=pricing(),
        occupancy_probe=occupancy,
        inventory_probe=inventory_probe,
        completion_launch=launch if with_completion else None,
        clock=lambda: NOW + timedelta(seconds=1),
    )
    return value, launch, client, occupancy, inventory_probe, adapter


def test_adapter_recovers_ambiguous_create_without_retrying_create() -> None:
    value, _, client, occupancy, inventory_probe, adapter = make_adapter()

    submitted = submit_approved_plan(
        adapter,
        value,
        expected_plan_fingerprint=value.fingerprint(),
        submitted_at_utc=NOW,
    )

    assert submitted.receipt.provider_job_id == "pod-123"
    assert client.create_calls == 1
    assert client.get_calls == 1
    assert inventory_probe.calls == 1
    assert occupancy.calls == 2


def test_adapter_does_not_reconcile_create_without_per_execution_identity() -> None:
    value, _, client, occupancy, inventory_probe, adapter = make_adapter(with_completion=False)

    with pytest.raises(RunPodV2Error, match="could not be reached"):
        adapter.submit(value)

    assert client.create_calls == 1
    assert client.get_calls == 0
    assert inventory_probe.calls == 0
    assert occupancy.calls == 1


def test_adapter_reconciliation_revalidates_full_pod_identity() -> None:
    value, _, client, _, _, adapter = make_adapter()
    client.get_response = dict(client.get_response, cost=0.45)

    with pytest.raises(RunPodV2AdapterError, match="could not be reconciled"):
        adapter.submit(value)

    assert client.create_calls == 1
    assert client.get_calls == 1


def terminal_observation(value: ApprovedExecutionPlan, pod_id: str = "pod-123") -> tuple[object, JobObservation]:
    receipt = build_submission_receipt(value, provider_job_id=pod_id, submitted_at_utc=NOW)
    terminal = JobObservation(
        provider="runpod",
        provider_job_id=pod_id,
        plan_fingerprint=receipt.plan_fingerprint,
        state=JobState.FAILED,
        cleanup_state=CleanupState.NOT_STARTED,
        observed_at_utc="2026-08-28T01:00:05Z",
        status_reference="runpod-v2:test:failed",
    )
    return receipt, terminal


def test_cleanup_recovers_ambiguous_terminate_when_pod_is_absent() -> None:
    value, _, client, _, inventory_probe, adapter = make_adapter()
    client.terminate_error = RunPodV2Error("RunPod API could not be reached")
    inventory_probe.responses = [[]]
    receipt, terminal = terminal_observation(value)

    final = cleanup_provider_job(
        adapter,
        receipt,  # type: ignore[arg-type]
        terminal,
        observed_at_utc=NOW + timedelta(seconds=10),
    )

    assert final.finalized is True
    assert final.cleanup_state is CleanupState.COMPLETED
    assert "reconciled-released" in final.status_reference
    assert client.terminate_calls == ["pod-123"]
    assert inventory_probe.calls == 1


def test_cleanup_does_not_fake_success_when_pod_remains_active() -> None:
    value, launch, client, _, inventory_probe, adapter = make_adapter()
    client.terminate_error = RunPodV2Error("RunPod API could not be reached")
    inventory_probe.responses = [
        [{"id": "pod-123", "name": launch.challenge.execution_name, "status": "RUNNING"}]
    ]
    receipt, terminal = terminal_observation(value)

    with pytest.raises(RunPodV2AdapterError, match="could not be proven released"):
        cleanup_provider_job(
            adapter,
            receipt,  # type: ignore[arg-type]
            terminal,
            observed_at_utc=NOW + timedelta(seconds=10),
        )

    assert client.terminate_calls == ["pod-123"]
    assert inventory_probe.calls == 1

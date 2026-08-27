from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
import json

import pytest

from gpu_control.execution import ApprovedExecutionPlan
from gpu_control.lifecycle import CleanupState, JobObservation, JobState, build_submission_receipt
from gpu_control.providers.base import ProviderCleanupSnapshot, ProviderResultSnapshot
from gpu_control.providers.controller import ProviderContractError, cleanup_provider_job
from gpu_control.providers.finalization import (
    ProviderResultCapture,
    capture_provider_results_before_cleanup,
    finalize_captured_provider_results,
    validate_result_capture_against_lifecycle,
)
from gpu_control.results import ArtifactDisposition, OutputArtifact, ResultContractError, load_result_policy


T0 = datetime(2026, 8, 28, 0, 0, tzinfo=timezone.utc)
TERMINAL_AT = datetime(2026, 8, 28, 0, 1, 0, tzinfo=timezone.utc)
CAPTURED_AT = datetime(2026, 8, 28, 0, 1, 2, tzinfo=timezone.utc)
CLEANED_AT = datetime(2026, 8, 28, 0, 1, 5, tzinfo=timezone.utc)
COMMITTED_AT = datetime(2026, 8, 28, 0, 1, 6, tzinfo=timezone.utc)


def plan() -> ApprovedExecutionPlan:
    value = ApprovedExecutionPlan(
        provider="runpod",
        provider_resource_id="synthetic-offer-3090",
        target_repo="example/model",
        target_sha="d" * 40,
        dockerfile_path="Dockerfile",
        image_digest="sha256:" + "a" * 64,
        container_verification_reference="container:1",
        gpu_profile="cheap-24gb",
        gpu_count=1,
        max_runtime_minutes=10,
        max_cost_usd=Decimal("0.10"),
        verified_hourly_price_usd=Decimal("0.30"),
        pricing_verification_reference="pricing:1",
        pricing_verified_at_utc="2026-08-27T23:59:00Z",
        pricing_valid_until_utc="2026-08-28T00:04:00Z",
        worst_case_cost_usd=Decimal("0.05"),
        authorization_reference="human:1",
    )
    value.validate_shape()
    return value


def receipt_and_terminal():  # type: ignore[no-untyped-def]
    value = plan()
    receipt = build_submission_receipt(value, provider_job_id="pod-1", submitted_at_utc=T0)
    terminal = JobObservation(
        provider="runpod",
        provider_job_id="pod-1",
        plan_fingerprint=receipt.plan_fingerprint,
        state=JobState.SUCCEEDED,
        cleanup_state=CleanupState.NOT_STARTED,
        observed_at_utc="2026-08-28T00:01:00Z",
        status_reference="runpod:authenticated-completion",
    )
    return receipt, terminal


def metric_artifact() -> OutputArtifact:
    return OutputArtifact(
        name="result.json",
        sha256="sha256:" + "b" * 64,
        size_bytes=4096,
        media_type="application/json",
        reference="provider:ephemeral-result",
        disposition=ArtifactDisposition.COLLECTED,
    )


def checkpoint_artifact() -> OutputArtifact:
    return OutputArtifact(
        name="checkpoints/canary-base.pt",
        sha256="sha256:" + "c" * 64,
        size_bytes=2 * 1024 * 1024 * 1024,
        media_type="application/x-pytorch-checkpoint",
        reference="provider:checkpoint",
        disposition=ArtifactDisposition.REFERENCE_ONLY,
    )


class EphemeralAdapter:
    provider_name = "runpod"

    def __init__(self) -> None:
        self.cleaned = False
        self.calls: list[str] = []
        self.result = ProviderResultSnapshot(
            provider_job_id="pod-1",
            log_bytes_retained=128,
            logs_truncated=True,
            artifacts=(metric_artifact(), checkpoint_artifact()),
        )

    def collect_results(self, receipt, lifecycle_observation):  # type: ignore[no-untyped-def]
        self.calls.append("collect")
        assert self.cleaned is False
        assert lifecycle_observation.terminal is True
        assert lifecycle_observation.cleanup_state is CleanupState.NOT_STARTED
        return self.result

    def cleanup(self, receipt, terminal_observation):  # type: ignore[no-untyped-def]
        self.calls.append("cleanup")
        self.cleaned = True
        return ProviderCleanupSnapshot(
            provider_job_id=receipt.provider_job_id,
            cleanup_state=CleanupState.COMPLETED,
            cleanup_reference="provider:cleanup",
        )

    def submit(self, plan):  # type: ignore[no-untyped-def]
        raise AssertionError("not used")

    def observe(self, receipt):  # type: ignore[no-untyped-def]
        raise AssertionError("not used")


def test_ephemeral_results_are_captured_before_cleanup_and_finalized_afterward() -> None:
    receipt, terminal = receipt_and_terminal()
    adapter = EphemeralAdapter()

    capture = capture_provider_results_before_cleanup(
        adapter,
        receipt,
        terminal,
        captured_at_utc=CAPTURED_AT,
    )
    assert adapter.calls == ["collect"]
    assert adapter.cleaned is False
    assert capture.captured_at_utc == "2026-08-28T00:01:02Z"
    assert capture.terminal_observation_fingerprint == terminal.fingerprint()

    final = cleanup_provider_job(
        adapter,
        receipt,
        terminal,
        observed_at_utc=CLEANED_AT,
    )
    assert adapter.calls == ["collect", "cleanup"]
    assert final.finalized is True

    finalized = finalize_captured_provider_results(
        capture,
        receipt,
        terminal,
        final,
        committed_at_utc=COMMITTED_AT,
    )

    assert finalized.capture == capture
    assert finalized.final_observation == final
    assert finalized.result_manifest.final_observation_fingerprint == final.fingerprint()
    assert finalized.result_manifest.artifacts == capture.artifacts
    assert finalized.result_manifest.log_bytes_retained == capture.log_bytes_retained
    assert finalized.result_manifest.logs_truncated is True
    assert finalized.result_manifest.collected_at_utc == "2026-08-28T00:01:06Z"


def test_capture_json_round_trip_is_canonical_and_fingerprint_stable() -> None:
    receipt, terminal = receipt_and_terminal()
    capture = capture_provider_results_before_cleanup(
        EphemeralAdapter(),
        receipt,
        terminal,
        captured_at_utc=CAPTURED_AT,
    )

    restored = ProviderResultCapture.from_json(capture.canonical_json())

    assert restored == capture
    assert restored.canonical_json() == capture.canonical_json()
    assert restored.fingerprint() == capture.fingerprint()


def test_capture_json_rejects_unknown_and_duplicate_fields() -> None:
    receipt, terminal = receipt_and_terminal()
    capture = capture_provider_results_before_cleanup(
        EphemeralAdapter(), receipt, terminal, captured_at_utc=CAPTURED_AT
    )
    payload = capture.to_dict()
    payload["unexpected"] = True
    with pytest.raises(ResultContractError, match="unknown fields"):
        ProviderResultCapture.from_json(json.dumps(payload))

    duplicate = capture.canonical_json().replace(
        '"provider":"runpod"',
        '"provider":"runpod","provider":"other"',
    )
    with pytest.raises(ResultContractError, match="duplicate field: provider"):
        ProviderResultCapture.from_json(duplicate)


def test_capture_requires_terminal_precleanup_state_before_adapter_call() -> None:
    receipt, terminal = receipt_and_terminal()
    adapter = EphemeralAdapter()
    running = replace(terminal, state=JobState.RUNNING)

    with pytest.raises(ProviderContractError, match="terminal"):
        capture_provider_results_before_cleanup(
            adapter, receipt, running, captured_at_utc=CAPTURED_AT
        )
    assert adapter.calls == []

    already_cleaned = replace(terminal, cleanup_state=CleanupState.COMPLETED)
    with pytest.raises(ProviderContractError, match="cleanup_state not_started"):
        capture_provider_results_before_cleanup(
            adapter, receipt, already_cleaned, captured_at_utc=CAPTURED_AT
        )
    assert adapter.calls == []


def test_capture_timestamp_cannot_predate_terminal_observation() -> None:
    receipt, terminal = receipt_and_terminal()
    adapter = EphemeralAdapter()

    with pytest.raises(ProviderContractError, match="cannot predate"):
        capture_provider_results_before_cleanup(
            adapter,
            receipt,
            terminal,
            captured_at_utc=datetime(2026, 8, 28, 0, 0, 59, tzinfo=timezone.utc),
        )
    assert adapter.calls == []


def test_capture_rejects_wrong_provider_job_identity() -> None:
    receipt, terminal = receipt_and_terminal()
    adapter = EphemeralAdapter()
    adapter.result = replace(adapter.result, provider_job_id="other-pod")

    with pytest.raises(ProviderContractError, match="result job id"):
        capture_provider_results_before_cleanup(
            adapter, receipt, terminal, captured_at_utc=CAPTURED_AT
        )


def test_capture_applies_result_policy_before_cleanup() -> None:
    receipt, terminal = receipt_and_terminal()
    adapter = EphemeralAdapter()
    policy = load_result_policy()
    adapter.result = replace(
        adapter.result,
        artifacts=(replace(metric_artifact(), size_bytes=policy.max_collected_file_bytes + 1),),
    )

    with pytest.raises(ResultContractError, match="per-file collection limit"):
        capture_provider_results_before_cleanup(
            adapter,
            receipt,
            terminal,
            captured_at_utc=CAPTURED_AT,
            policy=policy,
        )


def test_capture_lifecycle_binding_rejects_tampering() -> None:
    receipt, terminal = receipt_and_terminal()
    capture = capture_provider_results_before_cleanup(
        EphemeralAdapter(), receipt, terminal, captured_at_utc=CAPTURED_AT
    )

    with pytest.raises(ProviderContractError, match="plan_fingerprint"):
        validate_result_capture_against_lifecycle(
            replace(capture, plan_fingerprint="sha256:" + "f" * 64),
            receipt,
            terminal,
        )

    with pytest.raises(ProviderContractError, match="terminal_observation_fingerprint"):
        validate_result_capture_against_lifecycle(
            replace(capture, terminal_observation_fingerprint="sha256:" + "e" * 64),
            receipt,
            terminal,
        )


def test_finalization_requires_completed_cleanup_and_monotonic_times() -> None:
    receipt, terminal = receipt_and_terminal()
    capture = capture_provider_results_before_cleanup(
        EphemeralAdapter(), receipt, terminal, captured_at_utc=CAPTURED_AT
    )

    with pytest.raises(ProviderContractError, match="cleanup-finalized"):
        finalize_captured_provider_results(
            capture,
            receipt,
            terminal,
            terminal,
            committed_at_utc=COMMITTED_AT,
        )

    final_before_capture = replace(
        terminal,
        cleanup_state=CleanupState.COMPLETED,
        observed_at_utc="2026-08-28T00:01:01Z",
        status_reference="provider:cleanup",
    )
    with pytest.raises(ProviderContractError, match="cannot predate provider result capture"):
        finalize_captured_provider_results(
            capture,
            receipt,
            terminal,
            final_before_capture,
            committed_at_utc=COMMITTED_AT,
        )


def test_manifest_commit_timestamp_cannot_predate_final_observation() -> None:
    receipt, terminal = receipt_and_terminal()
    adapter = EphemeralAdapter()
    capture = capture_provider_results_before_cleanup(
        adapter, receipt, terminal, captured_at_utc=CAPTURED_AT
    )
    final = cleanup_provider_job(
        adapter, receipt, terminal, observed_at_utc=CLEANED_AT
    )

    with pytest.raises(ProviderContractError, match="commit cannot predate"):
        finalize_captured_provider_results(
            capture,
            receipt,
            terminal,
            final,
            committed_at_utc=datetime(2026, 8, 28, 0, 1, 4, tzinfo=timezone.utc),
        )

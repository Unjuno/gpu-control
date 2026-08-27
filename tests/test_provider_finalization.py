from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from gpu_control.execution import ApprovedExecutionPlan
from gpu_control.lifecycle import CleanupState, JobObservation, JobState, build_submission_receipt
from gpu_control.providers.base import ProviderCleanupSnapshot, ProviderResultSnapshot
from gpu_control.providers.finalization import collect_results_then_cleanup
from gpu_control.results import ArtifactDisposition, OutputArtifact


T0 = datetime(2026, 8, 28, 0, 0, tzinfo=timezone.utc)


def plan() -> ApprovedExecutionPlan:
    value = ApprovedExecutionPlan(
        provider="runpod",
        provider_resource_id="gpu",
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


class EphemeralAdapter:
    provider_name = "runpod"

    def __init__(self) -> None:
        self.cleaned = False
        self.calls: list[str] = []

    def collect_results(self, receipt, terminal_observation):  # type: ignore[no-untyped-def]
        self.calls.append("collect")
        assert self.cleaned is False
        return ProviderResultSnapshot(
            provider_job_id=receipt.provider_job_id,
            log_bytes_retained=128,
            logs_truncated=True,
            artifacts=(
                OutputArtifact(
                    name="result.json",
                    sha256="sha256:" + "b" * 64,
                    size_bytes=64,
                    media_type="application/json",
                    reference="provider:ephemeral-result",
                    disposition=ArtifactDisposition.COLLECTED,
                ),
            ),
        )

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


def test_ephemeral_results_are_captured_before_cleanup_but_manifest_binds_final_state() -> None:
    value = plan()
    receipt = build_submission_receipt(value, provider_job_id="pod-1", submitted_at_utc=T0)
    terminal = JobObservation(
        provider="runpod",
        provider_job_id="pod-1",
        plan_fingerprint=receipt.plan_fingerprint,
        state=JobState.SUCCEEDED,
        cleanup_state=CleanupState.NOT_STARTED,
        observed_at_utc="2026-08-28T00:00:10Z",
        status_reference="runpod:authenticated-completion",
    )
    adapter = EphemeralAdapter()

    finalized = collect_results_then_cleanup(
        adapter,
        receipt,
        terminal,
        cleanup_observed_at_utc=datetime(2026, 8, 28, 0, 0, 20, tzinfo=timezone.utc),
        collected_at_utc=datetime(2026, 8, 28, 0, 0, 21, tzinfo=timezone.utc),
    )

    assert adapter.calls == ["collect", "cleanup"]
    assert finalized.final_observation.finalized is True
    assert finalized.result_manifest.final_observation_fingerprint == finalized.final_observation.fingerprint()
    assert finalized.result_manifest.terminal_state is JobState.SUCCEEDED

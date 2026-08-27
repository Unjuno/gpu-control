from datetime import datetime, timezone
from decimal import Decimal

import pytest

from gpu_control.execution import ApprovedExecutionPlan
from gpu_control.lifecycle import CleanupState, JobObservation, JobState, build_submission_receipt
from gpu_control.providers.base import ProviderResultSnapshot
from gpu_control.providers.finalization import ProviderResultCapture, capture_provider_results_before_cleanup
from gpu_control.results import ArtifactDisposition, OutputArtifact, ResultContractError, load_result_policy


T0 = datetime(2026, 8, 28, 0, 0, tzinfo=timezone.utc)
CAPTURED_AT = datetime(2026, 8, 28, 0, 1, 2, tzinfo=timezone.utc)


def plan() -> ApprovedExecutionPlan:
    return ApprovedExecutionPlan(
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


def receipt_and_terminal():  # type: ignore[no-untyped-def]
    receipt = build_submission_receipt(plan(), provider_job_id="pod-1", submitted_at_utc=T0)
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


def artifact(index: int = 0) -> OutputArtifact:
    return OutputArtifact(
        name=f"result-{index}.json",
        sha256="sha256:" + f"{index % 16:x}" * 64,
        size_bytes=4096,
        media_type="application/json",
        reference=f"provider:result-{index}",
        disposition=ArtifactDisposition.COLLECTED,
    )


class Adapter:
    provider_name = "runpod"

    def collect_results(self, receipt, lifecycle_observation):  # type: ignore[no-untyped-def]
        return ProviderResultSnapshot(
            provider_job_id=receipt.provider_job_id,
            log_bytes_retained=128,
            logs_truncated=False,
            artifacts=(artifact(),),
        )

    def submit(self, plan):  # type: ignore[no-untyped-def]
        raise AssertionError("not used")

    def observe(self, receipt):  # type: ignore[no-untyped-def]
        raise AssertionError("not used")

    def cleanup(self, receipt, terminal_observation):  # type: ignore[no-untyped-def]
        raise AssertionError("not used")


def capture() -> ProviderResultCapture:
    receipt, terminal = receipt_and_terminal()
    return capture_provider_results_before_cleanup(
        Adapter(),
        receipt,
        terminal,
        captured_at_utc=CAPTURED_AT,
    )


def test_capture_json_rejects_unbounded_input_before_decode() -> None:
    with pytest.raises(ResultContractError, match="bounded input size"):
        ProviderResultCapture.from_json(" " + "x" * (2 * 1024 * 1024))


def test_capture_json_rejects_invalid_utf8_text_boundary() -> None:
    value = capture().canonical_json() + "\ud800"
    with pytest.raises(ResultContractError, match="valid UTF-8"):
        ProviderResultCapture.from_json(value)


def test_capture_from_dict_rejects_excess_artifact_count_before_materialization() -> None:
    policy = load_result_policy()
    payload = capture().to_dict()
    payload["artifacts"] = [artifact(index).to_dict() for index in range(policy.max_artifact_entries + 1)]

    with pytest.raises(ResultContractError, match="artifact count"):
        ProviderResultCapture.from_dict(payload, policy)

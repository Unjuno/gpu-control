from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from gpu_control.execution import ApprovedExecutionPlan
from gpu_control.lifecycle import CleanupState, JobState
from gpu_control.providers.base import (
    ProviderCleanupSnapshot,
    ProviderResultSnapshot,
    ProviderStatusSnapshot,
    ProviderSubmission,
)
from gpu_control.providers.controller import (
    ProviderContractError,
    cleanup_provider_job,
    collect_provider_results,
    observe_provider_job,
    submit_approved_plan,
)
from gpu_control.results import ArtifactDisposition, OutputArtifact, ResultContractError


SHA = "0123456789abcdef0123456789abcdef01234567"
IMAGE_DIGEST = "sha256:" + "a" * 64
SUBMIT_TIME = datetime(2026, 8, 22, 16, 0, tzinfo=timezone.utc)


def make_plan() -> ApprovedExecutionPlan:
    return ApprovedExecutionPlan(
        provider="runpod",
        provider_resource_id="synthetic-offer-3090",
        target_repo="example/model",
        target_sha=SHA,
        dockerfile_path="Dockerfile",
        image_digest=IMAGE_DIGEST,
        container_verification_reference="actions-run:100/container",
        gpu_profile="cheap-24gb",
        gpu_count=1,
        max_runtime_minutes=15,
        max_cost_usd=Decimal("0.10"),
        verified_hourly_price_usd=Decimal("0.34"),
        pricing_verification_reference="pricing-check:100",
        pricing_verified_at_utc="2026-08-22T15:55:00Z",
        pricing_valid_until_utc="2026-08-22T16:05:00Z",
        worst_case_cost_usd=Decimal("0.09"),
        authorization_reference="workflow_dispatch:100",
    )


def metric_artifact() -> OutputArtifact:
    return OutputArtifact(
        name="metrics.json",
        sha256="sha256:" + "b" * 64,
        size_bytes=4096,
        media_type="application/json",
        reference="provider://job-123/metrics.json",
        disposition=ArtifactDisposition.COLLECTED,
    )


def checkpoint_artifact() -> OutputArtifact:
    return OutputArtifact(
        name="checkpoints/model.safetensors",
        sha256="sha256:" + "c" * 64,
        size_bytes=2 * 1024 * 1024 * 1024,
        media_type="application/octet-stream",
        reference="provider://job-123/checkpoints/model.safetensors",
        disposition=ArtifactDisposition.REFERENCE_ONLY,
    )


class FakeProviderAdapter:
    """No-network test double used only to exercise the provider contract."""

    def __init__(self, provider_name: str = "runpod") -> None:
        self._provider_name = provider_name
        self.submit_calls = 0
        self.observe_calls = 0
        self.cleanup_calls = 0
        self.collect_calls = 0
        self.submission = ProviderSubmission(provider_job_id="job-123")
        self.statuses = [
            ProviderStatusSnapshot(
                provider_job_id="job-123",
                state=JobState.RUNNING,
                status_reference="provider-status:job-123:running",
            ),
            ProviderStatusSnapshot(
                provider_job_id="job-123",
                state=JobState.SUCCEEDED,
                status_reference="provider-status:job-123:succeeded",
            ),
        ]
        self.cleanup_snapshots = [
            ProviderCleanupSnapshot(
                provider_job_id="job-123",
                cleanup_state=CleanupState.COMPLETED,
                cleanup_reference="provider-cleanup:job-123:completed",
            )
        ]
        self.result = ProviderResultSnapshot(
            provider_job_id="job-123",
            log_bytes_retained=8192,
            logs_truncated=False,
            artifacts=(metric_artifact(), checkpoint_artifact()),
        )

    @property
    def provider_name(self) -> str:
        return self._provider_name

    def submit(self, plan: ApprovedExecutionPlan) -> ProviderSubmission:
        self.submit_calls += 1
        assert isinstance(plan, ApprovedExecutionPlan)
        return self.submission

    def observe(self, receipt):  # type: ignore[no-untyped-def]
        self.observe_calls += 1
        return self.statuses.pop(0)

    def cleanup(self, receipt, terminal_observation):  # type: ignore[no-untyped-def]
        self.cleanup_calls += 1
        return self.cleanup_snapshots.pop(0)

    def collect_results(self, receipt, final_observation):  # type: ignore[no-untyped-def]
        self.collect_calls += 1
        return self.result


def submit(adapter: FakeProviderAdapter, plan: ApprovedExecutionPlan | None = None):  # type: ignore[no-untyped-def]
    approved = plan or make_plan()
    return submit_approved_plan(
        adapter,
        approved,
        expected_plan_fingerprint=approved.fingerprint(),
        submitted_at_utc=SUBMIT_TIME,
    )


def test_submit_crosses_adapter_boundary_only_after_plan_checks() -> None:
    adapter = FakeProviderAdapter()
    plan = make_plan()

    submitted = submit(adapter, plan)

    assert adapter.submit_calls == 1
    assert submitted.receipt.provider == "runpod"
    assert submitted.receipt.provider_job_id == "job-123"
    assert submitted.receipt.plan_fingerprint == plan.fingerprint()
    assert submitted.initial_observation.state is JobState.SUBMITTED
    assert submitted.initial_observation.cleanup_state is CleanupState.NOT_STARTED


def test_wrong_expected_fingerprint_blocks_adapter_call() -> None:
    adapter = FakeProviderAdapter()
    plan = make_plan()

    with pytest.raises(ProviderContractError, match="expected fingerprint"):
        submit_approved_plan(
            adapter,
            plan,
            expected_plan_fingerprint="sha256:" + "f" * 64,
            submitted_at_utc=SUBMIT_TIME,
        )

    assert adapter.submit_calls == 0


def test_expired_pricing_blocks_adapter_call() -> None:
    adapter = FakeProviderAdapter()
    plan = replace(make_plan(), pricing_valid_until_utc="2026-08-22T16:00:00Z")

    with pytest.raises(ProviderContractError, match="expired before provider submission"):
        submit_approved_plan(
            adapter,
            plan,
            expected_plan_fingerprint=plan.fingerprint(),
            submitted_at_utc=SUBMIT_TIME,
        )

    assert adapter.submit_calls == 0


def test_provider_mismatch_blocks_adapter_call() -> None:
    adapter = FakeProviderAdapter(provider_name="other")
    plan = make_plan()

    with pytest.raises(ProviderContractError, match="does not match"):
        submit(adapter, plan)

    assert adapter.submit_calls == 0


def test_malformed_submission_response_is_rejected() -> None:
    adapter = FakeProviderAdapter()
    adapter.submission = ProviderSubmission(provider_job_id=" job-123 ")

    with pytest.raises(ProviderContractError, match="surrounding whitespace"):
        submit(adapter)


def test_status_and_cleanup_are_correlated_and_monotonic() -> None:
    adapter = FakeProviderAdapter()
    submitted = submit(adapter)

    running = observe_provider_job(
        adapter,
        submitted.receipt,
        observed_at_utc=datetime(2026, 8, 22, 16, 0, 10, tzinfo=timezone.utc),
        previous_observation=submitted.initial_observation,
    )
    succeeded = observe_provider_job(
        adapter,
        submitted.receipt,
        observed_at_utc=datetime(2026, 8, 22, 16, 1, 0, tzinfo=timezone.utc),
        previous_observation=running,
    )
    cleaned = cleanup_provider_job(
        adapter,
        submitted.receipt,
        succeeded,
        observed_at_utc=datetime(2026, 8, 22, 16, 1, 5, tzinfo=timezone.utc),
    )

    assert running.state is JobState.RUNNING
    assert succeeded.state is JobState.SUCCEEDED
    assert cleaned.finalized is True
    assert adapter.observe_calls == 2
    assert adapter.cleanup_calls == 1


def test_provider_status_job_id_mismatch_is_rejected() -> None:
    adapter = FakeProviderAdapter()
    submitted = submit(adapter)
    adapter.statuses = [
        ProviderStatusSnapshot(
            provider_job_id="other-job",
            state=JobState.RUNNING,
            status_reference="provider-status:other",
        )
    ]

    with pytest.raises(ProviderContractError, match="status job id"):
        observe_provider_job(
            adapter,
            submitted.receipt,
            observed_at_utc=datetime(2026, 8, 22, 16, 0, 10, tzinfo=timezone.utc),
            previous_observation=submitted.initial_observation,
        )


def test_terminal_state_cannot_regress_even_if_provider_reports_it() -> None:
    adapter = FakeProviderAdapter()
    submitted = submit(adapter)
    adapter.statuses = [
        ProviderStatusSnapshot(
            provider_job_id="job-123",
            state=JobState.SUCCEEDED,
            status_reference="provider-status:job-123:succeeded",
        ),
        ProviderStatusSnapshot(
            provider_job_id="job-123",
            state=JobState.RUNNING,
            status_reference="provider-status:job-123:running-again",
        ),
    ]

    succeeded = observe_provider_job(
        adapter,
        submitted.receipt,
        observed_at_utc=datetime(2026, 8, 22, 16, 1, 0, tzinfo=timezone.utc),
        previous_observation=submitted.initial_observation,
    )
    with pytest.raises(ProviderContractError, match="illegal job-state transition"):
        observe_provider_job(
            adapter,
            submitted.receipt,
            observed_at_utc=datetime(2026, 8, 22, 16, 1, 1, tzinfo=timezone.utc),
            previous_observation=succeeded,
        )


def test_cleanup_is_not_called_for_nonterminal_state() -> None:
    adapter = FakeProviderAdapter()
    submitted = submit(adapter)
    running = observe_provider_job(
        adapter,
        submitted.receipt,
        observed_at_utc=datetime(2026, 8, 22, 16, 0, 10, tzinfo=timezone.utc),
        previous_observation=submitted.initial_observation,
    )

    with pytest.raises(ProviderContractError, match="terminal"):
        cleanup_provider_job(
            adapter,
            submitted.receipt,
            running,
            observed_at_utc=datetime(2026, 8, 22, 16, 0, 11, tzinfo=timezone.utc),
        )

    assert adapter.cleanup_calls == 0


def test_result_collection_requires_cleanup_completed_before_adapter_call() -> None:
    adapter = FakeProviderAdapter()
    submitted = submit(adapter)
    terminal = replace(
        submitted.initial_observation,
        state=JobState.SUCCEEDED,
        observed_at_utc="2026-08-22T16:01:00Z",
    )

    with pytest.raises(ProviderContractError, match="finalized"):
        collect_provider_results(
            adapter,
            submitted.receipt,
            terminal,
            collected_at_utc=datetime(2026, 8, 22, 16, 1, 5, tzinfo=timezone.utc),
        )

    assert adapter.collect_calls == 0


def test_full_no_network_provider_contract_produces_bounded_result_manifest() -> None:
    adapter = FakeProviderAdapter()
    submitted = submit(adapter)
    running = observe_provider_job(
        adapter,
        submitted.receipt,
        observed_at_utc=datetime(2026, 8, 22, 16, 0, 10, tzinfo=timezone.utc),
        previous_observation=submitted.initial_observation,
    )
    succeeded = observe_provider_job(
        adapter,
        submitted.receipt,
        observed_at_utc=datetime(2026, 8, 22, 16, 1, 0, tzinfo=timezone.utc),
        previous_observation=running,
    )
    final = cleanup_provider_job(
        adapter,
        submitted.receipt,
        succeeded,
        observed_at_utc=datetime(2026, 8, 22, 16, 1, 5, tzinfo=timezone.utc),
    )

    manifest = collect_provider_results(
        adapter,
        submitted.receipt,
        final,
        collected_at_utc=datetime(2026, 8, 22, 16, 1, 10, tzinfo=timezone.utc),
    )

    assert manifest.provider == "runpod"
    assert manifest.provider_job_id == "job-123"
    assert manifest.terminal_state is JobState.SUCCEEDED
    assert manifest.artifacts[0].disposition is ArtifactDisposition.COLLECTED
    assert manifest.artifacts[1].disposition is ArtifactDisposition.REFERENCE_ONLY
    assert adapter.collect_calls == 1


def test_provider_result_policy_rejects_oversized_collected_artifact() -> None:
    adapter = FakeProviderAdapter()
    submitted = submit(adapter)
    succeeded = replace(
        submitted.initial_observation,
        state=JobState.SUCCEEDED,
        observed_at_utc="2026-08-22T16:01:00Z",
    )
    final = cleanup_provider_job(
        adapter,
        submitted.receipt,
        succeeded,
        observed_at_utc=datetime(2026, 8, 22, 16, 1, 5, tzinfo=timezone.utc),
    )
    adapter.result = ProviderResultSnapshot(
        provider_job_id="job-123",
        log_bytes_retained=0,
        logs_truncated=False,
        artifacts=(
            replace(
                metric_artifact(),
                size_bytes=65 * 1024 * 1024,
            ),
        ),
    )

    with pytest.raises(ResultContractError, match="per-file collection limit"):
        collect_provider_results(
            adapter,
            submitted.receipt,
            final,
            collected_at_utc=datetime(2026, 8, 22, 16, 1, 10, tzinfo=timezone.utc),
        )

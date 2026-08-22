from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from .container import ContainerVerificationResult
from .execution import build_approved_execution_plan
from .policy import load_policy, validate_against_policy
from .pricing import PricingVerificationResult
from .providers.controller import (
    cleanup_provider_job,
    collect_provider_results,
    observe_provider_job,
    submit_approved_plan,
)
from .providers.synthetic import SyntheticProviderAdapter
from .source import SourceVerificationResult
from .validation import build_request


_SELF_TEST_SHA = "0123456789abcdef0123456789abcdef01234567"
_SELF_TEST_IMAGE = "sha256:" + "a" * 64


def run_provider_contract_self_test() -> dict[str, object]:
    """Exercise the provider controller end-to-end without network or paid compute."""

    request = build_request(
        target_repo="example/model",
        target_sha=_SELF_TEST_SHA,
        dockerfile_path="Dockerfile",
        gpu_profile="cheap-24gb",
        max_runtime_minutes=5,
        max_cost_usd="0.05",
    )
    effective_policy = validate_against_policy(request, load_policy())

    source = SourceVerificationResult(
        repository=request.target_repo,
        commit_sha=request.target_sha,
        dockerfile_path=request.dockerfile_path,
        repository_public=True,
        commit_verified=True,
        dockerfile_verified=True,
    )
    container = ContainerVerificationResult(
        repository=request.target_repo,
        commit_sha=request.target_sha,
        dockerfile_path=request.dockerfile_path,
        image_digest=_SELF_TEST_IMAGE,
        verification_reference="offline-self-test:container",
        build_isolated=True,
        runtime_isolated=True,
        smoke_test_passed=True,
        output_contract_verified=True,
        credentials_absent=True,
        network_policy_enforced=True,
        resource_limits_enforced=True,
    )
    pricing = PricingVerificationResult(
        provider="synthetic",
        gpu_profile=request.gpu_profile,
        provider_resource_id="synthetic-no-network",
        hourly_price_usd=Decimal("0.01"),
        verification_reference="offline-self-test:pricing",
        verified_at_utc="2025-12-31T23:55:00Z",
        valid_until_utc="2026-01-01T00:10:00Z",
        price_verified=True,
        availability_verified=True,
    )

    plan = build_approved_execution_plan(
        request,
        effective_policy,
        source,
        container,
        pricing,
        dry_run_succeeded=True,
        cleanup_guaranteed=True,
        explicit_human_authorization=True,
        authorization_reference="offline-self-test:non-billable",
        decision_time_utc=datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc),
    )

    adapter = SyntheticProviderAdapter()
    submitted = submit_approved_plan(
        adapter,
        plan,
        expected_plan_fingerprint=plan.fingerprint(),
        submitted_at_utc=datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc),
    )
    running = observe_provider_job(
        adapter,
        submitted.receipt,
        observed_at_utc=datetime(2026, 1, 1, 0, 2, tzinfo=timezone.utc),
        previous_observation=submitted.initial_observation,
    )
    succeeded = observe_provider_job(
        adapter,
        submitted.receipt,
        observed_at_utc=datetime(2026, 1, 1, 0, 3, tzinfo=timezone.utc),
        previous_observation=running,
    )
    finalized = cleanup_provider_job(
        adapter,
        submitted.receipt,
        succeeded,
        observed_at_utc=datetime(2026, 1, 1, 0, 4, tzinfo=timezone.utc),
    )
    manifest = collect_provider_results(
        adapter,
        submitted.receipt,
        finalized,
        collected_at_utc=datetime(2026, 1, 1, 0, 5, tzinfo=timezone.utc),
    )

    return {
        "status": "ok",
        "dry_run": True,
        "provider": "synthetic",
        "network_access": False,
        "external_resources_created": False,
        "billable_compute": False,
        "checks": [
            "approved_plan",
            "trusted_plan_fingerprint",
            "submission_price_freshness",
            "submission_receipt",
            "running_observation",
            "terminal_observation",
            "cleanup_completed",
            "bounded_result_manifest",
            "large_artifact_reference_only",
        ],
        "plan_fingerprint": plan.fingerprint(),
        "submission_receipt_fingerprint": submitted.receipt.fingerprint(),
        "result_manifest_fingerprint": manifest.fingerprint(),
        "terminal_state": manifest.terminal_state.value,
        "artifact_dispositions": {
            artifact.name: artifact.disposition.value for artifact in manifest.artifacts
        },
    }

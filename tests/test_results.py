from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path

import pytest
import yaml

from gpu_control.execution import ApprovedExecutionPlan
from gpu_control.lifecycle import CleanupState, JobObservation, JobState, build_submission_receipt
from gpu_control.results import (
    ArtifactDisposition,
    OutputArtifact,
    ResultContractError,
    ResultManifest,
    build_result_manifest,
    load_result_policy,
    validate_manifest_against_lifecycle,
)


ROOT = Path(__file__).resolve().parents[1]
SHA = "0123456789abcdef0123456789abcdef01234567"
IMAGE_DIGEST = "sha256:" + "a" * 64
SUBMITTED_AT = datetime(2026, 8, 22, 16, 0, tzinfo=timezone.utc)
FINAL_AT = "2026-08-22T16:02:00Z"
COLLECTED_AT = datetime(2026, 8, 22, 16, 2, 5, tzinfo=timezone.utc)


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


def make_receipt():  # type: ignore[no-untyped-def]
    return build_submission_receipt(
        make_plan(),
        provider_job_id="job-123",
        submitted_at_utc=SUBMITTED_AT,
    )


def make_final_observation():  # type: ignore[no-untyped-def]
    receipt = make_receipt()
    return JobObservation(
        provider=receipt.provider,
        provider_job_id=receipt.provider_job_id,
        plan_fingerprint=receipt.plan_fingerprint,
        state=JobState.SUCCEEDED,
        cleanup_state=CleanupState.COMPLETED,
        observed_at_utc=FINAL_AT,
        status_reference="provider-status:job-123",
    )


def artifact(
    name: str,
    *,
    size_bytes: int = 1024,
    disposition: ArtifactDisposition = ArtifactDisposition.COLLECTED,
    digest_char: str = "b",
):
    return OutputArtifact(
        name=name,
        sha256="sha256:" + digest_char * 64,
        size_bytes=size_bytes,
        media_type="application/octet-stream",
        reference=f"provider://job-123/{name}",
        disposition=disposition,
    )


def test_bundled_and_public_result_policies_match() -> None:
    bundled = load_result_policy()
    public = load_result_policy(ROOT / "policies" / "result-policy.yaml")

    assert bundled == public
    raw = yaml.safe_load((ROOT / "policies" / "result-policy.yaml").read_text(encoding="utf-8"))
    assert raw["behavior"]["large_artifacts"] == "reference_only"
    assert raw["behavior"]["auto_fetch_references"] is False


def test_builds_manifest_with_small_collection_and_large_reference_only_artifact() -> None:
    receipt = make_receipt()
    final = make_final_observation()
    metrics = artifact("metrics.json", size_bytes=4096, digest_char="c")
    checkpoint = artifact(
        "checkpoints/model.safetensors",
        size_bytes=2 * 1024 * 1024 * 1024,
        disposition=ArtifactDisposition.REFERENCE_ONLY,
        digest_char="d",
    )

    manifest = build_result_manifest(
        receipt,
        final,
        artifacts=[metrics, checkpoint],
        log_bytes_retained=8192,
        logs_truncated=False,
        collected_at_utc=COLLECTED_AT,
    )

    assert manifest.terminal_state is JobState.SUCCEEDED
    assert manifest.submission_receipt_fingerprint == receipt.fingerprint()
    assert manifest.final_observation_fingerprint == final.fingerprint()
    assert manifest.artifacts[1].disposition is ArtifactDisposition.REFERENCE_ONLY
    assert manifest.fingerprint().startswith("sha256:")
    validate_manifest_against_lifecycle(manifest, receipt, final)


def test_result_manifest_json_round_trip_is_canonical() -> None:
    manifest = build_result_manifest(
        make_receipt(),
        make_final_observation(),
        artifacts=[artifact("metrics.json")],
        log_bytes_retained=1024,
        logs_truncated=False,
        collected_at_utc=COLLECTED_AT,
    )
    policy = load_result_policy()

    restored = ResultManifest.from_json(manifest.canonical_json(), policy)

    assert restored == manifest
    assert restored.canonical_json() == manifest.canonical_json()
    assert restored.fingerprint() == manifest.fingerprint()


def test_manifest_rejects_unknown_and_duplicate_json_fields() -> None:
    manifest = build_result_manifest(
        make_receipt(),
        make_final_observation(),
        artifacts=[],
        log_bytes_retained=0,
        logs_truncated=False,
        collected_at_utc=COLLECTED_AT,
    )
    policy = load_result_policy()
    payload = manifest.to_dict()
    payload["unexpected"] = True

    with pytest.raises(ResultContractError, match="unknown fields"):
        ResultManifest.from_json(json.dumps(payload), policy)

    duplicate = manifest.canonical_json().replace(
        '"provider":"runpod"',
        '"provider":"runpod","provider":"other"',
    )
    with pytest.raises(ResultContractError, match="duplicate field: provider"):
        ResultManifest.from_json(duplicate, policy)


def test_collected_artifact_per_file_limit_is_enforced() -> None:
    policy = load_result_policy()
    too_large = artifact(
        "large.bin",
        size_bytes=policy.max_collected_file_bytes + 1,
        disposition=ArtifactDisposition.COLLECTED,
    )

    with pytest.raises(ResultContractError, match="per-file collection limit"):
        build_result_manifest(
            make_receipt(),
            make_final_observation(),
            artifacts=[too_large],
            log_bytes_retained=0,
            logs_truncated=False,
            collected_at_utc=COLLECTED_AT,
            policy=policy,
        )


def test_reference_only_artifact_can_exceed_collection_limit_but_not_declared_limit() -> None:
    policy = load_result_policy()
    large_reference = artifact(
        "checkpoint.bin",
        size_bytes=policy.max_collected_file_bytes * 4,
        disposition=ArtifactDisposition.REFERENCE_ONLY,
    )
    manifest = build_result_manifest(
        make_receipt(),
        make_final_observation(),
        artifacts=[large_reference],
        log_bytes_retained=0,
        logs_truncated=False,
        collected_at_utc=COLLECTED_AT,
        policy=policy,
    )
    assert manifest.artifacts[0].size_bytes > policy.max_collected_file_bytes

    impossible = replace(large_reference, size_bytes=policy.max_declared_artifact_bytes + 1)
    with pytest.raises(ResultContractError, match="declared size"):
        impossible.validate_shape(policy)


def test_total_collected_bytes_are_bounded() -> None:
    policy = load_result_policy()
    each = 50 * 1024 * 1024
    artifacts = [
        artifact("a.bin", size_bytes=each, digest_char="a"),
        artifact("b.bin", size_bytes=each, digest_char="b"),
        artifact("c.bin", size_bytes=each, digest_char="c"),
    ]

    with pytest.raises(ResultContractError, match="total exceeds"):
        build_result_manifest(
            make_receipt(),
            make_final_observation(),
            artifacts=artifacts,
            log_bytes_retained=0,
            logs_truncated=False,
            collected_at_utc=COLLECTED_AT,
            policy=policy,
        )


def test_logs_and_artifact_count_are_bounded() -> None:
    policy = load_result_policy()

    with pytest.raises(ResultContractError, match="retained logs exceed"):
        build_result_manifest(
            make_receipt(),
            make_final_observation(),
            artifacts=[],
            log_bytes_retained=policy.max_log_bytes + 1,
            logs_truncated=True,
            collected_at_utc=COLLECTED_AT,
            policy=policy,
        )

    too_many = [
        artifact(
            f"refs/{index}.json",
            size_bytes=0,
            disposition=ArtifactDisposition.REFERENCE_ONLY,
            digest_char=hex(index % 16)[2:],
        )
        for index in range(policy.max_artifact_entries + 1)
    ]
    with pytest.raises(ResultContractError, match="artifact count"):
        build_result_manifest(
            make_receipt(),
            make_final_observation(),
            artifacts=too_many,
            log_bytes_retained=0,
            logs_truncated=False,
            collected_at_utc=COLLECTED_AT,
            policy=policy,
        )


def test_artifact_names_are_safe_relative_posix_paths_and_unique() -> None:
    policy = load_result_policy()

    for name in ("../secret", "/absolute.bin", "windows\\path.bin"):
        with pytest.raises(ResultContractError, match="artifact name"):
            artifact(name).validate_shape(policy)

    duplicate = artifact("metrics.json")
    with pytest.raises(ResultContractError, match="duplicate artifact name"):
        build_result_manifest(
            make_receipt(),
            make_final_observation(),
            artifacts=[duplicate, duplicate],
            log_bytes_retained=0,
            logs_truncated=False,
            collected_at_utc=COLLECTED_AT,
            policy=policy,
        )


def test_result_collection_requires_finalized_lifecycle_state() -> None:
    receipt = make_receipt()
    not_final = replace(make_final_observation(), cleanup_state=CleanupState.PENDING)

    with pytest.raises(ResultContractError, match="finalized"):
        build_result_manifest(
            receipt,
            not_final,
            artifacts=[],
            log_bytes_retained=0,
            logs_truncated=False,
            collected_at_utc=COLLECTED_AT,
        )


def test_result_collection_cannot_predate_final_observation() -> None:
    with pytest.raises(ResultContractError, match="cannot predate"):
        build_result_manifest(
            make_receipt(),
            make_final_observation(),
            artifacts=[],
            log_bytes_retained=0,
            logs_truncated=False,
            collected_at_utc=datetime(2026, 8, 22, 16, 1, 59, tzinfo=timezone.utc),
        )


def test_persisted_manifest_must_match_lifecycle_fingerprints() -> None:
    receipt = make_receipt()
    final = make_final_observation()
    manifest = build_result_manifest(
        receipt,
        final,
        artifacts=[],
        log_bytes_retained=0,
        logs_truncated=False,
        collected_at_utc=COLLECTED_AT,
    )

    for field, value, message in [
        ("provider_job_id", "other-job", "provider_job_id"),
        ("plan_fingerprint", "sha256:" + "f" * 64, "plan_fingerprint"),
        ("submission_receipt_fingerprint", "sha256:" + "e" * 64, "submission_receipt_fingerprint"),
        ("final_observation_fingerprint", "sha256:" + "d" * 64, "final_observation_fingerprint"),
        ("terminal_state", JobState.FAILED, "terminal_state"),
    ]:
        tampered = replace(manifest, **{field: value})
        with pytest.raises(ResultContractError, match=message):
            validate_manifest_against_lifecycle(tampered, receipt, final)

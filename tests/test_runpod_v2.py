from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
import io
import json
from urllib.error import HTTPError

import pytest

from gpu_control.completion import CompletionChallenge, execution_name_for
from gpu_control.execution import ApprovedExecutionPlan
from gpu_control.lifecycle import JobState
from gpu_control.providers.runpod_v2 import (
    RUNPOD_V2_BASE_URL,
    PublishedImageEvidence,
    RunPodCompletionLaunch,
    RunPodV2Error,
    RunPodV2HttpClient,
    build_create_pod_payload,
    translate_pod_status,
    validate_created_pod,
)


DIGEST = "sha256:" + "a" * 64
SECRET = bytes(range(32))


def make_plan(**overrides) -> ApprovedExecutionPlan:  # type: ignore[no-untyped-def]
    values = {
        "provider": "runpod",
        "provider_resource_id": "NVIDIA GeForce RTX 4090",
        "target_repo": "example/model",
        "target_sha": "0123456789abcdef0123456789abcdef01234567",
        "dockerfile_path": "Dockerfile",
        "image_digest": DIGEST,
        "container_verification_reference": "actions-run:100/container",
        "gpu_profile": "cheap-24gb",
        "gpu_count": 1,
        "max_runtime_minutes": 15,
        "max_cost_usd": Decimal("0.20"),
        "verified_hourly_price_usd": Decimal("0.44"),
        "pricing_verification_reference": "runpod-v2-catalog:100",
        "pricing_verified_at_utc": "2026-08-22T16:00:00Z",
        "pricing_valid_until_utc": "2026-08-22T16:10:00Z",
        "worst_case_cost_usd": Decimal("0.11"),
        "authorization_reference": "workflow_dispatch:100",
    }
    values.update(overrides)
    plan = ApprovedExecutionPlan(**values)
    plan.validate_shape()
    return plan


def make_image(plan: ApprovedExecutionPlan | None = None, **overrides) -> PublishedImageEvidence:  # type: ignore[no-untyped-def]
    plan = plan or make_plan()
    values = {
        "plan_fingerprint": plan.fingerprint(),
        "image_reference": f"ghcr.io/example/model@{DIGEST}",
        "image_digest": DIGEST,
        "verification_reference": "registry-publish:100",
    }
    values.update(overrides)
    return PublishedImageEvidence(**values)


def make_completion(plan: ApprovedExecutionPlan | None = None, *, secret_key: bytes = SECRET) -> RunPodCompletionLaunch:
    plan = plan or make_plan()
    nonce = "b" * 64
    challenge = CompletionChallenge(
        key_id="paid-runpod-v2",
        nonce=nonce,
        plan_fingerprint=plan.fingerprint(),
        execution_name=execution_name_for(plan.fingerprint(), nonce),
        source_sha=plan.target_sha,
        image_digest=plan.image_digest,
    )
    return RunPodCompletionLaunch(challenge=challenge, secret_key=secret_key)


def test_create_payload_is_minimal_and_digest_pinned() -> None:
    plan = make_plan()
    payload = build_create_pod_payload(plan, make_image(plan))

    assert payload == {
        "name": f"gpu-control-{plan.fingerprint()[7:19]}",
        "image": f"ghcr.io/example/model@{DIGEST}",
        "gpu": {"id": "NVIDIA GeForce RTX 4090", "count": 1},
        "disk": 20,
        "cloud": "SECURE",
        "globalNetworking": False,
    }
    assert "env" not in payload
    assert "ports" not in payload
    assert "mounts" not in payload


def test_authenticated_create_payload_injects_only_control_plane_completion_env() -> None:
    plan = make_plan()
    completion = make_completion(plan)
    payload = build_create_pod_payload(plan, make_image(plan), completion=completion)

    assert payload["name"] == completion.challenge.execution_name
    assert payload["env"] == {
        "GPU_CONTROL_COMPLETION_KEY_B64": "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8=",
        "GPU_CONTROL_COMPLETION_KEY_ID": "paid-runpod-v2",
        "GPU_CONTROL_COMPLETION_NONCE": "b" * 64,
        "GPU_CONTROL_EXECUTION_NAME": completion.challenge.execution_name,
        "GPU_CONTROL_PLAN_FINGERPRINT": plan.fingerprint(),
        "GPU_CONTROL_IMAGE_DIGEST": DIGEST,
    }
    assert "ports" not in payload
    assert "mounts" not in payload


def test_completion_launch_must_match_exact_approved_plan() -> None:
    plan = make_plan()
    other = make_plan(target_sha="f" * 40)
    with pytest.raises(RunPodV2Error, match="plan fingerprint"):
        build_create_pod_payload(plan, make_image(plan), completion=make_completion(other))


def test_completion_launch_must_match_approved_source_sha() -> None:
    plan = make_plan()
    valid = make_completion(plan)
    invalid = RunPodCompletionLaunch(
        challenge=replace(valid.challenge, source_sha="f" * 40),
        secret_key=valid.secret_key,
    )
    with pytest.raises(RunPodV2Error, match="source_sha"):
        build_create_pod_payload(plan, make_image(plan), completion=invalid)


def test_completion_launch_rejects_short_secret_before_create() -> None:
    plan = make_plan()
    with pytest.raises(RunPodV2Error, match="at least 32 bytes"):
        build_create_pod_payload(plan, make_image(plan), completion=make_completion(plan, secret_key=b"short"))


def test_create_payload_rejects_untrusted_or_mutable_image_binding() -> None:
    plan = make_plan()

    with pytest.raises(RunPodV2Error, match="plan fingerprint"):
        build_create_pod_payload(
            plan,
            make_image(plan, plan_fingerprint="sha256:" + "b" * 64),
        )

    with pytest.raises(RunPodV2Error, match="explicit registry"):
        build_create_pod_payload(
            plan,
            make_image(plan, image_reference="ghcr.io/example/model:latest"),
        )

    with pytest.raises(RunPodV2Error, match="digest does not match"):
        build_create_pod_payload(
            plan,
            make_image(
                plan,
                image_reference="ghcr.io/example/model@sha256:" + "b" * 64,
            ),
        )


def test_create_payload_requires_runpod_plan() -> None:
    plan = make_plan(provider="other")
    with pytest.raises(RunPodV2Error, match="runpod approved plan"):
        build_create_pod_payload(plan, make_image(plan))


def test_created_pod_is_revalidated_against_plan() -> None:
    plan = make_plan()
    image = make_image(plan)
    pod = {
        "id": "pod-123",
        "image": image.image_reference,
        "gpu": {"id": plan.provider_resource_id, "count": 1},
        "cost": 0.44,
        "status": "PROVISIONING",
    }

    assert validate_created_pod(plan, image, pod) == "pod-123"

    expensive = dict(pod, cost=0.45)
    with pytest.raises(RunPodV2Error, match="exceeds verified approved price"):
        validate_created_pod(plan, image, expensive)

    wrong_gpu = dict(pod, gpu={"id": "NVIDIA A100", "count": 1})
    with pytest.raises(RunPodV2Error, match="GPU identity"):
        validate_created_pod(plan, image, wrong_gpu)


def test_runpod_status_translation_is_fail_closed() -> None:
    assert translate_pod_status({"status": "PROVISIONING"}) is JobState.SUBMITTED
    assert translate_pod_status({"status": "STARTING"}) is JobState.SUBMITTED
    assert translate_pod_status({"status": "RUNNING"}) is JobState.RUNNING
    assert translate_pod_status({"status": "ERROR"}) is JobState.FAILED
    assert translate_pod_status({"status": "TERMINATED"}) is JobState.CANCELLED

    with pytest.raises(RunPodV2Error, match="EXITED is ambiguous"):
        translate_pod_status({"status": "EXITED"})
    with pytest.raises(RunPodV2Error, match="unknown or missing"):
        translate_pod_status({"status": "NEW_FUTURE_STATE"})


class FakeResponse:
    def __init__(self, status: int, payload: object | None = None) -> None:
        self.status = status
        self._raw = b"" if payload is None else json.dumps(payload).encode("utf-8")

    def __enter__(self):  # type: ignore[no-untyped-def]
        return self

    def __exit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
        return False

    def read(self) -> bytes:
        return self._raw


def test_http_client_uses_fixed_origin_bearer_auth_and_v2_paths() -> None:
    calls = []
    responses = iter(
        [
            FakeResponse(200, {"gpus": []}),
            FakeResponse(201, {"id": "pod-123"}),
            FakeResponse(200, {"id": "pod-123", "status": "RUNNING"}),
            FakeResponse(200, {"id": "pod-123", "status": "EXITED"}),
            FakeResponse(204),
        ]
    )

    def opener(request, timeout):  # type: ignore[no-untyped-def]
        calls.append((request, timeout))
        return next(responses)

    client = RunPodV2HttpClient("secret-token", timeout=3.0, opener=opener)
    client.list_gpu_types()
    client.create_pod({"name": "test"})
    client.get_pod("pod-123")
    client.transition_pod("pod-123", "stop")
    client.terminate_pod("pod-123")

    urls = [request.full_url for request, _ in calls]
    assert urls == [
        f"{RUNPOD_V2_BASE_URL}/catalog/gpus?include=AVAILABILITY&product=POD&count=1&cloud=SECURE",
        f"{RUNPOD_V2_BASE_URL}/pods",
        f"{RUNPOD_V2_BASE_URL}/pods/pod-123",
        f"{RUNPOD_V2_BASE_URL}/pods/pod-123/action",
        f"{RUNPOD_V2_BASE_URL}/pods/pod-123",
    ]
    assert [request.get_method() for request, _ in calls] == ["GET", "POST", "GET", "POST", "DELETE"]
    assert all(timeout == 3.0 for _, timeout in calls)
    assert all(request.get_header("Authorization") == "Bearer secret-token" for request, _ in calls)
    stop_body = json.loads(calls[3][0].data.decode("utf-8"))
    assert stop_body == {"action": "stop"}


def test_http_errors_do_not_leak_api_key() -> None:
    body = io.BytesIO(json.dumps({"detail": "access denied"}).encode("utf-8"))

    def opener(request, timeout):  # type: ignore[no-untyped-def]
        raise HTTPError(request.full_url, 403, "Forbidden", {}, body)

    client = RunPodV2HttpClient("super-secret-api-key", opener=opener)
    with pytest.raises(RunPodV2Error) as exc_info:
        client.get_pod("pod-123")

    message = str(exc_info.value)
    assert "HTTP 403" in message
    assert "access denied" in message
    assert "super-secret-api-key" not in message


def test_client_rejects_arbitrary_actions_and_bad_identifiers_without_network() -> None:
    calls = 0

    def opener(request, timeout):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        raise AssertionError("network should not be reached")

    client = RunPodV2HttpClient("secret", opener=opener)
    with pytest.raises(RunPodV2Error, match="unsupported"):
        client.transition_pod("pod-123", "shell")
    with pytest.raises(RunPodV2Error, match="whitespace"):
        client.get_pod("pod 123")
    assert calls == 0

"""Regression probes from the 2026-09-08 release audit. No network or GPU calls."""
from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from io import BytesIO
import json
from pathlib import Path
from urllib.error import HTTPError

import pytest

from gpu_control.policy import PolicyError, load_policy, validate_against_policy
from gpu_control.providers.runpod_v1 import RunPodV1HttpClient
from gpu_control.providers.runpod_v2 import RunPodV2Error, RunPodV2HttpClient
from gpu_control.validation import ValidationError, parse_cost, parse_runtime, validate_relative_path
from test_runpod_v1_adapter import NOW, FakeV1Client, RunPodV1AdapterError, adapter, plan


@pytest.mark.parametrize("value", [True, False, 1.5, Decimal("1.5"), "1_0", " 1", "+1"])
def test_runtime_is_not_coerced_or_silently_truncated(value: object) -> None:
    with pytest.raises(ValidationError):
        parse_runtime(value)  # type: ignore[arg-type]


@pytest.mark.parametrize("value", [".", "./Dockerfile", "a//Dockerfile", "a/./Dockerfile", "Dockerfile/", "a/\nDockerfile", "a/\x00Dockerfile"])
def test_dockerfile_path_must_be_canonical(value: str) -> None:
    with pytest.raises(ValidationError):
        validate_relative_path(value)


@pytest.mark.parametrize("value", ["1e100", "1e999999", "9" * 100])
def test_extreme_cost_is_a_validation_error_not_decimal_exception(value: str) -> None:
    with pytest.raises(ValidationError):
        parse_cost(value)


@pytest.mark.parametrize("value", [True, 1.9, "1"])
def test_policy_gpu_count_is_an_integer_not_coercible(value: object) -> None:
    policy = load_policy()
    policy["profiles"]["cheap-24gb"]["max_gpu_count"] = value
    from test_policy import request
    with pytest.raises(PolicyError):
        validate_against_policy(request(), policy)


def test_malformed_yaml_is_a_policy_error(tmp_path: Path) -> None:
    p = tmp_path / "bad.yaml"
    p.write_text("hard_limits: [\n", encoding="utf-8")
    with pytest.raises(PolicyError):
        load_policy(p)


def test_duplicate_yaml_keys_are_rejected(tmp_path: Path) -> None:
    p = tmp_path / "duplicate.yaml"
    p.write_text("version: 1\nversion: 2\n", encoding="utf-8")
    with pytest.raises(PolicyError):
        load_policy(p)


@pytest.mark.parametrize("client_type", [RunPodV1HttpClient, RunPodV2HttpClient])
def test_provider_error_cannot_echo_credential(client_type) -> None:  # type: ignore[no-untyped-def]
    credential = "audit-secret-never-print"
    def opener(request, timeout):  # type: ignore[no-untyped-def]
        body = BytesIO(json.dumps({"message": credential, "detail": credential}).encode())
        raise HTTPError(request.full_url, 403, "Forbidden", {}, body)
    client = client_type(credential, opener=opener)
    with pytest.raises(RunPodV2Error) as caught:
        client.list_pods()
    assert credential not in str(caught.value)


@pytest.mark.parametrize("client_type", [RunPodV1HttpClient, RunPodV2HttpClient])
@pytest.mark.parametrize("timeout", [float("nan"), float("inf"), True])
def test_http_timeout_is_finite_and_not_boolean(client_type, timeout) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(RunPodV2Error):
        client_type("test-key", timeout=timeout)


@pytest.mark.parametrize("expiry", ["pricing", "permit"])
def test_submission_rechecks_expiry_after_slow_occupancy_probe(expiry: str) -> None:
    value = plan()
    client = FakeV1Client(value)
    time = [NOW]
    runpod = adapter(value, client, lambda: time[0])
    if expiry == "permit":
        runpod = replace(runpod, live_permit=replace(runpod.live_permit, valid_until_utc=(NOW + timedelta(seconds=30)).isoformat()))
    original = client.list_pods
    def slow_list():  # type: ignore[no-untyped-def]
        time[0] = NOW + timedelta(seconds=31 if expiry == "permit" else 121)
        return original()
    client.list_pods = slow_list  # type: ignore[method-assign]
    with pytest.raises(RunPodV1AdapterError, match="expir"):
        runpod.submit(value)
    assert client.create_payloads == []

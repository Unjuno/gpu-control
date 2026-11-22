from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace

import pytest

from provider_adapter_core import (
    AdapterError, GPU_CONTROL_REPOSITORY, HF_WORKLOAD, KAGGLE_WORKLOAD,
    MODAL_GPU_IMAGE_DIGEST, MODAL_GPU_SOURCE_SHA, MODAL_GPU_WORKLOAD, ProviderAdapter, REPOSITORY,
    SOURCE_SHA, prepare,
)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def provider_evidence():
    value = {"schema_version": 1, "workspace": "unjuno", "environment": "main",
        "usage_limit_usd": "30.00", "credits_used_usd": "0.15", "charges_usd": "0.00",
        "gpu": "T4", "hourly_price_usd": "0.000164", "price_source": "https://modal.com/pricing",
        "verified_at": 900, "expires_at": 1200}
    return {**value, "evidence_id": hashlib.sha256(canonical(value)).hexdigest()}


def provider_evidence_at_usage(credits_used_usd: str):
    value = {key: item for key, item in provider_evidence().items() if key != "evidence_id"}
    value["credits_used_usd"] = credits_used_usd
    return {**value, "evidence_id": hashlib.sha256(canonical(value)).hexdigest()}


class FakeBackend:
    def __init__(self, provider):
        self.provider = provider
        self.started = 0
        self.reconciled = None

    def reconcile(self, run):
        return self.reconciled

    def start(self, run):
        self.started += 1
        return {"provider": self.provider, "run_id": run["id"],
                "plan_fingerprint": run["fingerprint"], "opaque": "handle"}

    def capture(self, handle):
        return SimpleNamespace(state="succeeded", result={"provider": self.provider, "gpu_used": True})

    def cleanup(self, handle):
        return None

    def is_clean(self, handle):
        return True

    def cancel(self, handle):
        return None


def prepared(workload=KAGGLE_WORKLOAD, parameters=None, runtime=300):
    return prepare("owner-1", {
        "workload": workload, "repository": REPOSITORY, "commit": SOURCE_SHA,
        "parameters": parameters or {}, "runtime_seconds": runtime,
        "max_cost_usd": "0", "idempotency_key": "adapter-test-001",
    })


def submission(prepared_value):
    state = prepared_value["machine_state"]
    return {
        "run_id": state["run_id"], "plan_fingerprint": state["plan_fingerprint"],
        "approved_plan": prepared_value["approved_plan"],
        "authorization": {"authorization_id": "a" * 32,
            "source": "chatgpt_mcp_write_confirmation", "authorized_at": 990, "expires_at": 1100},
    }


def test_prepare_is_owner_bound_deterministic_and_free_only():
    first = prepared()
    second = prepared()
    other = prepare("owner-2", {
        "workload": KAGGLE_WORKLOAD, "repository": REPOSITORY, "commit": SOURCE_SHA,
        "parameters": {}, "runtime_seconds": 300, "max_cost_usd": "0",
        "idempotency_key": "adapter-test-001",
    })
    assert first == second
    assert first["machine_state"]["run_id"] != other["machine_state"]["run_id"]
    assert first["approved_plan"]["paid_fallback_allowed"] is False
    assert first["approved_plan"]["known_cost_usd"] == "0"
    assert hashlib.sha256(canonical(first["approved_plan"])).hexdigest() == first["machine_state"]["plan_fingerprint"]


def test_submit_reconciles_kaggle_before_create_and_returns_handle():
    kaggle = FakeBackend("kaggle")
    value = prepared()
    args = submission(value)
    kaggle.reconciled = {"provider": "kaggle", "run_id": args["run_id"],
                         "plan_fingerprint": args["plan_fingerprint"]}
    result = ProviderAdapter(kaggle, FakeBackend("huggingface_space"), clock=lambda: 1000).submit("owner-1", args)
    assert kaggle.started == 0
    assert result["machine_state"]["provider_handle"] == kaggle.reconciled


def test_submission_validation_has_no_provider_side_effect():
    kaggle = FakeBackend("kaggle")
    value = prepared()
    args = submission(value)
    adapter = ProviderAdapter(kaggle, FakeBackend("huggingface_space"), clock=lambda: 1000)
    run = adapter.validate_submission("owner-1", args)
    assert run["id"] == args["run_id"]
    assert run["fingerprint"] == args["plan_fingerprint"]
    assert kaggle.started == 0
    result = adapter.submit_validated(run)
    assert result["machine_state"]["provider_handle"]["run_id"] == args["run_id"]
    assert kaggle.started == 1


def test_modified_plan_and_expired_authorization_are_rejected():
    value = prepared()
    args = submission(value)
    args["approved_plan"]["runtime_seconds"] = 301
    with pytest.raises(AdapterError, match="plan_or_authorization_invalid"):
        ProviderAdapter(FakeBackend("kaggle"), None, clock=lambda: 1000).submit("owner-1", args)

    clean = submission(prepared())
    with pytest.raises(AdapterError, match="plan_or_authorization_invalid"):
        ProviderAdapter(FakeBackend("kaggle"), None, clock=lambda: 1000).submit("owner-2", clean)


def test_huggingface_artifact_reference_is_fixed_and_bounded():
    parameters = {"artifact_repo_id": "Unjuno/gpu-control-orbitune-artifacts",
        "artifact_revision": "b" * 40, "artifact_path": f"runs/{'c' * 32}/orbitune-output.zip",
        "artifact_sha256": "d" * 64}
    result = prepared(HF_WORKLOAD, parameters, 30)
    assert result["approved_plan"]["provider"] == "huggingface_space"
    parameters["artifact_repo_id"] = "attacker/repo"
    with pytest.raises(AdapterError, match="invalid_arguments"):
        prepared(HF_WORKLOAD, parameters, 30)


def test_kaggle_plan_pins_the_reviewed_staged_bundle_digest():
    """Keep the adapter manifest aligned with the exact staged workload bytes."""
    plan = prepared()["approved_plan"]
    assert plan["image_digest"] == (
        "sha256:09742cdf89ec6646e0a227bfd88252aed7b7a44a854899d8bd3eea8da6a9f8bd"
    )
    assert plan["workload_manifest"]["image_digest"] == plan["image_digest"]


def test_terminal_observation_requires_cleanup_and_kaggle_cancel_is_blocked():
    backend = FakeBackend("kaggle")
    adapter = ProviderAdapter(backend, None, clock=lambda: 1000)
    value = prepared()
    args = submission(value)
    submitted = adapter.submit("owner-1", args)
    handle = submitted["machine_state"]["provider_handle"]
    observed = adapter.observe("experiment_status", {"run_id": args["run_id"], "provider_handle": handle})
    assert observed["machine_state"]["state"] == "succeeded"
    assert observed["machine_state"]["result"]["cleanup_state"] == "confirmed"
    cancelled = adapter.observe("experiment_cancel", {"run_id": args["run_id"], "provider_handle": handle})
    assert cancelled["blocking_reason"] == "CANCELLATION_UNSUPPORTED"


def test_external_artifact_is_read_only_through_exact_run_binding():
    class FakeArtifactStore:
        def read(self, reference, *, offset, max_bytes):
            assert reference["run_id"] == "f" * 32
            assert offset == 12
            assert max_bytes == 24
            return {"artifact_id": "orbitune-output.zip", "sha256": "a" * 64,
                    "size_bytes": 100, "offset": 12, "next_offset": 36,
                    "eof": False, "encoding": "base64", "full_file_verified": True,
                    "verification_method": "exact_revision_size_and_sha256", "data": "YWJj"}

    adapter = ProviderAdapter(FakeBackend("kaggle"), None, artifact_store=FakeArtifactStore())
    handle = {"provider": "kaggle", "run_id": "f" * 32,
              "plan_fingerprint": "e" * 64}
    reference = {"run_id": "f" * 32}
    value = adapter.invoke("owner-1", "experiment_artifact", {
        "run_id": "f" * 32, "artifact_id": "orbitune-output.zip",
        "offset": 12, "length": 24, "provider_handle": handle,
        "external_artifact": reference,
    })
    assert value["status"] == "ok"
    assert value["machine_state"]["sha256"] == "a" * 64
    assert value["machine_state"]["full_file_verified"] is True
    with pytest.raises(AdapterError, match="artifact_reference_mismatch"):
        adapter.invoke("owner-1", "experiment_artifact", {
            "run_id": "f" * 32, "artifact_id": "orbitune-output.zip",
            "offset": 12, "length": 24, "provider_handle": handle,
            "external_artifact": {"run_id": "0" * 32},
        })


def test_stalled_kaggle_is_blocked_without_cleanup_or_replacement():
    backend = FakeBackend("kaggle")
    backend.capture = lambda _handle: SimpleNamespace(state="running", result={
        "provider": "kaggle", "lifecycle_condition": "provider_deadline_exceeded",
        "cleanup_state": "unconfirmed", "replacement_submission_allowed": False,
    })
    backend.cleanup = lambda _handle: pytest.fail("non-terminal Kaggle run must not be cleaned")
    adapter = ProviderAdapter(backend, None, clock=lambda: 1000)
    value = prepared()
    args = submission(value)
    handle = adapter.submit("owner-1", args)["machine_state"]["provider_handle"]

    observed = adapter.observe(
        "experiment_status", {"run_id": args["run_id"], "provider_handle": handle})

    assert observed["status"] == "blocked"
    assert observed["blocking_reason"] == "PROVIDER_DEADLINE_EXCEEDED_CLEANUP_UNCONFIRMED"
    assert observed["machine_state"]["state"] == "running"
    assert observed["machine_state"]["result"]["replacement_submission_allowed"] is False
    assert observed["next_allowed_actions"] == ["experiment_status"]


def test_approved_runtime_upgrades_legacy_kaggle_handle_before_observation():
    backend = FakeBackend("kaggle")
    captured = []
    backend.capture = lambda handle: (
        captured.append(handle) or SimpleNamespace(state="running", result=None))
    adapter = ProviderAdapter(backend, None, clock=lambda: 1000)
    legacy = {"provider": "kaggle", "run_id": "f" * 32,
              "plan_fingerprint": "e" * 64, "opaque": "legacy"}

    observed = adapter.observe("experiment_status", {
        "run_id": "f" * 32, "provider_handle": legacy, "runtime_seconds": 300})

    assert observed["status"] == "pending"
    assert captured[0]["runtime_seconds"] == 300
    assert "runtime_seconds" not in legacy
    with pytest.raises(AdapterError, match="provider_handle_mismatch"):
        adapter.observe("experiment_status", {
            "run_id": "f" * 32,
            "provider_handle": {**legacy, "runtime_seconds": 120},
            "runtime_seconds": 300,
        })


def test_modal_gpu_plan_is_fixed_paid_bounded_and_owner_bound():
    value = prepare("owner-1", {
        "workload": MODAL_GPU_WORKLOAD, "repository": GPU_CONTROL_REPOSITORY,
        "commit": MODAL_GPU_SOURCE_SHA, "parameters": {}, "runtime_seconds": 30,
        "max_cost_usd": "0.01", "idempotency_key": "modal-gpu-test-001",
        "provider_evidence": provider_evidence(),
    })
    plan = value["approved_plan"]
    assert plan["provider"] == "modal_gpu"
    assert plan["cost_classification"] == "PAID_BOUNDED"
    assert plan["max_cost_usd"] == "0.01"
    assert plan["known_cost_usd"] is None
    assert plan["image_digest"] == MODAL_GPU_IMAGE_DIGEST
    assert plan["workload_manifest"]["gpu"] == "T4"
    assert plan["workload_manifest"]["network"] == "blocked"
    assert plan["workload_manifest"]["max_runtime_seconds"] == 30

    args = submission(value)
    modal_gpu = FakeBackend("modal_gpu")
    result = ProviderAdapter(None, None, modal_gpu, clock=lambda: 1000).submit("owner-1", args)
    assert result["machine_state"]["provider"] == "modal_gpu"
    assert modal_gpu.started == 1

    above_internal_project_limit = prepare("owner-1", {
        "workload": MODAL_GPU_WORKLOAD, "repository": GPU_CONTROL_REPOSITORY,
        "commit": MODAL_GPU_SOURCE_SHA, "parameters": {}, "runtime_seconds": 30,
        "max_cost_usd": "0.01", "idempotency_key": "modal-gpu-test-003",
        "provider_evidence": provider_evidence_at_usage("1.00"),
    })
    another_backend = FakeBackend("modal_gpu")
    ProviderAdapter(None, None, another_backend, clock=lambda: 1000).submit(
        "owner-1", submission(above_internal_project_limit))
    assert another_backend.started == 1

    exhausted_outer_limit = prepare("owner-1", {
        "workload": MODAL_GPU_WORKLOAD, "repository": GPU_CONTROL_REPOSITORY,
        "commit": MODAL_GPU_SOURCE_SHA, "parameters": {}, "runtime_seconds": 30,
        "max_cost_usd": "0.01", "idempotency_key": "modal-gpu-test-004",
        "provider_evidence": provider_evidence_at_usage("30.00"),
    })
    with pytest.raises(AdapterError, match="provider_evidence_expired_or_exhausted"):
        ProviderAdapter(None, None, FakeBackend("modal_gpu"), clock=lambda: 1000).submit(
            "owner-1", submission(exhausted_outer_limit))

    with pytest.raises(AdapterError, match="invalid_arguments"):
        prepare("owner-1", {
            "workload": MODAL_GPU_WORKLOAD, "repository": GPU_CONTROL_REPOSITORY,
            "commit": MODAL_GPU_SOURCE_SHA, "parameters": {}, "runtime_seconds": 30,
            "max_cost_usd": "1.00", "idempotency_key": "modal-gpu-test-002",
            "provider_evidence": provider_evidence(),
        })

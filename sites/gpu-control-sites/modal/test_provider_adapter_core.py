from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace

import pytest

from provider_adapter_core import (
    AdapterError, HF_WORKLOAD, KAGGLE_WORKLOAD, ProviderAdapter, REPOSITORY,
    SOURCE_SHA, prepare,
)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


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

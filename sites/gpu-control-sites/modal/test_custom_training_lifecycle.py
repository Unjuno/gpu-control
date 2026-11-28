import time
from types import SimpleNamespace

import pytest

from custom_training_lifecycle import dispatch
from custom_training_tool_args import lifecycle_arguments


class Store(dict):
    def put(self, key, value, *, skip_if_exists=False):
        if skip_if_exists and key in self:
            return False
        self[key] = value
        return True


def test_one_start_bound_to_owner_and_cancel_until_terminal():
    run = "a" * 32
    plan = {"run_id": run}
    args = {"run_id": run, "plan_fingerprint": "b" * 64, "plan": plan,
            "approved_plan": plan, "authorization_expires_at": int(time.time()) + 60}
    starts, cancels = [], []
    states = iter([{"state": "running"}, {"state": "cancelled", "cleanup": "confirmed"}])
    backend = SimpleNamespace(start=lambda plan, source_token=None: starts.append((plan, source_token)) or f"custom-training-{run}",
                              cancel=lambda handle: cancels.append(handle),
                              inspect=lambda *_: next(states))
    store = Store()
    def call(action, owner="owner"):
        bound = {**args, "approved_plan": plan}
        return dispatch(store, backend, owner, action, bound, validate=lambda *_: None, admission_enabled=True)
    assert call("submit") == {"state": "staging"}
    assert call("submit") == {"state": "staging"}
    with pytest.raises(ValueError, match="run_identity_mismatch"):
        call("status", "other")
    assert call("cancel") == {"state": "cancel_requested"}
    assert call("cancel") == {"state": "cancelled", "cleanup": "confirmed"}
    assert call("status") == {"state": "cancelled", "cleanup": "confirmed"}
    assert call("status") == {"state": "cancelled", "cleanup": "confirmed"}
    assert len(starts) == 1 and starts[0][1] is None and cancels == [f"custom-training-{run}"] * 2


def test_ambiguous_start_never_retries():
    run = "a" * 32
    plan = {"run_id": run}
    args = {"run_id": run, "plan_fingerprint": "b" * 64, "plan": plan,
            "approved_plan": plan, "authorization_expires_at": int(time.time()) + 60}
    attempts = []
    def start(_, source_token=None):
        attempts.append(1)
        raise TimeoutError()
    store = Store()
    backend = SimpleNamespace(start=start)
    with pytest.raises(TimeoutError):
        dispatch(store, backend, "owner", "submit", args, validate=lambda *_: None, admission_enabled=True)
    assert dispatch(store, backend, "owner", "submit", args, validate=lambda *_: None,
                    admission_enabled=True) == {"state": "uncertain"}
    assert attempts == [1]


def test_closed_admission_and_invalid_plan_never_claim_or_start():
    run = "a" * 32
    plan = {"run_id": run}
    args = {"run_id": run, "plan_fingerprint": "b" * 64, "plan": plan,
            "approved_plan": plan, "authorization_expires_at": int(time.time()) + 60}
    store = Store()
    backend = SimpleNamespace(start=lambda _: pytest.fail("must not start"))
    assert dispatch(store, backend, "owner", "submit", args, validate=lambda *_: None,
                    admission_enabled=False)["state"] == "blocked"
    def reject(*_):
        raise ValueError("invalid_budget")
    with pytest.raises(ValueError, match="invalid_budget"):
        dispatch(store, backend, "owner", "submit", args, validate=reject, admission_enabled=True)
    assert not store


def test_cleanup_must_be_confirmed_before_success_or_checkpoint():
    run = "a" * 32
    fingerprint = "b" * 64
    plan = {"run_id": run}
    args = {"run_id": run, "plan_fingerprint": fingerprint, "plan": plan,
            "approved_plan": plan, "authorization_expires_at": int(time.time()) + 60}
    backend = SimpleNamespace(start=lambda _, source_token=None: f"custom-training-{run}", cancel=lambda _: None,
        inspect=lambda *_: {"state": "succeeded", "cleanup": "pending"},
        checkpoint=lambda *_: pytest.fail("must not read before cleanup"))
    store = Store()
    dispatch(store, backend, "owner", "submit", args, validate=lambda *_: None, admission_enabled=True)
    status_args = {"run_id": run, "plan_fingerprint": fingerprint}
    assert dispatch(store, backend, "owner", "status", status_args,
                    validate=lambda *_: None, admission_enabled=True) == {
                        "state": "cleanup_pending", "execution_state": "succeeded"}


def test_declared_artifact_reads_require_success_and_confirmed_cleanup():
    run = "a" * 32
    fingerprint = "b" * 64
    plan = {"run_id": run}
    args = {"run_id": run, "plan_fingerprint": fingerprint, "plan": plan,
            "approved_plan": plan, "authorization_expires_at": int(time.time()) + 60}
    artifact_id = "c" * 64
    artifact = {"artifact_id": artifact_id, "path": "artifacts/result.csv",
                "size_bytes": 4, "sha256": "d" * 64}
    backend = SimpleNamespace(start=lambda *_args, **_kwargs: f"custom-training-{run}",
        cancel=lambda *_: None,
        inspect=lambda *_: {"state": "succeeded", "cleanup": "confirmed", "artifacts": [artifact]},
        artifact=lambda _run, _manifest, offset, maximum: {"offset": offset, "max_bytes": maximum})
    store = Store()
    dispatch(store, backend, "owner", "submit", args, validate=lambda *_: None, admission_enabled=True)
    result = dispatch(store, backend, "owner", "artifact", {
        "run_id": run, "plan_fingerprint": fingerprint, "artifact_id": artifact_id,
        "offset": 0, "max_bytes": 100}, validate=lambda *_: None, admission_enabled=True)
    assert result == {"state": "succeeded", "artifact_chunk": {"offset": 0, "max_bytes": 100}}
    with pytest.raises(ValueError, match="run_identity_mismatch"):
        dispatch(store, backend, "other-owner", "artifact", {
            "run_id": run, "plan_fingerprint": fingerprint, "artifact_id": artifact_id,
            "offset": 0, "max_bytes": 100}, validate=lambda *_: None, admission_enabled=True)


def test_cancel_during_cpu_staging_finishes_without_gpu_start():
    run = "a" * 32
    fingerprint = "b" * 64
    plan = {"run_id": run}
    args = {"run_id": run, "plan_fingerprint": fingerprint, "plan": plan,
            "approved_plan": plan, "authorization_expires_at": int(time.time()) + 60}
    starts, inspections, cancellations = [], [], []
    store = Store()

    def cancel(handle):
        assert store[f"custom-training:{run}"]["state"] == "cancel_requested"
        cancellations.append(handle)
        if len(cancellations) == 1:
            return {"state": "uncertain"}
        return {"state": "cancelled", "cleanup": "confirmed", "gpu_used": False}

    backend = SimpleNamespace(
        start=lambda *_args, **_kwargs: starts.append("stage") or f"custom-training-{run}",
        cancel=cancel,
        inspect=lambda *_args: inspections.append("inspect") or pytest.fail("cancel already completed"),
    )
    assert dispatch(store, backend, "owner", "submit", args, validate=lambda *_: None,
                    admission_enabled=True) == {"state": "staging"}
    status_args = {"run_id": run, "plan_fingerprint": fingerprint}
    assert dispatch(store, backend, "owner", "cancel", status_args, validate=lambda *_: None,
                    admission_enabled=True) == {"state": "cancel_requested"}
    assert dispatch(store, backend, "owner", "status", status_args, validate=lambda *_: None,
                    admission_enabled=True) == {
                        "state": "cancelled", "cleanup": "confirmed", "gpu_used": False}
    assert starts == ["stage"] and inspections == []
    assert cancellations == [f"custom-training-{run}"] * 2


def test_adapter_argument_projection_preserves_checkpoint_and_artifact_chunks():
    common = {"run_id": "a" * 32, "plan_fingerprint": "b" * 64, "approved_plan": {"run_id": "a" * 32},
              "offset": 128, "max_bytes": 4096}
    checkpoint = lifecycle_arguments("training_checkpoint", common)
    assert checkpoint == common
    artifact_args = {**common, "artifact_id": "c" * 64}
    assert lifecycle_arguments("training_artifact", artifact_args) == artifact_args
    assert lifecycle_arguments("training_status", common) == {
        "run_id": common["run_id"], "plan_fingerprint": common["plan_fingerprint"],
        "approved_plan": common["approved_plan"]}


def test_missing_journal_recovers_only_the_same_plan_without_starting_again():
    run = "a" * 32
    fingerprint = "b" * 64
    plan = {"run_id": run, "commit": "c" * 40}
    starts, inspections = [], []
    backend = SimpleNamespace(
        recover=lambda candidate: f"custom-training-{run}" if candidate == plan else None,
        start=lambda *_args, **_kwargs: starts.append("start") or pytest.fail("must not start"),
        inspect=lambda handle, candidate, cancelled: inspections.append((handle, candidate, cancelled)) or
            {"state": "succeeded", "cleanup": "confirmed", "gpu_used": True},
    )
    store = Store()
    result = dispatch(store, backend, "owner", "status", {
        "run_id": run, "plan_fingerprint": fingerprint, "approved_plan": plan,
    }, validate=lambda *_: None, admission_enabled=False)
    assert result["state"] == "succeeded"
    assert inspections == [(f"custom-training-{run}", plan, False)]
    assert starts == []
    assert store[f"custom-training:{run}"]["owner"] == "owner"


def test_missing_journal_without_recovery_evidence_is_uncertain_and_never_allocates():
    run = "a" * 32
    plan = {"run_id": run}
    starts = []
    backend = SimpleNamespace(recover=lambda _plan: None,
        start=lambda *_args, **_kwargs: starts.append(1))
    result = dispatch(Store(), backend, "owner", "status", {
        "run_id": run, "plan_fingerprint": "b" * 64, "approved_plan": plan,
    }, validate=lambda *_: None, admission_enabled=True)
    assert result == {"state": "uncertain"}
    assert starts == []


def test_uncertain_provider_observation_is_returned_without_caching_terminal_state():
    run = "a" * 32
    fingerprint = "b" * 64
    plan = {"run_id": run}
    args = {"run_id": run, "plan_fingerprint": fingerprint, "plan": plan,
            "approved_plan": plan, "authorization_expires_at": int(time.time()) + 60}
    states = iter([{"state": "uncertain", "cleanup": "unknown"},
                   {"state": "failed", "cleanup": "confirmed", "failure_code": "PROVIDER_FAILED"}])
    backend = SimpleNamespace(start=lambda *_args, **_kwargs: f"custom-training-{run}",
        cancel=lambda *_: None, inspect=lambda *_: next(states))
    store = Store()
    dispatch(store, backend, "owner", "submit", args, validate=lambda *_: None, admission_enabled=True)

    observed = dispatch(store, backend, "owner", "status", {
        "run_id": run, "plan_fingerprint": fingerprint}, validate=lambda *_: None, admission_enabled=True)
    assert observed == {"state": "uncertain", "cleanup": "unknown"}
    assert store[f"custom-training:{run}"]["state"] == "staging"
    assert "terminal" not in store[f"custom-training:{run}"]

    terminal = dispatch(store, backend, "owner", "status", {
        "run_id": run, "plan_fingerprint": fingerprint}, validate=lambda *_: None, admission_enabled=True)
    assert terminal == {"state": "failed", "cleanup": "confirmed", "failure_code": "PROVIDER_FAILED"}
    assert store[f"custom-training:{run}"]["terminal"] == terminal

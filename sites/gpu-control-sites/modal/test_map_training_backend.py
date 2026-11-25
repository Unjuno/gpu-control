from types import SimpleNamespace
import time

import modal
import pytest

from map_training_backend import MapTrainingBackend, dispatch_training_tool


class Store(dict):
    def put(self, key, value, *, skip_if_exists=False):
        if skip_if_exists and key in self:
            return False
        self[key] = value
        return True


def test_provider_rejects_bad_profile_before_claim_and_spawns_once(monkeypatch):
    source_sha = "a" * 40
    digest = "sha256:" + "b" * 64
    run_id = "c" * 32
    expires = int(time.time()) + 7 * 86400
    settings = {
        "SOURCE_SHA": source_sha, "IMAGE_DIGEST": digest, "RUNTIME_SECONDS": "120",
        "HOURLY_MICROUSD": "400000", "QUOTE_EXPIRES_AT": str(expires),
    }
    for key, value in settings.items():
        monkeypatch.setenv("MAP_TRAINING_" + key, value)
    plan = {"run_id": run_id, "repository": "unjuno/model-as-a-paper", "commit": source_sha,
            "image_digest": digest, "gpu": "L4", "gpu_count": 1, "runtime_seconds": 120,
            "max_cost_microusd": 100000, "hourly_microusd": 400000, "quote_expires_at": expires}
    starts = []

    def spawn(value):
        starts.append(value)
        return SimpleNamespace(object_id="fc-abcdefgh")

    backend = MapTrainingBackend(function_lookup=lambda: SimpleNamespace(spawn=spawn))
    store = Store()
    args = {"run_id": run_id, "plan_fingerprint": "d" * 64, "plan": plan}
    with pytest.raises(ValueError, match="training_quote_invalid"):
        dispatch_training_tool(store, backend, "owner", "training_submit",
                               {**args, "plan": {**plan, "hourly_microusd": 1}},
                               admission_enabled=True)
    assert not store and not starts
    for _ in range(2):
        assert dispatch_training_tool(store, backend, "owner", "training_submit", args,
                                      admission_enabled=True) == {"state": "running"}
    assert starts == [plan]
    with pytest.raises(ValueError, match="training_run_identity_mismatch"):
        dispatch_training_tool(store, backend, "other", "training_status", args,
                               admission_enabled=True)


def test_provider_wall_timeout_becomes_terminal():
    run_id = "c" * 32
    fingerprint = "d" * 64
    store = Store({f"map-training:{run_id}": {
        "owner": "owner", "fingerprint": fingerprint, "plan": {},
        "state": "running", "call_id": "fc-abcdefgh",
    }})
    calls = []

    def get(*, timeout):
        calls.append(timeout)
        if len(calls) == 1:
            raise modal.exception.TimeoutError()
        raise modal.exception.FunctionTimeoutError("provider details")

    backend = MapTrainingBackend(call_lookup=lambda _: SimpleNamespace(get=get))
    args = {"run_id": run_id, "plan_fingerprint": fingerprint}

    def status():
        return dispatch_training_tool(store, backend, "owner", "training_status", args,
                                      admission_enabled=False)

    assert status() == {"state": "running"}
    for _ in range(2):
        assert status() == {"state": "failed", "failure_code": "TRAINING_RUNTIME_LIMIT"}
    assert calls == [0, 0]

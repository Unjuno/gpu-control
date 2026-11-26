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


@pytest.mark.parametrize("native_image", [False, True])
def test_provider_rejects_bad_profile_before_claim_and_spawns_once(monkeypatch, native_image):
    source_sha = "a" * 40
    digest = "im-Abcdefgh1234" if native_image else "sha256:" + "b" * 64
    monkeypatch.delenv("MAP_TRAINING_MODAL_IMAGE_ID", raising=False)
    run_id = "c" * 32
    expires = int(time.time()) + 7 * 86400
    settings = {
        "SOURCE_SHA": source_sha, "IMAGE_DIGEST": digest, "RUNTIME_SECONDS": "120",
        "HOURLY_MICROUSD": "400000", "QUOTE_EXPIRES_AT": str(expires),
        "CONTROL_PLANE_SHA": "e" * 40,
    }
    for key, value in settings.items():
        monkeypatch.setenv("MAP_TRAINING_" + key, value)
    if native_image:
        monkeypatch.setenv("MAP_TRAINING_MODAL_IMAGE_ID", digest)
    plan = {"run_id": run_id, "repository": "unjuno/model-as-a-paper", "commit": source_sha,
            "image_digest": digest, "gpu": "L4", "gpu_count": 1, "runtime_seconds": 120,
            "max_cost_microusd": 100000, "hourly_microusd": 400000, "quote_expires_at": expires,
            "dataset": "papers", "run_name": "map44m", "steps": 100000,
            "provider": "modal", "provider_resource_id": "gpu-control-map-training/train_map"}
    starts = []

    def spawn(value):
        starts.append(value)
        return SimpleNamespace(object_id="fc-abcdefgh")

    backend = MapTrainingBackend(function_lookup=lambda: SimpleNamespace(spawn=spawn))
    store = Store()
    now = int(time.time())
    fingerprint = "d" * 64
    authorization = {"authorization_id": "f" * 32,
        "authorization_source": "chatgpt_mcp_write_confirmation", "authorization_reference": "a" * 64,
        "decision_record_id": f"training-plan:{run_id}:{fingerprint}", "authorized_by": "owner",
        "control_plane_sha": "e" * 40, "target_repository": plan["repository"],
        "target_sha": plan["commit"], "image_digest": plan["image_digest"], "provider": plan["provider"],
        "provider_resource_id": plan["provider_resource_id"], "gpu_count": plan["gpu_count"],
        "runtime_seconds": plan["runtime_seconds"], "max_cost_microusd": plan["max_cost_microusd"],
        "authorized_at": now, "expires_at": now + 60, "owner": "owner", "run_id": run_id,
        "plan_fingerprint": fingerprint}
    args = {"run_id": run_id, "plan_fingerprint": fingerprint, "plan": plan,
            "authorization": authorization, "authorization_expires_at": authorization["expires_at"]}
    with pytest.raises(ValueError, match="training_quote_invalid"):
        dispatch_training_tool(store, backend, "owner", "training_submit",
                               {**args, "plan": {**plan, "hourly_microusd": 1}},
                               admission_enabled=True)
    for invalid in ({"dataset": "../papers"}, {"run_name": "../run"}, {"steps": 0}):
        with pytest.raises(ValueError, match="training_parameters_invalid"):
            dispatch_training_tool(store, backend, "owner", "training_submit",
                                   {**args, "plan": {**plan, **invalid}},
                                   admission_enabled=True)
    expired = {**args, "authorization": {**authorization, "expires_at": now - 1},
               "authorization_expires_at": now - 1}
    assert dispatch_training_tool(store, backend, "owner", "training_submit", expired,
                                  admission_enabled=True) == {
        "state": "blocked", "reason": "TRAINING_AUTHORIZATION_EXPIRED",
    }
    assert not store and not starts
    for invalid in (
        {**authorization, "authorized_by": "other-owner"},
        {**authorization, "control_plane_sha": "f" * 40},
        {**authorization, "max_cost_microusd": 1000000},
        {**authorization, "provider_resource_id": "another-function"},
    ):
        with pytest.raises(ValueError, match="training_authorization_invalid"):
            dispatch_training_tool(store, backend, "owner", "training_submit",
                                   {**args, "authorization": invalid}, admission_enabled=True)
    assert not store and not starts
    for _ in range(2):
        assert dispatch_training_tool(store, backend, "owner", "training_submit", args,
                                      admission_enabled=True) == {"state": "running"}
    assert starts == [plan]
    with pytest.raises(ValueError, match="training_run_identity_mismatch"):
        dispatch_training_tool(store, backend, "other", "training_status", args,
                               admission_enabled=True)


@pytest.mark.parametrize("poll_timeout", [TimeoutError, modal.exception.TimeoutError])
@pytest.mark.parametrize("failure_code", ["TRAINING_RUNTIME_LIMIT", "TRAINING_WORKLOAD_FAILURE"])
def test_provider_failure_becomes_terminal(poll_timeout, failure_code):
    run_id = "c" * 32
    fingerprint = "d" * 64
    store = Store({f"map-training:{run_id}": {
        "owner": "owner", "fingerprint": fingerprint, "plan": {"run_id": run_id},
        "state": "running", "call_id": "fc-abcdefgh",
    }})
    calls = []

    def get(*, timeout):
        calls.append(timeout)
        if len(calls) == 1:
            raise poll_timeout()
        if failure_code == "TRAINING_RUNTIME_LIMIT":
            raise modal.exception.FunctionTimeoutError("provider details")
        return {"run_id": run_id, "failure_code": failure_code}

    backend = MapTrainingBackend(call_lookup=lambda _: SimpleNamespace(get=get))
    args = {"run_id": run_id, "plan_fingerprint": fingerprint}

    def status():
        return dispatch_training_tool(store, backend, "owner", "training_status", args,
                                      admission_enabled=False)

    assert status() == {"state": "running"}
    for _ in range(2):
        assert status() == {"state": "failed", "failure_code": failure_code}
    assert calls == [0, 0]


def test_cancel_request_is_retained_until_provider_reports_terminal():
    run_id = "c" * 32
    fingerprint = "d" * 64
    store = Store({f"map-training:{run_id}": {
        "owner": "owner", "fingerprint": fingerprint, "plan": {},
        "state": "running", "call_id": "fc-abcdefgh",
    }})
    cancellations = []
    observations = iter([{"state": "running"}, {"state": "cancelled"}])

    def cancel(call_id):
        cancellations.append(call_id)
        return {"state": "cancel_requested"}

    backend = SimpleNamespace(cancel=cancel, inspect=lambda *_: next(observations))
    args = {"run_id": run_id, "plan_fingerprint": fingerprint}

    def call(tool):
        return dispatch_training_tool(store, backend, "owner", tool, args,
                                      admission_enabled=False)

    assert call("training_cancel") == {"state": "cancel_requested"}
    assert call("training_cancel") == {"state": "cancel_requested"}
    assert call("training_status") == {"state": "cancel_requested"}
    assert call("training_status") == {"state": "cancelled"}
    assert cancellations == ["fc-abcdefgh"]


def test_timed_out_run_can_recover_a_checkpoint_without_relabeling_the_run():
    run_id = "c" * 32
    fingerprint = "d" * 64
    failure = {"state": "failed", "failure_code": "TRAINING_RUNTIME_LIMIT"}
    store = Store({f"map-training:{run_id}": {
        "owner": "owner", "fingerprint": fingerprint, "plan": {},
        "state": "failed", "call_id": "fc-abcdefgh", "terminal_result": failure,
    }})
    recovered = {"filename": "step-000000100-123abcde.pt", "size_bytes": 2, "sha256": "a" * 64}
    recoveries = []

    def recover(value):
        recoveries.append(value)
        return recovered

    backend = SimpleNamespace(recover_checkpoint=recover,
                              checkpoint=lambda *args: {"offset": args[-2]},
                              checkpoint_download=lambda run_id, manifest: {"path": f"/{run_id}/{manifest['filename']}"})
    args = {"run_id": run_id, "plan_fingerprint": fingerprint, "offset": 0, "max_bytes": 1}

    def tool(name):
        return dispatch_training_tool(store, backend, "owner", name, args, admission_enabled=False)

    for _ in range(2):
        assert tool("training_checkpoint") == {"state": "succeeded", "checkpoint_chunk": {"offset": 0}}
    assert tool("training_status") == {
        **failure, "checkpoint": recovered,
        "checkpoint_download": {"path": f"/{run_id}/{recovered['filename']}"},
    }
    assert recoveries == [run_id]


def test_gpu_job_leaves_time_to_finalize_checkpoint(monkeypatch, tmp_path):
    import map_training_job as job

    monkeypatch.setattr(job, "validate_map_plan", lambda *args, **kwargs:
                        ("a" * 32, 120, 250000, 1100000, "papers", "test-run", 5))
    monkeypatch.setattr(job, "checkpoint_manifest", lambda *_: {"size_bytes": 1})

    def train(_config, _corpus, output, *, device, seconds, steps, **_):
        assert device == "cuda"
        assert seconds == 75
        assert steps == 5
        output.mkdir()
        return {"device": "cuda:0", "steps": 5}

    corpus = tmp_path / "corpus"
    (corpus / "papers").mkdir(parents=True)
    runs = tmp_path / "runs"
    runs.mkdir()
    commits = []
    result = job.run_map_training(
        {"dataset": "papers", "run_name": "test-run", "steps": 5},
        source_sha="a" * 40, image_digest="im-Abcdefgh1234",
        hourly_microusd=1100000, quote_expires_at=0, config={},
        corpus_dir=corpus, runs_dir=runs, commit_volume=lambda: commits.append("commit"), train=train,
    )
    assert result["gpu_used"] and result["steps"] == 5
    assert result["dataset"] == "papers" and result["run_name"] == "test-run"
    assert (runs / ("a" * 32 + ".gpu-control-run.json")).exists()
    assert commits == ["commit", "commit"]
    assert result["checkpoint"] == {"size_bytes": 1}

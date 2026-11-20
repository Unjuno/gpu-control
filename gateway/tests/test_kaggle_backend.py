from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace

import pytest

from gpu_gateway.config import Settings
from gpu_gateway import kaggle_backend
from gpu_gateway.kaggle_backend import (
    KaggleBackend, KaggleCommandResult, KaggleQuotaError, _remaining_gpu_seconds,
)
from gpu_gateway.orbitune_workload import staged_bundle_digest


SOURCE_SHA = "a" * 40


class ScriptedRunner:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, argv):
        self.calls.append(tuple(argv))
        if not self.responses:
            raise AssertionError(f"unexpected Kaggle command: {argv}")
        return self.responses.pop(0)


def result(payload=None, *, stdout="", returncode=0):
    if payload is not None:
        stdout = json.dumps(payload)
    return KaggleCommandResult(returncode=returncode, stdout=stdout, stderr="")


def test_current_cli_quota_json_is_parsed_conservatively():
    payload = [
        {"resource": "GPU", "used": "3.00h", "remaining": "1.25h",
         "total": "4.25h", "refreshAt": "2026-11-20T00:00:00+00:00"},
        {"resource": "TPU", "used": "0.00h", "remaining": "20.00h",
         "total": "20.00h", "refreshAt": "2026-11-20T00:00:00+00:00"},
    ]
    # 1.25h minus the CLI's half-unit (0.005h) rounding uncertainty.
    assert _remaining_gpu_seconds(payload) == 4482


@pytest.mark.parametrize("payload", [
    [], [{"resource": "GPU", "remaining": "unknown"}],
    [{"resource": "GPU", "remaining": "1.00h"},
     {"resource": "gpu", "remaining": "1.00h"}],
])
def test_current_cli_quota_json_fails_closed_when_ambiguous(payload):
    assert _remaining_gpu_seconds(payload) is None


def run(tmp_path: Path):
    stage = tmp_path / "run-1"
    stage.mkdir()
    (stage / "train.py").write_text("print('registered workload')\n", encoding="utf-8")
    (stage / "orbitune").mkdir()
    (stage / "orbitune" / "__init__.py").write_text("", encoding="utf-8")
    image_digest = staged_bundle_digest(stage)
    (stage / "gpu-control-provenance.json").write_text(json.dumps({
        "source_sha": SOURCE_SHA, "image_digest": image_digest,
    }), encoding="utf-8")
    return {
        "id": "run-1",
        "fingerprint": "b" * 64,
        "started_at": 1000,
        "plan": {
            "runtime_seconds": 120,
            "image_digest": image_digest,
            "workload_manifest": {
                "provider": "kaggle",
                "provider_resource_id": "owner/orbitune-100-step",
                "source_sha": SOURCE_SHA,
                "gpu": "NvidiaTeslaT4",
                "image_digest": image_digest,
            },
        },
    }


def settings(tmp_path: Path):
    return Settings(
        enable_kaggle=True,
        kaggle_username="owner",
        kaggle_staging_root=str(tmp_path),
    )


def test_default_runner_passes_only_kaggle_and_process_environment(monkeypatch):
    captured = {}

    def fake_run(argv, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(returncode=0, stdout="{}", stderr="")

    monkeypatch.setenv("KAGGLE_API_TOKEN", "kaggle-token")
    monkeypatch.setenv("HF_ARTIFACT_WRITE_TOKEN", "hub-write-token")
    monkeypatch.setenv("HF_SPACE_READ_TOKEN", "hub-read-token")
    monkeypatch.setenv("RUNPOD_API_KEY", "runpod-token")
    monkeypatch.setenv("MODAL_TOKEN_SECRET", "modal-token")
    monkeypatch.setenv("GATEWAY_DATABASE_URL", "postgresql://secret")
    monkeypatch.setenv("GATEWAY_CANDIDATE_RECEIPT_SIGNING_KEY_B64", "signing-key")
    monkeypatch.setattr(kaggle_backend.subprocess, "run", fake_run)

    response = kaggle_backend._default_runner(("kaggle", "quota", "--format", "json"))

    assert response.returncode == 0
    assert captured["env"]["KAGGLE_API_TOKEN"] == "kaggle-token"
    for key in ("HF_ARTIFACT_WRITE_TOKEN", "HF_SPACE_READ_TOKEN", "RUNPOD_API_KEY", "MODAL_TOKEN_SECRET",
                "GATEWAY_DATABASE_URL", "GATEWAY_CANDIDATE_RECEIPT_SIGNING_KEY_B64"):
        assert key not in captured["env"]
    assert captured["shell"] is False


def test_prepare_is_offline_and_binds_owned_kernel_and_source(tmp_path):
    runner = ScriptedRunner([])
    backend = KaggleBackend(settings(tmp_path), runner=runner)

    prepared = backend.prepare(run(tmp_path))

    assert runner.calls == []
    assert prepared["kernel"] == "owner/orbitune-100-step"
    assert prepared["source_sha"] == SOURCE_SHA
    metadata = json.loads((tmp_path / "run-1" / "kernel-metadata.json").read_text())
    assert metadata["id"] == "owner/orbitune-100-step"
    assert metadata["enable_gpu"] is True
    assert metadata["machine_shape"] == "NvidiaTeslaT4"
    assert "accelerator" not in metadata


def test_prepare_recomputes_staged_bundle_digest_and_rejects_tampering(tmp_path):
    submitted = run(tmp_path)
    (tmp_path / "run-1" / "train.py").write_text("print('tampered')\n", encoding="utf-8")
    backend = KaggleBackend(settings(tmp_path), runner=ScriptedRunner([]))

    with pytest.raises(ValueError, match="image digest"):
        backend.prepare(submitted)


def test_reconciliation_metadata_projection_covers_security_controls():
    approved = {
        "id": "owner/orbitune-100-step", "title": "orbitune-100-step",
        "code_file": "train.py", "language": "python", "kernel_type": "script",
        "machine_shape": "NvidiaTeslaT4", "is_private": True,
        "enable_gpu": True, "enable_tpu": False, "enable_internet": False,
        "docker_image": "", "dataset_sources": [],
        "competition_sources": [], "kernel_sources": [], "model_sources": [],
    }
    remote = approved | {"is_private": "true", "enable_gpu": "true",
                         "enable_internet": "true"}

    approved_projection = KaggleBackend._metadata_projection(approved)
    remote_projection = KaggleBackend._metadata_projection(remote)

    assert approved_projection["enable_internet"] is False
    assert remote_projection["enable_internet"] is True
    assert remote_projection != approved_projection

    with pytest.raises(RuntimeError, match="custom image"):
        KaggleBackend._metadata_projection(approved | {"docker_image": "custom:latest"})


def test_start_checks_quota_and_persists_exact_new_version(tmp_path):
    runner = ScriptedRunner([
        result([{"resource": "GPU", "remaining": "1.00h"}]),
        result({"versionNumber": 7, "status": "complete"}),
        result(stdout="Kernel version 8 successfully pushed"),
        result({"versionNumber": 8, "status": "running"}),
    ])
    backend = KaggleBackend(settings(tmp_path), runner=runner)

    submitted = run(tmp_path)
    handle = backend.start(submitted)

    assert handle == {
        "provider": "kaggle", "owner": "owner", "kernel_slug": "orbitune-100-step",
        "version": 8, "source_sha": SOURCE_SHA, "run_id": "run-1",
        "plan_fingerprint": "b" * 64, "image_digest": submitted["plan"]["image_digest"],
        "started_at": 1000,
    }
    assert runner.calls == [
        ("kaggle", "quota", "--format", "json"),
        (sys.executable, "-m", "gpu_gateway.kaggle_bridge", "latest",
         "owner/orbitune-100-step"),
        ("kaggle", "kernels", "push", "-p", str(tmp_path / "run-1"),
         "--accelerator", "NvidiaTeslaT4", "--timeout", "120"),
        (sys.executable, "-m", "gpu_gateway.kaggle_bridge", "status",
         "owner/orbitune-100-step/8"),
    ]


@pytest.mark.parametrize("quota", [None, 0, 119])
def test_start_fails_closed_when_gpu_quota_is_unknown_or_insufficient(tmp_path, quota):
    payload = {"gpu": {}} if quota is None else {"gpu": {"remainingSeconds": quota}}
    runner = ScriptedRunner([result(payload)])
    backend = KaggleBackend(settings(tmp_path), runner=runner)

    with pytest.raises(KaggleQuotaError):
        backend.start(run(tmp_path))

    assert all(call[1:3] != ("kernels", "push") for call in runner.calls)


def test_ambiguous_push_is_not_retried_and_reconcile_discovers_version(tmp_path):
    class ReconcileRunner(ScriptedRunner):
        def __call__(self, argv):
            self.calls.append(tuple(argv))
            response = self.responses.pop(0)
            if tuple(argv[1:3]) == ("kernels", "pull"):
                target = Path(argv[argv.index("-p") + 1])
                source = tmp_path / "run-1"
                shutil.copytree(source / "orbitune", target / "orbitune")
                shutil.copyfile(source / "train.py", target / "train.py")
                shutil.copyfile(source / "gpu-control-provenance.json",
                                target / "gpu-control-provenance.json")
                shutil.copyfile(source / "kernel-metadata.json",
                                target / "kernel-metadata.json")
            return response

    runner = ReconcileRunner([
        result([{"resource": "GPU", "remaining": "1.00h"}]),
        result({"versionNumber": 7, "status": "complete"}),
        result(stdout="connection closed", returncode=1),
        result({"versionNumber": 8, "status": "running"}),
        result(stdout="downloaded"),
    ])
    backend = KaggleBackend(settings(tmp_path), runner=runner)
    submitted = run(tmp_path)

    with pytest.raises(RuntimeError, match="outcome unknown"):
        backend.start(submitted)
    handle = backend.reconcile(submitted)

    assert handle["version"] == 8
    assert sum(call[1:3] == ("kernels", "push") for call in runner.calls) == 1
    assert sum(call[1:3] == ("kernels", "pull") for call in runner.calls) == 1


@pytest.mark.parametrize("runtime", [None, True, 0, 3601, "120"])
def test_start_rejects_invalid_runtime_before_provider_call(tmp_path, runtime):
    runner = ScriptedRunner([])
    backend = KaggleBackend(settings(tmp_path), runner=runner)
    submitted = run(tmp_path)
    submitted["plan"]["runtime_seconds"] = runtime

    with pytest.raises(ValueError, match="runtime limit"):
        backend.start(submitted)

    assert runner.calls == []


def test_logs_are_bounded_and_cancel_is_not_advertised(tmp_path):
    runner = ScriptedRunner([result(stdout="x" * 100)])
    backend = KaggleBackend(settings(tmp_path), runner=runner, max_output_bytes=16)
    handle = {"provider": "kaggle", "owner": "owner", "kernel_slug": "k", "version": 3,
              "source_sha": SOURCE_SHA}

    logs, truncated = backend.logs(handle)

    assert logs == "x" * 16
    assert truncated is True
    assert backend.capabilities()["cancellation_supported"] is False
    with pytest.raises(NotImplementedError):
        backend.cancel(handle)


def test_capture_downloads_exact_version_and_normalizes_gpu_result(tmp_path):
    output = tmp_path / "run-1" / "output-v8" / "gpu-control-output"

    class OutputRunner(ScriptedRunner):
        def __call__(self, argv):
            self.calls.append(tuple(argv))
            response = self.responses.pop(0)
            if tuple(argv[1:3]) == ("kernels", "output"):
                output.mkdir(parents=True)
                raw = {
                    "status": "succeeded", "exit_status": 0, "source_sha": SOURCE_SHA,
                    "gpu_name": "Tesla T4", "elapsed_seconds": 12.5,
                    "steps": 100, "first_loss": 4.0, "final_loss": 2.0,
                    "checkpoint_sha256": "47320987f9a49d5b00119b960f247a956773f57543982b8bfcb6da5bb3afd9ef",
                    "evaluation": {"validation_loss": 2.25},
                }
                (output / "result.json").write_text(json.dumps(raw), encoding="utf-8")
                (output / "training-config.json").write_text("{}", encoding="utf-8")
                (output / "evaluation.json").write_text("{}", encoding="utf-8")
                (output / "checkpoint.pt").write_bytes(b"checkpoint")
            return response

    runner = OutputRunner([
        result({"status": "complete", "versionNumber": 8}),
        result(stdout="finished"),
        result(stdout="downloaded"),
    ])
    backend = KaggleBackend(settings(tmp_path), runner=runner)
    handle = {
        "provider": "kaggle", "owner": "owner", "kernel_slug": "orbitune-100-step",
        "version": 8, "source_sha": SOURCE_SHA, "run_id": "run-1",
        "plan_fingerprint": "b" * 64, "image_digest": "sha256:" + "c" * 64,
        "started_at": 1000,
    }

    observation = backend.capture(handle)

    assert observation.state == "succeeded"
    assert observation.result["gpu_used"] is True
    assert observation.result["device"] == "Tesla T4"
    assert observation.result["metrics"] == {
        "steps": 100, "first_loss": 4.0, "final_loss": 2.0,
        "validation_loss": 2.25,
    }
    assert observation.result["checksum"] == "47320987f9a49d5b00119b960f247a956773f57543982b8bfcb6da5bb3afd9ef"
    assert runner.calls[-1] == (
        "kaggle", "kernels", "output", "owner/orbitune-100-step/8",
        "-p", str(tmp_path / "run-1" / "output-v8"), "--force",
    )

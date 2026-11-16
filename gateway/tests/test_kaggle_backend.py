from __future__ import annotations

import json
from pathlib import Path

import pytest

from gpu_gateway.config import Settings
from gpu_gateway.kaggle_backend import KaggleBackend, KaggleCommandResult, KaggleQuotaError


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


def run(tmp_path: Path):
    stage = tmp_path / "run-1"
    stage.mkdir()
    (stage / "train.py").write_text("print('registered workload')\n", encoding="utf-8")
    return {
        "id": "run-1",
        "fingerprint": "b" * 64,
        "plan": {
            "runtime_seconds": 120,
            "workload_manifest": {
                "provider": "kaggle",
                "provider_resource_id": "owner/orbitune-100-step",
                "source_sha": SOURCE_SHA,
                "gpu": "NvidiaTeslaT4",
            },
        },
    }


def settings(tmp_path: Path):
    return Settings(
        enable_kaggle=True,
        kaggle_username="owner",
        kaggle_staging_root=str(tmp_path),
    )


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
    assert metadata["accelerator"] == "NvidiaTeslaT4"


def test_start_checks_quota_and_persists_exact_new_version(tmp_path):
    runner = ScriptedRunner([
        result({"gpu": {"remainingSeconds": 3600}}),
        result({"versionNumber": 7, "status": "complete"}),
        result(stdout="Kernel version 8 successfully pushed"),
        result({"versionNumber": 8, "status": "running"}),
    ])
    backend = KaggleBackend(settings(tmp_path), runner=runner)

    handle = backend.start(run(tmp_path))

    assert handle == {
        "provider": "kaggle", "owner": "owner", "kernel_slug": "orbitune-100-step",
        "version": 8, "source_sha": SOURCE_SHA,
    }
    assert runner.calls == [
        ("kaggle", "quota", "--format", "json"),
        ("kaggle", "kernels", "status", "owner/orbitune-100-step", "--format", "json"),
        ("kaggle", "kernels", "push", "-p", str(tmp_path / "run-1")),
        ("kaggle", "kernels", "status", "owner/orbitune-100-step", "--format", "json"),
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
    runner = ScriptedRunner([
        result({"gpu": {"remainingSeconds": 3600}}),
        result({"versionNumber": 7, "status": "complete"}),
        result(stdout="connection closed", returncode=1),
        result({"versionNumber": 8, "status": "running"}),
    ])
    backend = KaggleBackend(settings(tmp_path), runner=runner)
    submitted = run(tmp_path)

    with pytest.raises(RuntimeError, match="outcome unknown"):
        backend.start(submitted)
    handle = backend.reconcile(submitted)

    assert handle["version"] == 8
    assert sum(call[1:3] == ("kernels", "push") for call in runner.calls) == 1


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

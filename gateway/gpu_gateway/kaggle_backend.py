"""Fail-closed Kaggle Kernel execution through the official CLI.

Only operator-registered plans reach this module.  It never accepts arbitrary
CLI flags, never retries a push, and keeps a small non-secret reconciliation
journal beside the trusted staging directory before provider submission.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
import subprocess
from typing import Any, Callable, Mapping

from .backends import Observation, bounded_text
from .config import Settings


_KERNEL_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9_-]{0,49})/([a-z0-9][a-z0-9-]{0,49})$")
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class KaggleQuotaError(RuntimeError):
    pass


@dataclass(frozen=True)
class KaggleCommandResult:
    returncode: int
    stdout: str
    stderr: str


def _default_runner(argv: tuple[str, ...]) -> KaggleCommandResult:
    completed = subprocess.run(
        argv, shell=False, capture_output=True, text=True, timeout=60, check=False,
    )
    return KaggleCommandResult(completed.returncode, completed.stdout, completed.stderr)


def _duration_seconds(value: object) -> int | None:
    if type(value) is int and value >= 0:
        return value
    if isinstance(value, str) and re.fullmatch(r"\d+(?:\.\d+)?s", value):
        return int(float(value[:-1]))
    return None


def _remaining_gpu_seconds(payload: object) -> int | None:
    """Accept reviewed CLI JSON shapes and reject everything else as unknown."""
    if not isinstance(payload, Mapping):
        return None
    gpu = payload.get("gpu")
    if isinstance(gpu, Mapping):
        direct = _duration_seconds(gpu.get("remainingSeconds"))
        if direct is not None:
            return direct
    for key, value in payload.items():
        if isinstance(value, Mapping):
            label = " ".join(str(value.get(name, "")) for name in ("type", "name", "acceleratorType"))
            if "gpu" in (str(key) + " " + label).lower():
                total = _duration_seconds(value.get("totalTimeAllowed"))
                used = _duration_seconds(value.get("timeUsed"))
                if total is not None and used is not None:
                    return max(0, total - used)
            nested = _remaining_gpu_seconds(value)
            if nested is not None:
                return nested
        elif isinstance(value, list):
            for item in value:
                nested = _remaining_gpu_seconds(item)
                if nested is not None:
                    return nested
    return None


class KaggleBackend:
    """Recoverable, version-bound Kernel backend with no automatic resubmit."""

    def __init__(
        self,
        settings: Settings,
        *,
        runner: Callable[[tuple[str, ...]], KaggleCommandResult] | None = None,
        max_output_bytes: int | None = None,
    ) -> None:
        self.settings = settings
        self.runner = runner or _default_runner
        self.max_output_bytes = max_output_bytes or settings.max_output_bytes

    def _command(self, *args: str) -> KaggleCommandResult:
        result = self.runner(("kaggle", *args))
        if not isinstance(result, KaggleCommandResult):
            raise TypeError("Kaggle runner returned an invalid result")
        return result

    def _manifest(self, run: Mapping[str, Any]) -> tuple[str, str, str, str]:
        try:
            manifest = (run["plan"].get("workload_manifest") or
                        run["registered_workload_manifest"])
            kernel = manifest["provider_resource_id"]
            source_sha = manifest["source_sha"]
            accelerator = manifest["gpu"]
        except (KeyError, TypeError) as exc:
            raise ValueError("Kaggle plan is missing its registered manifest") from exc
        match = _KERNEL_RE.fullmatch(kernel) if isinstance(kernel, str) else None
        if manifest.get("provider") != "kaggle" or match is None:
            raise ValueError("Kaggle workload requires a canonical owner/kernel slug")
        owner, slug = match.groups()
        if owner.lower() != self.settings.kaggle_username.lower():
            raise ValueError("Kaggle kernel must be owned by the configured account")
        if not isinstance(source_sha, str) or _SHA_RE.fullmatch(source_sha) is None:
            raise ValueError("Kaggle workload requires a full source SHA")
        if accelerator not in {"NvidiaTeslaT4", "NvidiaL4", "NvidiaL4X1"}:
            raise ValueError("Kaggle accelerator is not in the reviewed free-GPU allowlist")
        return owner, slug, source_sha, accelerator

    def _stage(self, run: Mapping[str, Any]) -> Path:
        run_id = run.get("id")
        if not isinstance(run_id, str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", run_id) is None:
            raise ValueError("Kaggle run id is invalid")
        root = Path(self.settings.kaggle_staging_root).resolve()
        stage = (root / run_id).resolve()
        if stage.parent != root:
            raise ValueError("trusted Kaggle staging directory is unavailable")
        if not stage.exists() and self.settings.kaggle_source_cache_root:
            from .orbitune_workload import stage_orbitune_checkout
            _owner, _slug, source_sha, _accelerator = self._manifest(run)
            checkout = Path(self.settings.kaggle_source_cache_root).resolve() / source_sha
            stage_orbitune_checkout(checkout, stage, expected_sha=source_sha)
        if not stage.is_dir():
            raise ValueError("trusted Kaggle staging directory is unavailable")
        return stage

    def prepare(self, run: Mapping[str, Any]) -> dict[str, object]:
        owner, slug, source_sha, accelerator = self._manifest(run)
        stage = self._stage(run)
        metadata = {
            "id": f"{owner}/{slug}",
            "title": slug,
            "code_file": "train.py",
            "language": "python",
            "kernel_type": "script",
            "is_private": True,
            "enable_gpu": True,
            "enable_internet": False,
            "accelerator": accelerator,
            "dataset_sources": [],
            "competition_sources": [],
            "kernel_sources": [],
        }
        (stage / "kernel-metadata.json").write_text(
            json.dumps(metadata, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8",
        )
        return {"kernel": f"{owner}/{slug}", "source_sha": source_sha, "stage": str(stage)}

    def _json(self, result: KaggleCommandResult, label: str) -> Mapping[str, Any]:
        if result.returncode != 0:
            raise RuntimeError(f"Kaggle {label} failed")
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Kaggle {label} returned invalid JSON") from exc
        if not isinstance(payload, Mapping):
            raise RuntimeError(f"Kaggle {label} returned an invalid object")
        return payload

    def _status(self, kernel: str) -> Mapping[str, Any]:
        return self._json(
            self._command("kernels", "status", kernel, "--format", "json"), "status",
        )

    @staticmethod
    def _version(status: Mapping[str, Any]) -> int:
        version = status.get("versionNumber", status.get("version"))
        if type(version) is not int or version < 1:
            raise RuntimeError("Kaggle status did not identify an exact version")
        return version

    def start(self, run: dict) -> dict:
        if not self.settings.enable_kaggle:
            raise RuntimeError("Kaggle submission is disabled")
        prepared = self.prepare(run)
        quota = self._json(self._command("quota", "--format", "json"), "quota")
        remaining = _remaining_gpu_seconds(quota)
        required = run.get("plan", {}).get("runtime_seconds")
        if type(required) is not int or remaining is None or remaining < required:
            raise KaggleQuotaError("Kaggle GPU quota is unknown or insufficient")
        baseline = self._version(self._status(str(prepared["kernel"])))
        journal = {
            "kernel": prepared["kernel"], "source_sha": prepared["source_sha"],
            "baseline_version": baseline,
        }
        Path(str(prepared["stage"]), ".gpu-control-submission.json").write_text(
            json.dumps(journal, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8",
        )
        pushed = self._command("kernels", "push", "-p", str(prepared["stage"]))
        if pushed.returncode != 0:
            raise RuntimeError("Kaggle submission outcome unknown")
        current = self._status(str(prepared["kernel"]))
        version = self._version(current)
        if version <= baseline:
            raise RuntimeError("Kaggle submission outcome unknown")
        owner, slug = str(prepared["kernel"]).split("/", 1)
        return {"provider": "kaggle", "owner": owner, "kernel_slug": slug,
                "version": version, "source_sha": prepared["source_sha"]}

    def start_candidate_bound(self, run: dict) -> dict:
        owner, slug, _source_sha, _accelerator = self._manifest(run)
        binding = run.get("plan", {}).get("selection_binding")
        if not isinstance(binding, Mapping) or binding.get("resource_id") != f"{owner}/{slug}":
            raise ValueError("Kaggle candidate binding does not match the registered Kernel")
        return self.start(run)

    def reconcile(self, run: dict) -> dict | None:
        prepared = self.prepare(run)
        journal_path = Path(str(prepared["stage"]), ".gpu-control-submission.json")
        if not journal_path.is_file():
            return None
        journal = json.loads(journal_path.read_text(encoding="utf-8"))
        if journal.get("kernel") != prepared["kernel"] or journal.get("source_sha") != prepared["source_sha"]:
            raise RuntimeError("Kaggle reconciliation journal does not match the run")
        baseline = journal.get("baseline_version")
        current = self._status(str(prepared["kernel"]))
        version = self._version(current)
        if type(baseline) is not int or version <= baseline:
            return None
        owner, slug = str(prepared["kernel"]).split("/", 1)
        return {"provider": "kaggle", "owner": owner, "kernel_slug": slug,
                "version": version, "source_sha": prepared["source_sha"]}

    def inspect(self, handle: dict) -> Observation:
        ref = f'{handle["owner"]}/{handle["kernel_slug"]}/{handle["version"]}'
        status = self._status(ref)
        state = str(status.get("status", "")).lower()
        if state in {"running", "queued", "pending"}:
            return Observation("running")
        logs, truncated = self.logs(handle)
        succeeded = state in {"complete", "completed", "succeeded"}
        return Observation("succeeded" if succeeded else "failed", {
            "provider": "kaggle", "kernel": ref, "source_sha": handle["source_sha"],
            "logs": logs, "logs_truncated": truncated,
        })

    def capture(self, handle: dict) -> Observation:
        return self.inspect(handle)

    def validate_candidate_observation(self, run: dict, observation: Observation) -> bool:
        if observation.state == "running" or not isinstance(observation.result, Mapping):
            return False
        owner, slug, source_sha, _accelerator = self._manifest(run)
        kernel = observation.result.get("kernel")
        return (observation.result.get("provider") == "kaggle" and
                observation.result.get("source_sha") == source_sha and
                isinstance(kernel, str) and kernel.startswith(f"{owner}/{slug}/"))

    def cleanup(self, handle: dict) -> None:
        if self.inspect(handle).state == "running":
            raise RuntimeError("Kaggle Kernel is not terminal; cleanup cannot be proven")

    def is_clean(self, handle: dict) -> bool:
        return self.inspect(handle).state != "running"

    def logs(self, handle: Mapping[str, Any]) -> tuple[str, bool]:
        ref = f'{handle["owner"]}/{handle["kernel_slug"]}/{handle["version"]}'
        result = self._command("kernels", "logs", ref)
        if result.returncode != 0:
            raise RuntimeError("Kaggle logs failed")
        return bounded_text((result.stdout,), self.max_output_bytes)

    def cancel(self, handle: dict) -> None:
        raise NotImplementedError("official Kaggle CLI does not provide reliable Kernel cancellation")

    def capabilities(self) -> dict[str, bool]:
        return {"cancellation_supported": False, "reconcile_without_create": True}

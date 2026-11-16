"""Fail-closed Kaggle Kernel execution through the official CLI.

Only operator-registered plans reach this module.  It never accepts arbitrary
CLI flags, never retries a push, and keeps a small non-secret reconciliation
journal beside the trusted staging directory before provider submission.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import zipfile
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
        artifact_store: Any = None,
    ) -> None:
        self.settings = settings
        self.runner = runner or _default_runner
        self.max_output_bytes = max_output_bytes or settings.max_output_bytes
        self.artifact_store = artifact_store

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

    def quota_snapshot(self) -> Mapping[str, Any]:
        """Read-only official CLI quota snapshot for signed worker evidence."""
        return self._json(self._command("quota", "--format", "json"), "quota")

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
        quota = self.quota_snapshot()
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
        return self._handle(run, owner=owner, slug=slug, version=version,
                            source_sha=str(prepared["source_sha"]))

    @staticmethod
    def _handle(run: Mapping[str, Any], *, owner: str, slug: str, version: int,
                source_sha: str) -> dict[str, Any]:
        plan = run.get("plan")
        if not isinstance(plan, Mapping):
            raise ValueError("Kaggle run plan is unavailable")
        values = {
            "provider": "kaggle", "owner": owner, "kernel_slug": slug,
            "version": version, "source_sha": source_sha,
            "run_id": run.get("id"), "plan_fingerprint": run.get("fingerprint"),
            "image_digest": plan.get("image_digest"), "started_at": run.get("started_at"),
        }
        if (not isinstance(values["run_id"], str) or
                not isinstance(values["plan_fingerprint"], str) or
                not isinstance(values["image_digest"], str) or
                type(values["started_at"]) is not int):
            raise ValueError("Kaggle run identity is incomplete")
        return values

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
        return self._handle(run, owner=owner, slug=slug, version=version,
                            source_sha=str(prepared["source_sha"]))

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
        observation = self.inspect(handle)
        if observation.state != "succeeded":
            return observation
        ref = f'{handle["owner"]}/{handle["kernel_slug"]}/{handle["version"]}'
        stage_root = Path(self.settings.kaggle_staging_root).resolve()
        output_root = (stage_root / str(handle["run_id"]) / f'output-v{handle["version"]}').resolve()
        if output_root.parent.parent != stage_root:
            raise ValueError("Kaggle output directory escaped the trusted staging root")
        result_path = output_root / "gpu-control-output" / "result.json"
        if not result_path.is_file():
            output_root.mkdir(parents=True, exist_ok=True)
            downloaded = self._command(
                "kernels", "output", ref, "-p", str(output_root), "--force",
            )
            if downloaded.returncode != 0:
                raise RuntimeError("Kaggle output download failed")
        directory = output_root / "gpu-control-output"
        expected = {"result.json", "training-config.json", "evaluation.json", "checkpoint.pt"}
        if (not directory.is_dir() or any(item.is_symlink() for item in output_root.rglob("*")) or
                {item.name for item in directory.iterdir()} != expected or
                any(not item.is_file() for item in directory.iterdir())):
            raise RuntimeError("Kaggle output bundle is incomplete or unsafe")
        limits = {"result.json": 1_048_576, "training-config.json": 1_048_576,
                  "evaluation.json": 1_048_576, "checkpoint.pt": 64 * 1024 * 1024}
        if any((directory / name).stat().st_size < 1 or
               (directory / name).stat().st_size > limit for name, limit in limits.items()):
            raise RuntimeError("Kaggle output file exceeds its bound")
        try:
            raw = json.loads(result_path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("Kaggle result manifest is invalid") from exc
        checkpoint = directory / "checkpoint.pt"
        checkpoint_sha = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
        evaluation = raw.get("evaluation") if isinstance(raw, Mapping) else None
        required = {
            "status": "succeeded", "exit_status": 0, "source_sha": handle["source_sha"],
            "steps": 100, "checkpoint_sha256": checkpoint_sha,
        }
        if (not isinstance(raw, Mapping) or any(raw.get(k) != v for k, v in required.items()) or
                not isinstance(evaluation, Mapping)):
            raise RuntimeError("Kaggle result does not match the registered workload")
        numeric = (raw.get("elapsed_seconds"), raw.get("first_loss"), raw.get("final_loss"),
                   evaluation.get("validation_loss"))
        if any(not isinstance(value, (int, float)) or isinstance(value, bool) or
               not math.isfinite(value) for value in numeric):
            raise RuntimeError("Kaggle result metrics are invalid")
        if not isinstance(raw.get("gpu_name"), str) or not raw["gpu_name"].strip():
            raise RuntimeError("Kaggle result did not identify a GPU")
        elapsed = float(raw["elapsed_seconds"])
        external_artifacts = []
        if self.settings.hf_artifact_repositories:
            store = self.artifact_store
            if store is None:
                from .huggingface_artifacts import HuggingFaceArtifactStore
                store = HuggingFaceArtifactStore(self.settings)
            bundle = output_root / "orbitune-output.zip"
            with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_STORED) as archive:
                for name in sorted(expected):
                    info = zipfile.ZipInfo(f"gpu-control-output/{name}", (1980, 1, 1, 0, 0, 0))
                    info.external_attr = 0o100600 << 16
                    archive.writestr(info, (directory / name).read_bytes())
            external_artifacts.append(store.publish(
                bundle, repo_id=self.settings.hf_artifact_repositories[0],
                path_in_repo=f'runs/{handle["run_id"]}/orbitune-output.zip',
                run_id=handle["run_id"], source_sha=handle["source_sha"],
            ))
        result = {
            "schema_version": 2, "run_id": handle["run_id"],
            "source_sha": handle["source_sha"],
            "plan_fingerprint": handle["plan_fingerprint"], "provider": "kaggle",
            "image_digest": handle["image_digest"], "simulation": False,
            "gpu_used": True, "device": raw["gpu_name"], "exit_code": 0,
            "started_at": handle["started_at"],
            "finished_at": handle["started_at"] + max(1, math.ceil(elapsed)),
            "runtime_seconds": elapsed,
            "metrics": {"steps": 100, "first_loss": float(raw["first_loss"]),
                        "final_loss": float(raw["final_loss"]),
                        "validation_loss": float(evaluation["validation_loss"])},
            "checks": ["kaggle_exact_version", "checkpoint_reloaded"],
            "checksum": checkpoint_sha, "artifacts": [],
            "external_artifacts": external_artifacts, "known_cost_usd": "0",
            "cost_classification": "FREE_QUOTA", "cleanup_state": "pending",
            "logs": observation.result.get("logs", ""),
            "logs_truncated": observation.result.get("logs_truncated", False),
        }
        return Observation("succeeded", result)

    def validate_candidate_observation(self, run: dict, observation: Observation) -> bool:
        if observation.state == "running" or not isinstance(observation.result, Mapping):
            return False
        owner, slug, source_sha, _accelerator = self._manifest(run)
        return (observation.result.get("provider") == "kaggle" and
                observation.result.get("source_sha") == source_sha and
                observation.result.get("gpu_used") is True and
                observation.result.get("exit_code") == 0 and
                isinstance(observation.result.get("checksum"), str))

    def candidate_receipt_claims(self, handle: dict, observation: Observation) -> dict[str, Any]:
        if observation.state != "succeeded" or not isinstance(observation.result, Mapping):
            raise ValueError("Kaggle receipt requires a successful captured result")
        ref = f'{handle["owner"]}/{handle["kernel_slug"]}/{handle["version"]}'
        status = self._status(ref)
        if str(status.get("status", "")).lower() not in {"complete", "completed", "succeeded"}:
            raise RuntimeError("Kaggle Kernel is not terminal-successful")
        projection = {
            "kernel": ref,
            "version": handle["version"],
            "status": str(status.get("status", "")).lower(),
            "source_sha": handle["source_sha"],
            "device_model": observation.result.get("device"),
            "checkpoint_sha256": observation.result.get("checksum"),
        }
        return {
            "provider_execution_id": ref,
            "device_id": f'kaggle:{ref}:{observation.result.get("device")}',
            "evidence_source": "kaggle.cli.status-and-output",
            "provider_object_projection": projection,
        }

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

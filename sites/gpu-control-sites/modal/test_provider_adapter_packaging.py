"""Keep legacy Gateway services out of the deployed provider adapter image."""
from __future__ import annotations

import ast
from pathlib import Path


ADAPTER = Path(__file__).with_name("provider_adapter.py")
PROVIDER_RUNTIME_MODULES = {
    "contracts.py",
    "huggingface_artifacts.py",
    "huggingface_space_backend.py",
    "kaggle_backend.py",
    "kaggle_bridge.py",
    "orbitune_workload.py",
    "settings.py",
}


def test_adapter_packages_sites_owned_provider_runtime() -> None:
    source = ADAPTER.read_text(encoding="utf-8")
    assert "PROVIDER_MODULES" not in source
    assert "PROVIDER_MODULE_ROOT" not in source
    assert "gateway/gpu_gateway" not in source
    assert 'remote_path="/root/gateway"' not in source
    assert 'from provider_runtime.settings import ProviderSettings' in source
    assert '.add_local_dir(str(MODAL_ROOT), remote_path="/root/site-modal", copy=True)' in source
    assert "WORKLOAD_ROOT" not in source
    assert 'from workload_registry import WORKLOADS' in source
    assert (ADAPTER.with_name("workload_registry.py")).is_file()
    registry = (ADAPTER.parents[1] / "workloads" / "registry.json").read_text(encoding="utf-8")
    assert "orbitune-zero-gpu-eval-v1" in registry
    runtime = ADAPTER.with_name("provider_runtime")
    assert (runtime / "workloads" / "orbitune-kaggle-100" / "train.py").is_file()
    assert (runtime / "workloads" / "orbitune-zero-gpu-eval" / "app.py").is_file()


def test_packaged_modules_do_not_import_gateway_services_or_databases() -> None:
    module_root = ADAPTER.with_name("provider_runtime")
    forbidden = {
        "api", "auth", "database", "local_oauth", "migrations", "service",
        "store", "worker",
    }
    assert {path.name for path in module_root.glob("*.py")} >= PROVIDER_RUNTIME_MODULES
    for name in PROVIDER_RUNTIME_MODULES:
        tree = ast.parse((module_root / name).read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.rsplit(".", 1)[-1])
            elif isinstance(node, ast.Import):
                imported.update(alias.name.rsplit(".", 1)[-1] for alias in node.names)
        assert imported.isdisjoint(forbidden), f"{name} imports a legacy service module"


def test_modal_signed_payloads_share_one_canonical_byte_encoder() -> None:
    assert ADAPTER.with_name("canonical_json.py").is_file()
    for name in ("provider_adapter.py", "provider_adapter_core.py", "app.py"):
        source = ADAPTER.with_name(name).read_text(encoding="utf-8")
        assert "allow_nan=False" not in source, f"{name} duplicates the canonical JSON encoding policy"


def test_legacy_gateway_compatibility_uses_a_private_fixed_package() -> None:
    repository_root = ADAPTER.parents[3]
    helper = (repository_root / "gateway" / "gpu_gateway" / "_sites_provider_runtime.py").read_text(
        encoding="utf-8",
    )
    assert "sys.path.insert" not in helper
    assert '_PACKAGE = "gpu_gateway._provider_runtime"' in helper
    for dockerfile in ("Dockerfile", "Dockerfile.worker"):
        source = (repository_root / "gateway" / dockerfile).read_text(encoding="utf-8")
        assert "COPY sites/gpu-control-sites/modal/provider_runtime ./provider_runtime" in source


def test_slow_submission_uses_durable_idempotent_modal_spawn() -> None:
    source = ADAPTER.read_text(encoding="utf-8")
    core = ADAPTER.with_name("provider_adapter_core.py").read_text(encoding="utf-8")
    assert 'modal.Dict.from_name("gpu-control-provider-adapter-submissions"' in source
    assert "skip_if_exists=True" in source
    assert "provider_submit_worker.spawn(owner, arguments)" in source
    assert '"transport": "modal_spawn_v1"' in source
    assert 'actual = {**actual, "runtime_seconds": runtime_seconds}' in source
    assert "service.validate_submission(owner, arguments)" in source
    assert '"state": "uncertain"' in source
    assert 'reconcile_submission(run)' in source
    assert 'record.get("state") == "claimed"' in source
    assert 'provider_submit_worker_start_unknown' in source
    assert 'provider_submit_worker_timeout' in source
    assert "provider_submission_failure_state(failure_stage, code)" in source
    assert "data_volume.commit()" in source
    assert "def reconcile_submission(self, run" in core
    assert 'blocker="SUBMISSION_OUTCOME_UNCONFIRMED"' in core


def test_runpod_relay_uses_signed_tool_path_and_one_use_claim() -> None:
    source = ADAPTER.read_text(encoding="utf-8")
    assert '@api.post("/internal/runpod/v1/proxy")' not in source
    assert 'verified_tool == "runpod_queue_request"' in source
    assert 'claim_key = f"runpod:{run_id}"' in source
    assert 'skip_if_exists=True' in source
    assert 'record.get("job_id") != job_id' in source
    assert '"owner_binding_sha256": _submission_binding(owner)' in source
    assert 'operation == "receipt"' in source


def test_custom_training_adapter_forwards_bounded_artifact_chunk_arguments() -> None:
    source = ADAPTER.read_text(encoding="utf-8")
    assert "from custom_training_tool_args import lifecycle_arguments" in source
    assert "custom_args = lifecycle_arguments(tool, arguments, plan=plan)" in source

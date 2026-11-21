"""Keep legacy Gateway services out of the deployed provider adapter image."""
from __future__ import annotations

import ast
from pathlib import Path


ADAPTER = Path(__file__).with_name("provider_adapter.py")
ALLOWED_PROVIDER_MODULES = {
    "__init__.py",
    "backends.py",
    "config.py",
    "huggingface_artifacts.py",
    "huggingface_space_backend.py",
    "kaggle_backend.py",
    "kaggle_bridge.py",
    "orbitune_workload.py",
}


def test_adapter_packages_only_reviewed_provider_modules() -> None:
    source = ADAPTER.read_text(encoding="utf-8")
    tree = ast.parse(source)
    assignments = {
        node.targets[0].id: ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == "PROVIDER_MODULES"
    }

    assert set(assignments["PROVIDER_MODULES"]) == ALLOWED_PROVIDER_MODULES
    assert '.add_local_dir(str(GATEWAY_ROOT)' not in source
    assert 'remote_path="/root/gateway"' not in source
    assert "/root/provider-runtime" in source
    assert '.add_local_dir(str(WORKLOAD_ROOT), remote_path="/root/provider-runtime/workloads", copy=True)' in source


def test_packaged_modules_do_not_import_gateway_services_or_databases() -> None:
    repository_root = ADAPTER.parents[3]
    module_root = repository_root / "gateway" / "gpu_gateway"
    forbidden = {
        "api", "auth", "database", "local_oauth", "migrations", "service",
        "store", "worker",
    }
    for name in ALLOWED_PROVIDER_MODULES:
        tree = ast.parse((module_root / name).read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.rsplit(".", 1)[-1])
            elif isinstance(node, ast.Import):
                imported.update(alias.name.rsplit(".", 1)[-1] for alias in node.names)
        assert imported.isdisjoint(forbidden), f"{name} imports a legacy service module"


def test_slow_submission_uses_durable_idempotent_modal_spawn() -> None:
    source = ADAPTER.read_text(encoding="utf-8")
    assert 'modal.Dict.from_name("gpu-control-provider-adapter-submissions"' in source
    assert "skip_if_exists=True" in source
    assert "provider_submit_worker.spawn(owner, arguments)" in source
    assert '"transport": "modal_spawn_v1"' in source
    assert "service.validate_submission(owner, arguments)" in source

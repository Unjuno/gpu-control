from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
SOURCE = HERE / "gpu_canary.py"


def load_result():
    function = next(node for node in ast.parse(SOURCE.read_text(encoding="utf-8")).body
                    if isinstance(node, ast.FunctionDef) and node.name == "_result")
    namespace = {"Any": object, "hashlib": hashlib, "json": json, "WORKLOAD": "modal-gpu-vector-add-v1"}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(SOURCE), "exec"), namespace)
    return namespace["_result"]


def test_result_binds_gpu_evidence_to_exact_plan() -> None:
    metrics = {
        "device_count": 1,
        "device_name": "Tesla T4",
        "compute_capability": "7.5",
        "operation": "u32_vector_add_4",
        "output_sha256": "a" * 64,
    }
    result = load_result()("1" * 32, "3" * 40, "2" * 64, metrics)

    assert result["provider"] == "modal_gpu"
    assert result["gpu_used"] is True
    identity = {key: result[key] for key in ("run_id", "source_sha", "plan_fingerprint", "metrics")}
    expected = hashlib.sha256(json.dumps(
        identity, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode()).hexdigest()
    assert result["checksum"] == expected


def test_deployment_has_fixed_bounded_gpu_contract() -> None:
    source = SOURCE.read_text(encoding="utf-8")

    assert 'gpu="T4"' in source
    assert "block_network=True" in source
    assert "restrict_modal_access=True" in source
    assert "single_use_containers=True" in source
    assert "secrets=" not in source
    assert "cuLaunchKernel" in source
    assert "output != [11, 22, 33, 44]" in source


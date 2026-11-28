import ast
import hashlib
import json
from pathlib import Path

import pytest

from gpu_control.canonical_json import canonical_json, sha256_fingerprint


_CANONICAL_MODEL_MODULES = (
    "execution.py",
    "lifecycle.py",
    "capabilities.py",
    "workloads.py",
    "results.py",
    "providers/finalization.py",
)


def test_canonical_json_is_stable_across_mapping_order_and_nested_values():
    left = {"z": [{"b": 2, "a": 1}], "a": "日本語"}
    right = {"a": "日本語", "z": [{"a": 1, "b": 2}]}

    expected = json.dumps(left, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    assert canonical_json(left) == expected
    assert canonical_json(left) == canonical_json(right)
    assert sha256_fingerprint(left) == sha256_fingerprint(right)
    assert sha256_fingerprint(left) == "sha256:" + hashlib.sha256(expected.encode()).hexdigest()


def test_canonical_json_rejects_non_finite_numbers():
    with pytest.raises(ValueError):
        canonical_json({"nested": [float("nan")]})


def test_core_model_fingerprints_do_not_reimplement_serialization():
    package = Path(__file__).parents[1] / "src" / "gpu_control"
    duplicate_calls = []
    for module in _CANONICAL_MODEL_MODULES:
        path = package / module
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or node.name not in {
                "canonical_json", "fingerprint",
            }:
                continue
            for call in ast.walk(node):
                if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Attribute):
                    continue
                owner = call.func.value
                if isinstance(owner, ast.Name) and (owner.id, call.func.attr) in {
                    ("json", "dumps"), ("hashlib", "sha256"),
                }:
                    duplicate_calls.append(f"{module}:{node.name}:{call.lineno}")

    assert duplicate_calls == []

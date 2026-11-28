"""Protect the dependency direction between the reusable core and hosts."""
from __future__ import annotations

import ast
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CORE_PACKAGE = REPOSITORY_ROOT / "src" / "gpu_control"


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_reusable_core_does_not_depend_on_gateway_or_site_hosts() -> None:
    forbidden_prefixes = ("gpu_gateway", "provider_runtime")
    violations = []
    for path in sorted(CORE_PACKAGE.rglob("*.py")):
        for module in sorted(_imported_modules(path)):
            if any(module == prefix or module.startswith(prefix + ".")
                   for prefix in forbidden_prefixes):
                violations.append(f"{path.relative_to(REPOSITORY_ROOT)} imports {module}")

    assert violations == [], "Reusable gpu_control package must not depend on host apps:\n" + "\n".join(violations)

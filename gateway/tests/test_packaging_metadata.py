from pathlib import Path
import tomllib

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name


ROOT = Path(__file__).resolve().parents[2]
GATEWAY = ROOT / "gateway"


def _identity(value: str) -> tuple[str, frozenset[str], str]:
    requirement = Requirement(value)
    return canonicalize_name(requirement.name), frozenset(requirement.extras), str(requirement.specifier)


def test_pep621_dependencies_match_runtime_requirements():
    project = tomllib.loads((GATEWAY / "pyproject.toml").read_text())
    requirements = [line.strip() for line in (GATEWAY / "requirements.txt").read_text().splitlines()
                   if line.strip() and not line.lstrip().startswith(("#", "-e "))]
    project_dependencies = {_identity(item) for item in project["project"]["dependencies"]}
    assert project_dependencies - {_identity(item) for item in requirements} == {
        ("gpu-control", frozenset(), "")
    }
    assert project_dependencies - {("gpu-control", frozenset(), "")} == {
        _identity(item) for item in requirements
    }


def test_runtime_requirements_install_the_shared_monorepo_package():
    requirements = (GATEWAY / "requirements.txt").read_text().splitlines()
    assert "-e .." in requirements
    project = tomllib.loads((GATEWAY / "pyproject.toml").read_text())
    assert project["tool"]["uv"]["sources"]["gpu-control"] == {
        "path": "..", "editable": True,
    }
    assert (ROOT / "src" / "gpu_control" / "__init__.py").is_file()

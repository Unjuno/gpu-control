from pathlib import Path
import re

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
FULL_SHA_ACTION = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[0-9a-f]{40}$")


def workflow_files() -> list[Path]:
    return sorted([*WORKFLOWS.glob("*.yml"), *WORKFLOWS.glob("*.yaml")])


def test_every_third_party_action_is_pinned_to_full_commit_sha() -> None:
    assert workflow_files()
    for workflow in workflow_files():
        for raw_line in workflow.read_text(encoding="utf-8").splitlines():
            stripped = raw_line.strip()
            if not stripped.startswith("uses:") and not stripped.startswith("- uses:"):
                continue
            reference = stripped.split("uses:", 1)[1].strip().split(" #", 1)[0].strip()
            if reference.startswith("./"):
                continue
            assert FULL_SHA_ACTION.fullmatch(reference), (
                f"{workflow.relative_to(ROOT)} contains a mutable or non-full action reference: {reference}"
            )


def test_uv_bootstrap_uses_immutable_setup_uv_not_pip_install() -> None:
    for workflow in workflow_files():
        content = workflow.read_text(encoding="utf-8")
        assert "pip install 'uv==" not in content
        assert 'uses: astral-sh/setup-uv@c771a70e6277c0a99b617c7a806ffedaca235ff9' in content or (
            workflow.name not in {"ci.yml", "dry-run.yml"}
        )


def test_required_ci_checks_are_unique_and_report_for_pull_requests_and_merge_groups() -> None:
    def load(name: str) -> dict:
        path = WORKFLOWS / name
        return yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)

    workflow_names = ("ci.yml", "gateway-ci.yml", "gateway-bridge-ci.yml", "project-checks-ci.yml")
    workflows = {name: load(name) for name in workflow_names}
    contexts = []

    for name, workflow in workflows.items():
        triggers = workflow["on"]
        assert "pull_request" in triggers, name
        assert triggers["merge_group"]["types"] == ["checks_requested"], name
        assert triggers["push"]["branches"] == ["main"], name
        if name != "ci.yml":
            assert "paths" not in (triggers["pull_request"] or {}), name

    ci_jobs = workflows["ci.yml"]["jobs"]
    contexts.append(ci_jobs["reference-workload"]["name"])
    contexts.extend(f"Python {version}" for version in
                    ci_jobs["test"]["strategy"]["matrix"]["python-version"])
    contexts.extend(workflows[name]["jobs"][job]["name"] for name, job in (
        ("gateway-ci.yml", "gateway"),
        ("gateway-bridge-ci.yml", "bridge"),
        ("project-checks-ci.yml", "test"),
    ))
    assert len(contexts) == len(set(contexts)), contexts


def test_gateway_checks_run_when_the_shared_core_package_changes() -> None:
    for name in ("gateway-ci.yml", "gateway-bridge-ci.yml"):
        workflow = yaml.load((WORKFLOWS / name).read_text(encoding="utf-8"),
                             Loader=yaml.BaseLoader)
        paths = workflow["on"]["push"]["paths"]
        assert "src/gpu_control/**" in paths, name
        assert "pyproject.toml" in paths, name

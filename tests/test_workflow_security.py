from pathlib import Path
import re


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

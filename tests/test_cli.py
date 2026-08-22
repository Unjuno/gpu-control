import json

import gpu_control.cli as cli_module
from gpu_control.cli import main
from gpu_control.source import SourceVerificationResult


SHA = "0123456789abcdef0123456789abcdef01234567"


def test_self_test_works_outside_repository(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)

    exit_code = main(["self-test"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "ok"
    assert payload["dry_run"] is True
    assert payload["effective_policy"]["gpu_count"] == 1


def test_validate_uses_bundled_policy_outside_repository(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)

    exit_code = main(
        [
            "validate",
            "--target-repo",
            "example/model",
            "--target-sha",
            SHA,
            "--gpu-profile",
            "cheap-24gb",
            "--max-runtime-minutes",
            "15",
            "--max-cost-usd",
            "0.20",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "valid"
    assert payload["dry_run"] is True


def test_verify_source_runs_after_policy_validation(monkeypatch, capsys) -> None:
    def fake_verify(request):  # type: ignore[no-untyped-def]
        return SourceVerificationResult(
            repository=request.target_repo,
            commit_sha=request.target_sha,
            dockerfile_path=request.dockerfile_path,
            repository_public=True,
            commit_verified=True,
            dockerfile_verified=True,
        )

    monkeypatch.setattr(cli_module, "verify_public_github_source", fake_verify)

    exit_code = main(
        [
            "verify-source",
            "--target-repo",
            "example/model",
            "--target-sha",
            SHA,
            "--dockerfile-path",
            "Dockerfile",
            "--gpu-profile",
            "cheap-24gb",
            "--max-runtime-minutes",
            "15",
            "--max-cost-usd",
            "0.20",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "verified"
    assert payload["dry_run"] is True
    assert payload["source"]["repository"] == "example/model"
    assert payload["source"]["commit_verified"] is True
    assert payload["source"]["dockerfile_verified"] is True

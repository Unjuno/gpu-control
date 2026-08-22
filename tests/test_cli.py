import json

from gpu_control.cli import main


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

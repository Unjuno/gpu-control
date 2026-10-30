"""Static safety checks for the Linux systemd deployment templates."""
from configparser import ConfigParser
import json
from pathlib import Path
import sys
from types import SimpleNamespace

DEPLOY = Path(__file__).resolve().parents[1] / "deploy"
sys.path.insert(0, str(DEPLOY))
import check_artifact_capacity


def load_unit(name: str) -> ConfigParser:
    unit = ConfigParser(interpolation=None, strict=True)
    unit.optionxform = str
    with (DEPLOY / name).open(encoding="utf-8") as source:
        unit.read_file(source)
    return unit


def test_gateway_api_is_loopback_only_and_has_no_docker_authority():
    unit = load_unit("gpu-control-api.service")
    service = unit["Service"]
    assert service["User"] == service["Group"] == "gpu-control"
    assert service["EnvironmentFile"] == "/etc/gpu-control/worker.env"
    assert "--host 127.0.0.1 --port 8000" in service["ExecStart"]
    assert "SupplementaryGroups" not in service


def test_database_migration_unit_is_restricted_and_never_enabled_automatically():
    unit = load_unit("gpu-control-db-migrate.service")
    service = unit["Service"]
    assert service["Type"] == "oneshot"
    assert service["User"] == service["Group"] == "gpu-control"
    assert service["EnvironmentFile"] == "/etc/gpu-control/worker.env"
    assert service["ExecStart"].endswith("-m gpu_gateway.worker --init-db")
    assert "SupplementaryGroups" not in service
    assert service["ProtectSystem"] == "strict"
    assert service["NoNewPrivileges"] == "true"
    assert "Install" not in unit


def test_only_worker_and_recovery_supervisor_join_docker_group():
    worker = load_unit("gpu-control-worker.service")["Service"]
    supervisor = load_unit("gpu-control-supervisor.service")["Service"]
    assert worker["SupplementaryGroups"] == "docker"
    assert supervisor["SupplementaryGroups"] == "docker"
    assert worker["EnvironmentFile"] == supervisor["EnvironmentFile"]
    assert worker["StateDirectory"] == supervisor["StateDirectory"] == "gpu-control"
    assert "RequiresMountsFor" not in load_unit("gpu-control-worker.service")["Unit"]
    assert "RequiresMountsFor" not in load_unit("gpu-control-supervisor.service")["Unit"]
    assert "--supervise" not in worker["ExecStart"]
    assert "--supervise" in supervisor["ExecStart"]


def test_shared_deployment_environment_uses_public_https_and_persistent_artifacts():
    values = {}
    for line in (DEPLOY / "worker.env.example").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            key, value = line.split("=", 1)
            values[key] = value
    assert values["GATEWAY_PUBLIC_URL"].startswith("https://")
    assert values["GATEWAY_ARTIFACT_DIR"] == "/var/lib/gpu-control/artifacts"
    assert int(values["GATEWAY_ARTIFACT_MIN_FREE_BYTES"]) > 0
    assert values["GATEWAY_ENABLE_MODAL"] == "false"
    assert values["GATEWAY_ENABLE_RUNPOD_BRIDGE"] == "false"


def test_capacity_monitor_timer_is_installed_and_polling_unit_shares_deployment_env():
    timer = load_unit("gpu-control-artifact-capacity.timer")
    assert timer["Timer"]["Unit"] == "gpu-control-artifact-capacity.service"
    assert timer["Timer"]["OnUnitActiveSec"] == "5min"
    service = load_unit("gpu-control-artifact-capacity.service")["Service"]
    capacity_unit = load_unit("gpu-control-artifact-capacity.service")["Unit"]
    assert service["EnvironmentFile"] == "/etc/gpu-control/worker.env"
    assert capacity_unit["RequiresMountsFor"] == "/var/lib/gpu-control/artifacts"
    assert "check_artifact_capacity.py" in service["ExecStart"]
    assert "SupplementaryGroups" not in service

def test_capacity_probe_requires_dedicated_filesystem_and_reports_low_space(tmp_path, monkeypatch):
    root = tmp_path / "artifacts"
    root.mkdir()
    original_stat = check_artifact_capacity.Path.stat

    def different_devices(path, *args, **kwargs):
        result = original_stat(path, *args, **kwargs)
        return SimpleNamespace(st_dev=2 if path == root else result.st_dev,
                               st_mode=result.st_mode)

    monkeypatch.setattr(check_artifact_capacity.Path, "stat", different_devices)
    monkeypatch.setattr(check_artifact_capacity.os, "statvfs", lambda _: SimpleNamespace(
        f_bavail=10, f_frsize=1024 * 1024,
    ))
    assert check_artifact_capacity.inspect_capacity(str(root), 5 * 1024 * 1024) == {
        "available": True, "reason": None, "free_bytes": 10 * 1024 * 1024,
        "minimum_free_bytes": 5 * 1024 * 1024,
    }
    low = check_artifact_capacity.inspect_capacity(str(root), 11 * 1024 * 1024)
    assert low["available"] is False
    assert low["reason"] == "below_minimum_free_bytes"


def test_capacity_probe_fails_closed_on_same_filesystem_and_probe_error(tmp_path, monkeypatch):
    root = tmp_path / "artifacts"
    root.mkdir()
    same_fs = check_artifact_capacity.inspect_capacity(str(root), 1024)
    assert same_fs == {"available": False, "reason": "not_dedicated_filesystem"}

    original_stat = check_artifact_capacity.Path.stat

    def different_devices(path, *args, **kwargs):
        result = original_stat(path, *args, **kwargs)
        return SimpleNamespace(st_dev=2 if path == root else result.st_dev,
                               st_mode=result.st_mode)

    monkeypatch.setattr(check_artifact_capacity.Path, "stat", different_devices)
    monkeypatch.setattr(check_artifact_capacity.os, "statvfs", lambda _: (_ for _ in ()).throw(OSError()))
    failed = check_artifact_capacity.inspect_capacity(str(root), 1024)
    assert failed == {"available": False, "reason": "probe_failed"}


def test_capacity_monitor_cli_emits_machine_readable_failure_and_nonzero_exit(tmp_path, monkeypatch, capsys):
    root = tmp_path / "artifacts"
    root.mkdir()
    monkeypatch.setenv("GATEWAY_ARTIFACT_DIR", str(root))
    monkeypatch.setenv("GATEWAY_ARTIFACT_MIN_FREE_BYTES", "1024")

    assert check_artifact_capacity.main() == 1
    assert json.loads(capsys.readouterr().out) == {
        "check": "gpu-control-artifact-capacity",
        "available": False,
        "reason": "not_dedicated_filesystem",
    }


def test_capacity_monitor_cli_emits_machine_readable_success(tmp_path, monkeypatch, capsys):
    root = tmp_path / "artifacts"
    root.mkdir()
    original_stat = Path.stat

    def different_devices(path, *args, **kwargs):
        result = original_stat(path, *args, **kwargs)
        return SimpleNamespace(st_dev=2 if path == root else result.st_dev,
                               st_mode=result.st_mode)

    monkeypatch.setattr(check_artifact_capacity.Path, "stat", different_devices)
    monkeypatch.setattr(check_artifact_capacity.os, "statvfs", lambda _: SimpleNamespace(
        f_bavail=4, f_frsize=1024,
    ))
    monkeypatch.setenv("GATEWAY_ARTIFACT_DIR", str(root))
    monkeypatch.setenv("GATEWAY_ARTIFACT_MIN_FREE_BYTES", "2048")

    assert check_artifact_capacity.main() == 0
    assert json.loads(capsys.readouterr().out) == {
        "check": "gpu-control-artifact-capacity",
        "available": True,
        "reason": None,
        "free_bytes": 4096,
        "minimum_free_bytes": 2048,
    }

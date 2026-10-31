"""Static safety checks for the Linux systemd deployment templates."""
from configparser import ConfigParser
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from jsonschema import Draft202012Validator

DEPLOY = Path(__file__).resolve().parents[1] / "deploy"
sys.path.insert(0, str(DEPLOY))
import check_artifact_capacity

CAPACITY_EVENT_SCHEMA = json.loads(
    (DEPLOY / "capacity-event.schema.json").read_text(encoding="utf-8"))
Draft202012Validator.check_schema(CAPACITY_EVENT_SCHEMA)
capacity_event_validator = Draft202012Validator(CAPACITY_EVENT_SCHEMA)


def load_unit(name: str, *, strict: bool = True) -> ConfigParser:
    unit = ConfigParser(interpolation=None, strict=strict)
    unit.optionxform = str
    with (DEPLOY / name).open(encoding="utf-8") as source:
        unit.read_file(source)
    return unit


def test_gateway_api_is_loopback_only_and_has_no_docker_authority():
    unit = load_unit("gpu-control-api.service", strict=False)
    service = unit["Service"]
    assert service["User"] == "gpu-control-api"
    assert service["Group"] == "gpu-control-artifacts"
    assert service["SupplementaryGroups"] == "gpu-control-artifact-probes"
    env_files = [line.partition("=")[2] for line in
                 (DEPLOY / "gpu-control-api.service").read_text(encoding="utf-8").splitlines()
                 if line.startswith("EnvironmentFile=")]
    assert env_files == ["/etc/gpu-control/gateway.env", "/etc/gpu-control/api.env"]
    assert "--host 127.0.0.1 --port 8000" in service["ExecStart"]
    assert "docker" not in service["SupplementaryGroups"]
    assert service["ReadWritePaths"] == "-/var/lib/gpu-control/artifacts/.gpu-control-probes"
    assert service["StateDirectory"] == "gpu-control-api"


def test_database_migration_unit_is_restricted_and_never_enabled_automatically():
    unit = load_unit("gpu-control-db-migrate.service")
    service = unit["Service"]
    assert service["Type"] == "oneshot"
    assert service["User"] == service["Group"] == "gpu-control-migrate"
    assert service["EnvironmentFile"] == "/etc/gpu-control/gateway.env"
    assert service["ExecStartPre"].endswith("-m gpu_gateway.worker --check-db")
    assert service["ExecStart"].endswith("-m gpu_gateway.worker --init-db")
    assert "SupplementaryGroups" not in service
    assert service["ProtectSystem"] == "strict"
    assert service["NoNewPrivileges"] == "true"
    assert "Install" not in unit


def test_database_preflight_unit_is_manual_read_only_and_uses_migration_identity():
    unit = load_unit("gpu-control-db-check.service")
    service = unit["Service"]
    assert service["Type"] == "oneshot"
    assert service["User"] == service["Group"] == "gpu-control-migrate"
    assert service["EnvironmentFile"] == "/etc/gpu-control/gateway.env"
    assert service["ExecStart"].endswith("-m gpu_gateway.worker --check-db")
    assert service["ProtectSystem"] == "strict"
    assert service["NoNewPrivileges"] == "true"
    assert "Install" not in unit


def test_only_worker_and_recovery_supervisor_join_docker_group():
    worker = load_unit("gpu-control-worker.service", strict=False)["Service"]
    supervisor = load_unit("gpu-control-supervisor.service", strict=False)["Service"]
    assert worker["User"] == supervisor["User"] == "gpu-control-worker"
    assert worker["Group"] == supervisor["Group"] == "gpu-control-artifacts"
    assert worker["SupplementaryGroups"] == supervisor["SupplementaryGroups"] == "docker"
    worker_env_files = [line.partition("=")[2].removeprefix("-") for line in
                        (DEPLOY / "gpu-control-worker.service").read_text(encoding="utf-8").splitlines()
                        if line.startswith("EnvironmentFile=")]
    supervisor_env_files = [line.partition("=")[2].removeprefix("-") for line in
                            (DEPLOY / "gpu-control-supervisor.service").read_text(encoding="utf-8").splitlines()
                            if line.startswith("EnvironmentFile=")]
    assert worker_env_files == ["/etc/gpu-control/gateway.env", "/etc/gpu-control/worker-secrets.env",
                                "/etc/gpu-control/provider-evidence.env"]
    assert supervisor_env_files == ["/etc/gpu-control/gateway.env", "/etc/gpu-control/worker-secrets.env"]
    assert worker["StateDirectory"] == supervisor["StateDirectory"] == "gpu-control"
    assert worker["StateDirectoryMode"] == supervisor["StateDirectoryMode"] == "2750"
    assert worker["ReadWritePaths"] == supervisor["ReadWritePaths"] == "-/var/lib/gpu-control/artifacts"
    assert "RequiresMountsFor" not in load_unit("gpu-control-worker.service", strict=False)["Unit"]
    assert "RequiresMountsFor" not in load_unit("gpu-control-supervisor.service", strict=False)["Unit"]
    assert "--supervise" not in worker["ExecStart"]
    assert "--supervise" in supervisor["ExecStart"]


def test_service_unix_users_isolate_worker_secrets_from_api_and_oneshots():
    api = load_unit("gpu-control-api.service", strict=False)["Service"]
    worker = load_unit("gpu-control-worker.service", strict=False)["Service"]
    supervisor = load_unit("gpu-control-supervisor.service", strict=False)["Service"]
    migration = load_unit("gpu-control-db-migrate.service")["Service"]
    capacity = load_unit("gpu-control-artifact-capacity.service")["Service"]
    bridge = load_unit("gpu-control-capacity-bridge.service")["Service"]
    assert api["User"] not in {worker["User"], migration["User"], capacity["User"]}
    assert supervisor["User"] == worker["User"]  # Both intentionally receive worker-only credentials.
    assert len({api["User"], worker["User"], migration["User"], capacity["User"],
                bridge["User"]}) == 5
    assert capacity["User"] == "gpu-control-capacity"
    assert capacity["Group"] == "gpu-control-artifacts"
    assert "SupplementaryGroups" not in capacity
    assert bridge["User"] == bridge["Group"] == "gpu-control-capacity-bridge"
    assert bridge["SupplementaryGroups"] == "systemd-journal"
    assert "EnvironmentFile" not in bridge
    assert "ReadWritePaths" not in bridge
    assert "gpu-control-artifact-probes" not in worker["SupplementaryGroups"]
    assert "gpu-control-artifact-probes" not in supervisor["SupplementaryGroups"]


def test_systemd_units_apply_kernel_proc_device_and_socket_restrictions():
    network_units = (
        "gpu-control-api.service", "gpu-control-worker.service",
        "gpu-control-supervisor.service", "gpu-control-db-migrate.service",
    )
    for name in (*network_units, "gpu-control-artifact-capacity.service"):
        service = load_unit(name, strict=False)["Service"]
        assert service["PrivateDevices"] == "true"
        assert service["ProtectProc"] == "invisible"
        assert service["ProcSubset"] == "pid"
        assert service["CapabilityBoundingSet"] == ""
        assert service["RestrictRealtime"] == "true"
        assert service["SystemCallArchitectures"] == "native"
        assert service["ProtectClock"] == "true"
        assert service["ProtectHostname"] == "true"
        assert service["ProtectKernelLogs"] == "true"
    for name in network_units:
        service = load_unit(name, strict=False)["Service"]
        assert service["RestrictAddressFamilies"] == "AF_UNIX AF_INET AF_INET6"
        assert "PrivateNetwork" not in service
    capacity = load_unit("gpu-control-artifact-capacity.service")["Service"]
    assert capacity["PrivateNetwork"] == "true"
    assert capacity["RestrictAddressFamilies"] == "AF_UNIX"
    bridge = load_unit("gpu-control-capacity-bridge.service")["Service"]
    assert bridge["PrivateNetwork"] == "true"
    assert bridge["RestrictAddressFamilies"] == "AF_UNIX"
    assert bridge["SupplementaryGroups"] == "systemd-journal"
    assert bridge["StateDirectory"] == "gpu-control-capacity-bridge"
    assert bridge["StateDirectoryMode"] == "0700"


def test_gateway_ci_runs_systemd_verification_for_all_service_templates():
    workflow = (DEPLOY.parents[1] / ".github/workflows/gateway-ci.yml").read_text(encoding="utf-8")
    helper_path = DEPLOY / "verify_systemd_units_ci.sh"
    assert "bash deploy/verify_systemd_units_ci.sh" in workflow
    helper = helper_path.read_text(encoding="utf-8")
    assert '"${GITHUB_ACTIONS:-}" != true' in helper
    assert '"${RUNNER_OS:-}" != Linux' in helper
    for unit in (
        "gpu-control-api.service", "gpu-control-worker.service",
        "gpu-control-supervisor.service", "gpu-control-db-check.service",
        "gpu-control-db-migrate.service",
        "gpu-control-artifact-capacity.service", "gpu-control-artifact-capacity.timer",
        "gpu-control-capacity-bridge.service",
    ):
        assert unit in helper
    assert "systemd-analyze verify" in helper
    assert "systemctl start" not in helper


def test_shared_deployment_environment_uses_public_https_and_persistent_artifacts():
    values = {}
    for line in (DEPLOY / "gateway.env.example").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            key, value = line.split("=", 1)
            values[key] = value
    assert values["GATEWAY_PUBLIC_URL"].startswith("https://")
    assert values["GATEWAY_ARTIFACT_DIR"] == "/var/lib/gpu-control/artifacts"
    assert int(values["GATEWAY_ARTIFACT_MIN_FREE_BYTES"]) > 0
    assert values["GATEWAY_ENABLE_MODAL"] == "false"
    assert values["GATEWAY_ENABLE_RUNPOD_BRIDGE"] == "false"
    assert values["GATEWAY_HOSTED"] == "true"
    assert "GATEWAY_COOKIE_KEY" not in values
    assert "GATEWAY_OIDC_CLIENT_SECRET" not in values


def test_authentication_and_capacity_settings_are_environment_isolated():
    def values(name):
        result = {}
        for line in (DEPLOY / name).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                key, value = line.split("=", 1)
                result[key] = value
        return result

    api = values("api.env.example")
    capacity = values("capacity.env.example")
    api_example = (DEPLOY / "api.env.example").read_text(encoding="utf-8")
    assert "# GATEWAY_COOKIE_KEY=" in api_example
    assert "does not use this" in api_example
    assert "Fernet.generate_key()" in api_example
    assert "GATEWAY_COOKIE_KEY" not in api
    assert "GATEWAY_OIDC_CLIENT_SECRET" not in api  # external OIDC is opt-in
    assert not {"GATEWAY_DATABASE_URL", "GATEWAY_COOKIE_KEY", "GATEWAY_OIDC_CLIENT_SECRET"} & capacity.keys()
    assert set(capacity) == {"GATEWAY_ARTIFACT_DIR", "GATEWAY_ARTIFACT_MIN_FREE_BYTES"}
    for name in ("gpu-control-worker.service", "gpu-control-supervisor.service"):
        assert "/etc/gpu-control/api.env" not in (DEPLOY / name).read_text(encoding="utf-8")
    for name in ("gpu-control-api.service", "gpu-control-artifact-capacity.service",
                 "gpu-control-db-check.service", "gpu-control-db-migrate.service",
                 "gpu-control-capacity-bridge.service"):
        assert "worker-secrets.env" not in (DEPLOY / name).read_text(encoding="utf-8")
    secret_example = (DEPLOY / "worker-secrets.env.example").read_text(encoding="utf-8")
    assert "MODAL_TOKEN_ID" in secret_example and "MODAL_TOKEN_SECRET" in secret_example
    assert "GATEWAY_PROVIDER_EVIDENCE_SIGNING_KEY_B64" not in secret_example
    evidence_example = (DEPLOY / "provider-evidence.env.example").read_text(encoding="utf-8")
    assert "GATEWAY_PROVIDER_EVIDENCE_SIGNING_KEY_B64" in evidence_example
    assert "RUNPOD_API_KEY" in evidence_example
    assert "GATEWAY_ENABLE_RUNPOD_EVIDENCE" in evidence_example
    assert "GATEWAY_PROVIDER_EVIDENCE_SIGNING_KEY_B64" not in api_example
    common_example = (DEPLOY / "gateway.env.example").read_text(encoding="utf-8")
    assert "GATEWAY_PROVIDER_EVIDENCE_PUBLIC_KEYS_JSON" in common_example
    assert "GATEWAY_PROVIDER_EVIDENCE_SIGNING_KEY_B64" not in common_example
    assert "/etc/gpu-control/provider-evidence.env" not in (DEPLOY / "gpu-control-supervisor.service").read_text(encoding="utf-8")
    assert all(line.lstrip().startswith("#") for line in secret_example.splitlines() if line.strip())


def test_capacity_monitor_timer_is_installed_and_polling_unit_shares_deployment_env():
    timer = load_unit("gpu-control-artifact-capacity.timer")
    assert timer["Timer"]["Unit"] == "gpu-control-artifact-capacity.service"
    assert timer["Timer"]["OnUnitActiveSec"] == "5min"
    service = load_unit("gpu-control-artifact-capacity.service")["Service"]
    capacity_unit = load_unit("gpu-control-artifact-capacity.service")["Unit"]
    assert service["SyslogIdentifier"] == "gpu-control-capacity"
    assert service["StandardOutput"] == service["StandardError"] == "journal"
    assert service["EnvironmentFile"] == "/etc/gpu-control/capacity.env"
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
    event = json.loads(capsys.readouterr().out)
    capacity_event_validator.validate(event)
    assert event == {
        "check": "gpu-control-artifact-capacity",
        "status": "alert",
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
    event = json.loads(capsys.readouterr().out)
    capacity_event_validator.validate(event)
    assert event == {
        "check": "gpu-control-artifact-capacity",
        "status": "ok",
        "available": True,
        "reason": None,
        "free_bytes": 4096,
        "minimum_free_bytes": 2048,
    }


def test_capacity_event_schema_rejects_invalid_alert_and_recovery_states():
    invalid_alert = {"check": "gpu-control-artifact-capacity", "status": "alert",
                     "available": False, "reason": None}
    invalid_recovery = {"check": "gpu-control-artifact-capacity", "status": "ok",
                        "available": False, "reason": "probe_failed"}
    for event in (invalid_alert, invalid_recovery):
        assert not capacity_event_validator.is_valid(event)

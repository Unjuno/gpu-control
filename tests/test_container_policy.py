from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "policies" / "container-verification-policy.yaml"


def load_policy() -> dict:
    with POLICY_PATH.open("r", encoding="utf-8") as handle:
        policy = yaml.safe_load(handle)
    assert isinstance(policy, dict)
    return policy


def test_generic_container_execution_is_denied_until_isolation_exists() -> None:
    policy = load_policy()
    assert policy["default"] == "denied"
    assert policy["status"] == "design_only"
    assert policy["build"]["generic_execution_enabled"] is False
    assert policy["runtime"]["generic_execution_enabled"] is False


def test_workload_environment_forbids_control_plane_credentials() -> None:
    credentials = load_policy()["credentials"]
    assert credentials["github_token_in_workload_environment"] == "forbidden"
    assert credentials["runpod_api_key"] == "forbidden"
    assert credentials["provider_credentials"] == "forbidden"


def test_runtime_defaults_to_restricted_offline_smoke_test() -> None:
    runtime = load_policy()["runtime"]
    assert runtime["gpu"] == "forbidden"
    assert runtime["network"] == "none"
    assert runtime["capabilities"] == "drop_all"
    assert runtime["no_new_privileges"] is True
    assert runtime["docker_socket"] == "forbidden"
    assert runtime["interactive_tty"] == "forbidden"
    assert runtime["limits"]["wall_clock_seconds"] <= 120
    assert runtime["limits"]["cpus"] <= 2
    assert runtime["limits"]["memory_mib"] <= 4096
    assert runtime["limits"]["pids"] <= 256


def test_untrusted_events_cannot_trigger_container_execution() -> None:
    trigger = load_policy()["trigger"]
    assert trigger["explicit_authenticated_authorization_required"] is True
    assert trigger["untrusted_pull_request"] == "forbidden"
    assert trigger["fork"] == "forbidden"
    assert trigger["issue"] == "forbidden"
    assert trigger["issue_comment"] == "forbidden"


def test_container_policy_requires_security_documentation() -> None:
    assert (ROOT / "docs" / "CONTAINER_VERIFICATION.md").is_file()

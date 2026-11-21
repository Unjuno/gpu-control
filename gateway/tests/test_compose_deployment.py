from pathlib import Path

import yaml


COMPOSE = Path(__file__).resolve().parents[1] / "docker-compose.yml"


def test_compose_initializes_schema_before_api_worker_and_supervisor():
    document = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    services = document["services"]

    assert services["migrate"]["command"] == [
        "python", "-m", "gpu_gateway.worker", "--init-db",
    ]
    assert services["migrate"]["depends_on"]["db"]["condition"] == "service_healthy"
    for name in ("api", "worker", "supervisor"):
        assert services[name]["depends_on"]["migrate"]["condition"] == "service_completed_successfully"


def test_compose_runs_independent_worker_and_recovery_supervisor():
    services = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))["services"]

    assert services["worker"]["image"] == services["supervisor"]["image"]
    assert "command" not in services["worker"]
    assert services["supervisor"]["command"] == [
        "python", "-m", "gpu_gateway.worker", "--supervise", "--poll-seconds", "3",
    ]
    assert services["worker"]["restart"] == "unless-stopped"
    assert services["supervisor"]["restart"] == "unless-stopped"

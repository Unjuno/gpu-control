from dataclasses import replace
import json
from pathlib import Path
import time
from types import SimpleNamespace

import pytest

from gpu_gateway.app import create_app
from gpu_gateway.service import GatewayError
from fastapi.testclient import TestClient


def rpc(w, method, params=None, **extra):
    data = {"jsonrpc": "2.0", "id": 1, "method": method}
    if params is not None: data["params"] = params
    data.update(extra)
    return w.client.post("/mcp", json=data, headers=w.headers)


def test_metadata_and_unauthenticated_challenge(web):
    response = web.client.post("/mcp", json={})
    assert response.status_code == 401
    assert "oauth-protected-resource/mcp" in response.headers["www-authenticate"]
    meta = web.client.get("/.well-known/oauth-protected-resource/mcp").json()
    assert meta["resource"] == web.settings.resource
    assert meta["authorization_servers"] == [web.settings.issuer]


def test_initialize_list_and_notification(web):
    response = rpc(web, "initialize", {"protocolVersion":"2025-11-25", "capabilities":{}, "clientInfo":{"name":"test", "version":"1"}})
    assert response.json()["result"]["protocolVersion"] == "2025-11-25"
    assert "mcp-session-id" not in response.headers
    response = rpc(web, "tools/list")
    names = {t["name"] for t in response.json()["result"]["tools"]}
    assert "experiment_submit" in names
    assert "experiments_submit" not in names
    assert not any("approve" in n or "authorize" in n for n in names)
    data = {"jsonrpc":"2.0", "method":"notifications/initialized"}
    response = web.client.post("/mcp", json=data, headers=web.headers)
    assert response.status_code == 202 and response.content == b""


def test_browser_approval_then_mcp_submit(web):
    created = rpc(web, "tools/call", {"name":"experiments_prepare", "arguments":{"workload":"demo", "idempotency_key":"http-request"}}).json()["result"]["structuredContent"]
    identifier = created["id"]
    response = rpc(web, "tools/call", {"name":"experiments_submit", "arguments":{"run_id":identifier}})
    assert response.json()["result"]["isError"] is True
    denied = web.client.post(f"/api/approvals/{identifier}", headers=web.headers, json={"fingerprint":created["fingerprint"]})
    assert denied.status_code == 403
    missing_csrf = web.client.post(f"/api/approvals/{identifier}", json={"fingerprint":created["fingerprint"]})
    assert missing_csrf.status_code == 403
    accepted = web.client.post(f"/api/approvals/{identifier}", headers=web.browser_headers, json={"fingerprint":created["fingerprint"]})
    assert accepted.status_code == 200
    response = rpc(web, "tools/call", {"name":"experiments_submit", "arguments":{"run_id":identifier}})
    assert response.json()["result"]["structuredContent"]["state"] == "queued"


@pytest.mark.parametrize("override", [{"aud":"https://another-resource.example"}, {"iss":"https://attacker.example"}, {"exp":1}, {"sub":"unauthorized"}, {"scope":[]}, {"iat":9999999999}])
def test_jwt_rejections(web, override):
    token = web.token(**override)
    with pytest.raises(GatewayError): web.auth.verify(token)


def test_scope_is_enforced_at_tool_call(web):
    token = web.token(scope="experiments:read")
    headers = dict(web.headers, Authorization="Bearer " + token)
    response = web.client.post("/mcp", headers=headers, json={"jsonrpc":"2.0", "id":1, "method":"tools/call", "params":{"name":"experiments_prepare", "arguments":{"workload":"demo", "idempotency_key":"no-permission"}}})
    assert response.status_code == 403
    assert "insufficient_scope" in response.headers["www-authenticate"]


def test_origin_and_transport_headers(web):
    invalid = dict(web.headers, Origin="https://attacker.example")
    assert web.client.post("/mcp", headers=invalid, json={}).status_code == 403
    assert web.client.get("/mcp", headers=web.headers).status_code == 405
    assert web.client.delete("/mcp", headers=web.headers).status_code == 405
    headers = dict(web.headers, **{"MCP-Protocol-Version":"1900-01-01"})
    assert web.client.post("/mcp", headers=headers, json={}).status_code == 400
    assert web.client.post("/mcp", headers={"Authorization":web.headers["Authorization"]}, json={}).status_code == 406


@pytest.mark.parametrize("body", ['{', '{"x":1,"x":2}', '{"x":NaN}'])
def test_invalid_json_is_rejected(web, body):
    headers = dict(web.headers, **{"Content-Type":"application/json"})
    response = web.client.post("/mcp", headers=headers, content=body)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == -32700


def test_mcp_invalid_requests_and_methods(web):
    assert web.client.post("/mcp", headers=web.headers, json=[]).status_code == 400
    assert rpc(web, "unknown").json()["error"]["code"] == -32601
    assert rpc(web, "tools/call", {"name":"authorize_experiment"}).json()["error"]["code"] == -32602
    assert rpc(web, "tools/call", {"name":"experiments_get", "arguments":{"run_id":"invalid"}}).json()["result"]["isError"] is True
    assert rpc(web, "ping", id=True).status_code == 400


def test_body_size_and_ui_security_headers(web):
    response = web.client.post("/mcp", headers=web.headers, json={"pad":"x" * 70000})
    assert response.status_code == 413
    response = web.client.get("/")
    assert response.status_code == 200
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert "/static/app.js" in response.text
    assert web.client.get("/api/session").json()["csrf"] == "test-csrf"
    assert web.client.get("/api/tools").headers["cache-control"] == "no-store"


def test_configuration_failure_is_closed():
    from gpu_gateway.config import Settings
    app = create_app(Settings(hosted=True))
    client = TestClient(app)
    assert client.get("/healthz").json()["configured"] is False
    assert client.post("/mcp", json={}).status_code == 503


def test_readiness_requires_current_database_migration_worker_and_registry(web):
    from sqlalchemy import update
    from gpu_gateway.migrations import SCHEMA_VERSION, schema_version
    from gpu_gateway.store import control

    cold = web.client.get("/readyz")
    assert cold.status_code == 503
    assert cold.json()["database"] is True
    assert cold.json()["migration"] is True
    assert cold.json()["worker"] is False
    assert cold.json()["supervisor"] is False
    assert cold.json()["registry"] is True
    assert cold.json()["authentication"] is True

    with web.service.store.transaction() as connection:
        connection.execute(update(control).where(control.c.id == 1).values(worker_seen_at=int(time.time())))
    worker_only = web.client.get("/readyz")
    assert worker_only.status_code == 503
    assert worker_only.json()["worker"] is True
    assert worker_only.json()["supervisor"] is False
    with web.service.store.transaction() as connection:
        connection.execute(update(control).where(control.c.id == 1).values(supervisor_seen_at=int(time.time())))
    ready = web.client.get("/readyz")
    assert ready.status_code == 200
    assert ready.json()["local_cpu_storage_required"] is False
    assert ready.json()["artifact_storage"] is None
    with web.service.store.transaction() as connection:
        connection.execute(update(control).where(control.c.id == 1).values(
            supervisor_seen_at=int(time.time()) - 16))
    stale_supervisor = web.client.get("/readyz")
    assert stale_supervisor.status_code == 503
    assert stale_supervisor.json()["supervisor"] is False
    with web.service.store.transaction() as connection:
        connection.execute(update(control).where(control.c.id == 1).values(supervisor_seen_at=int(time.time())))

    from gpu_gateway.config import Workload
    web.service.workloads["unregistered"] = Workload(provider="ghost")
    invalid_registry = web.client.get("/readyz")
    assert invalid_registry.status_code == 503
    assert invalid_registry.json()["registry"] is False
    del web.service.workloads["unregistered"]

    with web.service.store.transaction() as connection:
        connection.execute(update(schema_version).where(schema_version.c.id == 1).values(version=SCHEMA_VERSION - 1))
    stale_schema = web.client.get("/readyz")
    assert stale_schema.status_code == 503
    assert stale_schema.json()["migration"] is False

    # A liveness response remains independent from a stale schema or worker.
    assert web.client.get("/healthz").status_code == 200


@pytest.mark.parametrize(("storage_available", "expected_status"), [(False, 503), (True, 200)])
def test_readiness_checks_artifact_storage_for_enabled_local_cpu(
        web, tmp_path, monkeypatch, storage_available, expected_status):
    from sqlalchemy import update
    from gpu_gateway import app as gateway_app
    from gpu_gateway.config import Workload
    from gpu_gateway.registry import ProviderRegistration
    from gpu_gateway.store import control

    now = int(time.time())
    policy_path = tmp_path / "local-cpu.json"
    policy_path.write_text(json.dumps({
        "version": "local-cpu-v1", "enabled": True, "valid_until": now + 3600,
        "workloads": ["cpu-smoke"], "max_runtime_seconds": 30,
        "max_cost_usd": "0.00", "allowed_profiles": ["smoke"],
    }))
    monkeypatch.setenv("GATEWAY_LOCAL_CPU_POLICY_FILE", str(policy_path))
    with web.service.store.transaction() as connection:
        connection.execute(update(control).where(control.c.id == 1).values(
            worker_seen_at=now, supervisor_seen_at=now))

    web.service.workloads["cpu-smoke"] = Workload(
        provider="local_cpu", image_digest="sha256:" + "a" * 64,
        execution_profile="smoke", requires_gpu=False,
        source_repository="Unjuno/gpu-control", source_sha="a" * 40)
    web.service.registry["local_cpu"] = ProviderRegistration(
        name="local_cpu", execution="local_worker_container",
        enabled=lambda _settings: True, factory=lambda _settings: None)
    probe = {"configured": storage_available, "available": storage_available,
             "free_bytes": 1024 if storage_available else None,
             "minimum_free_bytes": 0,
             "reason": None if storage_available else "not_configured"}
    calls = []

    def inspect(root, minimum_free_bytes):
        calls.append((root, minimum_free_bytes))
        return probe

    monkeypatch.setattr(gateway_app, "inspect_artifact_storage", inspect)
    response = web.client.get("/readyz")

    assert response.status_code == expected_status
    assert response.json()["ready"] is storage_available
    assert response.json()["local_cpu_storage_required"] is True
    assert response.json()["local_cpu_admission_required"] is True
    assert response.json()["local_cpu_admission_ready"] is True
    assert response.json()["local_cpu_admission_blockers"] == []
    assert response.json()["artifact_storage"] == probe
    assert calls == [(web.settings.artifact_dir, web.settings.artifact_min_free_bytes)]


@pytest.mark.parametrize(("path_exists", "separate_filesystem"), [
    (False, True), (True, False), (True, True),
])
def test_readiness_probes_configured_artifact_path_for_enabled_local_cpu(
        web, tmp_path, monkeypatch, path_exists, separate_filesystem):
    from sqlalchemy import update
    from gpu_gateway.app import create_app
    from gpu_gateway.config import Workload
    from gpu_gateway.registry import ProviderRegistration
    from gpu_gateway.store import control

    now = int(time.time())
    policy_path = tmp_path / "local-cpu.json"
    policy_path.write_text(json.dumps({
        "version": "local-cpu-v1", "enabled": True, "valid_until": now + 3600,
        "workloads": ["cpu-smoke"], "max_runtime_seconds": 30,
        "max_cost_usd": "0.00", "allowed_profiles": ["smoke"],
    }))
    monkeypatch.setenv("GATEWAY_LOCAL_CPU_POLICY_FILE", str(policy_path))
    with web.service.store.transaction() as connection:
        connection.execute(update(control).where(control.c.id == 1).values(
            worker_seen_at=now, supervisor_seen_at=now))

    artifact_path = tmp_path / "artifacts"
    if path_exists:
        artifact_path.mkdir()
        probe_path = artifact_path / ".gpu-control-probes"
        probe_path.mkdir(mode=0o3770)
        probe_path.chmod(0o3770)
    settings = replace(web.settings, artifact_dir=str(artifact_path), artifact_min_free_bytes=1)
    if path_exists and separate_filesystem:
        original_stat = Path.stat
        probe_path = artifact_path / ".gpu-control-probes"

        def stat_with_dedicated_mount(path, *args, **kwargs):
            result = original_stat(path, *args, **kwargs)
            if path in {artifact_path, probe_path}:
                return SimpleNamespace(st_dev=2, st_mode=result.st_mode)
            return result

        monkeypatch.setattr(Path, "stat", stat_with_dedicated_mount)
    web.service.workloads["cpu-smoke"] = Workload(
        provider="local_cpu", image_digest="sha256:" + "b" * 64,
        execution_profile="smoke", requires_gpu=False,
        source_repository="Unjuno/gpu-control", source_sha="b" * 40)
    web.service.registry["local_cpu"] = ProviderRegistration(
        name="local_cpu", execution="local_worker_container",
        enabled=lambda _settings: True, factory=lambda _settings: None)
    client = TestClient(create_app(settings, service=web.service, auth=web.auth))

    response = client.get("/readyz")
    expected_ready = path_exists and separate_filesystem
    assert response.status_code == (200 if expected_ready else 503)
    assert response.json()["ready"] is expected_ready
    assert response.json()["local_cpu_admission_ready"] is True
    assert response.json()["artifact_storage"]["available"] is expected_ready


@pytest.mark.parametrize(("allowed_workloads", "source_repository", "source_sha", "expected_blocker"), [
    ([], "Unjuno/gpu-control", "c" * 40, "WORKLOAD_NOT_ALLOWLISTED"),
    (["cpu-smoke"], "", "", "SOURCE_IDENTITY_UNCONFIGURED"),
])
def test_readiness_fails_when_enabled_cpu_workload_is_not_admissible(
        web, tmp_path, monkeypatch, allowed_workloads, source_repository, source_sha, expected_blocker):
    from sqlalchemy import update
    from gpu_gateway import app as gateway_app
    from gpu_gateway.config import Workload
    from gpu_gateway.registry import ProviderRegistration
    from gpu_gateway.store import control

    now = int(time.time())
    with web.service.store.transaction() as connection:
        connection.execute(update(control).where(control.c.id == 1).values(
            worker_seen_at=now, supervisor_seen_at=now))
    policy_path = tmp_path / "local-cpu.json"
    policy_path.write_text(json.dumps({
        "version": "local-cpu-v1", "enabled": True, "valid_until": now + 3600,
        "workloads": allowed_workloads, "max_runtime_seconds": 30,
        "max_cost_usd": "0.00", "allowed_profiles": ["smoke"],
    }))
    monkeypatch.setenv("GATEWAY_LOCAL_CPU_POLICY_FILE", str(policy_path))
    web.service.workloads["cpu-smoke"] = Workload(
        provider="local_cpu", image_digest="sha256:" + "c" * 64,
        execution_profile="smoke", requires_gpu=False,
        source_repository=source_repository, source_sha=source_sha)
    web.service.registry["local_cpu"] = ProviderRegistration(
        name="local_cpu", execution="local_worker_container",
        enabled=lambda _settings: True, factory=lambda _settings: None)
    monkeypatch.setattr(gateway_app, "inspect_artifact_storage", lambda *_: {
        "configured": True, "available": True, "free_bytes": 1024,
        "minimum_free_bytes": 0, "reason": None,
    })

    response = web.client.get("/readyz")

    assert response.status_code == 503
    assert response.json()["ready"] is False
    assert response.json()["local_cpu_admission_ready"] is False
    assert response.json()["local_cpu_admission_blockers"] == [
        {"workload": "cpu-smoke", "reason": expected_blocker},
    ]


def test_readiness_uses_stale_boundary_at_exactly_fifteen_seconds(web, monkeypatch):
    from sqlalchemy import update
    from gpu_gateway import app as gateway_app
    from gpu_gateway.store import control

    now = 1_800_000_000
    monkeypatch.setattr(gateway_app, "time", SimpleNamespace(time=lambda: now))
    with web.service.store.transaction() as connection:
        connection.execute(update(control).where(control.c.id == 1).values(
            worker_seen_at=now - 15, supervisor_seen_at=now - 15))
    stale = web.client.get("/readyz")
    assert stale.status_code == 503
    assert stale.json()["worker"] is False
    assert stale.json()["supervisor"] is False

    with web.service.store.transaction() as connection:
        connection.execute(update(control).where(control.c.id == 1).values(
            worker_seen_at=now - 14, supervisor_seen_at=now - 14))
    fresh = web.client.get("/readyz")
    assert fresh.status_code == 200
    assert fresh.json()["worker"] is True
    assert fresh.json()["supervisor"] is True


def test_browser_cookie_tamper_rejected(web):
    web.client.cookies.clear()
    web.client.cookies.set("gpu_gateway_session", "forged")
    assert web.client.get("/api/session").status_code == 401


def modern_rpc(web, method, parameters=None, header_changes=None):
    params = dict(parameters or {})
    params['_meta'] = {'io.modelcontextprotocol/protocolVersion': '2026-07-28',
                       'io.modelcontextprotocol/clientCapabilities': {}}
    headers = dict(web.headers, **{'MCP-Protocol-Version': '2026-07-28', 'Mcp-Method': method})
    if 'name' in params: headers['Mcp-Name'] = params['name']
    headers.update(header_changes or {})
    return web.client.post('/mcp', json={'jsonrpc':'2.0','id':7,'method':method,'params':params}, headers=headers)


def test_modern_discovery_and_tools_without_initialize(web):
    discovery = modern_rpc(web, 'server/discover')
    assert discovery.status_code == 200
    result = discovery.json()['result']
    assert result['resultType'] == 'complete'
    assert '2026-07-28' in result['supportedVersions']
    assert result['_meta']['io.modelcontextprotocol/serverInfo']['name'] == 'gpu-control-gateway'
    response = modern_rpc(web, 'tools/call', {'name':'integrations_list', 'arguments':{}})
    assert response.json()['result']['isError'] is False
    assert modern_rpc(web, 'unknown').status_code == 404


@pytest.mark.parametrize('changes', [ {'Mcp-Method':'ping'}, {'Mcp-Name':'another_tool'}, {'MCP-Protocol-Version':'2025-11-25'} ])
def test_modern_header_mismatch(web, changes):
    response = modern_rpc(web, 'tools/call', {'name':'integrations_list'}, changes)
    assert response.status_code == 400
    assert response.json()['error']['code'] == -32020


def test_modern_metadata_and_unknown_version(web):
    headers = dict(web.headers, **{'MCP-Protocol-Version':'2026-07-28','Mcp-Method':'tools/list'})
    response = web.client.post('/mcp', json={'jsonrpc':'2.0','id':1,'method':'tools/list'}, headers=headers)
    assert response.status_code == 400 and response.json()['error']['code'] == -32602
    response = modern_rpc(web, 'tools/list', header_changes={'MCP-Protocol-Version':'2099-01-01'})
    assert response.json()['error']['code'] == -32022
    assert '2026-07-28' in response.json()['error']['data']['supported']

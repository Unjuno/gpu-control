from dataclasses import replace
import json
import time

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
    assert "experiments_submit" in names
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

"""Opt-in, real-Caddy integration test for the loopback Gateway deployment.

Run with ``GPU_CONTROL_CADDY_PROXY_INTEGRATION=1 pytest -q
gateway/tests/test_caddy_proxy_integration.py``. It builds a uniquely named
Gateway image, starts only disposable local containers, and removes only the
containers and volumes in its unique Compose project.
"""
from __future__ import annotations

import contextlib
import json
import os
import platform
import re
import shutil
import socket
import ssl
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

import httpx
import pytest


ROOT = Path(__file__).resolve().parents[2]
HOST = "mcp.example.test"
ORIGIN = f"https://{HOST}:8443"
CADDY_DIGESTS = {
    "aarch64": "sha256:cc447f149425221422153c6cdf33a123b3f458839679f950298f68a690a54a5b",
    "arm64": "sha256:cc447f149425221422153c6cdf33a123b3f458839679f950298f68a690a54a5b",
    "x86_64": "sha256:04913b1da43339a40ad1ea87827d70a576ac5aa6cf674c6e24fdca675887533a",
    "amd64": "sha256:04913b1da43339a40ad1ea87827d70a576ac5aa6cf674c6e24fdca675887533a",
}


def _run(command: list[str], *, timeout: int = 120, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True,
                            timeout=timeout, check=False)
    if check and result.returncode:
        detail = re.sub(r"(?i)(token=)[^&\s]+", r"\1[REDACTED]",
                        (result.stderr or result.stdout)[-4000:])
        raise AssertionError(f"command failed ({result.returncode}): {detail}")
    return result


@contextlib.contextmanager
def _pin_local_test_host():
    """Resolve only the test hostname locally while preserving TLS SNI/Host."""
    original = socket.getaddrinfo

    def getaddrinfo(host, port, *args, **kwargs):
        if host == HOST:
            host = "127.0.0.1"
        return original(host, port, *args, **kwargs)

    socket.getaddrinfo = getaddrinfo
    try:
        yield
    finally:
        socket.getaddrinfo = original


@pytest.mark.skipif(
    os.environ.get("GPU_CONTROL_CADDY_PROXY_INTEGRATION") != "1",
    reason="set GPU_CONTROL_CADDY_PROXY_INTEGRATION=1 to run disposable Docker integration",
)
def test_real_caddy_tls_oauth_proxy_and_error_log_redaction(tmp_path):
    if not shutil.which("docker"):
        pytest.skip("Docker CLI is unavailable")
    if platform.machine() not in CADDY_DIGESTS:
        pytest.skip(f"No pinned Caddy image for {platform.machine()}")

    compose = shutil.which("docker")
    assert compose
    project = "gpu-control-caddy-" + uuid.uuid4().hex[:12]
    image = "gpu-control-gateway:caddy-test-" + project.rsplit("-", 1)[-1]
    state_dir = tmp_path / "state"
    caddy_data_dir = tmp_path / "caddy-data"
    state_dir.mkdir(mode=0o777)
    caddy_data_dir.mkdir(mode=0o777)
    state_dir.chmod(0o777)
    caddy_data_dir.chmod(0o777)

    template = (ROOT / "gateway/deploy/Caddyfile.example").read_text(encoding="utf-8")
    site = "mcp.example.com {"
    proxy = "\treverse_proxy 127.0.0.1:8000"
    assert template.count(site) == 1
    assert template.count(proxy) == 1
    caddyfile = template.replace(site, f"{HOST}:8443 {{\n\ttls internal", 1)
    caddyfile = caddyfile.replace(
        proxy,
        "\thandle /__caddy_test_upstream_failure/* {\n"
        "\t\treverse_proxy 127.0.0.1:1\n"
        "\t}\n"
        "\thandle {\n"
        f"{proxy}\n"
        "\t}",
        1,
    )
    caddy_path = tmp_path / "Caddyfile"
    caddy_path.write_text(caddyfile, encoding="utf-8")
    caddy_path.chmod(0o644)

    compose_data = {
        "services": {
            "api": {
                "build": {
                    "context": str(ROOT),
                    "dockerfile": "gateway/Dockerfile",
                },
                "image": image,
                "command": ["sh", "-c",
                            "python -m gpu_gateway.worker --init-db && "
                            "exec uvicorn app:app --no-proxy-headers --no-access-log "
                            "--host 127.0.0.1 --port 8000"],
                "ports": ["127.0.0.1::8443"],
                "environment": {
                    "GATEWAY_DATABASE_URL": "sqlite:////state/gateway.db",
                    "GATEWAY_PUBLIC_URL": ORIGIN,
                    "GATEWAY_CLIENT_IP_MODE": "trusted_proxy",
                    "GATEWAY_TRUSTED_PROXY_CIDRS": "127.0.0.1/32,::1/128",
                    "GATEWAY_CLIENT_IP_HASH_KEY": "caddy-integration-test-key-32-bytes",
                    "GATEWAY_WORKLOADS_JSON": json.dumps({"demo": {"provider": "demo"}}),
                    "GATEWAY_ENABLE_MODAL": "false",
                    "GATEWAY_ENABLE_RUNPOD_BRIDGE": "false",
                    "GATEWAY_HOSTED": "false",
                },
                "volumes": [f"{state_dir}:/state"],
                "healthcheck": {
                    "test": ["CMD", "python", "-c",
                             "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=1)"],
                    "interval": "1s",
                    "timeout": "2s",
                    "retries": 30,
                },
            },
            "caddy": {
                "image": "caddy@" + CADDY_DIGESTS[platform.machine()],
                "network_mode": "service:api",
                "depends_on": {"api": {"condition": "service_healthy"}},
                "volumes": [f"{caddy_path}:/etc/caddy/Caddyfile:ro",
                            f"{caddy_data_dir}:/data"],
                "command": ["caddy", "run", "--config", "/etc/caddy/Caddyfile",
                            "--adapter", "caddyfile"],
            },
        }
    }
    compose_path = tmp_path / "compose.json"
    compose_path.write_text(json.dumps(compose_data), encoding="utf-8")
    base = [compose, "compose", "--project-name", project, "--file", str(compose_path)]
    try:
        _run(base + ["up", "--detach", "--build", "api", "caddy"], timeout=600)
        published = _run(base + ["port", "api", "8443"]).stdout.strip().splitlines()
        assert len(published) == 1, published
        match = re.fullmatch(r"127\.0\.0\.1:(\d+)", published[0])
        assert match, published
        host_port = int(match.group(1))
        base_url = f"https://{HOST}:{host_port}"
        bootstrap = _run(base + ["exec", "--", "api", "python", "-m",
                                 "gpu_gateway.worker", "--bootstrap-auth",
                                 "--bootstrap-auth-ttl", "600"]).stdout.strip()
        token_match = re.search(r"[?&]token=([^&\s]+)", bootstrap)
        assert token_match, "bootstrap command did not return its one-time local setup link"
        setup_token = token_match.group(1)

        root_cert = caddy_data_dir / "caddy/pki/authorities/local/root.crt"
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and not root_cert.is_file():
            time.sleep(0.2)
        assert root_cert.is_file(), "Caddy did not create its local test CA"

        with _pin_local_test_host(), httpx.Client(
            base_url=base_url, verify=ssl.create_default_context(cafile=str(root_cert)), trust_env=False,
            follow_redirects=False, timeout=10,
        ) as client:
            health = None
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                try:
                    health = client.get("/healthz")
                    break
                except httpx.TransportError:
                    time.sleep(0.2)
            assert health is not None and health.status_code == 200
            assert health.json()["configured"] is True

            protected = client.get("/.well-known/oauth-protected-resource/mcp")
            assert protected.status_code == 200
            assert protected.json()["resource"] == ORIGIN + "/mcp"
            assert protected.json()["authorization_servers"] == [ORIGIN]
            assert protected.headers["strict-transport-security"] == "max-age=15552000"
            assert protected.headers["x-content-type-options"] == "nosniff"
            assert protected.headers["x-frame-options"] == "DENY"
            assert protected.headers["referrer-policy"] == "no-referrer"

            discovery = client.get("/.well-known/oauth-authorization-server")
            assert discovery.status_code == 200
            discovery_data = discovery.json()
            assert discovery_data["issuer"] == ORIGIN
            assert discovery_data["authorization_endpoint"] == ORIGIN + "/oauth/authorize"
            assert discovery_data["token_endpoint"] == ORIGIN + "/oauth/token"

            setup_page = client.get("/auth/setup", params={"token": setup_token})
            assert setup_page.status_code == 200
            assert client.post("/auth/setup", data={
                "token": setup_token, "password": "caddy-test-only-correct-horse-battery-staple",
            }).status_code == 303
            login = client.post("/auth/login", data={
                "password": "caddy-test-only-correct-horse-battery-staple", "next": "/",
            })
            assert login.status_code == 303
            cookie_headers = login.headers.get_list("set-cookie")
            session_cookie = next((value for value in cookie_headers
                                   if value.startswith("gpu_gateway_session=")), "")
            assert session_cookie
            assert "secure" in session_cookie.lower()
            assert "httponly" in session_cookie.lower()
            assert "samesite=lax" in session_cookie.lower()
            session = client.get("/api/session")
            assert session.status_code == 200
            csrf = session.json()["csrf"]

            registered = client.post("/oauth/register", json={
                "client_name": "Caddy proxy integration",
                "redirect_uris": ["https://chatgpt.com/connector/oauth/cb_caddy_test"],
                "token_endpoint_auth_method": "none",
                "grant_types": ["authorization_code", "refresh_token"],
                "response_types": ["code"],
            })
            assert registered.status_code == 201
            params = {
                "response_type": "code",
                "client_id": registered.json()["client_id"],
                "redirect_uri": "https://chatgpt.com/connector/oauth/cb_caddy_test",
                "scope": "experiments:read offline_access",
                "resource": ORIGIN + "/mcp",
                "state": "caddy-test-state",
                "code_challenge": "A" * 43,
                "code_challenge_method": "S256",
            }
            assert client.get("/oauth/authorize", params=params).status_code == 200
            assert client.post("/oauth/authorize", data={**params, "decision": "approve"},
                               headers={"Origin": ORIGIN}).status_code == 403
            assert client.post("/oauth/authorize", data={**params, "csrf": csrf,
                                                           "decision": "approve"},
                               headers={"Origin": "https://attacker.example"}).status_code == 403

            invalid_bearer = client.post("/mcp", json={
                "jsonrpc": "2.0", "id": 1, "method": "tools/list",
            }, headers={"Authorization": "Bearer invalid-caddy-test-token",
                        "Accept": "application/json, text/event-stream"})
            assert invalid_bearer.status_code == 401

            # The successful login above is the first attempt in this source
            # bucket, so four failed attempts must exhaust its five-attempt cap.
            for index in range(4):
                response = client.post("/auth/login", data={
                    "password": f"incorrect-caddy-test-password-{index}", "next": "/",
                }, headers={
                    "X-Forwarded-For": f"198.51.100.{10 + index}",
                    "Forwarded": f"for=198.51.100.{100 + index};proto=https",
                })
                assert response.status_code == 401
                time.sleep(1.05)
            blocked = client.post("/auth/login", data={
                "password": "incorrect-caddy-test-password-final", "next": "/",
            }, headers={
                "X-Forwarded-For": "203.0.113.250",
                "Forwarded": "for=203.0.113.250;proto=https",
            })
            assert blocked.status_code == 429

            token_canary = "synthetic-setup-token-" + uuid.uuid4().hex
            code_canary = "synthetic-oauth-code-" + uuid.uuid4().hex
            failed = client.get("/__caddy_test_upstream_failure/" +
                                f"?token={token_canary}&code={code_canary}")
            assert failed.status_code == 502

        logs = _run(base + ["logs", "--no-color", "caddy"], check=False).stdout
        assert setup_token not in logs
        assert token_canary not in logs
        assert code_canary not in logs
        assert "synthetic-setup-token" not in logs
        assert "synthetic-oauth-code" not in logs
        api_logs = _run(base + ["logs", "--no-color", "api"], check=False).stdout
        assert setup_token not in api_logs
        assert token_canary not in api_logs
        assert code_canary not in api_logs
        assert "synthetic-setup-token" not in api_logs
        assert "synthetic-oauth-code" not in api_logs
        published_ports = _run(base + ["port", "api"], check=False).stdout
        assert "8000" not in published_ports
    finally:
        _run(base + ["down", "--volumes", "--remove-orphans"], check=False, timeout=120)

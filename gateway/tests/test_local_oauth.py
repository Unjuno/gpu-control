import base64
import hashlib
import secrets
from urllib.parse import parse_qs, urlsplit

from fastapi.testclient import TestClient

from gpu_gateway.app import create_app
from gpu_gateway.auth import Auth
from gpu_gateway.config import Settings, Workload
from gpu_gateway.service import ExperimentService
from gpu_gateway.store import Store


def challenge(verifier: str) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()


def test_local_oauth_bootstrap_login_dcr_pkce_refresh_and_mcp(tmp_path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'oauth.db'}",
        public_url="https://gateway.example",
    )
    store = Store(settings.database_url)
    store.initialize()
    service = ExperimentService(store, settings, {"demo": Workload(provider="demo")})
    auth = Auth(settings, store=store)
    auth.local.seed_bootstrap("bootstrap-secret", ttl_seconds=3600)
    client = TestClient(create_app(settings, service=service, auth=auth))

    health = client.get("/healthz").json()
    assert health["configured"] is True
    assert health["auth_configured"] is False
    assert health["auth_mode"] == "local_oauth"

    setup = client.post("/auth/setup", data={"token":"bootstrap-secret", "password":"correct horse battery staple"}, follow_redirects=False)
    assert setup.status_code == 303
    assert setup.headers["location"] == "/auth/login"
    assert client.get("/healthz").json()["auth_configured"] is True

    login = client.post("/auth/login", data={"password":"correct horse battery staple", "next":"/"}, follow_redirects=False)
    assert login.status_code == 303
    assert client.get("/api/session").status_code == 200

    meta = client.get("/.well-known/oauth-protected-resource/mcp").json()
    assert meta["authorization_servers"] == ["https://gateway.example"]
    discovery = client.get("/.well-known/oauth-authorization-server").json()
    assert discovery["registration_endpoint"].endswith("/oauth/register")
    assert "offline_access" in discovery["scopes_supported"]
    assert "refresh_token" in discovery["grant_types_supported"]

    registered = client.post("/oauth/register", json={
        "client_name": "ChatGPT test",
        "redirect_uris": ["https://chatgpt.com/oauth/callback/test"],
        "token_endpoint_auth_method": "none",
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
    })
    assert registered.status_code == 201
    client_id = registered.json()["client_id"]

    verifier = secrets.token_urlsafe(48)
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": "https://chatgpt.com/oauth/callback/test",
        "scope": "experiments:read offline_access",
        "resource": settings.resource,
        "state": "state-1",
        "code_challenge": challenge(verifier),
        "code_challenge_method": "S256",
    }
    authorized = client.get("/oauth/authorize", params=params, follow_redirects=False)
    assert authorized.status_code == 303
    query = parse_qs(urlsplit(authorized.headers["location"]).query)
    assert query["state"] == ["state-1"]
    code = query["code"][0]

    tokens = client.post("/oauth/token", data={
        "grant_type": "authorization_code",
        "client_id": client_id,
        "code": code,
        "redirect_uri": params["redirect_uri"],
        "code_verifier": verifier,
        "resource": settings.resource,
    })
    assert tokens.status_code == 200
    token_data = tokens.json()
    assert token_data["token_type"] == "Bearer"
    assert token_data["refresh_token"].startswith("gr_")

    headers = {
        "Authorization": "Bearer " + token_data["access_token"],
        "Accept": "application/json, text/event-stream",
    }
    mcp = client.post("/mcp", headers=headers, json={"jsonrpc":"2.0","id":1,"method":"tools/list"})
    assert mcp.status_code == 200
    names = {tool["name"] for tool in mcp.json()["result"]["tools"]}
    assert "integrations_list" in names

    refreshed = client.post("/oauth/token", data={
        "grant_type": "refresh_token",
        "client_id": client_id,
        "refresh_token": token_data["refresh_token"],
        "resource": settings.resource,
    })
    assert refreshed.status_code == 200
    assert refreshed.json()["access_token"] != token_data["access_token"]


def test_local_oauth_rejects_untrusted_redirect_and_wrong_pkce(tmp_path):
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'reject.db'}", public_url="https://gateway.example")
    store = Store(settings.database_url)
    store.initialize()
    service = ExperimentService(store, settings, {"demo": Workload(provider="demo")})
    auth = Auth(settings, store=store)
    auth.local.seed_bootstrap("bootstrap-secret")
    auth.local.bootstrap_admin("bootstrap-secret", "correct horse battery staple")
    client = TestClient(create_app(settings, service=service, auth=auth))

    bad = client.post("/oauth/register", json={"redirect_uris":["https://attacker.example/callback"]})
    assert bad.status_code == 400

    registered = client.post("/oauth/register", json={"redirect_uris":["https://chatgpt.com/oauth/callback/test"]})
    client_id = registered.json()["client_id"]
    login = client.post("/auth/login", data={"password":"correct horse battery staple","next":"/"}, follow_redirects=False)
    assert login.status_code == 303
    verifier = secrets.token_urlsafe(48)
    params = {
        "response_type":"code", "client_id":client_id,
        "redirect_uri":"https://chatgpt.com/oauth/callback/test",
        "scope":"experiments:read", "resource":settings.resource,
        "code_challenge":challenge(verifier), "code_challenge_method":"S256",
    }
    authorized = client.get("/oauth/authorize", params=params, follow_redirects=False)
    code = parse_qs(urlsplit(authorized.headers["location"]).query)["code"][0]
    failed = client.post("/oauth/token", data={
        "grant_type":"authorization_code", "client_id":client_id, "code":code,
        "redirect_uri":params["redirect_uri"], "code_verifier":"x" * 48,
        "resource":settings.resource,
    })
    assert failed.status_code == 400

import base64
import hashlib
import secrets
import threading
import time
from contextlib import contextmanager
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from gpu_gateway.app import create_app
from gpu_gateway.auth import Auth
from gpu_gateway.config import Settings, Workload
from gpu_gateway.local_oauth import LocalOAuth, oauth_codes, oauth_tokens
from gpu_gateway.service import ExperimentService, GatewayError
from gpu_gateway.store import Store


def challenge(verifier: str) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()


def test_refresh_rotation_and_grant_revocation_are_atomic(tmp_path, monkeypatch):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'oauth-revoke-race.db'}",
        public_url="https://gateway.example",
    )
    store = Store(settings.database_url)
    store.initialize()
    oauth = LocalOAuth(settings, store)
    client_id = oauth.register_client({
        "client_name": "ChatGPT test",
        "redirect_uris": ["https://chatgpt.com/oauth/callback/test"],
    })["client_id"]
    initial = oauth._new_token_pair(
        client_id=client_id, subject="owner",
        scope="experiments:read offline_access", resource=settings.resource,
    )
    pair_entered = threading.Event()
    allow_pair_to_finish = threading.Event()
    revoke_transaction_acquired = threading.Event()
    original_new_pair = oauth._new_token_pair
    original_transaction = store.transaction
    errors = []
    refreshed = []

    @contextmanager
    def observe_revoke_transaction():
        if threading.current_thread().name == "oauth-revoke-race":
            with original_transaction() as connection:
                revoke_transaction_acquired.set()
                yield connection
        else:
            with original_transaction() as connection:
                yield connection

    def pause_replacement_pair(**kwargs):
        pair_entered.set()
        if not allow_pair_to_finish.wait(timeout=5):
            raise TimeoutError("test did not release replacement token pair")
        return original_new_pair(**kwargs)

    monkeypatch.setattr(store, "transaction", observe_revoke_transaction)
    monkeypatch.setattr(oauth, "_new_token_pair", pause_replacement_pair)

    def refresh():
        try:
            refreshed.append(oauth.token({
                "grant_type": "refresh_token", "client_id": client_id,
                "refresh_token": initial["refresh_token"], "resource": settings.resource,
            }))
        except Exception as exc:  # surface worker-thread failures in the test thread
            errors.append(exc)

    def revoke():
        try:
            oauth.revoke({"client_id": client_id, "token": initial["refresh_token"]})
        except Exception as exc:
            errors.append(exc)

    refresh_thread = threading.Thread(target=refresh, name="oauth-refresh-race")
    refresh_thread.start()
    assert pair_entered.wait(timeout=5)
    revoke_thread = threading.Thread(target=revoke, name="oauth-revoke-race")
    revoke_thread.start()
    # Give the revoker a chance to reach BEGIN IMMEDIATE while rotation still
    # owns the write transaction. With split transactions it acquires and
    # completes in this gap, before replacement rows exist.
    time.sleep(0.05)
    blocked_until_rotation_commits = not revoke_transaction_acquired.is_set()
    allow_pair_to_finish.set()
    refresh_thread.join(timeout=5)
    revoke_thread.join(timeout=5)

    assert not refresh_thread.is_alive() and not revoke_thread.is_alive()
    assert not errors
    assert blocked_until_rotation_commits
    assert revoke_transaction_acquired.is_set()
    assert len(refreshed) == 1
    with pytest.raises(GatewayError) as error:
        oauth.verify_access(refreshed[0]["access_token"])
    assert error.value.code == "invalid_token"
    with pytest.raises(GatewayError) as error:
        oauth.token({
            "grant_type": "refresh_token", "client_id": client_id,
            "refresh_token": refreshed[0]["refresh_token"], "resource": settings.resource,
        })
    assert error.value.code == "invalid_grant"


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
    client = TestClient(create_app(settings, service=service, auth=auth), base_url="https://gateway.example")

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
    assert discovery["revocation_endpoint"] == "https://gateway.example/oauth/revoke"
    assert "offline_access" in discovery["scopes_supported"]
    assert "refresh_token" in discovery["grant_types_supported"]

    registered = client.post("/oauth/register", json={
        "client_name": "ChatGPT test",
        "redirect_uris": ["https://chatgpt.com/connector/oauth/cb_123-test"],
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
        "redirect_uri": "https://chatgpt.com/connector/oauth/cb_123-test",
        "scope": "experiments:read offline_access",
        "resource": settings.resource,
        "state": "state-1",
        "code_challenge": challenge(verifier),
        "code_challenge_method": "S256",
    }
    forged_consent = client.get("/oauth/authorize", params={**params, "decision": "approve"}, follow_redirects=False)
    assert forged_consent.status_code == 400
    consent = client.get("/oauth/authorize", params=params, follow_redirects=False)
    assert consent.status_code == 200
    assert "ChatGPT test" in consent.text
    assert "experiments:read" in consent.text
    assert "offline_access" in consent.text
    with store.engine.connect() as connection:
        assert connection.execute(select(oauth_codes.c.code_hash)).first() is None

    owner_session = auth.local.session(client.cookies.get("gpu_gateway_session"))
    denied = client.post("/oauth/authorize", data={**params, "csrf": owner_session["csrf"], "decision": "deny"},
                         headers={"Origin": settings.public_url}, follow_redirects=False)
    assert denied.status_code == 303
    denial_query = parse_qs(urlsplit(denied.headers["location"]).query)
    assert denial_query["error"] == ["access_denied"]
    assert denial_query["state"] == ["state-1"]
    with store.engine.connect() as connection:
        assert connection.execute(select(oauth_codes.c.code_hash)).first() is None

    missing_csrf = client.post("/oauth/authorize", data={**params, "decision": "approve"},
                               headers={"Origin": settings.public_url}, follow_redirects=False)
    assert missing_csrf.status_code == 403
    wrong_origin = client.post("/oauth/authorize", data={**params, "csrf": owner_session["csrf"], "decision": "approve"},
                               headers={"Origin": "https://attacker.example"}, follow_redirects=False)
    assert wrong_origin.status_code == 403

    authorized = client.post("/oauth/authorize", data={**params, "csrf": owner_session["csrf"], "decision": "approve"},
                             headers={"Origin": settings.public_url}, follow_redirects=False)
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

    scope_expansion = client.post("/oauth/token", data={
        "grant_type": "refresh_token",
        "client_id": client_id,
        "refresh_token": token_data["refresh_token"],
        "resource": settings.resource,
        "scope": "experiments:read experiments:run offline_access",
    })
    assert scope_expansion.status_code == 400

    headers = {
        "Authorization": "Bearer " + token_data["access_token"],
        "Accept": "application/json, text/event-stream",
    }
    mcp = client.post("/mcp", headers=headers, json={"jsonrpc":"2.0","id":1,"method":"tools/list"})
    assert mcp.status_code == 200
    names = {tool["name"] for tool in mcp.json()["result"]["tools"]}
    assert "experiment_capabilities" in names
    assert "integrations_list" not in names

    refreshed = client.post("/oauth/token", data={
        "grant_type": "refresh_token",
        "client_id": client_id,
        "refresh_token": token_data["refresh_token"],
        "resource": settings.resource,
    })
    assert refreshed.status_code == 200
    assert refreshed.json()["access_token"] != token_data["access_token"]

    refreshed_tokens = refreshed.json()
    token_hashes = [hashlib.sha256(value.encode()).hexdigest() for value in (
        token_data["refresh_token"], refreshed_tokens["access_token"], refreshed_tokens["refresh_token"]
    )]
    with store.engine.connect() as connection:
        grant_ids = connection.execute(select(oauth_tokens.c.grant_id).where(
            oauth_tokens.c.token_hash.in_(token_hashes)
        )).scalars().all()
    assert len(grant_ids) == 3 and len(set(grant_ids)) == 1

    still_valid = client.post("/mcp", headers={
        "Authorization": "Bearer " + refreshed_tokens["access_token"],
        "Accept": "application/json, text/event-stream",
    }, json={"jsonrpc":"2.0","id":2,"method":"tools/list"})
    assert still_valid.status_code == 200

    other_client = client.post("/oauth/register", json={
        "client_name": "Other MCP client",
        "redirect_uris": ["https://chatgpt.com/connector_platform_oauth_redirect"],
    }).json()["client_id"]
    wrong_client_revoke = client.post("/oauth/revoke", data={
        "client_id": other_client,
        "token": token_data["access_token"],
    })
    assert wrong_client_revoke.status_code == 200
    still_valid_after_wrong_client = client.post("/mcp", headers={
        "Authorization": "Bearer " + token_data["access_token"],
        "Accept": "application/json, text/event-stream",
    }, json={"jsonrpc":"2.0","id":3,"method":"tools/list"})
    assert still_valid_after_wrong_client.status_code == 200

    revoked_access = client.post("/oauth/revoke", data={
        "client_id": client_id,
        "token": token_data["access_token"],
        "token_type_hint": "access_token",
    })
    assert revoked_access.status_code == 200
    assert revoked_access.content == b""
    rejected_access = client.post("/mcp", headers={
        "Authorization": "Bearer " + token_data["access_token"],
        "Accept": "application/json, text/event-stream",
    }, json={"jsonrpc":"2.0","id":4,"method":"tools/list"})
    assert rejected_access.status_code == 401

    revoked_refresh = client.post("/oauth/revoke", data={
        "client_id": client_id,
        # Rotation marks the presented refresh token revoked. Repeating revoke
        # with that prior token must still revoke every credential in its grant.
        "token": token_data["refresh_token"],
        "token_type_hint": "refresh_token",
    })
    assert revoked_refresh.status_code == 200
    assert revoked_refresh.content == b""
    rejected_refresh = client.post("/oauth/token", data={
        "grant_type": "refresh_token",
        "client_id": client_id,
        "refresh_token": refreshed_tokens["refresh_token"],
        "resource": settings.resource,
    })
    assert rejected_refresh.status_code == 400

    rejected_cascaded_access = client.post("/mcp", headers={
        "Authorization": "Bearer " + refreshed_tokens["access_token"],
        "Accept": "application/json, text/event-stream",
    }, json={"jsonrpc":"2.0","id":5,"method":"tools/list"})
    assert rejected_cascaded_access.status_code == 401
    with store.engine.connect() as connection:
        revoked_states = connection.execute(select(oauth_tokens.c.revoked).where(
            oauth_tokens.c.token_hash.in_(token_hashes)
        )).scalars().all()
    assert revoked_states == [True, True, True]

    unknown = client.post("/oauth/revoke", data={"client_id": client_id, "token": "unknown-token"})
    assert unknown.status_code == 200
    missing_token = client.post("/oauth/revoke", data={"client_id": client_id})
    assert missing_token.status_code == 400


def test_local_oauth_rejects_untrusted_redirect_and_wrong_pkce(tmp_path):
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'reject.db'}", public_url="https://gateway.example")
    store = Store(settings.database_url)
    store.initialize()
    service = ExperimentService(store, settings, {"demo": Workload(provider="demo")})
    auth = Auth(settings, store=store)
    auth.local.seed_bootstrap("bootstrap-secret")
    auth.local.bootstrap_admin("bootstrap-secret", "correct horse battery staple")
    client = TestClient(create_app(settings, service=service, auth=auth), base_url="https://gateway.example")

    for redirect_uri in (
        "https://attacker.example/callback",
        "https://evil.chatgpt.com/connector_platform_oauth_redirect",
        "https://openai.com/connector_platform_oauth_redirect",
        "https://chatgpt.com.evil.example/connector_platform_oauth_redirect",
        "https://chatgpt.com/connector/oauth/callback?next=https://attacker.example",
    ):
        bad = client.post("/oauth/register", json={"redirect_uris":[redirect_uri]})
        assert bad.status_code == 400, redirect_uri

    registered = client.post("/oauth/register", json={"redirect_uris":["https://chatgpt.com/connector/oauth/callback-123"]})
    client_id = registered.json()["client_id"]
    login = client.post("/auth/login", data={"password":"correct horse battery staple","next":"/"}, follow_redirects=False)
    assert login.status_code == 303
    verifier = secrets.token_urlsafe(48)
    params = {
        "response_type":"code", "client_id":client_id,
        "redirect_uri":"https://chatgpt.com/connector/oauth/callback-123",
        "scope":"experiments:read", "resource":settings.resource,
        "code_challenge":challenge(verifier), "code_challenge_method":"S256",
    }
    consent = client.get("/oauth/authorize", params=params, follow_redirects=False)
    assert consent.status_code == 200
    owner_session = auth.local.session(client.cookies.get("gpu_gateway_session"))
    authorized = client.post("/oauth/authorize", data={
        **params, "csrf": owner_session["csrf"], "decision": "approve",
    }, headers={"Origin": settings.public_url}, follow_redirects=False)
    assert authorized.status_code == 303
    code = parse_qs(urlsplit(authorized.headers["location"]).query)["code"][0]
    failed = client.post("/oauth/token", data={
        "grant_type":"authorization_code", "client_id":client_id, "code":code,
        "redirect_uri":params["redirect_uri"], "code_verifier":"x" * 48,
        "resource":settings.resource,
    })
    assert failed.status_code == 400


def test_refresh_rotation_rolls_back_revocation_if_new_pair_insert_fails(tmp_path, monkeypatch):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'refresh-atomic.db'}",
        public_url="https://gateway.example",
    )
    store = Store(settings.database_url)
    store.initialize()
    auth = Auth(settings, store=store)
    local = auth.local
    client_id = local.register_client({
        "redirect_uris": ["https://chatgpt.com/connector_platform_oauth_redirect"],
    })["client_id"]
    original = local._new_token_pair(
        client_id=client_id, subject="owner", scope="experiments:read offline_access",
        resource=settings.resource,
    )
    real_insert = local._insert_token

    def fail_refresh_insert(connection, raw, **kwargs):
        if kwargs["kind"] == "refresh":
            raise RuntimeError("injected token persistence failure")
        return real_insert(connection, raw, **kwargs)

    monkeypatch.setattr(local, "_insert_token", fail_refresh_insert)
    with pytest.raises(RuntimeError, match="injected token persistence failure"):
        local.token({
            "grant_type": "refresh_token", "client_id": client_id,
            "refresh_token": original["refresh_token"], "resource": settings.resource,
        })

    monkeypatch.setattr(local, "_insert_token", real_insert)
    with store.engine.connect() as connection:
        tokens = connection.execute(select(oauth_tokens.c.kind, oauth_tokens.c.revoked)).all()
    assert sorted(tokens, key=lambda row: row.kind) == [
        ("access", False), ("refresh", False),
    ]

    retried = local.token({
        "grant_type": "refresh_token", "client_id": client_id,
        "refresh_token": original["refresh_token"], "resource": settings.resource,
    })
    assert retried["refresh_token"] != original["refresh_token"]


def test_local_oauth_failed_login_rate_limit_persists_and_expires(tmp_path, monkeypatch):
    now = [1_800_000_000]
    monkeypatch.setattr("gpu_gateway.local_oauth.time.time", lambda: now[0])
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'rate-limit.db'}",
        public_url="https://gateway.example",
    )
    store = Store(settings.database_url)
    store.initialize()
    auth = Auth(settings, store=store)
    auth.local.seed_bootstrap("one-time-setup", ttl_seconds=600)
    auth.local.bootstrap_admin("one-time-setup", "correct horse battery staple")

    for _ in range(4):
        with pytest.raises(GatewayError) as error:
            auth.local.login("incorrect password")
        assert error.value.code == "invalid_credentials"
    with pytest.raises(GatewayError) as error:
        auth.local.login("incorrect password")
    assert error.value.code == "login_rate_limited"

    # A separately constructed auth facade shares the persisted lockout state.
    second_auth = Auth(settings, store=Store(settings.database_url))
    with pytest.raises(GatewayError) as error:
        second_auth.local.login("correct horse battery staple")
    assert error.value.code == "login_rate_limited"

    now[0] += 301
    with pytest.raises(GatewayError) as error:
        second_auth.local.login("incorrect password")
    assert error.value.code == "invalid_credentials"


def test_dcr_registration_is_idempotent_and_reclaimable(tmp_path):
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'dcr.db'}", public_url="https://gateway.example")
    store = Store(settings.database_url)
    store.initialize()
    service = ExperimentService(store, settings, {"demo": Workload(provider="demo")})
    auth = Auth(settings, store=store)
    auth.local.seed_bootstrap("bootstrap-secret")
    auth.local.bootstrap_admin("bootstrap-secret", "correct horse battery staple")
    client = TestClient(create_app(settings, service=service, auth=auth), base_url="https://gateway.example")
    payload = {"client_name":"ChatGPT","redirect_uris":["https://chatgpt.com/connector_platform_oauth_redirect"]}
    first = client.post("/oauth/register", json=payload)
    second = client.post("/oauth/register", json=payload)
    assert first.status_code == 201 and second.status_code == 201
    assert first.json()["client_id"] == second.json()["client_id"]

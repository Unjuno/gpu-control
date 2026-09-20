from __future__ import annotations

import time
from dataclasses import replace
from types import SimpleNamespace

import jwt
import pytest
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from gpu_gateway.app import create_app
from gpu_gateway.auth import Auth
from gpu_gateway.config import Settings, Workload
from gpu_gateway.service import ExperimentService, Principal
from gpu_gateway.store import Store

SCOPES = frozenset({"experiments:read", "experiments:run", "experiments:cancel"})


class Clock:
    def __init__(self): self.value = int(time.time())
    def __call__(self): return self.value
    def advance(self, seconds): self.value += seconds


@pytest.fixture
def system(tmp_path):
    clock = Clock()
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'test.db'}", public_url="https://gateway.example",
        issuer="https://issuer.example", jwks_url="https://issuer.example/jwks", allowed_subjects=("owner", "other"),
        cookie_key=Fernet.generate_key().decode())
    store = Store(settings.database_url); store.initialize()
    service = ExperimentService(store, settings, {"demo": Workload(provider="demo")}, clock)
    owner = Principal("owner", SCOPES)
    browser = replace(owner, browser=True)
    return SimpleNamespace(clock=clock, settings=settings, store=store, service=service, owner=owner, browser=browser)


@pytest.fixture
def web(system):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    keys = SimpleNamespace(get_signing_key_from_jwt=lambda token: SimpleNamespace(key=key.public_key()))
    auth = Auth(system.settings, keys=keys)
    def token(sub="owner", **overrides):
        data = dict(iss=system.settings.issuer, sub=sub, aud=system.settings.resource,
                    exp=int(time.time()) + 1200, iat=int(time.time()), scope=" ".join(SCOPES))
        data.update(overrides)
        return jwt.encode(data, key, algorithm="RS256")
    access = token()
    owner = auth.verify(access)
    system.owner = owner
    system.browser = replace(owner, browser=True)
    client = TestClient(create_app(system.settings, service=system.service, auth=auth))
    csrf = "test-csrf"
    client.cookies.set("gpu_gateway_session", auth.seal({"access_token": access, "csrf": csrf}))
    return SimpleNamespace(**vars(system), client=client, auth=auth, token=token,
        browser_headers={"Origin": system.settings.public_url, "X-CSRF-Token": csrf},
        headers={"Authorization": "Bearer " + access, "Accept": "application/json, text/event-stream"})

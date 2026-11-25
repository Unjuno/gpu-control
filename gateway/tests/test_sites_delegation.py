import base64
from dataclasses import replace
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select

from gpu_gateway.app import create_app
from gpu_gateway.config import Settings
from gpu_gateway.migrations import migrate, sites_delegation_nonces
from gpu_gateway.service import GatewayError, Prepare
from gpu_gateway.sites_delegation import (
    canonical_payload,
    principal_for,
    signature_for,
    verify_and_claim,
)


KEY = b"sites-delegation-test-key-material-32-bytes"


def settings():
    value = Settings(
        sites_delegation_key_id="sites-v1",
        sites_delegation_hmac_key_b64=base64.b64encode(KEY).decode(),
    )
    value.validate()
    return value


def engine():
    value = create_engine("sqlite+pysqlite:///:memory:")
    migrate(value)
    return value


def payload(**overrides):
    value = {
        "version": 1,
        "key_id": "sites-v1",
        "owner": "chatgpt-owner_123@example",
        "tool": "experiment_capabilities",
        "arguments": {},
        "nonce": "a" * 32,
        "issued_at": 1_000,
        "expires_at": 1_060,
    }
    value.update(overrides)
    return value


def verify(value, db, **overrides):
    signed_body = canonical_payload(value)
    return verify_and_claim(
        payload=value,
        signed_body=signed_body,
        signature=signature_for(value, KEY),
        settings=settings(),
        engine=db,
        expected_tool=overrides.pop("expected_tool", value["tool"]),
        now=overrides.pop("now", 1_030),
        **overrides,
    )


def test_exact_signed_request_is_claimed_once_and_owner_is_pseudonymous():
    db = engine()
    request = verify(payload(), db)
    principal = principal_for(request)
    assert principal.owner.startswith("sites:")
    assert request.owner not in principal.owner
    assert principal.scopes == frozenset({"experiments:read"})
    with db.connect() as connection:
        assert connection.execute(select(func.count()).select_from(sites_delegation_nonces)).scalar_one() == 1
    with pytest.raises(GatewayError, match="already used") as replay:
        verify(payload(), db)
    assert replay.value.code == "delegation_replayed"


@pytest.mark.parametrize("change", [
    {"owner": "another-owner"},
    {"arguments": {"run_id": "b" * 32}},
    {"tool": "experiment_list"},
    {"expires_at": 1_061},
])
def test_any_signed_field_tampering_is_rejected(change):
    db = engine()
    original = payload()
    signature = signature_for(original, KEY)
    modified = {**original, **change}
    with pytest.raises(GatewayError) as error:
        verify_and_claim(
            payload=modified, signed_body=canonical_payload(modified), signature=signature,
            settings=settings(), engine=db,
            expected_tool=modified["tool"], now=1_030,
        )
    assert error.value.code == "invalid_delegation"


def test_route_tool_mismatch_and_expired_window_are_rejected_without_claim():
    db = engine()
    value = payload()
    with pytest.raises(GatewayError) as mismatch:
        verify(value, db, expected_tool="experiment_list")
    assert mismatch.value.code == "invalid_delegation"
    with pytest.raises(GatewayError) as expired:
        verify(value, db, now=1_061)
    assert expired.value.code == "delegation_expired"
    with db.connect() as connection:
        assert connection.execute(select(func.count()).select_from(sites_delegation_nonces)).scalar_one() == 0


def test_submit_and_cancel_receive_only_their_minimum_scopes():
    db = engine()
    submit = payload(tool="experiment_submit", arguments={
        "run_id": "b" * 32, "plan_fingerprint": "c" * 64,
    })
    submit_principal = principal_for(verify(submit, db))
    assert submit_principal.scopes == frozenset({"experiments:read", "experiments:run"})
    cancel = payload(tool="experiment_cancel", arguments={"run_id": "b" * 32}, nonce="d" * 32)
    cancel_principal = principal_for(verify(cancel, db))
    assert cancel_principal.scopes == frozenset({"experiments:read", "experiments:cancel"})


def test_configuration_requires_key_id_and_strong_key():
    with pytest.raises(ValueError, match="key ID"):
        replace(settings(), sites_delegation_key_id="").validate()
    weak = base64.b64encode(b"too-short").decode()
    with pytest.raises(ValueError, match="32-4096"):
        replace(settings(), sites_delegation_hmac_key_b64=weak).validate()


def test_internal_http_boundary_dispatches_read_and_rejects_replay(web):
    configured = replace(
        web.settings,
        sites_delegation_key_id="sites-v1",
        sites_delegation_hmac_key_b64=base64.b64encode(KEY).decode(),
    )
    client = TestClient(create_app(configured, service=web.service, auth=web.auth))
    now = int(time.time())
    value = payload(issued_at=now, expires_at=now + 60)
    headers = {"x-gpu-control-sites-signature": signature_for(value, KEY)}
    response = client.post(
        "/internal/sites/v1/tools/experiment_capabilities", content=canonical_payload(value),
        headers={**headers, "content-type": "application/json"})
    assert response.status_code == 200
    assert response.json()["schema_version"] == 2
    replay = client.post(
        "/internal/sites/v1/tools/experiment_capabilities", content=canonical_payload(value),
        headers={**headers, "content-type": "application/json"})
    assert replay.status_code == 409
    assert replay.json()["code"] == "delegation_replayed"


def test_internal_http_boundary_requires_and_consumes_exact_plan_authorization(web):
    configured = replace(
        web.settings,
        sites_delegation_key_id="sites-v1",
        sites_delegation_hmac_key_b64=base64.b64encode(KEY).decode(),
    )
    client = TestClient(create_app(configured, service=web.service, auth=web.auth))
    now = int(web.clock())
    owner_request = payload(
        owner="owner-123", tool="experiment_submit", nonce="f" * 32,
        arguments={}, issued_at=now, expires_at=now + 60,
    )
    from gpu_gateway.sites_delegation import DelegatedRequest, principal_for
    principal = principal_for(DelegatedRequest(
        key_id="sites-v1", owner=owner_request["owner"], tool="experiment_submit",
        arguments={}, nonce=owner_request["nonce"], issued_at=now, expires_at=now + 60,
    ))
    prepared = web.service.prepare(principal, Prepare(
        workload="demo", parameters={}, runtime_seconds=30,
        max_cost_usd="0.10", idempotency_key="sites-submit-approval",
    ))
    authorization_id = "1" * 32
    submit_arguments = {
        "run_id": prepared["id"], "plan_fingerprint": prepared["fingerprint"],
        "approved_plan": prepared["plan"],
        "authorization": {
            "authorization_id": authorization_id,
            "source": "chatgpt_mcp_write_confirmation",
            "authorized_at": now,
            "expires_at": now + 60,
        },
    }
    value = payload(
        tool="experiment_submit", nonce="f" * 32,
        owner="owner-123", arguments=submit_arguments,
        issued_at=now, expires_at=now + 60,
    )
    response = client.post(
        "/internal/sites/v1/tools/experiment_submit", content=canonical_payload(value),
        headers={"content-type": "application/json",
                 "x-gpu-control-sites-signature": signature_for(value, KEY)},
    )
    assert response.status_code == 200
    assert response.json()["machine_state"]["state"] == "queued"

    # A transport retry needs a new nonce but reuses the same one-use approval
    # and resolves to the already-queued run rather than creating another run.
    retry = {**value, "nonce": "2" * 32}
    retry_response = client.post(
        "/internal/sites/v1/tools/experiment_submit", content=canonical_payload(retry),
        headers={"content-type": "application/json",
                 "x-gpu-control-sites-signature": signature_for(retry, KEY)},
    )
    assert retry_response.status_code == 200
    assert retry_response.json()["machine_state"]["run_id"] == prepared["id"]

    second = web.service.prepare(principal, Prepare(
        workload="demo", parameters={}, runtime_seconds=20,
        max_cost_usd="0.10", idempotency_key="sites-submit-approval-2",
    ))
    reused = {**value, "nonce": "4" * 32, "arguments": {
        **submit_arguments, "run_id": second["id"],
        "plan_fingerprint": second["fingerprint"], "approved_plan": second["plan"],
    }}
    reused_response = client.post(
        "/internal/sites/v1/tools/experiment_submit", content=canonical_payload(reused),
        headers={"content-type": "application/json",
                 "x-gpu-control-sites-signature": signature_for(reused, KEY)},
    )
    assert reused_response.status_code == 409
    assert reused_response.json()["code"] == "delegated_authorization_reused"


def test_transport_signature_without_exact_plan_authorization_is_rejected(web):
    configured = replace(
        web.settings,
        sites_delegation_key_id="sites-v1",
        sites_delegation_hmac_key_b64=base64.b64encode(KEY).decode(),
    )
    client = TestClient(create_app(configured, service=web.service, auth=web.auth))
    now = int(time.time())
    value = payload(tool="experiment_submit", nonce="3" * 32,
                    arguments={"run_id": "b" * 32, "plan_fingerprint": "c" * 64},
                    issued_at=now, expires_at=now + 60)
    response = client.post(
        "/internal/sites/v1/tools/experiment_submit", content=canonical_payload(value),
        headers={"content-type": "application/json",
                 "x-gpu-control-sites-signature": signature_for(value, KEY)},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "invalid_arguments"


def test_signature_verification_uses_exact_received_bytes_not_cross_language_number_formatting():
    db = engine()
    raw = (b'{"arguments":{"rate":0.000001},"expires_at":1060,"issued_at":1000,'
           b'"key_id":"sites-v1","nonce":"eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",'
           b'"owner":"owner-123","tool":"experiment_prepare","version":1}')
    import json
    parsed = json.loads(raw)
    signed = create_hmac(raw)
    request = verify_and_claim(
        payload=parsed, signed_body=raw, signature=signed, settings=settings(),
        engine=db, expected_tool="experiment_prepare", now=1030,
    )
    assert request.arguments == {"rate": 0.000001}


def create_hmac(raw):
    import hashlib
    import hmac
    return hmac.new(KEY, raw, hashlib.sha256).hexdigest()

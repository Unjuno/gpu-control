from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gpu_gateway.ci_bridge import (ACTIONS_ISSUER, BridgeError, GitHubOIDC, Policy,
    parse_command, validate_event, validate_remote_comment, public_summary, owner_principal)
from gpu_gateway.ci_routes import install_ci_routes

BASE = Path(__file__).resolve().parents[1]
SHA = "a" * 40
IDENTIFIER = "b" * 32


@pytest.fixture
def policy():
    return Policy.load()


@pytest.fixture
def event(policy):
    created = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return {"action": "created", "repository": {"id": policy.repository_id, "owner": {"id": policy.owner_id}},
            "sender": {"id": policy.actor_id}, "issue": {"number": policy.issue_number, "state": "open"},
            "comment": {"id": 10001, "user": {"id": policy.actor_id, "type": "User"},
                        "body": "/gpu list", "created_at": created, "updated_at": created,
                        "issue_url": f"https://api.github.com/repos/{policy.repository}/issues/{policy.issue_number}"}}


@pytest.fixture
def env(policy):
    return {"GITHUB_EVENT_NAME": "issue_comment", "GITHUB_REPOSITORY": policy.repository,
            "GITHUB_REF": "refs/heads/main", "GITHUB_RUN_ATTEMPT": "1"}


@pytest.fixture
def signing(policy):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    keys = SimpleNamespace(get_signing_key_from_jwt=lambda _: SimpleNamespace(key=key.public_key()))
    verifier = GitHubOIDC(policy, SHA, keys=keys)
    now = int(time.time())
    claims = dict(iss=ACTIONS_ISSUER, aud=policy.audience, sub=sorted(policy.subjects)[0],
                  exp=now + 300, iat=now, nbf=now, jti="test-jti", repository=policy.repository,
                  repository_id=str(policy.repository_id), repository_owner_id=str(policy.owner_id),
                  actor_id=str(policy.actor_id), ref="refs/heads/main", event_name="issue_comment",
                  run_attempt="1", workflow_ref=policy.workflow_ref, workflow_sha=SHA, sha=SHA,
                  runner_environment="github-hosted", run_id="12345")
    def token(**overrides):
        return jwt.encode(dict(claims, **overrides), key, algorithm="RS256")
    return SimpleNamespace(verifier=verifier, token=token, claims=claims, key=key)


def envelope(event):
    return {"comment_id": event["comment"]["id"],
            "body_sha256": hashlib.sha256(event["comment"]["body"].encode()).hexdigest()}


def test_prepare_uses_comment_identity_not_supplied_authority(policy):
    raw = '/gpu prepare\n{"workload":"tiny-lm-t4","runtime_seconds":60,"max_cost_usd":"0.10","parameters":{"steps":5}}'
    command = parse_command(raw, repository_id=policy.repository_id, comment_id=100)
    assert command.tool == "experiments_prepare"
    assert command.arguments["idempotency_key"] == f"github:{policy.repository_id}:100"
    again = parse_command(raw, repository_id=policy.repository_id, comment_id=100)
    assert again == command


@pytest.mark.parametrize("body", [
    '/gpu approve\n{}', '/gpu run\n{}', '/gpu local\nrm -rf /', '/gpu local; echo x',
    '/gpu list\n{}', '/gpu prepare\n[]', '/gpu submit\n{"run_id":"main"}',
    '/gpu prepare\n{"workload":"demo","runtime_seconds":true,"max_cost_usd":"0.1"}',
    '/gpu prepare\n{"workload":"demo","runtime_seconds":0,"max_cost_usd":"0.1"}',
    '/gpu prepare\n{"workload":"demo","runtime_seconds":3601,"max_cost_usd":"0.1"}',
    '/gpu prepare\n{"workload":"demo","runtime_seconds":60,"max_cost_usd":0.1}',
    '/gpu prepare\n{"workload":"demo","runtime_seconds":60,"max_cost_usd":"NaN"}',
    '/gpu prepare\n{"workload":"demo","runtime_seconds":60,"runtime_seconds":1,"max_cost_usd":"0.1"}',
    '/gpu prepare\n{"workload":"demo","runtime_seconds":60,"max_cost_usd":"0.1","idempotency_key":"forged"}',
    '/gpu prepare\n{"workload":"demo","runtime_seconds":60,"max_cost_usd":"0.1","approved":true}',
    '/gpu prepare\n{"workload":"demo","runtime_seconds":60,"max_cost_usd":"0.1","command":"bash"}',
    '/gpu prepare\n{"workload":"$(whoami)","runtime_seconds":60,"max_cost_usd":"0.1"}',
    '/gpu prepare\n{"workload":"demo","runtime_seconds":60,"max_cost_usd":"0.1","parameters":{"x":NaN}}',
    '/gpu list\n' + 'x' * 9000,
])
def test_rejects_unstructured_or_injectable_commands(body, policy):
    with pytest.raises(BridgeError):
        parse_command(body, repository_id=policy.repository_id, comment_id=100)


@pytest.mark.parametrize("change", [
    {"action": "edited"}, {"sender": {"id": 55}},
    {"issue": {"number": 49, "state": "open"}},
    {"issue": {"number": 48, "state": "open", "pull_request": {}}},
    {"repository": {"id": 123, "owner": {"id": 241447786}}},
])
def test_untrusted_events_rejected(policy, env, event, change):
    event.update(change)
    with pytest.raises(BridgeError):
        validate_event(event, env, policy)


@pytest.mark.parametrize("key,value", [("GITHUB_RUN_ATTEMPT", "2"), ("GITHUB_EVENT_NAME", "pull_request"),
    ("GITHUB_REF", "refs/heads/feature"), ("GITHUB_REPOSITORY", "attacker/gpu-control")])
def test_untrusted_runner_context_rejected(policy, env, event, key, value):
    env[key] = value
    with pytest.raises(BridgeError):
        validate_event(event, env, policy)


def test_valid_event_and_live_comment(policy, env, event):
    assert validate_event(event, env, policy)[1].tool == "experiments_list"
    assert validate_remote_comment(event["comment"], event["issue"], envelope(event), policy).operation == "list"


@pytest.mark.parametrize("change", [{"updated_at": "2020-01-01T00:00:00Z"},
    {"body": "/gpu cancel\n{}"}, {"issue_url": "https://example.com"},
    {"user": {"id": 55, "type": "User"}}, {"id": 99},
    {"created_at": "2020-01-01T00:00:00Z", "updated_at": "2020-01-01T00:00:00Z"}])
def test_live_comment_binding(policy, event, change):
    original = envelope(event)
    event["comment"].update(change)
    with pytest.raises(BridgeError):
        validate_remote_comment(event["comment"], event["issue"], original, policy)


def test_oidc_accepts_both_verified_github_subject_formats(signing, policy):
    for subject in policy.subjects:
        assert signing.verifier.verify(signing.token(sub=subject))["run_id"] == "12345"


@pytest.mark.parametrize("override", [
    {"iss": "https://other.example"}, {"aud": "https://gpu-control.vercel.app/mcp"},
    {"sub": "repo:evil/repo:ref:refs/heads/main"}, {"actor_id": "55"},
    {"repository_id": "55"}, {"repository_owner_id": "55"},
    {"event_name": "pull_request"}, {"workflow_ref": "Unjuno/gpu-control/.github/workflows/ci.yml@refs/heads/main"},
    {"workflow_sha": "c" * 40}, {"sha": "c" * 40}, {"run_attempt": "2"},
    {"ref": "refs/pull/49/merge"}, {"runner_environment": "self-hosted"},
    {"exp": 1}, {"run_id": "$(x)"}, {"iat": 9999999999},
])
def test_oidc_rejects_wrong_identity_and_context(signing, override):
    with pytest.raises(BridgeError):
        signing.verifier.verify(signing.token(**override))


def test_oidc_rejects_unsigned_or_wrong_signature(signing):
    bad = jwt.encode(signing.claims, "incorrect-secret-that-is-long-enough", algorithm="HS256")
    with pytest.raises(BridgeError):
        signing.verifier.verify(bad)
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with pytest.raises(BridgeError):
        signing.verifier.verify(jwt.encode(signing.claims, other, algorithm="RS256"))


def test_no_deployed_sha_does_not_silently_trust_main(policy):
    with pytest.raises(BridgeError) as e:
        GitHubOIDC(policy, "").verify("anything")
    assert e.value.status == 503


def test_summary_hides_secrets_and_raw_logs(policy):
    result = {"id": IDENTIFIER, "state": "running", "fingerprint": "a" * 64,
              "plan": {"parameters": {"password": "secret"}}, "error": "api-key-secret",
              "result": {"stdout": "npg_password", "stderr": "secret", "gpu_used": True,
                         "metrics": {"loss": 1.2, "token": "secret", "steps": float("nan")}}}
    report = public_summary(result, policy.gateway_origin)
    text = json.dumps(report, allow_nan=False)
    assert "secret" not in text and "npg_" not in text and "stdout" not in text
    assert report["metrics"] == {"loss": 1.2}
    assert report["gpu_used"] is True
    assert public_summary({"state": []}, policy.gateway_origin) == {}


@pytest.fixture
def http_system(policy, signing, event):
    app = FastAPI()
    calls = []
    def invoke(principal, name, arguments):
        calls.append((principal, name, arguments))
        return {"id": IDENTIFIER, "state": "queued", "result": {"stdout": "secret", "metrics": {"loss": 1.0}}}
    service = SimpleNamespace(invoke=invoke, list=lambda _: {"worker_last_seen_at": 0},
                              get=lambda principal, run_id: {"id": run_id, "plan": {"provider": "demo"}})
    auth = SimpleNamespace(external=False, settings=SimpleNamespace(public_url=policy.gateway_origin), configured=lambda: True)
    app.state.service, app.state.auth = service, auth
    reader = SimpleNamespace(read=lambda _: (event["comment"], event["issue"]))
    install_ci_routes(app, policy=policy, verifier=signing.verifier, comments=reader)
    return SimpleNamespace(client=TestClient(app), calls=calls, app=app,
        headers={"Authorization": "Bearer " + signing.token()}, path="/api/ci/comment")


def test_authenticated_ci_request_is_never_browser_approval(http_system, event, policy):
    event["comment"]["body"] = '/gpu submit\n' + json.dumps({"run_id": IDENTIFIER})
    response = http_system.client.post(http_system.path, headers=http_system.headers, json=envelope(event))
    assert response.status_code == 200
    principal, name, args = http_system.calls[0]
    assert name == "experiments_submit" and args == {"run_id": IDENTIFIER}
    assert principal.browser is False and principal.owner == owner_principal(policy.gateway_origin).owner
    assert response.json()["worker_recently_seen"] is False
    assert response.json()["gpu_execution_confirmed"] is False
    assert "secret" not in response.text


@pytest.mark.parametrize("provider", ["modal", "runpod", "future-provider", None])
def test_paid_submit_is_denied_before_queue_mutation(http_system, event, provider):
    http_system.app.state.service.get = lambda principal, run_id: {"id": run_id, "plan": {"provider": provider}}
    event["comment"]["body"] = '/gpu submit\n' + json.dumps({"run_id": IDENTIFIER})
    response = http_system.client.post(http_system.path, headers=http_system.headers, json=envelope(event))
    assert response.status_code == 409
    assert response.json()["code"] == "paid_submission_parked"
    assert not http_system.calls


def test_cancel_remains_available_while_paid_submit_is_parked(http_system, event):
    http_system.app.state.service.get = lambda *_: {"plan": {"provider": "modal"}}
    event["comment"]["body"] = '/gpu cancel\n' + json.dumps({"run_id": IDENTIFIER})
    response = http_system.client.post(http_system.path, headers=http_system.headers, json=envelope(event))
    assert response.status_code == 200
    assert http_system.calls[0][1] == "experiments_cancel"


def test_ci_rejects_browser_and_missing_auth(http_system, event):
    c, p = http_system.client, http_system.path
    assert c.post(p, json=envelope(event)).status_code == 401
    assert c.post(p, json=envelope(event), headers=dict(http_system.headers, Origin="https://gpu-control.vercel.app")).status_code == 403
    assert c.post(p, content="{}", headers=http_system.headers).status_code == 415
    assert not http_system.calls


def test_ci_rejects_edited_comment_before_service(http_system, event):
    original = envelope(event)
    event["comment"]["body"] = "/gpu integrations"
    response = http_system.client.post(http_system.path, json=original, headers=http_system.headers)
    assert response.status_code == 403
    assert not http_system.calls


def test_ci_rejects_extra_or_duplicate_envelope_fields(http_system, event):
    bad = dict(envelope(event), approved=True)
    assert http_system.client.post(http_system.path, json=bad, headers=http_system.headers).status_code == 400
    assert http_system.client.post(http_system.path, content='{"comment_id":10001,"comment_id":1}', headers=dict(http_system.headers, **{"Content-Type":"application/json"})).status_code == 400
    assert not http_system.calls


def test_ci_does_not_infer_external_oidc_owner(http_system, event):
    http_system.app.state.auth.external = True
    response = http_system.client.post(http_system.path, headers=http_system.headers, json=envelope(event))
    assert response.status_code == 503
    assert not http_system.calls


def test_authorization_stays_enabled_with_python_optimization():
    code = '''
from gpu_gateway.ci_bridge import Policy, validate_event, BridgeError
try:
    validate_event({}, {}, Policy.load())
except BridgeError:
    print("denied")
else:
    raise SystemExit("validation disabled")
'''
    result = subprocess.run([sys.executable, "-O", "-c", code], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0 and result.stdout.strip() == "denied"


def load_tiny():
    spec = importlib.util.spec_from_file_location("tiny_lm", BASE / "workloads/tiny-lm/tiny_lm.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_tiny_language_model_cpu_loss_improves():
    result = load_tiny().train()
    assert result["gpu_used"] is False
    assert result["parameters"] == 169
    assert result["training_pairs"] == 95
    assert result["final_loss"] < result["initial_loss"]


def test_tiny_python_and_torch_cpu_agree():
    pytest.importorskip("torch")
    tiny = load_tiny()
    reference = tiny.train(steps=5)
    actual = tiny.train(steps=5, backend="torch", device="cpu")
    assert abs(reference["final_loss"] - actual["final_loss"]) < 1e-10


@pytest.mark.parametrize("kwargs", [{"steps":0}, {"steps":201}, {"steps":True}, {"backend":"shell"}, {"device":"cuda"}])
def test_tiny_rejects_scope_expansion(kwargs):
    with pytest.raises(ValueError):
        load_tiny().train(**kwargs)


def test_workflow_no_provider_secrets_or_shell_interpolation():
    text = (BASE.parent / ".github/workflows/gateway-comments.yml").read_text()
    assert "secrets." not in text
    assert "${{ github.event.comment.body }}" not in text
    assert "pull_request_target" not in text
    assert "--network none" in text and "--read-only" in text
    assert "id-token: write" in text
    assert "persist-credentials: false" in text


def load_cli():
    spec = importlib.util.spec_from_file_location("comment_bridge", BASE / "scripts/comment_bridge.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cli_validates_event_file_without_shell_execution(monkeypatch, tmp_path, policy, env, event):
    event["comment"]["body"] = "/gpu local"
    path, output = tmp_path / "event.json", tmp_path / "outputs"
    path.write_text(json.dumps(event))
    for key, value in dict(env, GITHUB_EVENT_PATH=str(path), GITHUB_OUTPUT=str(output), GITHUB_RUN_ID="12345").items():
        monkeypatch.setenv(key, value)
    assert load_cli().main(["validate"]) == 0
    assert output.read_text() == "kind=local\n"


def test_cli_scopes_id_token_and_does_not_print_it(monkeypatch, policy, capsys):
    cli = load_cli()
    calls = []
    def fake_http(url, **kwargs):
        calls.append((url, kwargs))
        return {"value": "test-identity-token"}
    monkeypatch.setattr(cli, "http_json", fake_http)
    env = {"ACTIONS_ID_TOKEN_REQUEST_URL":"https://pipelines.actions.githubusercontent.com/oidc?api-version=1",
           "ACTIONS_ID_TOKEN_REQUEST_TOKEN":"test-request-token"}
    assert cli.oidc_token(policy, env) == "test-identity-token"
    from urllib.parse import parse_qs, urlsplit
    assert parse_qs(urlsplit(calls[0][0]).query)["audience"] == [policy.audience]
    assert capsys.readouterr().out == ""


def test_cli_refuses_identity_token_request_to_other_hosts(policy):
    with pytest.raises(BridgeError):
        load_cli().oidc_token(policy, {"ACTIONS_ID_TOKEN_REQUEST_URL":"https://attacker.example/oidc",
                                     "ACTIONS_ID_TOKEN_REQUEST_TOKEN":"secret"})


def test_cli_does_not_resubmit_automatically_on_network_failure(monkeypatch, tmp_path, env, event):
    cli = load_cli()
    path, report = tmp_path / "event.json", tmp_path / "report.json"
    path.write_text(json.dumps(event))
    for key, value in dict(env, GITHUB_EVENT_PATH=str(path), GITHUB_RUN_ID="12345").items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(cli, "oidc_token", lambda *args: "test-token")
    calls = []
    def failure(*args, **kwargs):
        calls.append(1)
        raise BridgeError("network_request_failed", 503)
    monkeypatch.setattr(cli, "http_json", failure)
    assert cli.main(["invoke", "--report", str(report)]) == 1
    assert len(calls) == 1
    assert "test-token" not in report.read_text()
    assert json.loads(report.read_text())["code"] == "network_request_failed"

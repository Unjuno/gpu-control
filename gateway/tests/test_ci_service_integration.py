"""Real ExperimentService/SQLite integration; no live provider or auth credentials."""
from dataclasses import replace
import hashlib
import json
import time
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import insert, select

from gpu_gateway.ci_bridge import Policy, owner_principal
from gpu_gateway.ci_routes import install_ci_routes
from gpu_gateway.config import Settings, Workload
from gpu_gateway.registry import ProviderRegistration
from gpu_gateway.service import ExperimentService, GatewayError
from gpu_gateway.store import Store, control, metadata


@pytest.fixture
def bridge(tmp_path):
    policy = Policy.load()
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'bridge.db'}", public_url=policy.gateway_origin)
    store = Store(settings.database_url)
    # This test concerns the experiment queue, not local-OAuth bootstrap/migrations.
    metadata.create_all(store.engine)
    with store.engine.begin() as c:
        c.execute(insert(control).values(id=1, active_count=0, worker_seen_at=0))
    clock = [int(time.time())]
    registry = {"demo": ProviderRegistration("demo", "simulation", lambda _: True, lambda _: None)}
    service = ExperimentService(store, settings, {"demo": Workload(provider="demo")}, lambda: clock[0], registry=registry)
    app = FastAPI()
    app.state.service = service
    app.state.auth = SimpleNamespace(external=False, settings=settings, configured=lambda: True)
    @app.exception_handler(GatewayError)
    async def error(_, exc):
        return JSONResponse({"code": exc.code}, exc.status)
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    comment = {"id": 100, "body": "/gpu list", "created_at": now, "updated_at": now,
               "user": {"id": policy.actor_id, "type": "User"},
               "issue_url": f"https://api.github.com/repos/{policy.repository}/issues/{policy.issue_number}"}
    issue = {"number": policy.issue_number, "state": "open"}
    verifier = SimpleNamespace(verify=lambda _: {"run_id": "12345", "workflow_sha": "a" * 40})
    install_ci_routes(app, policy=policy, verifier=verifier, comments=SimpleNamespace(read=lambda _: (comment, issue)))
    client = TestClient(app)
    def send(operation, arguments=None, *, comment_id=100):
        body = "/gpu " + operation
        if arguments is not None:
            body += "\n" + json.dumps(arguments)
        comment.update(id=comment_id, body=body)
        return client.post("/api/ci/comment", json={"comment_id": comment_id, "body_sha256": hashlib.sha256(body.encode()).hexdigest()},
                           headers={"Authorization": "Bearer test-fixture"})
    return SimpleNamespace(send=send, service=service, store=store, clock=clock,
                           principal=owner_principal(policy.gateway_origin), registry=registry)


def prepare(b):
    return b.send("prepare", {"workload":"demo", "runtime_seconds":60, "max_cost_usd":"0.10"})


def test_comment_to_actual_queue_preserves_approval_and_dedup(bridge):
    a, b = prepare(bridge), prepare(bridge)
    assert a.status_code == b.status_code == 200
    run_id = a.json()["run_id"]
    assert b.json()["run_id"] == run_id
    blocked = bridge.send("submit", {"run_id": run_id}, comment_id=101)
    assert blocked.status_code == 409 and blocked.json()["code"] == "approval_required"
    with pytest.raises(GatewayError) as e:
        bridge.service.approve(bridge.principal, run_id, a.json()["fingerprint"])
    assert e.value.code == "browser_approval_required"
    # A separate authenticated human action is represented explicitly by this fixture.
    bridge.service.approve(replace(bridge.principal, browser=True), run_id, a.json()["fingerprint"])
    for _ in range(3):
        accepted = bridge.send("submit", {"run_id": run_id}, comment_id=102)
        assert accepted.status_code == 200 and accepted.json()["state"] == "queued"
    with bridge.store.engine.connect() as c:
        assert c.execute(select(control.c.active_count)).scalar_one() == 1
    cancelled = bridge.send("cancel", {"run_id": run_id}, comment_id=103)
    assert cancelled.json()["state"] == "cancelled"
    with bridge.store.engine.connect() as c:
        assert c.execute(select(control.c.active_count)).scalar_one() == 0


def test_expired_approval_cannot_be_replaced_by_comment(bridge):
    report = prepare(bridge).json()
    bridge.service.approve(replace(bridge.principal, browser=True), report["run_id"], report["fingerprint"])
    bridge.clock[0] += 901
    result = bridge.send("submit", {"run_id": report["run_id"]}, comment_id=101)
    assert result.status_code == 409
    assert result.json()["code"] == "approval_required"


def test_new_provider_does_not_change_comment_schema(bridge):
    bridge.registry["futuregpu"] = ProviderRegistration("futuregpu", "external_worker", lambda _: False, lambda _: None)
    bridge.service.workloads["future-smoke"] = Workload(provider="futuregpu", quoted_usd_per_hour="0.50",
        quote_reference="TEST-ONLY-NOT-A-LIVE-QUOTE", quote_expires_at=bridge.clock[0]+600)
    result = bridge.send("prepare", {"workload":"future-smoke", "runtime_seconds":60, "max_cost_usd":"0.10"})
    assert result.status_code == 200 and result.json()["state"] == "awaiting_approval"
    bridge.service.approve(replace(bridge.principal, browser=True), result.json()["run_id"], result.json()["fingerprint"])
    result = bridge.send("submit", {"run_id":result.json()["run_id"]}, comment_id=104)
    # The ingress-level parked gate is deliberately stricter than provider enablement.
    assert result.status_code == 409 and result.json()["code"] == "paid_submission_parked"
    with bridge.store.engine.connect() as c:
        assert c.execute(select(control.c.active_count)).scalar_one() == 0

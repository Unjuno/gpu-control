from dataclasses import replace

from sqlalchemy import insert, update

from gpu_gateway.paid_authorization_bridge import VerifiedPaidAuthorization
from gpu_gateway.migrations import paid_authorizations
from gpu_gateway.store import Store, runs


RUN_ID = "0123456789abcdef0123456789abcdef"
OWNER = "owner-a"
PLAN = "a" * 64
APPROVAL = "b" * 32


def _verified(*, authorization_id="auth-1", run_id=RUN_ID, owner=OWNER,
              plan=PLAN, valid_until=200):
    return VerifiedPaidAuthorization(
        authorization_id=authorization_id, revocation_id="rev-1", issuer="issuer-a",
        run_id=run_id, owner=owner, actor=owner, decision_record_id=APPROVAL,
        gateway_plan_fingerprint=plan, core_plan_fingerprint="c" * 64,
        valid_until=valid_until, authorization_reference="decision-1",
    )


def _envelope(verified):
    return {
        "authorization_id": verified.authorization_id,
        "issuer": verified.issuer,
        "revocation_id": verified.revocation_id,
        "run_id": verified.run_id,
        "owner": verified.owner,
        "actor": verified.actor,
        "decision_record_id": verified.decision_record_id,
        "gateway_plan_fingerprint": verified.gateway_plan_fingerprint,
        "core_plan_fingerprint": verified.core_plan_fingerprint,
        "authorization_reference": verified.authorization_reference,
        "expires_at": verified.valid_until,
    }


def _approved_run(store, *, approval=APPROVAL, owner=OWNER, fingerprint=PLAN):
    with store.transaction() as connection:
        connection.execute(insert(runs).values(
            id=RUN_ID, owner=owner, idempotency_key="request-1", request_hash="d" * 64,
            fingerprint=fingerprint, plan={"schema_version": 2}, state="approved",
            created_at=1, started_at=0, approved_until=180, approval_id=approval,
            handle=None, result=None, error="", lease_until=0, lease_token="",
            cancel_requested=False, slot_reserved=False,
        ))


def test_paid_authorization_is_persisted_and_reloaded_only_for_exact_approval(tmp_path):
    store = Store(f"sqlite:///{tmp_path / 'paid-auth.db'}")
    store.initialize()
    _approved_run(store)
    verified = _verified()
    envelope = _envelope(verified)

    assert store.persist_verified_paid_authorization(
        run_id=RUN_ID, owner=OWNER, plan_fingerprint=PLAN, approval_id=APPROVAL,
        envelope=envelope, verified=verified, now=100,
    ) is True
    stored = store.read_paid_authorization(
        run_id=RUN_ID, owner=OWNER, plan_fingerprint=PLAN, approval_id=APPROVAL, now=120,
    )
    assert stored["authorization_id"] == "auth-1"
    assert stored["envelope"] == envelope
    assert store.read_paid_authorization(
        run_id=RUN_ID, owner="owner-b", plan_fingerprint=PLAN, approval_id=APPROVAL, now=120,
    ) is None
    assert store.read_paid_authorization(
        run_id=RUN_ID, owner=OWNER, plan_fingerprint=PLAN, approval_id="e" * 32, now=120,
    ) is None
    store.engine.dispose()


def test_paid_authorization_refuses_stale_approval_and_plan(tmp_path):
    store = Store(f"sqlite:///{tmp_path / 'paid-auth-stale.db'}")
    store.initialize()
    _approved_run(store)
    verified = _verified()
    envelope = _envelope(verified)

    assert store.persist_verified_paid_authorization(
        run_id=RUN_ID, owner=OWNER, plan_fingerprint=PLAN, approval_id="e" * 32,
        envelope=envelope, verified=verified, now=100,
    ) is False
    wrong_plan = "f" * 64
    wrong_plan_verified = replace(verified, gateway_plan_fingerprint=wrong_plan)
    assert store.persist_verified_paid_authorization(
        run_id=RUN_ID, owner=OWNER, plan_fingerprint=wrong_plan, approval_id=APPROVAL,
        envelope=_envelope(wrong_plan_verified), verified=wrong_plan_verified, now=100,
    ) is False
    assert store.persist_verified_paid_authorization(
        run_id=RUN_ID, owner=OWNER, plan_fingerprint=PLAN, approval_id=APPROVAL,
        envelope=envelope, verified=verified, now=180,
    ) is False
    store.engine.dispose()


def test_paid_authorization_reload_rejects_envelope_tampering(tmp_path):
    store = Store(f"sqlite:///{tmp_path / 'paid-auth-tamper.db'}")
    store.initialize()
    _approved_run(store)
    verified = _verified()
    envelope = _envelope(verified)
    assert store.persist_verified_paid_authorization(
        run_id=RUN_ID, owner=OWNER, plan_fingerprint=PLAN, approval_id=APPROVAL,
        envelope=envelope, verified=verified, now=100,
    ) is True

    changed = envelope | {"actor": "other-actor"}
    with store.transaction() as connection:
        connection.execute(update(paid_authorizations).where(
            paid_authorizations.c.run_id == RUN_ID,
        ).values(envelope=changed))

    assert store.read_paid_authorization(
        run_id=RUN_ID, owner=OWNER, plan_fingerprint=PLAN, approval_id=APPROVAL, now=120,
    ) is None
    store.engine.dispose()


def test_paid_authorization_replacement_requires_a_new_browser_approval(tmp_path):
    store = Store(f"sqlite:///{tmp_path / 'paid-auth-replace.db'}")
    store.initialize()
    _approved_run(store)
    first = _verified()
    assert store.persist_verified_paid_authorization(
        run_id=RUN_ID, owner=OWNER, plan_fingerprint=PLAN, approval_id=APPROVAL,
        envelope=_envelope(first), verified=first, now=100,
    ) is True

    next_approval = "e" * 32
    with store.transaction() as connection:
        connection.execute(update(runs).where(runs.c.id == RUN_ID).values(
            approval_id=next_approval, approved_until=250,
        ))
    second = replace(_verified(authorization_id="auth-2", valid_until=240),
                     decision_record_id=next_approval)
    second_envelope = _envelope(second)
    assert store.persist_verified_paid_authorization(
        run_id=RUN_ID, owner=OWNER, plan_fingerprint=PLAN, approval_id=next_approval,
        envelope=second_envelope, verified=second, now=110,
    ) is True
    assert store.read_paid_authorization(
        run_id=RUN_ID, owner=OWNER, plan_fingerprint=PLAN, approval_id=APPROVAL, now=120,
    ) is None
    assert store.read_paid_authorization(
        run_id=RUN_ID, owner=OWNER, plan_fingerprint=PLAN, approval_id=next_approval, now=120,
    )["authorization_id"] == "auth-2"
    store.engine.dispose()


def test_paid_authorization_reload_requires_live_browser_and_envelope_approval(tmp_path):
    store = Store(f"sqlite:///{tmp_path / 'paid-auth-expired.db'}")
    store.initialize()
    _approved_run(store)
    verified = _verified()
    assert store.persist_verified_paid_authorization(
        run_id=RUN_ID, owner=OWNER, plan_fingerprint=PLAN, approval_id=APPROVAL,
        envelope=_envelope(verified), verified=verified, now=100,
    ) is True

    with store.transaction() as connection:
        connection.execute(update(runs).where(runs.c.id == RUN_ID).values(approved_until=300))
    assert store.read_paid_authorization(
        run_id=RUN_ID, owner=OWNER, plan_fingerprint=PLAN, approval_id=APPROVAL, now=120,
    ) is not None
    with store.transaction() as connection:
        connection.execute(update(runs).where(runs.c.id == RUN_ID).values(state="submitting"))
    assert store.read_paid_authorization(
        run_id=RUN_ID, owner=OWNER, plan_fingerprint=PLAN, approval_id=APPROVAL, now=120,
    ) is not None
    with store.transaction() as connection:
        connection.execute(update(runs).where(runs.c.id == RUN_ID).values(cancel_requested=True))
    assert store.read_paid_authorization(
        run_id=RUN_ID, owner=OWNER, plan_fingerprint=PLAN, approval_id=APPROVAL, now=120,
    ) is None
    with store.transaction() as connection:
        connection.execute(update(runs).where(runs.c.id == RUN_ID).values(cancel_requested=False))
    assert store.read_paid_authorization(
        run_id=RUN_ID, owner=OWNER, plan_fingerprint=PLAN, approval_id=APPROVAL, now=200,
    ) is None

    with store.transaction() as connection:
        connection.execute(update(runs).where(runs.c.id == RUN_ID).values(approved_until=150))
    assert store.read_paid_authorization(
        run_id=RUN_ID, owner=OWNER, plan_fingerprint=PLAN, approval_id=APPROVAL, now=160,
    ) is None

    with store.transaction() as connection:
        connection.execute(update(runs).where(runs.c.id == RUN_ID).values(
            state="cancelled", approved_until=300,
        ))
    assert store.read_paid_authorization(
        run_id=RUN_ID, owner=OWNER, plan_fingerprint=PLAN, approval_id=APPROVAL, now=120,
    ) is None
    store.engine.dispose()

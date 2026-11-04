import pytest
from sqlalchemy import insert, select

from test_paid_authorization_bridge import _build_bridge_case
from gpu_gateway.contracts import plan_fingerprint
from gpu_gateway.migrations import paid_authorizations
from gpu_gateway.paid_authorization_coordinator import (
    PaidAuthorizationContext,
    PaidAuthorizationCoordinator,
    PaidAuthorizationCoordinatorError,
)
from gpu_gateway.store import Store, runs


def _setup(store, envelope, args):
    store.initialize()
    with store.transaction() as connection:
        connection.execute(insert(runs).values(
            id=envelope["run_id"], owner=envelope["owner"],
            idempotency_key="request-1", request_hash="d" * 64,
            fingerprint=plan_fingerprint(args["gateway_plan"]),
            plan=args["gateway_plan"].model_dump(mode="json"), state="approved",
            created_at=1, started_at=0, approved_until=1_800_000_100,
            approval_id=envelope["approval_id"], handle=None, result=None, error="",
            lease_until=0, lease_token="", cancel_requested=False,
            slot_reserved=False,
        ))


def _context(envelope, args, *, approval_id=None):
    return PaidAuthorizationContext(
        approval_id=approval_id or envelope["approval_id"],
        gateway_plan=args["gateway_plan"], core_plan=args["core_plan"],
        actor=args["actor"], decision_record_id=args["decision_record_id"],
        control_plane_sha=args["control_plane_sha"],
    )


def _coordinator(store, envelope, args, clock, *, revoked=lambda *_: False,
                 context=None):
    return PaidAuthorizationCoordinator(
        store=store,
        resolve_context=lambda _run_id, _owner: context or _context(envelope, args),
        trusted_keys=args["trusted_keys"], expected_issuer=args["expected_issuer"],
        expected_policy_version=args["expected_policy_version"],
        is_revoked=revoked, clock=clock,
    )


def test_signed_authorization_is_verified_before_store_and_on_reload(tmp_path):
    envelope, args, _ = _build_bridge_case()
    store = Store(f"sqlite:///{tmp_path / 'paid-auth-coordinator.db'}")
    _setup(store, envelope, args)
    clock = lambda: args["now"]
    coordinator = _coordinator(store, envelope, args, clock)

    saved = coordinator.persist(run_id=envelope["run_id"], owner=envelope["owner"], envelope=envelope)
    assert saved == {
        "authorization_id": envelope["authorization_id"],
        "approval_id": envelope["approval_id"],
        "issuer": envelope["issuer"],
    }
    verified = coordinator.reload_verified(run_id=envelope["run_id"], owner=envelope["owner"])
    assert verified.authorization_id == envelope["authorization_id"]
    assert verified.approval_id == envelope["approval_id"]
    store.engine.dispose()


def test_old_signed_approval_cannot_be_rebound_after_reapproval(tmp_path):
    envelope, args, _ = _build_bridge_case()
    store = Store(f"sqlite:///{tmp_path / 'paid-auth-reapproval.db'}")
    _setup(store, envelope, args)
    next_approval = "8" * 32
    with store.transaction() as connection:
        connection.execute(runs.update().where(runs.c.id == envelope["run_id"]).values(
            approval_id=next_approval, approved_until=1_800_000_200,
        ))
    coordinator = _coordinator(
        store, envelope, args, lambda: args["now"],
        context=_context(envelope, args, approval_id=next_approval),
    )

    with pytest.raises(PaidAuthorizationCoordinatorError, match="approval"):
        coordinator.persist(run_id=envelope["run_id"], owner=envelope["owner"], envelope=envelope)
    with store.engine.connect() as connection:
        assert connection.execute(select(paid_authorizations)).first() is None
    store.engine.dispose()


def test_revocation_lookup_failure_prevents_persistence_and_reload(tmp_path):
    envelope, args, _ = _build_bridge_case()
    store = Store(f"sqlite:///{tmp_path / 'paid-auth-revocation.db'}")
    _setup(store, envelope, args)

    def unavailable(*_):
        raise OSError("revocation service unavailable")

    coordinator = _coordinator(store, envelope, args, lambda: args["now"], revoked=unavailable)
    with pytest.raises(PaidAuthorizationCoordinatorError, match="revocation"):
        coordinator.persist(run_id=envelope["run_id"], owner=envelope["owner"], envelope=envelope)
    with store.engine.connect() as connection:
        assert connection.execute(select(paid_authorizations)).first() is None
    store.engine.dispose()


def test_revocation_is_rechecked_when_a_persisted_authorization_is_reloaded(tmp_path):
    envelope, args, _ = _build_bridge_case()
    store = Store(f"sqlite:///{tmp_path / 'paid-auth-revoked-later.db'}")
    _setup(store, envelope, args)
    revoked = False
    coordinator = _coordinator(
        store, envelope, args, lambda: args["now"],
        revoked=lambda *_: revoked,
    )
    coordinator.persist(run_id=envelope["run_id"], owner=envelope["owner"], envelope=envelope)

    revoked = True
    with pytest.raises(PaidAuthorizationCoordinatorError, match="revoked"):
        coordinator.reload_verified(run_id=envelope["run_id"], owner=envelope["owner"])
    store.engine.dispose()


def test_missing_trusted_context_fails_before_store_write(tmp_path):
    envelope, args, _ = _build_bridge_case()
    store = Store(f"sqlite:///{tmp_path / 'paid-auth-no-context.db'}")
    _setup(store, envelope, args)
    coordinator = _coordinator(
        store, envelope, args, lambda: args["now"], context=None,
    )
    # Replace the resolver with the unavailable server-side decision lookup.
    coordinator.resolve_context = lambda _run_id, _owner: None

    with pytest.raises(PaidAuthorizationCoordinatorError, match="context"):
        coordinator.persist(run_id=envelope["run_id"], owner=envelope["owner"], envelope=envelope)
    with store.engine.connect() as connection:
        assert connection.execute(select(paid_authorizations)).first() is None
    store.engine.dispose()


def test_signed_envelope_for_another_owner_is_not_persisted(tmp_path):
    envelope, args, _ = _build_bridge_case()
    store = Store(f"sqlite:///{tmp_path / 'paid-auth-wrong-owner.db'}")
    _setup(store, envelope, args)
    coordinator = _coordinator(store, envelope, args, lambda: args["now"])

    with pytest.raises(PaidAuthorizationCoordinatorError, match="owner"):
        coordinator.persist(run_id=envelope["run_id"], owner="another-owner", envelope=envelope)
    with store.engine.connect() as connection:
        assert connection.execute(select(paid_authorizations)).first() is None
    store.engine.dispose()

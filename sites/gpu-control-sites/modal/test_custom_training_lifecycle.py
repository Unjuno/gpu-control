import time
from types import SimpleNamespace

import pytest

from custom_training_lifecycle import dispatch


class Store(dict):
    def put(self, key, value, *, skip_if_exists=False):
        if skip_if_exists and key in self:
            return False
        self[key] = value
        return True


def test_one_start_bound_to_owner_and_cancel_until_terminal():
    run = "a" * 32
    args = {"run_id": run, "plan_fingerprint": "b" * 64, "plan": {"run_id": run},
            "authorization_expires_at": int(time.time()) + 60}
    starts, cancels = [], []
    states = iter([{"state": "running"}, {"state": "cancelled", "cleanup": "confirmed"}])
    backend = SimpleNamespace(start=lambda plan: starts.append(plan) or "sb-abcdefgh",
                              cancel=lambda handle: cancels.append(handle),
                              inspect=lambda *_: next(states))
    store = Store()
    def call(action, owner="owner"):
        return dispatch(store, backend, owner, action, args, validate=lambda *_: None, admission_enabled=True)
    assert call("submit") == {"state": "running"}
    assert call("submit") == {"state": "running"}
    with pytest.raises(ValueError, match="run_identity_mismatch"):
        call("status", "other")
    assert call("cancel") == {"state": "cancel_requested"}
    assert call("cancel") == {"state": "cancel_requested"}
    assert call("status") == {"state": "cancelled", "cleanup": "confirmed"}
    assert call("status") == {"state": "cancelled", "cleanup": "confirmed"}
    assert len(starts) == 1 and cancels == ["sb-abcdefgh"]


def test_ambiguous_start_never_retries():
    run = "a" * 32
    args = {"run_id": run, "plan_fingerprint": "b" * 64, "plan": {"run_id": run},
            "authorization_expires_at": int(time.time()) + 60}
    attempts = []
    def start(_):
        attempts.append(1)
        raise TimeoutError()
    store = Store()
    backend = SimpleNamespace(start=start)
    with pytest.raises(TimeoutError):
        dispatch(store, backend, "owner", "submit", args, validate=lambda *_: None, admission_enabled=True)
    assert dispatch(store, backend, "owner", "submit", args, validate=lambda *_: None,
                    admission_enabled=True) == {"state": "uncertain"}
    assert attempts == [1]


def test_closed_admission_and_invalid_plan_never_claim_or_start():
    run = "a" * 32
    args = {"run_id": run, "plan_fingerprint": "b" * 64, "plan": {"run_id": run},
            "authorization_expires_at": int(time.time()) + 60}
    store = Store()
    backend = SimpleNamespace(start=lambda _: pytest.fail("must not start"))
    assert dispatch(store, backend, "owner", "submit", args, validate=lambda *_: None,
                    admission_enabled=False)["state"] == "blocked"
    def reject(*_):
        raise ValueError("invalid_budget")
    with pytest.raises(ValueError, match="invalid_budget"):
        dispatch(store, backend, "owner", "submit", args, validate=reject, admission_enabled=True)
    assert not store

"""Owner-bound durable lifecycle for the custom Sandbox adapter.

The injected validator must verify source, image, quote, budget reservation,
admission and the signed plan before this module may be used with a provider.
The store's put(skip_if_exists=True) must be an atomic create operation.
"""
import re
import time


def dispatch(store, backend, owner, action, args, *, validate, admission_enabled):
    run_id = args.get("run_id")
    fingerprint = args.get("plan_fingerprint")
    if action in {"status", "cancel"} and fingerprint is None:
        raise ValueError("invalid_run_identity")
    if (not isinstance(owner, str) or not owner or
            not isinstance(run_id, str) or re.fullmatch(r"[a-f0-9]{32}", run_id) is None or
            not isinstance(fingerprint, str) or re.fullmatch(r"[a-f0-9]{64}", fingerprint) is None):
        raise ValueError("invalid_run_identity")
    key = f"custom-training:{run_id}"
    record = store.get(key)
    if record is not None and (record.get("owner") != owner or record.get("fingerprint") != fingerprint):
        raise ValueError("run_identity_mismatch")
    if action == "submit" and record is None:
        if not admission_enabled:
            return {"state": "blocked", "reason": "TRAINING_ADMISSION_DISABLED"}
        plan, expiry = args.get("plan"), args.get("authorization_expires_at")
        now = int(time.time())
        if (not isinstance(plan, dict) or plan.get("run_id") != run_id or
                plan.get("plan_fingerprint") != fingerprint or plan.get("owner") != owner):
            raise ValueError("invalid_plan")
        if type(expiry) is not int or not now < expiry <= now + 900:
            return {"state": "blocked", "reason": "TRAINING_AUTHORIZATION_EXPIRED"}
        validate(owner, fingerprint, plan)
        claim = {"owner": owner, "fingerprint": fingerprint, "plan": plan, "state": "dispatching"}
        if store.put(key, claim, skip_if_exists=True):
            # Any failure after claim is ambiguous. Do not launch a second job.
            handle = backend.start(plan)
            if not isinstance(handle, str) or re.fullmatch(r"sb-[A-Za-z0-9]{8,128}", handle) is None:
                raise ValueError("invalid_sandbox_handle")
            store.put(key, {**claim, "handle": handle, "state": "running"})
            return {"state": "running"}
        record = store.get(key)
        if record is None or record.get("owner") != owner or record.get("fingerprint") != fingerprint:
            raise ValueError("run_identity_mismatch")
    if record is None:
        return {"state": "not_found"}
    if action == "submit":
        return {"state": record["state"] if "handle" in record else "uncertain"}
    if action not in {"status", "cancel"}:
        raise ValueError("invalid_action")
    plan = args.get("approved_plan")
    if (not isinstance(plan, dict) or plan.get("owner") != owner or
            plan.get("plan_fingerprint") != fingerprint or plan.get("run_id") != run_id):
        raise ValueError("run_identity_mismatch")
    if "handle" not in record:
        return {"state": "uncertain"}
    if record.get("terminal") is not None:
        return record["terminal"]
    if action == "cancel" and record["state"] != "cancel_requested":
        backend.cancel(record["handle"])
        store.put(key, {**record, "state": "cancel_requested"})
        return {"state": "cancel_requested"}
    result = backend.inspect(record["handle"], record["plan"])
    if not isinstance(result, dict) or result.get("state") not in {"running", "succeeded", "failed", "cancelled"}:
        raise ValueError("invalid_provider_state")
    if result["state"] == "running" and record["state"] == "cancel_requested":
        return {"state": "cancel_requested"}
    if result["state"] != "running":
        store.put(key, {**record, "state": result["state"], "terminal": result})
    return result

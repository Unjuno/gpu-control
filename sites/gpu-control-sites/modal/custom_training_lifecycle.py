"""Owner-bound durable lifecycle for the custom Sandbox adapter.

The injected validator must verify source, image, quote, budget reservation,
admission and the signed plan before this module may be used with a provider.
The store's put(skip_if_exists=True) must be an atomic create operation.
"""
import re
import time


def _handle(value):
    if not isinstance(value, str) or re.fullmatch(r"custom-training-[a-f0-9]{32}", value) is None:
        raise ValueError("invalid_sandbox_handle")
    return value


def dispatch(store, backend, owner, action, args, *, validate, admission_enabled):
    run_id = args.get("run_id")
    fingerprint = args.get("plan_fingerprint")
    if action in {"status", "cancel"} and fingerprint is None:
        raise ValueError("invalid_run_identity")
    if (not isinstance(owner, str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:@-]{0,255}", owner) is None or
            not isinstance(run_id, str) or re.fullmatch(r"[a-f0-9]{32}", run_id) is None or
            not isinstance(fingerprint, str) or re.fullmatch(r"[a-f0-9]{64}", fingerprint) is None):
        raise ValueError("invalid_run_identity")
    key = f"custom-training:{run_id}"
    record = store.get(key)
    if record is not None and (record.get("owner") != owner or record.get("fingerprint") != fingerprint):
        raise ValueError("run_identity_mismatch")
    if record is None and action in {"status", "cancel", "checkpoint", "artifact"}:
        plan = args.get("approved_plan")
        if not isinstance(plan, dict) or plan.get("run_id") != run_id:
            raise ValueError("run_identity_mismatch")
        # The Sites Worker supplies this immutable plan from its owner-bound
        # D1 row over the signed adapter channel. Recovery may inspect only the
        # deterministic handle and durable output for this run; it never calls
        # start() and therefore cannot allocate a replacement runtime.
        recover = getattr(backend, "recover", None)
        handle = recover(plan) if callable(recover) else None
        if not isinstance(handle, str):
            return {"state": "uncertain"}
        recovered = {"owner": owner, "fingerprint": fingerprint, "plan": plan,
                     "handle": _handle(handle), "state": "running"}
        if store.put(key, recovered, skip_if_exists=True):
            record = recovered
        else:
            record = store.get(key)
            if record is None or record.get("owner") != owner or record.get("fingerprint") != fingerprint:
                raise ValueError("run_identity_mismatch")
    if action == "submit" and record is None:
        if not admission_enabled:
            return {"state": "blocked", "reason": "TRAINING_ADMISSION_DISABLED"}
        plan, expiry = args.get("plan"), args.get("authorization_expires_at")
        source_token = args.get("source_token")
        if source_token is not None and (not isinstance(source_token, str) or not 20 <= len(source_token) <= 512):
            raise ValueError("invalid_source_token")
        now = int(time.time())
        approved_plan = args.get("approved_plan")
        if (not isinstance(plan, dict) or not isinstance(approved_plan, dict) or
                approved_plan != plan or plan.get("run_id") != run_id):
            raise ValueError("invalid_plan")
        if type(expiry) is not int or not now < expiry <= now + 900:
            return {"state": "blocked", "reason": "TRAINING_AUTHORIZATION_EXPIRED"}
        validate(owner, fingerprint, plan)
        claim = {"owner": owner, "fingerprint": fingerprint, "plan": plan, "state": "dispatching"}
        if store.put(key, claim, skip_if_exists=True):
            # Any failure after claim is ambiguous. Do not launch a second job.
            # source_token is a short-lived GitHub App installation token
            # supplied only for trusted source staging. Never persist it in
            # the durable owner/run record or pass it to the Sandbox.
            handle = backend.start(plan, source_token=source_token)
            if not isinstance(handle, str) or re.fullmatch(r"custom-training-[a-f0-9]{32}", handle) is None:
                raise ValueError("invalid_sandbox_handle")
            store.put(key, {**claim, "handle": handle, "state": "staging"})
            return {"state": "staging"}
        record = store.get(key)
        if record is None or record.get("owner") != owner or record.get("fingerprint") != fingerprint:
            raise ValueError("run_identity_mismatch")
    if record is None:
        return {"state": "not_found"}
    if action == "submit":
        return {"state": record["state"] if "handle" in record else "uncertain"}
    if action not in {"status", "cancel", "checkpoint", "artifact"}:
        raise ValueError("invalid_action")
    plan = args.get("approved_plan")
    if ((plan is not None and (not isinstance(plan, dict) or plan != record.get("plan"))) or
            record.get("plan", {}).get("run_id") != run_id):
        raise ValueError("run_identity_mismatch")
    if "handle" not in record:
        # A Sandbox create can succeed while its response is lost. Recover the
        # deterministic provider name before declaring uncertainty; never
        # repeat the create call for this plan.
        recover = getattr(backend, "recover", None)
        handle = recover(record.get("plan", {})) if callable(recover) else None
        if not isinstance(handle, str):
            return {"state": "uncertain"}
        record = {**record, "handle": _handle(handle), "state": "running"}
        store.put(key, record)
    if record.get("terminal") is not None:
        result = record["terminal"]
        if action == "checkpoint":
            checkpoint = result.get("checkpoint")
            if result.get("state") != "succeeded" or not isinstance(checkpoint, dict):
                return {"state": "checkpoint_not_ready"}
            return {"state": "succeeded", "checkpoint_chunk": backend.checkpoint(
                run_id, checkpoint, args.get("offset"), args.get("max_bytes"))}
        if action == "artifact":
            artifact = next((item for item in result.get("artifacts", [])
                             if item.get("artifact_id") == args.get("artifact_id")), None)
            if result.get("state") != "succeeded" or artifact is None:
                return {"state": "artifact_not_ready"}
            return {"state": "succeeded", "artifact_chunk": backend.artifact(
                run_id, artifact, args.get("offset"), args.get("max_bytes"))}
        return result
    if action == "cancel" and record["state"] != "cancel_requested":
        # Persist cancellation before the provider call. If cleanup is
        # ambiguous, recovery must never inspect staging as an uncancelled run
        # and allocate the GPU.
        record = {**record, "state": "cancel_requested"}
        store.put(key, record)
    if record["state"] == "cancel_requested":
        cancelled = backend.cancel(record["handle"])
        if isinstance(cancelled, dict) and cancelled.get("state") == "uncertain":
            return {"state": "cancel_requested"}
        if (isinstance(cancelled, dict) and cancelled.get("state") == "cancelled" and
                cancelled.get("cleanup") == "confirmed"):
            store.put(key, {**record, "state": "cancelled", "terminal": cancelled})
            return cancelled
    result = backend.inspect(record["handle"], record["plan"], record.get("state") == "cancel_requested")
    if not isinstance(result, dict) or result.get("state") not in {"staging", "running", "cancel_requested", "cleanup_pending", "uncertain", "succeeded", "failed", "cancelled"}:
        raise ValueError("invalid_provider_state")
    if result["state"] == "uncertain":
        # Provider absence without a durable result is an observation, not a
        # terminal failure. Keep the existing record intact for recovery.
        return result
    if result["state"] in {"staging", "running"}:
        return {**result, "state": "cancel_requested" if record["state"] == "cancel_requested" else result["state"]}
    if result["state"] in {"cancel_requested", "cleanup_pending"}:
        return result
    if result["state"] != "running":
        # Provider exit is not cleanup evidence. Keep the run observable, but
        # do not turn execution completion into a terminal product state until
        # the backend proves the per-run Sandbox and source staging are cleaned.
        if result.get("cleanup") != "confirmed":
            return {"state": "cleanup_pending", "execution_state": result["state"]}
        store.put(key, {**record, "state": result["state"], "terminal": result})
        record = {**record, "state": result["state"], "terminal": result}
    if action == "checkpoint":
        checkpoint = result.get("checkpoint")
        if result.get("state") != "succeeded" or not isinstance(checkpoint, dict):
            return {"state": "checkpoint_not_ready"}
        return {"state": "succeeded", "checkpoint_chunk": backend.checkpoint(
            run_id, checkpoint, args.get("offset"), args.get("max_bytes"))}
    if action == "artifact":
        artifacts = result.get("artifacts", [])
        artifact = next((item for item in artifacts if item.get("artifact_id") == args.get("artifact_id")), None)
        if result.get("state") != "succeeded" or artifact is None:
            return {"state": "artifact_not_ready"}
        return {"state": "succeeded", "artifact_chunk": backend.artifact(
            run_id, artifact, args.get("offset"), args.get("max_bytes"))}
    return result

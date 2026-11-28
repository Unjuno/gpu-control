# ADR 0003: Owner-selected runtime readiness and profile parity

- **Status:** proposed in PR #70; not deployed or runtime-accepted.
- **Date:** 2026-11-28
- **Scope:** ChatGPT Sites and the Modal adapter readiness contract for the
  owner-selected GitHub training path.

## Context

The Sites control plane and Modal adapter each hold an independently deployed
copy of the bounded runtime profile. A local readiness check can pass while
the remote adapter has a different image, quote, runtime, budget or control
plane SHA. If the mismatch is discovered after Sites consumes authorization
and reserves monthly budget, a run that never reached provider execution can
still consume product budget and block later work.

## Decision

1. `experiment_capabilities.machine_state.owner_selected_training` is the
   agent-facing projection for the custom-source route. It reports stable
   blocker codes and only the gate booleans needed to choose the next tool.
2. Sites and the Modal adapter independently normalize the same ordered
   runtime/quote/control-plane fields and compute a SHA-256 fingerprint from
   their canonical JSON array representation. The adapter returns this
   fingerprint only over the authenticated Sites-to-adapter channel; Sites
   strips it from the ChatGPT-facing response.
3. Sites advertises `ready_to_prepare=true` only when the owner GitHub
   connection, both admission switches, both valid profiles and the profile
   fingerprints agree. Source manifest and exact-plan checks remain separate.
4. Before consuming one-use authorization or reserving monthly budget, owner
   selected submit rechecks adapter admission and profile fingerprint through
   the read-only capabilities operation. A mismatch or unavailable adapter
   fails closed without reserving or starting compute.
5. The profile check is not a provider health check and never starts a GPU
   Sandbox. Its Modal control-function fee, if any, is outside the Sandbox
   estimate and is disclosed in tool documentation.

## Consequences

- The status projection and exact submit gate share the adapter's current
  runtime profile without exposing image IDs, rates, limits or credentials to
  the agent.
- Drift may require correcting one side's configuration before preparation;
  the response identifies the stable blocker instead of allowing a costly
  failed attempt.
- Each eligible submit performs an extra authenticated control call. Before
  production enablement, verify its latency and control-function cost against
  the account limits.
- This decision covers the Modal-backed custom-source path only. Other
  providers must implement and validate equivalent capability and parity
  contracts before they advertise arbitrary repository execution.

## Evidence and limits

- Shared cross-runtime bounds and canonical fingerprint vector:
  `sites/gpu-control-sites/contracts/owner-training-profile-cases.json`.
- Site projection and pre-reservation check: `worker/index.js` and
  `worker/training_plan.js`.
- Adapter profile parsing and projection: `modal/custom_training_plan.py`,
  `modal/provider_adapter.py`, and `modal/provider_adapter_core.py`.
- Worker and Python offline tests cover matching vectors, closed admission,
  profile drift, and no authorization/budget reservation on a failed
  preflight. They do not prove deployed parity or end-to-end GPU execution.

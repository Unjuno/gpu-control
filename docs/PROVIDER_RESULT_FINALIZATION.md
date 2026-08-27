# Provider result finalization

Some providers keep logs and small result metadata after resource deletion; others may destroy that evidence during cleanup. `gpu-control` therefore supports two bounded collection orders without weakening the lifecycle rule that a durable `ResultManifest` is created only after cleanup is finalized.

## Existing post-cleanup path

For transports that survive cleanup:

```text
terminal observation
    -> cleanup
    -> finalized observation
    -> collect_provider_results(...)
    -> ResultManifest
```

This path remains unchanged.

## Ephemeral pre-cleanup path

For transports that may disappear during cleanup:

```text
terminal observation
    -> capture_provider_results_before_cleanup(...)
    -> durable ProviderResultCapture
    -> cleanup_provider_job(...)
    -> finalized observation
    -> finalize_captured_provider_results(...)
    -> ResultManifest
```

`ProviderResultCapture` is not provider-finalized success. It is a bounded, durable record of untrusted provider result metadata after control-plane policy validation and lifecycle correlation, captured while the terminal resource still exists.

The capture binds:

- provider and provider job id;
- approved-plan fingerprint;
- submission-receipt fingerprint;
- exact terminal-observation fingerprint and terminal state;
- trusted capture timestamp;
- retained-log byte count and truncation state;
- bounded artifact metadata and SHA-256 identities.

It has strict JSON restoration, deterministic canonical serialization, and a `sha256:` fingerprint. Unknown fields, duplicate JSON fields, malformed states, policy violations, identity mismatches, and capture timestamps before the terminal observation fail closed.

## Cleanup remains mandatory

Capturing result evidence does not authorize leaving compute running. The capture is designed to survive the transition into the existing cleanup controller. `finalize_captured_provider_results(...)` requires:

- the original submission receipt;
- the exact terminal observation bound into the capture;
- a lifecycle-valid transition to a cleanup-finalized observation;
- cleanup finalization at or after the capture time;
- a trusted manifest-commit timestamp at or after the final observation.

Only then is the existing `ResultManifest` built from the exact captured log/artifact payload and rebound to the final observation.

The legacy `ResultManifest.collected_at_utc` field remains unchanged for schema compatibility. On the pre-cleanup path it records when the already-captured bounded result is committed into the cleanup-finalized manifest. The actual provider snapshot time is preserved separately and immutably as `ProviderResultCapture.captured_at_utc`.

## Security properties

The pre-cleanup path must not:

- collect before the provider job is terminal;
- collect after cleanup has already started;
- let provider output choose or alter lifecycle identity;
- bypass result-policy limits because cleanup has not happened yet;
- treat a capture as cleanup success or provider-finalized success;
- rebuild a final manifest from result metadata other than the validated capture;
- allow final cleanup timestamps to predate the capture;
- enable a live provider adapter, credential, workflow, or paid-compute path merely because the offline contract exists.

`ProviderAdapter.collect_results(...)` remains a read-only translation boundary. A provider implementation may be called with a terminal pre-cleanup observation or a cleanup-finalized observation, depending on whether its result transport is ephemeral or durable.

## RunPod status

This contract does not solve the current RunPod production transport blocker. Production Pod-log SSE is still treated as unavailable according to the pinned provider audit. The new path only establishes the provider-neutral lifecycle semantics required if a supported production transport can retrieve bounded authenticated completion evidence before destructive cleanup.

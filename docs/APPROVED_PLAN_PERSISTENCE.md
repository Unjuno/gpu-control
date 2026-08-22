# Persisted Approved Execution Plans

`ApprovedExecutionPlan` is the provider-facing authorization artifact produced after source, container, pricing, dry-run, cost/runtime, cleanup, and explicit-human-authorization gates pass.

Because asynchronous submission may run in a different process or GitHub Actions job from approval, the plan must be safe to persist and restore without silently weakening those gates.

## Strict restoration

`ApprovedExecutionPlan.from_json(...)` restores only the exact schema version and exact known field set. It rejects:

- invalid or non-object JSON;
- duplicate JSON keys;
- missing or unknown fields;
- non-canonical repository, commit SHA, Dockerfile path, GPU profile, or provider identity;
- malformed or non-lowercase image digests;
- JSON-number money fields instead of decimal strings;
- malformed pricing timestamps;
- any gate flag that is not exactly `true`;
- a GPU count other than one in the current MVP;
- non-positive runtime;
- a serialized worst-case cost that does not recompute from the verified hourly price and runtime;
- a worst-case cost above the approved maximum cost.

Parsing successfully establishes structural validity only. It does not authenticate where the plan came from.

## Expected fingerprint boundary

The plan has a deterministic canonical JSON representation and a `sha256:` content fingerprint.

A trusted orchestration stage that restores a persisted plan before provider submission must compare it with an **expected fingerprint obtained through a separate trusted state or metadata channel**.

For example:

```text
approval stage
    -> persist plan JSON
    -> persist/transport expected plan fingerprint through trusted workflow metadata

submit stage
    -> restore plan JSON strictly
    -> compare plan fingerprint to trusted expected fingerprint
    -> re-check pricing freshness
    -> provider submission
```

The expected fingerprint must not be computed from the same untrusted plan payload immediately before comparison; that would only prove that the payload matches itself.

The fingerprint is an integrity/correlation identifier, not a cryptographic signature and not an identity provider. If an attacker controls both the plan and the trusted expected-fingerprint channel, fingerprint comparison alone does not provide authorization.

## Provider boundary

A future provider adapter should receive a restored `ApprovedExecutionPlan` only after:

1. strict schema restoration succeeds;
2. the plan matches the trusted expected fingerprint;
3. all plan invariants still validate;
4. `validate_plan_for_submission(...)` confirms pricing evidence is still fresh immediately before the billable request.

Provider credentials becoming available must never bypass these checks.

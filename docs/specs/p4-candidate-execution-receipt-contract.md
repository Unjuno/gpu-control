# P4 candidate execution receipt contract

Status: **contract implemented; no provider adapter accepted**. Modal and
RunPod remain `supports_candidate_binding: false`; keep provider switches off
and `policies/repository-state.yaml` parked.

## Trust boundary

The envelope distinguishes two signer scopes: `provider` means the provider
signed the claims; `gateway_adapter` means trusted adapter code signed claims
derived from an authenticated provider API snapshot. The second scope is an
adapter attestation, not a provider signature. Do not reuse the Gateway
worker's provider-observation signing key, a workload-supplied key, or a key
included in the receipt itself. The receipt verifier is local and performs no
network access. A provider adapter must implement
`validate_candidate_observation(run, observation)` to independently query or
reconcile its authenticated provider object and confirm its identity, device,
terminal state, and result claims.

The implemented verifier is `gateway/gpu_gateway/candidate_receipts.py`.
Trusted public keys use the distinct
`GATEWAY_CANDIDATE_RECEIPT_PUBLIC_KEYS_JSON` setting, formatted as one-line JSON
mapping namespaced key IDs to Ed25519 public PEM values. Use
`provider:<provider>:<key-id>` only for provider keys and
`adapter:<provider>:<key-id>` only for adapter-attestation keys. The signer
field must match the key namespace. An empty map means no candidate success
can be accepted. Key provenance, rotation, revocation, and production
provisioning remain operator acceptance work.

## Signed envelope

The provider signs canonical ASCII JSON using UTF-8-compatible ASCII encoding,
sorted object keys, compact separators, and `allow_nan=false`. The envelope has
exactly:

```json
{
  "schema_version": 1,
  "signer": "provider",
  "key_id": "provider:runpod:receipt-v1",
  "provider": "runpod",
  "issued_at": 0,
  "expires_at": 0,
  "payload": {},
  "signature": "base64url-ed25519-signature"
}
```

`signer` is either `provider` or `gateway_adapter`. For
`gateway_adapter`, `evidence_source` in the payload must name the authenticated
provider API projection that the adapter checked (for example
`runpod.graphql.pod`). `provider_object_sha256` is the digest of that bounded
projection. `signature` is the unpadded base64url Ed25519 signature over the
canonical envelope without the `signature` member. Receipt size is at most 16
KiB and validity at most 300 seconds. The signer must issue the receipt only
after execution has finished and result claims are final.

The payload has exactly these fields:

| Field | Required binding |
| --- | --- |
| `run_id` | persisted Gateway run ID |
| `plan_fingerprint` | exact approved PlanV2 fingerprint |
| `source_sha` | approved source revision |
| `image_digest` | approved immutable image digest |
| `resource_id` | exact `selection_binding.resource_id`; no replacement |
| `provider_execution_id` | provider's durable execution identity |
| `device_id` | provider-observed physical/virtual device identity |
| `device_model` | equals normalized `ResultV2.device` |
| `gpu_used` | literal `true` for a successful GPU result |
| `exit_code` | integer `0` for a successful GPU result |
| `result_sha256` | SHA-256 of canonical `{device,gpu_used,exit_code,metrics,checksum}` claims |
| `evidence_source` | provider receipt type or authenticated API projection, prefixed by provider |
| `provider_object_sha256` | SHA-256 of the bounded authenticated provider object projection |

The Gateway checks signer scope, signature against the independently pinned
key, current time window, provider, exact plan/run/source/image/resource
identity, evidence source, and result digest. A worker-added validation marker
is not accepted as proof by itself. A `gateway_adapter` signature attests to
trusted adapter code's authenticated API observation; it must never be
displayed or described as provider-signed hardware attestation.
After receipt verification, the worker adds
`candidate_resource_verified` and `device_identity_verified` to the normalized
result and persists the signed receipt for later audit. Public result consumers
can independently verify the receipt against the configured public key.

## Adapter and acceptance requirements

An accepted registry entry needs all of:

- `supports_candidate_binding=true` set only after review;
- `start_candidate_bound(run)` consuming the bound PlanV2 and never selecting
  a replacement resource;
- `validate_candidate_observation(run, observation)` authenticating the live
  provider object and cross-checking receipt execution/resource/device claims;
- terminal `capture`, idempotent `cleanup`, and `is_clean` proof;
- `Observation.candidate_receipt` carrying the bounded signed receipt on
  success;
- result digest computed over the same normalized claims as the Gateway;
- tests for signature, wrong key, expiry, replay/identity mismatch, resource
  substitution, changed result, cancellation, uncertain create, worker restart,
  and cleanup failure.

Provider documentation or a live account must establish whether it can issue
a verifiable provider-signed receipt or expose authenticated API fields that a
trusted adapter can reconcile. Never label a workload self-report as provider
attestation.
Offline fake-signer tests prove only cryptographic contract behavior. They do
not prove provider support, hardware identity, GPU execution, billing, or
cleanup. Paid execution remains a separate explicit authorization gate.

## Current provider source check — 2026-10-28

The current [RunPod GraphQL API spec](https://graphql-spec.runpod.io/) exposes
Pod identity, `machineId`, `gpuTypeId`, `gpus`, and runtime/telemetry fields in
authenticated queries. The reviewed schema does not define a provider-signed
execution-result receipt. The [Modal Sandbox SDK](https://modal.com/docs/sdk/py/latest/Sandbox)
exposes Sandbox identity, polling, streams, and termination; the documented
[Sandbox runtime environment](https://modal.com/docs/guide/environment_variables)
includes `MODAL_SANDBOX_ID`, but the reviewed interfaces do not provide a
provider-signed hardware/result receipt. This is documentation evidence only;
no account credentials or provider API were used.

The envelope now distinguishes provider signatures from Gateway adapter
attestations. An adapter attestation requires a separately scoped adapter key
and a provider-specific live API cross-check against the exact approved plan.
The distinction is persisted in the signed receipt so API consumers can inspect
the evidence source. This does not upgrade authenticated API metadata into
cryptographic provider attestation, and it never accepts workload self-report
as provider evidence.


## Current RunPod REST API source revalidation — 2026-10-28

Current official API documentation is captured in
`docs/acceptance/2026-10-28-runpod-api-v2-revalidation.md`. RunPod REST v1 is
deprecated and scheduled for retirement on 2026-11-15. V2 documents authenticated
Pod/GPU identity and state, runtime/CUDA metadata, SSE container/system logs,
lifecycle actions, and termination. These fields make trusted adapter
attestation technically plausible, but logs are not yet accepted as durable
result/artifact transport or provider-signed evidence. The legacy REST v1 client
and adapter are not eligible for live activation. No registration or provider
flag changed; parked mode remains.

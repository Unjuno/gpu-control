# Runpod REST v2 / Sites adapter foundation — 2026-11-15

## Scope

This slice replaces the stale assumption that a persistent Runpod Network
Volume and S3 credentials are required for the first GPU canary. It does not
enable or perform paid compute.

Current official Runpod REST v2 documentation records:

- `POST /v2/pods` creates one Pod and returns `201`; provisioning is async;
- `GET /v2/pods/{id}` reports lifecycle state;
- `POST /v2/pods/{id}/exec` runs a direct argv command without SSH or an
  exposed port, waits at most 25 seconds, and returns bounded stdout, stderr,
  exit code, timeout, truncation, and duration fields;
- `DELETE /v2/pods/{id}` permanently terminates the Pod and returns `204`.

References:

- <https://docs.runpod.io/api-reference-v2/pods/create-a-pod>
- <https://docs.runpod.io/api-reference-v2/pods/get-a-pod>
- <https://docs.runpod.io/api-reference-v2/pods/run-a-command-in-a-pod>
- <https://docs.runpod.io/api-reference-v2/pods/terminate-a-pod>

## Implemented boundary

- A Sites Worker REST v2 client uses only `https://api.runpod.io` and rejects
  redirects, unexpected success statuses, oversized/invalid JSON, and
  provider text as control-plane errors.
- Pod creation is fixed to Secure Cloud, one configured GPU, one immutable
  image reference, no SSH, no Jupyter, no public ports, and no global network.
- The execution method exposes only the registered image wrapper and bounded
  `steps` and `seed`; it cannot accept a shell command from ChatGPT.
- The fixed GPU canary runs training as UID 10001. Its root wrapper alone
  receives the ephemeral completion key and emits bounded result and HMAC-v3
  completion markers.
- A manually dispatched GitHub workflow can publish the linux/amd64 canary to
  GHCR. Every third-party action and the CUDA/PyTorch base image are pinned by
  immutable digest or full commit SHA.
- `experiment_capabilities` now describes `runpod_gpu` and
  `runpod-gpu-canary-v1`, but keeps them disabled until server-side credential,
  immutable published image, admission, pricing, authorization, and lifecycle
  wiring all exist.

## Verification

- Sites Worker: 52 tests passed.
- Runpod v2 policy and workflow security: 13 tests passed.
- Python canary files compiled successfully.
- `git diff --check` passed.

An independent Security Review worker was requested twice but did not start:
both attempts returned service-side `403` because Daybreak was unavailable for
the selected worker model. This is a review-infrastructure failure, not a
security acceptance. Independent review remains required before live
admission.

## Remaining activation gates

No Runpod API key was created, no Site secret was changed, no image was
published, and no Pod was allocated in this slice. The account balance observed
earlier was `$0.00`.

Before one paid canary:

1. finish D1 provider/run lifecycle and encrypted ephemeral completion-key
   persistence;
2. bind catalog price and exact GPU/datacenter availability to the owner-bound
   plan and short-lived ChatGPT confirmation;
3. publish and record the immutable canary digest;
4. create a minimum-permission Runpod credential and store it only as a Sites
   secret;
5. independently review the final source;
6. verify balance and exact total cost ceiling immediately before execution;
7. terminate the exact Pod and reconcile account-wide absence before accepting
   the result.

# P5 signed paid-authorization verifier — 2026-10-31

Status: **PASS for pure offline envelope and exact-plan verification only.**
No authority issuer is configured, no authorization was issued, no worker or
database integration was added, and no provider call or paid execution occurred.
Keep `policies/repository-state.yaml` at `mode: parked`.

## Implemented boundary

`gateway/gpu_gateway/paid_authorization_bridge.py` verifies an Ed25519-signed,
strict-schema authorization from an externally trusted issuer. The verifier
requires a caller-supplied trusted key map and revocation lookup. It fails
closed on a missing or failing revocation lookup. The envelope is bound to the
audience, issuer/key namespace, authorization and revocation IDs, owner, actor,
decision record, control-plane SHA, Gateway run ID, Gateway PlanV2 fingerprint,
RunPod core-plan fingerprint, provider/resource, immutable image, exact runtime,
cost ceiling, and core authorization reference.

The mapping check also requires a candidate-bound RunPod plan, current
`PAID` cost evidence with a known positive total within the approved ceiling,
exact repository
and source SHA correspondence, exact GPU profile/count, and a minute-aligned
runtime that maps exactly to the approved core plan. The approved core plan's
worst-case amount must also fit within the current Gateway cost evidence, in
addition to the independently enforced authorization ceiling. Zero-additional-cost plans
cannot use the paid-authority verifier. The verifier creates no human evidence,
`LiveExecutionPermit`, or authorization envelope; the independent issuer and
existing provider gates remain separate. `Settings` can parse the bounded
Ed25519 trust map and enforce that configured keys match the configured issuer
and policy version; these values are not consumed by worker admission yet.

## Evidence

- Focused command: `uv run --project . pytest tests/test_paid_authorization_bridge.py -q`
  from `gateway/`.
- Focused result: **38 passed**, one existing Starlette deprecation warning.
- Adversarial cases include validly signed wrong run/owner/actor/decision/control
  plane/resource/image/runtime/cost claims, signature tampering, untrusted key,
  wrong audience or stale policy version, negative/expired/future issue time, overlong
  TTL, revoked authorization, revocation lookup failure or malformed return,
  nested/oversized fields, unknown fields, core-plan
  fingerprint mismatch, missing/unknown/zero/stale/over-cap Gateway cost
  evidence, a core worst-case quote above Gateway cost evidence, and
  zero-additional-cost misuse.
- Full Gateway command: `./.venv/bin/python -m pytest -o addopts= -q -rs tests`
  from `gateway/`.
- Initial offline full Gateway result: **467 passed, 15 skipped**, one existing
  Starlette deprecation warning. The skips included optional dependencies and
  container/database integrations, so this run alone was not the complete
  Gateway evidence.

## Current-worktree Docker/PostgreSQL revalidation — 2026-10-31

- Source checkout HEAD: `a794438`; the 40-path worktree remained uncommitted.
- CPU image: `sha256:81a53ab7aa2b1ae7f3cc685457c73b98f66c456a5baba204a139397f856db31b`
  (`linux/arm64`, labels `Unjuno/gpu-control` and the all-`a` fixture SHA).
  This is a local fixture identity, not a published source commit.
- PostgreSQL image: `postgres@sha256:9e2cf6287f25c3151f4c9421ccce2b17f3e60061c111a29165e0d2cdd9ff0a97`,
  PostgreSQL 16, exposed only on `127.0.0.1:55471` in a uniquely named,
  disposable container. The container was removed after the run; a follow-up
  inventory found no matching container and no listener on that port.
- Gateway result: **480 passed, 2 skipped**, one existing Starlette
  deprecation warning. The skips were optional Torch and Modal checks. This
  includes real local CPU container and MCP/artifact flows, PostgreSQL
  migrations/OAuth, and PostgreSQL outage recovery against this worktree.
- Core result: **550 passed, 1 skipped**; the skip is the Python 3.11-specific
  malformed-RunPod-log reproducer on Python 3.12.
- `git diff --check` passed. No provider call, GPU allocation, paid run,
  deployment, or ChatGPT conversation was made.

This is not independent security review, durable persistence, one-use/replay
control, provider pre-create revalidation, worker acceptance, GitHub CI, or
live RunPod evidence. Provider registration and paid switches remain off.

## P1+P2+P3+P4+P5 cumulative candidate — 2026-10-31 11:55 JST

- Reconstructed `/tmp/gpu-control-p1p2p3p4candidate-on-561a6c7` from exact
  PR #58 head `561a6c7ac697dfdf22f304b60e313fccb2c806a4`, applying P1, P2, P3,
  P4 and P5 patches sequentially. The P4 provider-contract patch SHA-256 is
  `f45f0e7b84057e83945e200a1176be0cd6ec83cd6adcde7d0d1c6eb70a51e9fb`; P5
  offline authorization patch SHA-256 is
  `fcc6b9fd524b477f335a75205767b31b24598626b92a03bb2b66e3ddd12b4f5c`. Every
  patch passed `git apply --check`; cumulative `git diff --check` passed.
- A first full-suite run with P4 but without P5 had **443 passed, 1 failed,
  2 skipped**. The failure was the paid-candidate worker test double missing
  `reconcile` and `cancel`, which the P4 candidate-bound backend contract now
  requires before reaching authorization validation. P5's six-line test
  fixture update implements those required methods. This intermediate failure
  is retained as dependency evidence; the production worker correctly failed
  closed with `paid_execution_contract_unavailable`.
- After applying P5, the full Gateway suite passed **482 tests, 2 skipped**,
  one existing Starlette deprecation warning, in 26.01 seconds. Skips were
  optional Torch and Modal. The full Core suite passed **559 tests, 1
  Python-3.11-specific skip** in 1.40 seconds. Both suites imported code from
  the cumulative candidate worktree.
- Verified candidate policies still say `mode: parked`,
  `live_paid_compute_allowed: false`, `runpod_live_calls_allowed: false`, and
  `live_paid_compute_enabled: false` in both paid-policy files. The disposable
  PostgreSQL container and local CPU image were removed; port 55501 was
  confirmed closed. No provider credentials, provider calls, GPU allocation,
  or paid execution occurred.
- This establishes cumulative local regression evidence only. No GitHub CI or
  approval covers this candidate; the paid verifier remains offline-only, and
  deployed readiness, ChatGPT use, real GPU operation, and paid-execution
  acceptance remain open.

## P5 account-lease and worker-auth cumulative refresh — 2026-10-31 12:02 JST

- Extended the same PR #58-based candidate with the account-lease persistence
  patch SHA-256
  `00756f8f4573763decf13db60244a2bff1338990f0637e74a909c605d7570a4d`,
  worker-auth refresh
  `9526868ecca6cbd4d29571616c0e5f35ff585fc2a0938691779ff3f77977c057`, and P4
  contract refresh `e2d1758382b8d8504b2b026cff5e8e5f1d262d3d1fc77f78fc5ec2ee715d9165`.
  The latter supplies the shared paid/credit authorization-kind helper required
  by P5 service wiring. All three patches applied cleanly and cumulative
  `git diff --check` passed.
- Before the full test pass, two incomplete-stack attempts identified exact
  dependencies: P5 service import needed the P4 authorization-kind helper;
  after that was added, three account-scope tests exposed the missing HMAC-key
  configuration overlay. Applying the worker-auth refresh supplied that
  setting and its parsing/validation. These intermediate failures are kept as
  stack-composition evidence.
- On the completed cumulative candidate, Gateway passed **520 tests, 2
  optional skips**, one existing Starlette deprecation warning, in 25.81
  seconds. Core passed **559 tests, 1 Python-version-specific skip** in 0.92
  seconds. The tests imported the candidate worktree and used PostgreSQL 16
  plus a digest-identified local CPU smoke image. Source hashes include
  `provider_account_scope.py`
  `915a60f500665e62b6d18379772341a2ccbd5be15c6e36b3acb33264c63a901e` and
  `test_provider_account_leases.py`
  `1a7be6f5ab84f1be06cffbf90bea83fa19b04c2d36cc1f71254eec34567305f3`.
- Confirmed policy values remain `mode: parked`,
  `live_paid_compute_allowed: false`, `runpod_live_calls_allowed: false`, and
  `live_paid_compute_enabled: false` in both paid-policy files. Removed the
  disposable database container and local CPU image; port 55502 was confirmed
  closed. No credentials, provider, GPU, or paid execution was used.
- This validates local cumulative code and tests, not GitHub CI/review, hosted
  readiness, ChatGPT acceptance, real GPU execution, or live paid execution.

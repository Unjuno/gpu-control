# P4 fake candidate lifecycle evidence — 2026-10-31

## Result

The current Gateway suite passed **498 tests, 2 skipped**, with one existing
Starlette deprecation warning. The run used disposable loopback PostgreSQL 16
and the digest-pinned local CPU smoke image. The temporary PostgreSQL
container was removed after the run; no listener remained on its port.

The added regression
`test_free_candidate_backend_success_requires_bound_receipt_and_confirmed_cleanup`
exercises the Gateway lifecycle with a synthetic `FREE` candidate and fake
adapter: prepare, explicit test approval, submit, worker start/capture, signed
receipt verification, result persistence/read, cleanup confirmation, and slot
release. The test asserts the receipt binds the approved plan, run, resource,
and result, and that the public result records `simulation=false`,
`gpu_used=true`, and completed cleanup.

## Scope boundary

The provider inventory, NVIDIA A10 device identity, adapter signing key, and
provider receipt are synthetic test fixtures. No provider API/account, real
GPU, paid resource, deployed service, or ChatGPT workspace was used. This is
offline contract and lifecycle evidence; it does not pass `FREE_GPU_EXECUTION`
or product acceptance. Provider registrations remain disabled and
`policies/repository-state.yaml` remains parked.

The full-suite result was observed on the current working tree on 2026-10-31;
this record does not establish that the changed tree was pushed, reviewed by
GitHub, merged, or deployed.

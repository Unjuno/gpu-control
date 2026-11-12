# Result-to-plan binding acceptance — 2026-10-28

Status: **PASS for the worker result identity contract only**.

## Finding and change

The worker finish validator compared `image_digest` to the approved plan only
for `local_cpu` and did not compare the result's `provider` at all. A backend
could therefore return a result claiming a different provider or image while
the run remained bound to its original plan. This undermined the roadmap's
requirement to return exact provider and workload image identity.

`validate_result_binding` now requires the result's provider and image digest
to match the persisted plan for every newly completed plan. The image field
remains optional in the `ResultV2` schema for legacy persisted data; existing
stored runs are not rewritten or revalidated by this change. The validator is
used at `Worker.finish`, before a terminal result is accepted.

## Evidence

- Base commit: `f054aebe96460fe033dde8d91d7e3bbab0255655`.
- `gateway/tests/test_contracts_v2.py` and
  `gateway/tests/test_local_admission.py` — **37 passed**. The cases cover
  legitimate non-CPU binding and rejection of wrong provider, wrong image,
  missing image, and worker terminalization as `result_integrity_failed`.
- Full offline Gateway suite — **344 passed / 9 skipped**, one existing
  Starlette deprecation warning.
- After the contract change, the full Gateway suite ran against the digest-pinned
  CPU image `sha256:687f52cf7292fc7109cb8df2469cfa9b1296d0d0b5bf1894582cf738c4d8481e`
  and PostgreSQL 16 image
  `postgres@sha256:9e2cf6287f25c3151f4c9421ccce2b17f3e60061c111a29165e0d2cdd9ff0a97`.
  PostgreSQL was bound only to `127.0.0.1:55545` in the uniquely named
  disposable container `gpu-control-postgres-result-binding-1028`. Result:
  **351 passed / 2 optional skips**, one Starlette deprecation warning, 21.39s.
  Skips were optional Torch and Modal SDK checks. This verifies the normal
  digest-pinned local CPU execution and result acceptance path after the new
  provider/image binding.
- Cleanup inventory found no matching PostgreSQL container, no container with
  `io.unjuno.gpu-control.run-id`, and no PostgreSQL volume. No unrelated
  container or volume was changed.
- Source SHA-256: `a711fc9c6a4b6d8786d73463146647d0ddab8e020b880a9ab0ad1916392b33a3`.
- Contract test SHA-256:
  `1652470aaf4e579f2f4d871cb42f41971a3935f4e61ccc4badca62558d1fc138`.
- Worker integration test SHA-256:
  `9b54f0e49851a7bd49294b57a956717cbb0b3eeb3bac02fd0565dc293fe32f7d`.
- `git diff --check` passed.

The integration run exercises a local CPU worker and PostgreSQL, not a GPU or
external provider. This does not establish provider evidence, ChatGPT
acceptance, deployment acceptance, or paid-compute authorization. Parked mode
is unchanged.

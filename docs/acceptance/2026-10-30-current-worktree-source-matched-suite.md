# Current worktree source-matched local suites — 2026-10-30

Status: **PASS for local Gateway/Core suites at the identified source snapshot. GitHub CI, GitHub review, deployment, ChatGPT and target-host acceptance remain open.**

## Exact source inputs

- Git base: `aa681f4062dac6b73bcf380a38a4258b96a47e1d`.
- Gateway dirty-source fingerprint: `06dc2a2d9b48d146d0dc45a650feacaa7949ff7860eb4fba25c6bc1cfd605877`.
  The fingerprint is SHA-256 over the binary tracked diff from HEAD followed
  by the sorted path and bytes of untracked Gateway files.
- CPU image was built from the current `gateway/workloads/cpu-smoke/Dockerfile`
  with pinned Python base image
  `python:3.12-slim-bookworm@sha256:6dd8b6dab6b3adc7812bab69eca5dbdc1a5cc690ad28306d234ffb4ef8ac9753`.
  Image digest: `sha256:df0740a1425e47096f2921b57810f40d91ffb59d13b7f85766b21f95d097837a`
  (`linux/arm64`). The image repository label is `Unjuno/gpu-control`.
- This test suite's registered workload fixture uses the synthetic source SHA
  `aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa`; the image revision label matches
  that fixture. This is a test identity, not a release source claim.
- Image `/app/smoke.py` SHA-256:
  `bab9a5e10a516a631d8a7a12ed004d9c64e7efd639fe7ff6c64614bfb09e2d9a`.
  Image `/app/supervise.py` SHA-256:
  `89874c0924102322e223a285d6ba64a72774b99300ba7ed752c5b46fae1440bb`.
  Both match the exact build-context files.
- PostgreSQL 16 image digest:
  `sha256:9e2cf6287f25c3151f4c9421ccce2b17f3e60061c111a29165e0d2cdd9ff0a97`.
  The disposable test container was loopback-only and deliberately lacked
  `--rm`, because one integration test stops and restarts PostgreSQL. An exit
  trap removed only this named container after the run.

## Results

- Gateway command: `./.venv/bin/python -m pytest -o addopts= -q -rs tests`
  from `gateway/`, with `GATEWAY_TEST_DATABASE_URL`,
  `GPU_CONTROL_POSTGRES_CONTAINER`, `GPU_CONTROL_CPU_SMOKE_IMAGE_DIGEST`, and
  `GPU_CONTROL_CPU_SMOKE_SOURCE_SHA` set to the disposable resources and test
  fixture above.
- Gateway: **427 passed, 2 skipped** in 24.10 seconds. Skips were the optional
  PyTorch bridge and Modal backend; one existing Starlette deprecation warning
  remained. The run included Docker CPU execution, authenticated MCP artifact
  retrieval, worker crash recovery, and PostgreSQL outage/recovery.
- Core command: `./.venv/bin/python -m pytest -o addopts= -q -rs` from the
  repository root. Result: **550 passed, 1 skipped** in 1.08 seconds. The skip
  is Python-3.11-specific.
- `git diff --check` passed; the disposable DB container was removed; the
  primary worktree and Git refs were preserved. The CPU image remains in the
  local Docker cache and was not pushed.

## Excluded harness attempts and limits

Earlier attempts are excluded: one supplied the wrong image environment
variable and skipped Docker integration tests; a later image used a revision
label different from the synthetic fixture; and a PostgreSQL container started
with `--rm` was deleted when the outage test stopped it. The corrected run above
uses the documented environment variables, matching fixture provenance, and a
restartable disposable database. No product code was changed to mask these
harness issues.

This proves local source behavior only. The dirty Gateway changes remain
uncommitted and have not passed the seven required GitHub checks or GitHub
review. No production service, ChatGPT account, selected host, GPU, provider, or
paid resource was used. Keep `policies/repository-state.yaml` at
`mode: parked`.

## Trusted reference container check — 2026-10-30 17:23 UTC

Reproduced the separate `.github/workflows/ci.yml` trusted reference workload
job locally against the current checkout's unchanged `examples/reference-workload`
tree. Built `gpu-control-reference:codex-aa681f4` from the checked-in Dockerfile;
the local image manifest digest was
`sha256:feec6366e18bd63ab1c3434312b98066b6e0460bc8a4701ab6ca0c0f8680c52d`.
Created a uniquely named container with network disabled, read-only root,
all capabilities dropped, no-new-privileges, 64 PID limit, 128 MiB memory, one
CPU, and bounded noexec tmpfs mounts. The workload emitted the expected
success JSON and all four isolation checks were true. Docker inspect confirmed
the requested limits, no devices/binds/host PID or IPC, and no GitHub, RunPod,
or host sentinel secret in the container environment. The host sentinel was
supplied only to the `docker start` client process. The 30-second deadline was
enforced with Python `subprocess.run(timeout=30)` because macOS lacks the GNU
`timeout` command used in CI. The first harness attempt stopped before starting
the container due to that missing command; the named container and image were
absent after cleanup verification. The successful rerun removed its container
and image. This is local arm64 container evidence, not the required Ubuntu
GitHub Actions check and not independent review.

## Required bridge workflow checks — 2026-10-30 17:26 UTC

Reproduced both bridge workflow test payloads from the current checkout:

- Gateway comment bridge modules:
  `PYTHONPATH=gateway ./gateway/.venv/bin/python -m pytest -o addopts= -q -ra gateway/tests/test_ci_bridge.py gateway/tests/test_ci_service_integration.py`
  passed **81 tests / 1 skipped** in 3.11 seconds. The skip is the optional
  Torch test; the existing Starlette deprecation warning remains.
- The workflow's tiny-LM Docker fixture was built from
  `gateway/workloads/tiny-lm` with `--pull`; image manifest digest
  `sha256:8570298faaa565feb632c469b747b59e9783bf9f569a7a7069f3ba4c251a4a1e`.
  Ran with network disabled, read-only root, no capabilities, no-new-privileges,
  UID/GID 10001, 32 PID limit, 128 MiB memory, one CPU, and bounded noexec
  tmpfs. At 40 steps it reported `gpu_used=false` and loss decreased from
  `2.564949357461535` to `1.8011487310380074`. Python enforced the workflow's
  30-second deadline because GNU `timeout` is unavailable on this macOS host.
  The named container was auto-removed and the temporary image tag was removed.
- Project bridge unit workflow:
  `./gateway/.venv/bin/python -m unittest discover -s gateway/project_control/tests -v`
  passed **19/19**. Its real Docker smoke script passed with the expected
  `script-contract-v1` receipt, `gpu_used=false`, and loss decreasing from
  `25.0` to `0.0009140396100157518`; local image ID was
  `sha256:2e72cbf7045715672f14d27390b9ded044475004cbf49994f243f8bf54dae202`.
  The runner removed its uniquely named container in `finally`; the exact
  image tag was removed after success.

These are local macOS/OrbStack arm64 reproductions of the test steps. They do
not establish GitHub Actions status, an Ubuntu run, source review, production
readiness, or ChatGPT acceptance.

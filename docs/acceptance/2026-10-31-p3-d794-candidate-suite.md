# P3 paired backup and operations candidate suite — 2026-10-31

Status: **PASS for local candidate-source and backup operations integration only. Production-host and ChatGPT acceptance NOT RUN.**

## Candidate and image

- Candidate source: `d794c134358b075caaad213f2b0d6a0378202d02`
  (`Add paired backup and Linux operations tooling`), proposed range
  `c8172c0..d794c13`.
- A fresh detached worktree at `d794c13` built the CPU image using its own
  `gateway/workloads/cpu-smoke/Dockerfile`, with source repository and full SHA
  supplied as build arguments.
- Image:
  `sha256:205561a7ff6d32de0a750485f72613878435f660b90b050c86c789aad876fc2d`
  (`linux/arm64`). OCI labels match `Unjuno/gpu-control` and the exact
  `d794c13` source SHA. Base image is the pinned Python image declared in that
  Dockerfile:
  `python:3.12-slim-bookworm@sha256:6dd8b6dab6b3adc7812bab69eca5dbdc1a5cc690ad28306d234ffb4ef8ac9753`.

## Test environment and result

- Full Gateway suite ran from the candidate worktree with candidate-local
  `PYTHONPATH`, the primary Python 3.12 venv, and a disposable PostgreSQL 16
  container bound to loopback port 55615. PostgreSQL digest:
  `sha256:9e2cf6287f25c3151f4c9421ccce2b17f3e60061c111a29165e0d2cdd9ff0a97`.
- Command: `python -m pytest -o addopts= -q -rs tests` from `gateway/`.
  Result: **272 passed, 2 skipped** in 20.62 seconds. The optional PyTorch
  bridge and Modal backend were skipped because `torch` and `modal` are absent.
  One existing Starlette `BlockingPortal` deprecation warning remained.
- Full root/Core suite ran from the same candidate worktree:
  **515 passed, 1 skipped** in 1.25 seconds. The skip is Python-3.11-specific.
- The focused backup-generation/deployment-unit subset previously passed
  21/21 at this checkpoint; this full run includes those tests.

## Cleanup and scope

The disposable PostgreSQL container and detached worktree were removed. The
candidate-specific image remains locally tagged
`gpu-control-cpu-smoke:p3-d794-candidate-20261031`; it was not pushed. The
primary dirty worktree and Git refs were unchanged. No production backup,
restore, host service, alert sink, database, provider, GPU, paid resource,
GitHub write, or deployment was used.

This validates the local source and integration contract for the P3 backup and
operations code at this candidate. It does not establish second-operator
recovery, target-host RPO/RTO, Neon behavior, alert delivery, seven-day
stability, GitHub CI/review, or ChatGPT acceptance. Keep
`policies/repository-state.yaml` at `mode: parked`.

## P1+P2+P3 cumulative candidate on exact PR #58 base — 2026-10-31 11:51 JST

- Reconstructed `/tmp/gpu-control-p1p2p3candidate-on-561a6c7` from exact PR #58
  head `561a6c7ac697dfdf22f304b60e313fccb2c806a4`, applying P1 readiness,
  P2 recovery, and P3 operations patches in order. The P3 patch SHA-256 is
  `e70747ef9b481ca49647f2ca776ce4b2f65dbec505f33bef0348e1844f8e0e11`.
  Every patch passed `git apply --check`; the cumulative candidate passed
  `git diff --check`.
- Candidate code hashes: backup generator
  `bf2f343a286c29772b3d13c19ac1fb40f007391c6a1ba349e085974773f1f724`, backup
  generation tests
  `de3688414649cbab9c2fd69ed21340b3e180269dec3dae90a33269e5541f4915`, and
  PostgreSQL backup-integrity tests
  `133e21b9b62922723cfc6ad940924e118db12016ae06d0976c5d2fde50a5bebe`.
- Full Gateway suite from this candidate: **433 passed, 2 skipped**, one
  existing Starlette deprecation warning, in 25.86 seconds. It used local
  candidate imports, a PostgreSQL 16 container pinned to
  `sha256:9e2cf6287f25c3151f4c9421ccce2b17f3e60061c111a29165e0d2cdd9ff0a97`
  on loopback port 55500, and the repository CPU smoke image built from this
  candidate's Dockerfile. The image had synthetic fixture revision label
  `dddddddddddddddddddddddddddddddddddddddd`, not a published source SHA.
  Skips were optional Torch and Modal dependencies.
- Removed the temporary PostgreSQL container and CPU smoke image; port 55500
  was confirmed closed. This is cumulative local regression evidence only.
  GitHub CI/review, target-host backup and restore, measured RPO/RTO,
  production readiness, and ChatGPT-originated run/result acceptance remain
  open. No provider/GPU/paid resource was used; retain `mode: parked`.

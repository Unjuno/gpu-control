# P1 CPU and OAuth candidate source-provenance suite — 2026-10-31

Status: **PASS for local candidate-source, image-provenance, Gateway, and Core suites only. Live ChatGPT and production acceptance NOT RUN.**

## Candidate and image

- Candidate source: `c8172c0b2e90d9e3332b18c2a4d25e5509ef1e16`
  (`Harden OAuth lifecycle and owner migration`). This is the proposed final
  P1 CPU/recovery candidate boundary that includes the schema-v7 OAuth
  migration fix. `7c4454b` is not a valid final boundary because its
  PostgreSQL migration regression fails; the later fix is present at `c8172c0`.
- A fresh detached worktree at `c8172c0` built the CPU smoke image from that
  worktree's `gateway/workloads/cpu-smoke/Dockerfile`, with
  `SOURCE_REPOSITORY=Unjuno/gpu-control` and `SOURCE_SHA` set to the full
  candidate SHA.
- Image:
  `sha256:f78a373ce68b1bc54bc383eaf9a4e68ddfa250b253627a990a6686105493b461`
  (`linux/arm64`). Its OCI labels read
  `org.opencontainers.image.source=Unjuno/gpu-control` and
  `org.opencontainers.image.revision=c8172c0b2e90d9e3332b18c2a4d25e5509ef1e16`.
- Base image is pinned in the candidate Dockerfile:
  `python:3.12-slim-bookworm@sha256:6dd8b6dab6b3adc7812bab69eca5dbdc1a5cc690ad28306d234ffb4ef8ac9753`.

## Test environment and result

- Gateway suite ran from the detached candidate tree with candidate-local
  `PYTHONPATH`, the primary Python 3.12 venv, and a disposable PostgreSQL 16
  container at loopback-only port 55614. PostgreSQL image digest:
  `sha256:9e2cf6287f25c3151f4c9421ccce2b17f3e60061c111a29165e0d2cdd9ff0a97`.
- Command: `python -m pytest -o addopts= -q -rs tests` from `gateway/`.
  Result: **251 passed, 2 skipped** in 21.01 seconds. The optional Torch bridge
  (`torch`) and Modal backend (`modal`) were unavailable. One existing Starlette
  `BlockingPortal` deprecation warning remained.
- The full root/Core suite from the same candidate source passed **515 passed,
  1 skipped** in 1.20 seconds; the skip is Python-3.11-specific.
- An earlier exact-head run in a fresh Python 3.12.13 environment passed
  Gateway **252 / 1 skipped**, WebMCP registration **3/3**, entrypoint
  compilation, and Core **515 / 1 skipped**. The current Gateway rerun has the
  same 253-test inventory; its second skip is the optional Modal suite because
  the reused venv lacks `modal`.

## Cleanup and scope

The disposable PostgreSQL container and detached worktree were removed. The
candidate-specific image remains locally tagged as
`gpu-control-cpu-smoke:p1-c817-candidate-20261031` for reproducible future
acceptance; no image was pushed. The primary dirty worktree, current branch,
and refs were unchanged. No provider API, GPU, paid compute, GitHub write,
deployment, or production database was used.

This proves local candidate-source execution with an image whose repository and
source SHA match the candidate, including OAuth schema migration tests. It does
not prove GitHub CI/review, ChatGPT OAuth or tool discovery, a ChatGPT-originated
CPU run, hosted readiness, or target-host P3 operations. Keep
`policies/repository-state.yaml` at `mode: parked`.

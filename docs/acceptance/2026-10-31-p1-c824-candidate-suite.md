# P1 CPU vertical candidate full-suite revalidation — 2026-10-31

Status: **PASS for local candidate-source integration only. ChatGPT and production acceptance NOT RUN.**

## Candidate and environment

- Proposed initial P1 review candidate: `origin/main..c824b90`
  (`c824b90` / `test(gateway): recover local runs after postgres outage`).
- Both test runs used a fresh detached worktree at exactly `c824b90`; `PYTHONPATH`
  pointed to that candidate's `gateway/` and `src/` directories. Python
  dependencies were reused from the primary checkout's Python 3.12 venv; this
  was not a clean locked-environment install.
- CPU worker image digest for the authoritative exact-source rerun:
  `sha256:991687fa94a8724a6ab968ecc47a9db2e5b4838b7ff350e04d72ad550dd43e20`
  (Linux arm64). It was built from the detached `c824b90` worktree using that
  candidate's Dockerfile and its pinned Python base image. Extracted
  `/app/smoke.py` and `/app/supervise.py` matched the candidate files byte for
  byte. Their hashes were respectively
  `a900d8c923b33e71e4263a6c5f1bb79e54fc35a9ae54af572489d503ecf51c58` and
  `89874c0924102322e223a285d6ba64a72774b99300ba7ed752c5b46fae1440bb`.
- The `c824b90` Dockerfile predates OCI source/revision labels, and that
  candidate's backend only checks the immutable image digest. This run passed
  the exact `c824b9018ea9dfd3d9f8b45f65b7b3fd60c4fb01` source SHA in the
  registered workload and container environment. The later `c8172c0` candidate
  adds source/revision labels and enforces them; its exact-source acceptance is
  recorded separately.
- PostgreSQL image:
  `postgres@sha256:9e2cf6287f25c3151f4c9421ccce2b17f3e60061c111a29165e0d2cdd9ff0a97`
  (PostgreSQL 16), in disposable container
  `gpu-control-p1-c824-postgres`, bound only to `127.0.0.1:55613`.

## Results

- Full Gateway suite from `gateway/` in the dependency environment reused for
  this re-run:
  `python -m pytest -o addopts= -q -rs tests` — **198 passed, 2 skipped** in
  19.82 seconds. The skips were the optional PyTorch bridge (`torch` absent)
  and Modal backend (`modal` absent). The suite exercised the digest-pinned real
  Docker CPU smoke workload and PostgreSQL lifecycle/recovery integrations.
- An earlier exact-candidate run using a fresh Python 3.12.13 environment
  passed **199 / 1 skipped** and WebMCP **3/3**; it also passed entrypoint
  compilation. The single skip was optional. This authoritative rerun used a
  source-matched image and passed **198 / 2 skipped**, also 200 total tests;
  the extra skip is the optional Modal suite because the reused environment
  lacks `modal`. An intervening rerun with the later cached image
  `sha256:687f52cf...` is not used as source-matched evidence: its embedded
  `smoke.py` differed from `c824b90` by one serialization change.
- Full root/Core suite from the candidate repository root:
  `python -m pytest -o addopts= -q` — **452 passed, 1 skipped** in 1.14 seconds.
  The skip is the Python 3.11-only RunPod recursion regression, not applicable
  to this Python 3.12 environment.
- Both invocations emitted the existing Starlette `BlockingPortal`
  deprecation warning.

## Cleanup and scope

The disposable PostgreSQL container was removed; a read-only follow-up found no
container with its test name and confirmed loopback port 55613 was free. Both
detached worktrees were removed; `git worktree list` returned only the primary
checkout at `aa681f4`. The primary dirty worktree and all local refs were left
unchanged. No provider call, GPU allocation, paid execution, GitHub write,
deployment, or production database operation occurred.

This source-matched re-run passes the complete Gateway and Core suites for the
first P1 candidate under the available dependency set; the earlier fresh-env
run additionally confirms WebMCP registration and compilation. It is not
GitHub CI, independent GitHub review,
ChatGPT OAuth/tool discovery, a ChatGPT-originated CPU run, production
readiness, or target-host operations acceptance. Keep
`policies/repository-state.yaml` at `mode: parked`.

# P1 CPU vertical CI parity fixes — 2026-10-31

## Findings from PR #51 head `69ef1cfd5b201c21c4bb7eae2492846ed20b44fd`

- GitHub check run `41165274529` failed before tests: the comment-bridge job
  installed `gateway/requirements-test.txt` from repository root. Its nested
  `-e ..` was therefore resolved to the checkout's parent, which has no
  `pyproject.toml`. The workflow now runs installation from `gateway/`, so
  `-e ..` resolves to the repository package.
- The first Gateway offline run exposed one stale assertion in the real
  container-crash recovery test. The new dispatch fence durably records
  `provider_call_started` before backend I/O; the test expected the older
  `dispatching` phase. It now asserts the fenced state and continues recovery.

## Local verification after the fixes

Gateway suite with disposable PostgreSQL 16 and the candidate CPU smoke image:
**425 passed, 3 skipped**, one existing Starlette deprecation warning, 18.57s.

Gateway comment-bridge tests: **81 passed, 1 skipped**, one existing Starlette
deprecation warning, 2.86s. The isolated tiny-lm container also completed its
40 CPU-only steps with `gpu_used=false` and lower final loss.

The Gateway wheel built successfully. `uv sync --project gateway --locked
--no-dev` succeeded in a disposable environment, and both runtime imports
passed. Core suite: **550 passed, 1 skipped**, 1.40s. The requirements dry-run
from `gateway/` resolved `-e ..` to this repository checkout. `git diff
--check` passed.

`deploy/verify_systemd_units_ci.sh` explicitly refuses to run outside an
ephemeral Linux Actions runner, so its authoritative result must come from
GitHub CI.

## Limits

These checks reproduce and fix the observed CI issues locally. Fresh GitHub CI
and independent review remain pending. Live ChatGPT acceptance and provider or
paid execution remain unverified; spending gates stay closed.

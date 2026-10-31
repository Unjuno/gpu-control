# PR #65 missing workload file startup follow-up

## Scope

- PR: https://github.com/Unjuno/gpu-control/pull/65
- Source and entrypoint-test commit: `36a26af4b4f5abfb667d177b560e5b0e37e52a77`
- Latest docs commit at this refresh: `3cd5e700830b8083afc6cae020ed43026b1f94c0`
- Base: PR #62 head `317240d2224e05e23aa5bb190ce7a4f0fc101c01`
- Change: classify `OSError` while loading Gateway settings/workloads as invalid configuration and keep health/readiness routes available; add a missing-file regression test.
- Repository parked mode and all live GPU/paid execution gates remain unchanged.

## Local evidence

Using the current Gateway virtualenv against this candidate source:

```text
PYTHONPATH="$PWD/gateway:$PWD/src" /Users/taka/Documents/ChatGPT/Gpuラッパリポジトリ/gpu-control/gateway/.venv/bin/python -m pytest -q gateway/tests/test_http_auth.py
35 passed, 1 existing Starlette deprecation warning
```

The suite imports the actual `gateway/app.py` Vercel entrypoint under a
missing-workload-file environment and verifies both health responses after
`install_ci_routes()` runs. This complements the direct `create_app()` test;
it still does not reproduce the Vercel runtime environment.

`git diff --check` passed before the commits. The source changes are limited to
`gateway/gpu_gateway/app.py` and `gateway/tests/test_http_auth.py`; this
acceptance record is the third changed path. A read-only Security Review of
the source-fix branch diff found no issues before the entrypoint test was
added; this is not a GitHub review or deployment approval.

## CI and Preview

Checks for the latest head all passed: Python 3.11/3.12/3.13, trusted
reference container, Gateway offline tests, Gateway comment bridge tests,
Project bridge tests, Vercel deployment, and Vercel Preview Comments.

The READY Preview deployment sourced from the latest PR head `3cd5e70` is
`dpl_FNRCNLmVN4KEj7REHQuAQEhJ5U3w`
(`gpu-control-3xm2hhx73-unjunos-projects.vercel.app`). Protected GET requests
on 2026-10-31 at 07:26 UTC to `/healthz` and `/readyz` both returned HTTP 500
`FUNCTION_INVOCATION_FAILED` before an application response. Request IDs:

- `/healthz`: `hnd1:iad1::m6vm9-1793431582511-62a522aeb066`
- `/readyz`: `hnd1:iad1::9lkp2-1793431585206-4509e46158ec`

Vercel runtime-log queries scoped to the deployment and request ID returned no
records. Thus the missing-workload-file exception path is fixed and locally
covered through the deployment entrypoint, but it does not explain the
observed Vercel invocation failure. Its startup cause remains undiagnosed. Do
not count the Preview deployment's `READY` state as function-runtime or
ChatGPT acceptance.

The read-only trace request for the health request ID returned HTTP 403.

The current connection also cannot list Preview environment-variable
metadata: a read request with decryption disabled returned HTTP 403. The
`vercel` CLI is not installed locally, and no variable names or values were
retrieved. Required Preview configuration therefore remains unverified.

## Remaining acceptance

- Obtain runtime diagnostics or verified deployment configuration sufficient
  to identify the Vercel invocation failure.
- Review and integrate the PR stack through the repository's protected path.
- Re-deploy and observe application-level health/readiness.
- Complete authenticated ChatGPT OAuth, tool discovery, registered CPU
  execution, and second-conversation result retrieval.

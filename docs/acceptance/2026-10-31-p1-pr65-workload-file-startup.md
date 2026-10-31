# PR #65 missing workload file startup follow-up

## Scope

- PR: https://github.com/Unjuno/gpu-control/pull/65
- Source and entrypoint-test commit: `36a26af4b4f5abfb667d177b560e5b0e37e52a77`
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

`git diff --check` passed before the commit. The PR contains only
`gateway/gpu_gateway/app.py` and `gateway/tests/test_http_auth.py` at this
point. A read-only Security Review of the branch diff found no issues; this is
not a GitHub review or deployment approval.

## CI and Preview

The prior source-fix commit passed all GitHub checks. After adding the
entrypoint regression test and this record, checks for the current head were
rerun and all passed: Python 3.11/3.12/3.13, trusted reference container,
Gateway offline tests, Gateway comment bridge tests, Project bridge tests,
Vercel deployment, and Vercel Preview Comments.

The READY Preview deployment sourced from the current PR head is
`dpl_GHswBncuQhXbK6TbdgQtVmpas5za` (`gpu-control-ffmkc4fdz-unjunos-projects.vercel.app`).
Protected GET requests on 2026-10-31 at 07:21 UTC to `/healthz` and `/readyz`
both returned HTTP 500 `FUNCTION_INVOCATION_FAILED` before an application
response. Request IDs:

- `/healthz`: `hnd1:iad1::4gt64-1793431290937-aa728d631130`
- `/readyz`: `hnd1:iad1::gwl98-1793431293753-af614463af2f`

Vercel runtime-log queries scoped to the deployment and request ID returned no
records. Thus the missing-workload-file exception path is fixed and locally
covered through the deployment entrypoint, but it does not explain the
observed Vercel invocation failure. Its startup cause remains undiagnosed. Do
not count the Preview deployment's `READY` state as function-runtime or
ChatGPT acceptance. The entrypoint regression test was added after this
deployment probe; application source is unchanged, but the test-only follow-up
needs its own CI run.

## Remaining acceptance

- Obtain runtime diagnostics or verified deployment configuration sufficient
  to identify the Vercel invocation failure.
- Review and integrate the PR stack through the repository's protected path.
- Re-deploy and observe application-level health/readiness.
- Complete authenticated ChatGPT OAuth, tool discovery, registered CPU
  execution, and second-conversation result retrieval.

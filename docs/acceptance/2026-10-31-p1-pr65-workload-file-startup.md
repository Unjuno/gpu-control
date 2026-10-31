# PR #65 missing workload file startup follow-up

## Scope

- PR: https://github.com/Unjuno/gpu-control/pull/65
- Head: `a9d610d3682f1985a65280da05619462a5825cd1`
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

The PR's current GitHub checks all passed: Python 3.11/3.12/3.13, trusted
reference container, Gateway offline tests, Gateway comment bridge tests,
Project bridge tests, Vercel deployment, and Vercel Preview Comments.

The READY Preview deployment sourced from the exact source-fix commit is
`dpl_2CUftHSvpFSSY38uuqsm3Ggn8gZh` (`gpu-control-cqk7pa8m7-unjunos-projects.vercel.app`).
Protected GET requests on 2026-10-31 to `/healthz` and `/readyz` both returned
HTTP 500 `FUNCTION_INVOCATION_FAILED` before an application response. Sample
request IDs:

- `/healthz`: `hnd1:iad1::wlx9z-1793430955217-d9393410c184`
- `/readyz`: `hnd1:iad1::dvws2-1793430957852-45630a583830`

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

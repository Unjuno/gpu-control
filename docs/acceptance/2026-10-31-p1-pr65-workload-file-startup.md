# PR #65 missing workload file startup follow-up

## Scope

- PR: https://github.com/Unjuno/gpu-control/pull/65
- Original source-fix commit: `a9d610d3682f1985a65280da05619462a5825cd1`
- CI bridge fail-closed source commit: `f9e691f5af6267f9599f89f7bc160b8dbf583a5d`
- Hosted-environment regression commit: `faedd8c474a38d851ce9e27adee30fb118059446`
- Latest validated PR head at this refresh: `7797d5e95e7f8bf1a6eb0a9da4793785c20fe7e7`
- Base: PR #62 head `317240d2224e05e23aa5bb190ce7a4f0fc101c01`
- Change: classify `OSError` while loading Gateway settings/workloads as invalid configuration and keep health/readiness routes available. If optional CI bridge policy loading fails, keep the Gateway up and expose that bridge as unconfigured (503). Cover both cases through the deployed entrypoint.
- Repository parked mode and all live GPU/paid execution gates remain unchanged.

## Local evidence

Using the current Gateway virtualenv against this candidate source:

```text
PYTHONPATH="$PWD/gateway:$PWD/src" /Users/taka/Documents/ChatGPT/Gpuラッパリポジトリ/gpu-control/gateway/.venv/bin/python -m pytest -q gateway/tests/test_http_auth.py
35 passed, 1 existing Starlette deprecation warning
```

The suite imports the actual `gateway/app.py` Vercel entrypoint with both a
missing workload registry and an injected CI policy file read failure. It
verifies that health/readiness remain available and the optional CI bridge
returns 503 under `VERCEL=1`, a production HTTPS origin, and a syntactically
valid PostgreSQL URL. No database connection is made. This complements the
direct `create_app()` test; it still does not reproduce the Vercel runtime
environment or verify Preview environment variables.

Additional focused verification after adding the CI policy boundary:

```text
PYTHONPATH="$PWD/gateway:$PWD/src" /Users/taka/Documents/ChatGPT/Gpuラッパリポジトリ/gpu-control/gateway/.venv/bin/python -m pytest -o addopts='' gateway/tests/test_http_auth.py gateway/tests/test_ci_bridge.py gateway/tests/test_ci_service_integration.py
116 passed, 1 skipped, 1 existing Starlette deprecation warning
```

`git diff --check` passed before the commits. Source changes are limited to
`gateway/gpu_gateway/app.py`, `gateway/gpu_gateway/ci_routes.py`, and
`gateway/tests/test_http_auth.py`; this acceptance record is the fourth path.
A read-only Security Review of the original source-fix branch diff found no
issues, before the later CI policy handling change; it is not a GitHub review
or deployment approval.

## CI and Preview

Checks for head `7797d5e` all passed: Python 3.11/3.12/3.13, trusted
reference container, Gateway offline tests, Gateway comment bridge tests,
Project bridge tests, Vercel deployment, and Vercel Preview Comments.

The READY Preview deployment sourced from head `7797d5e` is
`dpl_8EtpxT5tfq85gXzSD2XGaPSAdDSn`
(`gpu-control-ct73fkocw-unjunos-projects.vercel.app`). Its build events show
Python 3.12 selected from `gateway/.python-version`, dependency installation
from `pyproject.toml`, and successful build/deployment completion. Protected
GET requests on 2026-10-31 at 07:34 UTC to `/healthz` and `/readyz` both
returned HTTP 500
`FUNCTION_INVOCATION_FAILED` before an application response. Request IDs:

- `/healthz`: `hnd1:iad1::xwnsb-1793432067126-972867fa216a`
- `/readyz`: `hnd1:iad1::9slpq-1793432070172-fcc9b3d5bffb`

Vercel runtime-log queries scoped to the deployment and request ID returned no
records. Thus the missing-workload-file exception path is fixed and locally
covered through the deployment entrypoint, but it does not explain the
observed Vercel invocation failure. Its startup cause remains undiagnosed. Do
not count the Preview deployment's `READY` state as function-runtime or
ChatGPT acceptance.

The request-ID-scoped runtime-log query returned no records; trace lookup for
the health request ID returned HTTP 403. Thus build success is observed, but
function import/invocation diagnostics are not available to this connection.

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

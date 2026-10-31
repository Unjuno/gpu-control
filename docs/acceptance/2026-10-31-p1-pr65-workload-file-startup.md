# PR #65 missing workload file startup follow-up

## Scope

- PR: https://github.com/Unjuno/gpu-control/pull/65
- Original source-fix commit: `a9d610d3682f1985a65280da05619462a5825cd1`
- CI bridge fail-closed source commit: `f9e691f5af6267f9599f89f7bc160b8dbf583a5d`
- Hosted-environment regression commit: `faedd8c474a38d851ce9e27adee30fb118059446`
- Current PR head: `09eee9a11e0d1da748362b9e9f81a5b58f3a7e4a`
- Base: PR #62 head `317240d2224e05e23aa5bb190ce7a4f0fc101c01`
- Change: classify `OSError` while loading Gateway settings/workloads as invalid configuration and keep health/readiness routes available. If optional CI bridge policy loading fails, keep the Gateway up and expose that bridge as unconfigured (503). Cover both cases through the deployed entrypoint. Install the shared root `gpu-control` package in Vercel because Gateway imports it at runtime.
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

The install command was exercised in a temporary Python virtual environment:
install `gateway/requirements.txt`, install the root project as a wheel from
`..`, then import `gateway/app.py` and `gpu_control`. The final imports succeeded.
This matched the Preview fix; the actual Preview runtime provides the stronger
Python 3.12 evidence below. `git diff --check` and JSON parsing of
`gateway/vercel.json` passed. A read-only Security Review of the original
source-fix branch diff found no issues before the later CI policy and packaging
changes; it is not a GitHub review or deployment approval.

## CI and Preview

Checks for head `7797d5e` all passed: Python 3.11/3.12/3.13, trusted
reference container, Gateway offline tests, Gateway comment bridge tests,
Project bridge tests, Vercel deployment, and Vercel Preview Comments.

Before the packaging fix, Vercel runtime logs for READY deployment
`dpl_3vdbYmjTpkNkJbxRUBaifsxJ8y9f` showed the concrete startup failure:
`ModuleNotFoundError: No module named 'gpu_control'` while importing
`gpu_gateway.experiment_api`. The Gateway project selected its local
`gateway/` app and requirements, but did not install the root package. The
tracked `installCommand` now installs Gateway requirements and the parent
project as a built wheel.

The READY Preview for current head `09eee9a` is
`dpl_5vpf4hBh8Z42GeVVCfJjNKs5JaQV`
(`gpu-control-qlnbkxx3n-unjunos-projects.vercel.app`). Its protected runtime
probes on 2026-10-31 at 07:43 UTC returned:

- `/healthz`: HTTP 200, `configured:false`, `auth_configured:false`,
  `auth_mode:local_oauth`.
- `/readyz`: HTTP 503, `ready:false`.
- `/.well-known/oauth-protected-resource/mcp`: HTTP 503,
  `configuration_required`.

The previous import failure is fixed: the deployed app now returns its own
JSON responses and security headers. Readiness remains closed because Preview
does not have its durable database, OAuth configuration, or workload registry.
Runtime-log query for the new deployment returned no application errors. The
Preview's `READY` state alone is not used as function-runtime acceptance; the
above endpoint responses establish that the function imports and handles
requests.

The project environment-variable metadata endpoint remains denied (HTTP 403).
No names or values were retrieved. Health responses independently confirm that
the required runtime configuration is incomplete.

## Security review

Codex Security diff scan `87f1dbf6-9074-4f99-8380-c2bf4c711b95` reviewed
`d6949b678e0fefccb2638b143cd2d241be2ea70f..09eee9a11e0d1da748362b9e9f81a5b58f3a7e4a`
with complete coverage of the changed source diff (`gateway/vercel.json` and
`gateway/README.md`) and reported zero findings. The review does not certify
the full Gateway security posture or ChatGPT integration. Vercel environment
variable names/values and fork-protection metadata were not available to the
review, and no secrets were accessed.

## Remaining acceptance

- Configure a separate Preview PostgreSQL database and owner OAuth/workload
  settings, initialize the schema through the trusted operator procedure, and
  run the non-paid CPU worker path.
- Review and integrate the PR stack through the repository's protected path.
- Complete authenticated ChatGPT OAuth, tool discovery, registered CPU
  execution, and second-conversation result retrieval.

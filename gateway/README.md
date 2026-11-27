# Gateway source area

## Product boundary

ChatGPT Sites is the only intended ChatGPT-facing GPU Control control plane.
The FastAPI/PostgreSQL service in this directory is not a deployed production
dependency and must not be brought back as an alternate runtime without a new
product decision. Current owner-facing state, plans and provider lifecycle are
handled by the Sites Worker and D1/R2.

## What this directory still contains

This directory currently mixes three separately owned pieces:

1. **Legacy FastAPI/PostgreSQL Gateway:** `gpu_gateway/app.py`, OAuth, API,
   SQLAlchemy store, queue worker, recovery supervisor and `deploy/` service
   templates. `gateway/app.py` itself says it is retained for local
   compatibility tests. No current production deployment is established by
   these files. Do not deploy the Caddy/systemd/PostgreSQL templates as part of
   GPU Control Sites.
2. **GitHub Issue bridge helpers:** `gpu_gateway/ci_bridge.py` and related
   modules are imported by `gateway/scripts/comment_bridge.py` and the
   separate Project Checks workflow. This is not the ChatGPT GPU experiment
   control plane.
3. **Provider-runtime compatibility imports:** several `gpu_gateway` modules
   wrap the canonical implementation under
   `sites/gpu-control-sites/modal/provider_runtime/`. The current
   `gateway-ci.yml` exercises those provider-runtime modules and packaging
   contracts; it does not run or deploy the legacy FastAPI/PostgreSQL service.

The provider-runtime package is the authoritative implementation for the
Kaggle/Hugging Face adapter protocols. Keep the compatibility imports while
tests or a real caller require them. The Gateway service code and its
compatibility callers are tracked separately in
[`docs/architecture/refactoring-backlog.md`](../docs/architecture/refactoring-backlog.md).

## Local compatibility work

`docker compose -f gateway/docker-compose.yml up -d --build` starts a local
PostgreSQL/API/worker rehearsal only. It is not required for ChatGPT Sites,
does not publish an endpoint, and does not prove provider or ChatGPT
acceptance. Do not put live provider credentials in this local compose stack.

Before adding to or removing from this directory, identify the exact caller
and preserve the separate contracts above. Do not add a new public API,
database, deployment or provider route merely to reuse legacy code.

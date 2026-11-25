# Gateway Compose readiness rehearsal — 2026-11-17

## Scope

This rehearsal used the branch candidate at `4dda57c` plus the uncommitted
Compose fix. It used local OrbStack/Docker and the repository-owned
PostgreSQL/API/worker images. No provider credential, external job, GPU,
Kaggle, Hugging Face, Modal, RunPod, public endpoint, or paid resource was
used.

## Failure reproduced

The original Compose file started the API and worker immediately after an
empty PostgreSQL database became healthy. It had no migration service and no
recovery supervisor. The worker exited on missing `gateway_runs_v1` and
`gateway_control_v1`; `/healthz` returned 503 and `/readyz` reported database,
migration, worker, supervisor and authentication unavailable.

## Correction and observed result

The Compose graph now runs `python -m gpu_gateway.worker --init-db` as a
one-shot dependency before the API, worker and supervisor. It also starts a
separate `--supervise` process and gives both long-running processes the same
durable artifact mount without exposing it to the migration service.

After recreating the stack:

- migration completed with exit 0;
- schema version was 15;
- PostgreSQL, worker and supervisor were fresh and ready;
- built-in OAuth was bootstrapped with a generated local-only credential;
- `/readyz` returned HTTP 200 with database, migration, worker, supervisor,
  registry and authentication all `true`;
- OAuth authorization-server discovery returned the PKCE, DCR, refresh and
  revocation endpoints;
- an unauthenticated MCP `tools/list` request with the required Accept header
  returned HTTP 401 and the protected-resource Bearer challenge;
- health and discovery did not start GPU work.

The test containers and network were stopped afterward. The two named local
volumes were retained; they contain only this disposable local rehearsal state.

## Acceptance boundary

This proves the local deployment graph and fail-closed authentication boundary.
It does not prove public TLS/proxy behavior, hosted PostgreSQL roles, backup or
restore, ChatGPT OAuth completion, provider credentials, Kaggle/Hugging Face
availability, real GPU execution, artifact roundtrip, or external cleanup.

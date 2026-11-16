# Gateway directory

The deployed ChatGPT entry point remains the Sites MCP Worker with D1/R2 in
[`../sites/gpu-control-sites`](../sites/gpu-control-sites). This directory is
the maintained asynchronous Gateway/Remote MCP implementation used for
provider integrations that cannot execute inside a Sites Worker: Kaggle,
private Hugging Face Hub artifacts, private ZeroGPU evaluation, Modal, and
RunPod. It is no longer a legacy-only reference.

Do not recreate the removed Vercel or Neon deployments. A production Gateway
requires a reviewed long-running worker deployment, PostgreSQL with the
separate runtime roles under `deploy/`, TLS, and the OAuth boundary implemented
here. Until that endpoint is deployed and connected, the live Sites connector
continues to advertise only its own Modal/RunPod registry; offline Gateway
support for Kaggle/Hugging Face is not live ChatGPT acceptance.

Paid execution remains parked. The repository policy contains a narrow
free-provider acceptance lane, but configuration never authorizes a job: each
Kaggle submission and private ZeroGPU call requires current authentication,
included-quota evidence, an exact one-use owner approval, and cleanup evidence.

## Local deployment rehearsal

`docker compose -f gateway/docker-compose.yml up -d --build` is a disposable
local rehearsal only. It starts PostgreSQL, applies schema migrations to
completion, then starts the API, queue worker, and independent recovery
supervisor. The API is not ready until built-in owner authentication is
bootstrapped. The Compose password and HTTP origin are deliberately local-test
values and must never be reused for a hosted deployment.

For a hosted service, follow `deploy/` instead: use distinct database roles,
TLS, the restricted systemd units, root-owned environment files, an explicit
migration step, and separate API versus worker secrets. Provider credentials
belong only to the worker/supervisor secret boundary.

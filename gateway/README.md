# GPU Control Experiment Gateway

Additive gateway for ChatGPT-driven experiments. The first real execution path is
an operator-registered, digest-pinned local CPU smoke container. Existing `src/`,
RunPod adapters, policy files, `uv.lock`, and existing workflows are unchanged.
This is a separate optional deployment, not a replacement for RunPod CI.

## Implemented

- FastAPI Web API, authenticated Japanese dashboard, browser-only plan approval.
- Remote MCP at `/mcp`: a tools-only JSON Streamable HTTP profile, with legacy
  2025-03-26 / 2025-06-18 / 2025-11-25 and modern 2026-07-28 request handling.
  Modern `server/discover`, request metadata/header agreement and `resultType`
  are implemented. No SSE subscriptions, sampling, elicitation, prompts or resources.
- WebMCP registration via feature-detected `document.modelContext.registerTool`.
  Unsupported browsers keep the ordinary dashboard. Approval is NOT an MCP tool.
- Durable PostgreSQL queue, owned experiments, atomic admission, idempotency,
  expiring approval, worker leases, recovery-only supervision and
  ambiguous-submission reconciliation.
- Disabled-by-default `local_cpu` admission and a Docker worker backend with
  non-root, no-network, read-only, resource-bounded CPU containers. Results are
  persisted before cleanup; worker and PostgreSQL restart recovery is tested.
- Modal Sandbox backend using prebuilt images, fixed argv, bounded runtime,
  blocked network, bounded logs and structured last-line JSON metrics.
- Provider registry shared by API and worker; a tested third-provider extension.
- Optional bridge interface to the **existing approved RunPod execution pipeline**.
  There is no guessed workflow ID, automatic workflow dispatch or new raw RunPod path.
- Vercel configuration, dedicated-worker Dockerfile, optional Modal CPU worker.

## What this does not claim

Local test runs include synthetic providers, generated JWTs and real local Docker
and PostgreSQL fault-injection tests. They do not prove live ChatGPT/OAuth
interoperability, HTTPS deployment, or provider GPU execution. The local CPU
admission policy remains disabled by default. An official MCP client and actual
ChatGPT conversation acceptance are still required. This is not a complete
implementation of every optional MCP feature.

No billable compute is enabled by merely adding these files. No provider credential
is stored here. **Do not enable a provider until you have reviewed its registered
workload, quote and cleanup behavior.** The demo is explicitly a simulation, not GPU
access. The RunPod bridge is an extension seam, not an already-connected Web pathway.

## Topology

```text
ChatGPT / Remote MCP client -> HTTPS /mcp -----+
Browser / WebMCP -> /api/tools ---------+-> ExperimentService -> PostgreSQL
Browser human approval -> /api/approvals+
                                                 |
                                     independent local CPU worker
                                                 |
                                  isolated digest-pinned container
```

Long GPU work never occupies a Vercel request. API requests reserve a durable job;
worker invocations consume it. The provider owns the GPU process lifetime.

`docker-compose.yml` is a **demo-only** stack: it runs the simulated `demo`
provider and is not a local CPU execution deployment. `Dockerfile.worker` does
not include Docker CLI or daemon access. The `local_cpu` backend requires an
operator-managed worker host with Docker CLI access to a dedicated daemon. Access
to `/var/run/docker.sock` is effectively host-root authority; if a container is
used for that worker, grant socket access only on a dedicated trusted host and
only to the worker. Never mount it into the public API or share that daemon with
untrusted workloads. The job containers themselves are further restricted, but
those restrictions do not remove the worker's authority over its daemon.

## Local installation and tests (no GPU)

From repository root:

```sh
cd gateway
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-test.txt
python -m gpu_gateway.worker --init-db
python -m pytest -o addopts= -q
node --test tests/webmcp.test.js
python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Without OAuth configuration the static dashboard and health endpoint work, while
private actions are closed. There is intentionally no public anonymous execution
mode or insecure "disable auth" environment variable. Test fixtures supply a local
signing key and a simulation backend without changing deployed authentication.

SQLite is for local tests/development ONLY. Vercel and `GATEWAY_HOSTED=true` require
`postgresql+psycopg://...`; never use `/tmp` as production job state. Dependencies
are isolated from the root project. Direct framework versions are pinned; this is
not a complete transitive lockfile. Python 3.12 is the deployment baseline.

## Vercel setup

1. Import this repository and set **Root Directory = `gateway`** and framework
   **FastAPI**. `app.py` exports the ASGI app. `vercel.json` bounds HTTP requests
   to 30 seconds; GPU execution is not inside that duration.
2. Provision a PostgreSQL database (any compatible provider), preferably using its
   connection pooler/TLS endpoint. Use a distinct DB for Preview and Production.
3. Set gateway configuration from `.env.example` in Vercel project settings. Set
   `GATEWAY_PUBLIC_URL` to the exact stable HTTPS origin, without a trailing path.
4. Run `python -m gpu_gateway.worker --init-db` once against that database from a
   trusted operator environment. Schema creation is never triggered by an HTTP call.
5. Deploy the Web/API application. `/healthz` reports liveness; `/readyz` reports
   database/migration state, execution-worker and recovery-supervisor heartbeats,
   authentication and workload-registry readiness.
6. Run `gpu-control-worker.service` and `gpu-control-supervisor.service` against
   that database. The supervisor claims expired active leases and may take over a
   submitting intent after the worker heartbeat goes stale; it never takes newly
   queued work. A Vercel deployment alone runs neither process.
   The local Docker backend needs a dedicated worker host with Docker access;
   never mount the Docker socket into the API container.

Do not put `MODAL_TOKEN_ID`, `MODAL_TOKEN_SECRET`, RunPod API/S3 credentials or an
operator shell token into the Vercel frontend/API environment. They belong to the
worker's secret store. The API only needs DB access, trusted workload manifests,
OAuth verification/login settings and a stable encrypted-cookie key.

### OAuth and ChatGPT connection

Use an external authorization server that issues JWT access tokens with:

- issuer exactly `GATEWAY_OIDC_ISSUER`;
- audience/resource exactly `https://YOUR_HOST/mcp`;
- `sub` in the explicitly configured `GATEWAY_ALLOWED_SUBJECTS` allowlist;
- required `iss`, `sub`, `aud`, `exp`, `iat` and string `scope` claims;
- RS256 or ES256 signatures verified using the operator-fixed HTTPS JWKS URL;
- scopes `experiments:read`, `experiments:run`, `experiments:cancel` as appropriate.

The authorization server must publish its OAuth discovery metadata and support the
registration method required by your MCP client (pre-registration, DCR or CIMD).
Do not use the gateway's browser OAuth client ID as a substitute for the MCP
client's independent registration. The gateway publishes protected-resource
metadata and returns a `WWW-Authenticate` challenge; it is NOT an OAuth issuer.

For Web login, separately configure an OAuth/OIDC client with authorization-code
flow, PKCE S256 and the exact callback `https://YOUR_HOST/auth/callback`. The token
endpoint must support the configured public client or `client_secret_basic`.
The sample uses the standard `resource` parameter, not a vendor-specific audience
parameter. Configure your authorization server accordingly. ID-token nonce and
access-token user binding are validated.

Generate a stable cookie key in a trusted environment:

```sh
python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
```

Store it only as `GATEWAY_COOKIE_KEY`. Browser tokens are encrypted in HttpOnly,
Secure, SameSite=Lax cookies; mutations require matching Origin + CSRF token.
Tokens are checked again on each request. This initial browser client reauthenticates
when the token expires; it does not implement refresh-token storage/rotation.
Oversized JWTs (> cookie capacity) require a future server-side session adapter.
Neither login nor an MCP `approved=true` argument grants spending approval.

See [`../docs/CHATGPT_SETUP.md`](../docs/CHATGPT_SETUP.md) for the current ChatGPT
plan/permission, OAuth and live-acceptance gates. Connect to
`https://YOUR_HOST/mcp`; do not paste provider credentials into ChatGPT. Human Web
approval remains distinct from ChatGPT tool calls.

See [`../docs/OPERATIONS.md`](../docs/OPERATIONS.md) for the PostgreSQL backup and
isolated restore drill. A successful archive creation is not restore evidence.

## Worker placement

### Existing CPU host or container

```sh
cd gateway
python -m pip install -r requirements-worker.txt
python -m gpu_gateway.worker --poll-seconds 3
python -m gpu_gateway.worker --supervise --poll-seconds 3
# Alternatively run these as separately supervised services with the shared secret store.
```

The worker must stay available independently of browser sessions. Shutdown of the
Web application must not disable worker recovery. A single global admission record
limits in-flight jobs; an uncertain submission continues holding its slot.

For `local_cpu`, install a Docker CLI compatible with the dedicated worker host's
daemon and verify that the worker service identity can run `docker info` and
inspect the exact digest-pinned image before enabling the policy. The API and
worker must use the same operator-owned workload registry and policy file. Keep
the policy disabled until the host, workload digest, resource limits, cleanup
path and zero-provider-charge assumptions have been reviewed. The repository's
demo Compose stack does not perform these steps and does not validate this path.

`deploy/gpu-control-worker.service`, `deploy/gpu-control-supervisor.service` and
`deploy/worker.env.example` are starting templates for a dedicated Linux host,
not a tested installer. They assume the
checkout is at `/opt/gpu-control`, its venv at `/opt/gpu-control/venv`, and the
Docker daemon socket group is named `docker`; adjust and review those values for
the host. Install the env file as root-owned mode 0600, keep workload and policy
files operator-owned, then validate the service identities' DB and Docker access
before enabling any policy. Neither service exposes an API listener. Both have
the Docker daemon trust boundary; the supervisor needs access to cancel and clean
only exact tracked resources.

### Modal CPU worker (no new GPU provider required)

`modal_worker.py` supplies an optional CPU-only scheduled worker using the same DB.
Create a Modal secret named `gpu-control-worker` containing the worker gateway
settings, PostgreSQL URL and provider credentials as needed. Then, from `gateway/`:

```sh
# Explicit operator action: deploying this activates recurring CPU usage/charges.
modal deploy modal_worker.py
```

This template wakes once per minute and drains for approximately 45 seconds, with
3-second polls while active. Scheduling is NOT a latency guarantee. An always-on
CPU worker has lower admission latency; it also has a different idle-cost tradeoff.
The HTTP handler does not trigger this deployment. The template is not live-tested
in the local implementation environment.

## Register the first Modal workload

1. In your Modal workspace, prepare an App named `gpu-control` (or set
   `GATEWAY_MODAL_APP`). The backend uses `create_if_missing=False`.
2. Build a reusable Modal Image containing a compatible Python/PyTorch/CUDA build,
   your exact committed code, and any necessary model/data files. Record its `im-`
   image ID and exact source revision. No image build occurs during an MCP call.
3. Copy `examples/workloads.json` into trusted operator configuration. Replace the
   image/source placeholders and supply a current, conservative **all-in compute**
   hourly quote, source reference and Unix-seconds expiry. GPU-only advertised
   pricing is not sufficient: include CPU, RAM and applicable execution overhead.
4. Store that JSON as `GATEWAY_WORKLOADS_JSON` on the API. Do NOT allow a client to
   set image IDs, argv, import paths, endpoint URLs, quotas or credentials.
5. Review/configure limits, then enable `GATEWAY_ENABLE_MODAL=true` on both API and
   worker for an explicitly approved small experiment. This change is not done by CI.

`examples/gpu_smoke.py` is a small workload to bake into the image at
`/workload/gpu_smoke.py`; it tests that a CUDA operation and gradient calculation
work. It is not a hardware benchmark. The template admits 1–100 steps through a
closed parameter schema. Parameters travel as `GPU_CONTROL_CONFIG_JSON`.

Runtime network access is blocked. Pre-stage dependencies/models/data in the image;
future network or dataset capabilities require an explicit registered policy.
Sandbox output is currently bounded stdout/stderr plus last-line JSON metrics,
retained in PostgreSQL. Large checkpoints/object-store artifact export are not yet
implemented. Workload output is untrusted data, not instructions or proof of model
quality. Result evidence is the provider exit code and retrieved logs; it is not
the RunPod core's authenticated completion-v3 protocol.

The cost field is a **requested admission ceiling**, not a promise that the cloud
provider enforces an exact financial cap. Startup, retries inside provider control,
CPU worker, storage, OAuth and database costs can add overhead. No automatic GPU
creation retry is configured here. Quote conservatively and verify real bills.
Free credits do not turn resource usage into a verified zero-cost execution.

## Existing RunPod: deliberately preserved

Continue using your existing RunPod/CI path. This change neither dispatches it nor
changes its configuration, permissions, credentials, permits or completion checks.

To expose that same existing path through the new API later, implement an
operator-owned `module:factory` returning the `Backend` contract and set
`GATEWAY_RUNPOD_FACTORY` on the worker, with the same registered provider name and
`GATEWAY_ENABLE_RUNPOD_BRIDGE` setting on admission/worker. The factory must keep the
old plan/permit/pricing gates; a gateway browser approval does NOT manufacture a
legacy `LiveExecutionPermit`. Do not wire it straight to unguarded RunPod creation.

The gateway registry can advertise that adapter when configured, but this PR does
not assume which existing workflow/resource IDs the operator uses. CI connectivity
is not discovered from secret values and no live RunPod call is used as a test.

## Add another GPU provider

Implement four methods in a worker backend: `start(run)`, `inspect(handle)`,
`cancel(handle)`, `reconcile(run)`. Register its factory and admission switch once
in `gpu_gateway/registry.py`. API/MCP/UI and persisted experiment contracts remain
unchanged; see the third-provider test in `tests/test_extensions.py`.

Required contract:

- `start` uses the exact trusted stored plan, never an unvalidated raw tool input;
- `handle` is JSON-serializable and durable across worker restarts;
- `reconcile` locates an already-submitted job and never creates another one;
- a terminal `inspect` result means billable compute is released, not merely that
  the workload wrote "success"; preserve separate existing provider cleanup gates;
- `cancel` is retry-safe and works after new submissions are disabled;
- ambiguous results raise/return unknown, not invented success;
- provider secrets and raw exception messages never reach browser/MCP results.

This is a small GPU registry, not an arbitrary tool marketplace or all-service SDK.

## Failure behavior and acceptance

- Repeated request with the same owner/key returns the same plan. Changed inputs
  with that key return a conflict. Concurrent submission reserves one slot.
- Approval is short-lived and bound to the plan fingerprint. A caller cannot
  submit a different plan or approve using a bearer-only MCP call.
- A crash after create but before handle persistence is reconciled, never blindly
  retried. If the Sandbox has already exited and cannot be resolved by name, the
  state remains `submit_unknown` for operator investigation. This is intentional.
- Result/termination failures remain visible and keep the slot reserved. Do not
  simply delete DB state to make room: first verify the exact provider resource is
  stopped. Starting a different GPU is not recovery of the original experiment.
- Worker-side timeout attempts complement Modal's provider timeout. Turning off
  new-submission switches does not remove observation/cancellation capabilities.
- Browser closure does not cancel the GPU. Use explicit cancellation when needed.

Before live use: verify OAuth login + client connection, exact image/quote, first
small GPU result, forced worker restart, cancellation and actual provider billing.
Before Production: use a separate preview database, owner allowlist, TLS/pooler,
protected deployment secrets and review of exposed routes. Health is not an end-
to-end readiness proof. Vercel deployment protection must permit authenticated
MCP clients to reach `/mcp`; an unrelated interactive Vercel login is not MCP OAuth.

## Upstream references checked for this implementation

- https://vercel.com/docs/frameworks/backend/fastapi
- https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http
- https://modelcontextprotocol.io/specification/2026-07-28/server/discover
- https://webmachinelearning.github.io/webmcp/
- https://modal.com/docs/sdk/py/latest/Sandbox
- https://modal.com/docs/sdk/py/latest/Period
- https://developers.openai.com/plugins/build/auth

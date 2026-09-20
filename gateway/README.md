# GPU Control Gateway

Additive gateway for **Modal + the existing RunPod pipeline**. Existing `src/`,
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
  expiring approval, worker leases and ambiguous-submission reconciliation.
- Modal Sandbox backend using prebuilt images, fixed argv, bounded runtime,
  blocked network, bounded logs and structured last-line JSON metrics.
- Provider registry shared by API and worker; a tested third-provider extension.
- Optional bridge interface to the **existing approved RunPod execution pipeline**.
  There is no guessed workflow ID, automatic workflow dispatch or new raw RunPod path.
- Vercel configuration, dedicated-worker Dockerfile, optional Modal CPU worker.

## What this does not claim

Local tests use synthetic providers, fake Modal calls and generated JWTs. They do
not prove live Modal, real OAuth-provider/ChatGPT/browser-agent interoperability,
Vercel deployment or existing RunPod end-to-end success. An official MCP SDK client
interoperability test remains a deployment acceptance item; this is not a complete
implementation of every optional MCP feature. Existing upstream tests were not
rerun in the isolated implementation environment; the PR retains them unchanged.

No billable compute is enabled by merely adding these files. No provider credential
is stored here. **Do not enable a provider until you have reviewed its registered
workload, quote and cleanup behavior.** The demo is explicitly a simulation, not GPU
access. The RunPod bridge is an extension seam, not an already-connected Web pathway.

## Topology

```text
ChatGPT / Remote MCP client -> /mcp -----+
Browser / WebMCP -> /api/tools ---------+-> ExperimentService -> PostgreSQL
Browser human approval -> /api/approvals+
                                                 |
                                     independent CPU worker
                                                 |
                                   Modal / existing RunPod bridge
```

Long GPU work never occupies a Vercel request. API requests reserve a durable job;
worker invocations consume it. The provider owns the GPU process lifetime.

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
5. Deploy the Web/API application. Check `/healthz`, OAuth metadata, login, prepare,
   explicit approval and simulation before registering a real GPU workload.
6. Run a CPU worker sharing that database. A Vercel deployment alone does NOT run it.

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

Connect the remote MCP client to `https://YOUR_HOST/mcp`. Use the actual client's
OAuth flow; do not paste Modal/RunPod credentials into ChatGPT. In the Web UI,
approve the exact prepared plan, then submit from the UI or MCP. Native WebMCP
requires a browser/agent exposing the current API; there is no misleading polyfill.

## Worker placement

### Existing CPU host or container

```sh
cd gateway
python -m pip install -r requirements-worker.txt
python -m gpu_gateway.worker --poll-seconds 3
# Alternatively build Dockerfile.worker and provide environment through a secret store.
```

The worker must stay available independently of browser sessions. Shutdown of the
Web application must not disable worker recovery. A single global admission record
limits in-flight jobs; an uncertain submission continues holding its slot.

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

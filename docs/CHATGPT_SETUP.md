# ChatGPT Sites setup and operations

> **Historical release note:** the hosted-state section below is a snapshot
> from the Sites v72 release, not a current live check. For the current source
> candidate and unverified release gates, see
> [the release matrix](RELEASE_MATRIX.md) and
> [architecture map](architecture/repository-map.md). Do not infer that the
> latest Git branch is deployed.

## Supported production architecture

The only ChatGPT-facing control plane is the authenticated MCP endpoint at:

`https://gpu-control-sites.unjuno.chatgpt.site/mcp`

The compute providers are exactly:

1. Modal
2. RunPod
3. Kaggle
4. Hugging Face

Railway, Vercel, Neon, an external PostgreSQL database, and a separately hosted
Gateway are not production dependencies. Historical documents may mention
those systems, but they must not be recreated for this path.

```text
ChatGPT authenticated user
  -> Sites MCP Worker
     -> D1: plans, owner binding, one-use authorization, budgets, run state
     -> R2: bounded immutable result artifacts
     -> Modal fixed CPU control API
     -> RunPod REST v2 through the authenticated provider adapter
     -> authenticated Modal provider adapter
        -> Kaggle fixed private training workload
        -> Hugging Face private artifact and ZeroGPU evaluation
```

The Modal provider adapter is secret-bearing infrastructure, not a fifth
provider. Chat input cannot select a command, image, repository, provider URL,
credential, owner ID, or arbitrary environment variable.

## Current verified state

As of the Sites v72 publication:

- the Site and generated MCP plugin are published;
- D1 migrations through `0020_modal_gpu_budget.sql` are applied;
- `experiment_capabilities` reports all four providers;
- Modal CPU is configured and admitted;
- RunPod is configured and its fixed real-GPU canary has completed with
  authenticated result and cleanup evidence;
- the fixed Modal T4 canary has completed with authenticated result and cleanup
  evidence; its admission is closed between explicitly bounded runs;
- Kaggle and Hugging Face are configured behind the authenticated Modal adapter;
  the fixed Kaggle Tesla T4 training run and its dependent private artifact plus
  Hugging Face ZeroGPU evaluation round trip have live acceptance evidence;
- Kaggle and Hugging Face each have an independent D1 policy of exactly `$0`
  per run and `$0` per month, with paid fallback prohibited;
- the former macOS Keychain Runner is retired and must not be restored.

This is deployment and control-plane evidence. It is not a substitute for a
fresh bounded canary, terminal result validation and cleanup evidence for each
enabled provider.

## ChatGPT connection

Publishing a Site with the `mcp` capability creates its ChatGPT plugin. No
local MCP process, `codex mcp add`, Vercel app, or separate OAuth server is
needed.

1. In ChatGPT, open Plugins and select the personal plugin created by
   **GPU Control — ChatGPT実験管理**.
2. Install or connect it if it is not already connected.
3. Start a new chat after installation if the tools do not appear immediately.
4. Call `experiment_capabilities` before every new experiment session.

The public Site and execution authority are separate boundaries. Anonymous
visitors may view the Site, but every stateful MCP tool requires the Sites
authenticated user ID and the server-side `GPU_CONTROL_ALLOWED_USER_IDS`
allowlist. D1 reads and writes are owner-scoped.

## First verification prompt

Use this prompt after all intended provider credentials have been connected:

```text
GPU Controlのexperiment_capabilitiesを呼び出して、Modal、RunPod、Kaggle、
Hugging Faceの4プロバイダーについて、configured、enabled、blocker、予算、
利用可能な登録済みworkloadを表にしてください。

Google Colabを希望する場合はcolab_capabilitiesも呼び出してください。
現在は接続とeligible GPU確認までで、GPU Controlの実行・結果・cleanupには
まだ接続されていません。

まだ実験は開始しないでください。秘密値を表示せず、Railway、Vercel、
Neon、外部PostgreSQLが実行経路に含まれていないことも確認してください。
```

For a real run, name one registered workload and tell ChatGPT to execute it.
When that instruction already authorizes execution, it covers one complete
`prepare -> submit -> status/log polling -> result -> cleanup` lifecycle. The
assistant must not split that lifecycle into repeated conversational questions.
The server still binds the write to one exact owner-bound, short-lived plan and
enforces provider budgets, replay prevention and cleanup before replacement.

Repository-aware ChatGPT/Codex agents should load the shared project skill at
`.cursor/skills/gpu-control-operator/SKILL.md`. It provides the canonical
provider-selection, idempotent recovery, monitoring, artifact-verification and
completion-report workflow. Its examples never grant authority and its plan
values must always come from the current MCP response.

## Provider configuration inventory

Secret values belong only in their named hosted secret stores. Never put them
in Git, chat messages, screenshots, local committed `.env` files, D1, R2, logs,
plan JSON or result JSON.

### Modal fixed CPU route

Sites runtime configuration:

- `MODAL_API_URL`
- `MODAL_PROXY_TOKEN_ID` (secret)
- `MODAL_PROXY_TOKEN_SECRET` (secret)
- `MODAL_WORKLOAD_IMAGE_FINGERPRINT`
- `CPU_WORKLOAD_ADMISSION_ENABLED`

The D1 policy is independent of Modal account billing. Both must remain within
the operator-approved ceiling. Credits are not a guarantee of zero charges.

The fixed Modal GPU route additionally uses
`MODAL_GPU_WORKLOAD_ADMISSION_ENABLED` and a short-lived secret
`MODAL_GPU_ACCOUNT_EVIDENCE_JSON`. The evidence records the actual outer Modal
Workspace usage limit, current credit/charge totals and pinned T4 price. D1
independently enforces the stricter project ceiling (`$1.00` monthly and
`$0.01` per run). Do not substitute the outer Workspace limit for the internal
project ledger.

### Kaggle and Hugging Face adapter

Modal secret `gpu-control-worker` contains only provider credentials needed by
the fixed adapter, such as:

- `KAGGLE_API_TOKEN`
- `HF_ARTIFACT_WRITE_TOKEN`
- `HF_SPACE_READ_TOKEN`
- `RUNPOD_API_KEY` (one endpoint only; `api.runpod.ai` Read/Write, no REST or
  GraphQL permissions)

Modal secret `gpu-control-provider-adapter-auth` contains:

- `PROVIDER_ADAPTER_KEY_ID`
- `PROVIDER_ADAPTER_HMAC_KEY_B64`

Sites contains the matching adapter transport settings:

- `PROVIDER_ADAPTER_URL`
- `PROVIDER_ADAPTER_KEY_ID`
- `PROVIDER_ADAPTER_HMAC_KEY_B64` (secret)
- `PROVIDER_ADAPTER_PROXY_TOKEN_ID` (secret)
- `PROVIDER_ADAPTER_PROXY_TOKEN_SECRET` (secret)

The adapter requires Modal proxy authentication and a second HMAC envelope.
Every envelope binds the authenticated owner, tool and exact arguments to a
short expiry and nonce. D1 remains the authoritative plan and run store.
The Worker also pins the adapter to
`unjuno--gpu-control-provider-adapter-provider-adapter-api.us-east.modal.run`.
Another otherwise valid `*.modal.run` origin is rejected before proxy
credentials are attached.

### RunPod

Sites configuration is separate from every other provider. The RunPod API key
is deliberately not a Sites secret; it is injected only into the private Modal
provider adapter from `gpu-control-worker`:

- `RUNPOD_WORKLOAD_IMAGE`
- `RUNPOD_WORKLOAD_SOURCE_SHA`
- `RUNPOD_SERVERLESS_ENDPOINT_ID`
- `RUNPOD_SERVERLESS_GPU_POOL_ID`
- `RUNPOD_SERVERLESS_HOURLY_PRICE_USD` (fail-closed maximum hourly price,
  never treated as current provider price evidence; use a fixed six-decimal
  USD value such as `0.580000`)
- `RUNPOD_GPU_ID` (displayed exact GPU identity)
- `RUNPOD_ACCOUNT_SCOPE_ID` (secret or protected configuration)
- `RUNPOD_ACCOUNT_SCOPE_HMAC_KEY_B64` (secret)
- `RUNPOD_STATE_KEY_B64` (secret)
- `RUNPOD_WORKLOAD_ADMISSION_ENABLED`
- `RUNPOD_LIVE_COMPLETION_TRANSPORT_VERIFIED`

The RunPod key is restricted to `api.runpod.ai` Read/Write for the one
registered endpoint only. It has no REST, GraphQL, Pod, billing, account,
secret, authentication, catalog, volume, or endpoint-management access.

Creating an API key is not sufficient to enable RunPod. The Worker requires the
registered immutable Serverless image, exact queue endpoint (`min=0`, `max=1`,
five-second idle timeout, one GPU, no ports or volumes, 30-second maximum timeout),
a fresh REST v2 Catalog `price.serverless` at or below the configured maximum,
one-use plan authorization, D1 account lease, paid admission and authenticated
completion transport. Both prepare and submit fail closed unless admission and
the live completion transport gate are enabled. Provider configuration alone
must fail closed.

## Rotation procedure

Rotate one trust boundary at a time. Do not rotate a provider credential and
the Sites-to-adapter HMAC in the same unobserved change.

1. Close the affected provider's admission flag.
2. Confirm there is no active or cleanup-pending run for that provider.
3. Create the replacement credential at the provider.
4. Update only the matching hosted secret.
5. Deploy or restart only the affected adapter when required.
6. Run `experiment_capabilities`; perform a non-executing authenticated health
   check when the provider supports one.
7. Revoke the old credential.
8. Re-read capabilities and provider inventory.
9. Reopen admission only after a separately approved bounded canary.

For HMAC rotation, update the Modal adapter secret and Sites secret as one
controlled maintenance operation while adapter-backed admission is closed.
There is no intentional dual-key grace period.

## Disable or remove a provider

Disabling a provider must be reversible and must preserve historical D1/R2
records.

1. Set its admission flag to false or remove the minimum credential required by
   its configuration predicate.
2. Confirm `experiment_capabilities` reports `enabled=false` and a concrete
   blocker.
3. Reconcile every active or uncertain provider resource and record cleanup.
4. Revoke the provider credential after cleanup.
5. Remove the corresponding hosted secret values.
6. Do not delete D1 plans, runs, authorization, budget or cleanup evidence.

Removing Kaggle or Hugging Face does not require removing the other provider.
Their provider credentials and D1 free policies are separate. Removing the
shared Modal adapter transport disables both adapter-backed routes, so use that
only for an emergency stop or complete adapter retirement.

## Add another ChatGPT account

Do not make execution open to every Site visitor. To authorize another account:

1. grant that account access through the supported Sites access policy;
2. obtain its Site-scoped authenticated user ID through the supported signed-in
   flow, without accepting a user-supplied claimed ID;
3. append that exact ID to `GPU_CONTROL_ALLOWED_USER_IDS`;
4. verify the new account sees no existing owner's runs;
5. verify a third, unlisted account receives `SITE_USER_NOT_AUTHORIZED`;
6. perform a new-account prepare-only check before any real execution.

User IDs are Site-scoped and must not be copied from another Site.

## Emergency stop

When cost, credential exposure, ambiguous provider state or cleanup failure is
suspected:

1. close the affected admission flag;
2. do not retry an ambiguous create request;
3. inventory provider resources directly in the provider account;
4. terminate only the exact resource bound to the persisted run;
5. record cleanup or uncertainty in D1;
6. revoke the affected credential;
7. keep admission closed until recovery and a fresh bounded canary pass.

Never bypass a blocked route with SSH, Jupyter, public ports, arbitrary shell
execution, unrestricted networking, a different provider, or a higher budget.

## Acceptance required before calling the system complete

For each enabled provider, retain evidence of:

- authenticated ChatGPT tool discovery;
- owner-bound prepare and exact one-use confirmation;
- provider-side resource identity;
- bounded execution under the provider-specific cost policy;
- status and terminal result validation;
- artifact digest verification when artifacts exist;
- cancellation behavior or an explicit unsupported-cancellation state;
- exact cleanup and absence of leaked resources;
- successful retry/recovery behavior for an intentionally lost response;
- secret non-disclosure in model-visible output and logs.

Passing tests, a health endpoint, a successful deployment, or a configured API
key proves only that layer. It does not prove an end-to-end provider route.

## One instruction means one complete run

When the owner says to execute a registered workload, that one instruction
authorizes the bounded lifecycle for the prepared plan that matches it:
`prepare -> submit -> monitor -> result -> cleanup`. Do not ask the owner to
repeat "run this plan once" after `prepare`. The ChatGPT client may still show
its native write-action approval UI; that is distinct from an additional
conversational confirmation.

Provider credentials are long-lived, least-privilege runtime configuration and
are reused across runs. Do not create or rotate them per experiment. Credential
rotation, deletion, privilege expansion, or a budget increase is a separate
administrative action and still requires immediate notice before it is done.

## Owner training with MAP-44M

Attach **GPU Control — ChatGPT実験管理** to a new ChatGPT conversation.
In Chat, use the plugin page's **Try in chat** button. In Work, use the
composer's **Plugins** menu. Start with a read-only `training_list` call. An
owner-scoped response confirms the ChatGPT Sites identity. Do not ask for a
Modal login for ordinary runs: provider credentials are held by the server-side
adapter and are separate from the Sites owner session. If the tool is
unavailable or reports an authentication error, diagnose that exact MCP
connection before changing provider credentials.

Register with `training_register` using only
`{"repository":"unjuno/model-as-a-paper"}`. The server supplies its
configured, reviewed commit. For this repository, the server defaults to
dataset `papers`, run name `map44m`, and a maximum of 100,000 steps; optional
`dataset`, `run_name`, and `steps` values can be supplied at registration.
The server fixes the reviewed source/image, Modal L4 profile, and private
Volumes. Registration does not start training. Preview or prepare using only
the returned `registration_id`; the server supplies the fixed 120-second
runtime, $0.25 per-run ceiling, and prepare idempotency key. If `training_list`
shows multiple execution profiles, include the selected `execution_spec_id`.
The explicit commit, runtime, budget, and idempotency-key inputs remain
available for compatibility. The plan exposes the resolved GPU, dataset, run
name, step ceiling, runtime, and estimated cost. When the user requests
execution, submit that exact plan.
`training_submit` is the one billable write action. Before dispatch, open the
`authorization_url` returned by `training_prepare` and confirm the exact source, image, dataset, run name, step ceiling, GPU,
runtime, and cost in the authenticated GPU Control Site. This is
not another MCP or Modal login. After returning to ChatGPT, check
`training_status` for `authorization_state=authorized` and continue with the
exact `training_submit` plan; do not ask the user to repeat their run request.
The Worker records short-lived evidence against the authenticated owner, exact
plan fingerprint, current control-plane commit, source/image, Modal function,
runtime, and budget, then consumes it with the dispatch reservation. Continue
monitoring the same run after submission; do not resubmit after an ambiguous
response.

After submission, preserve the run ID. Use it to check status or request
cancellation. If the submit response is interrupted, check that run before
starting another. After success, retrieve and verify the checkpoint with an
authenticated client that can assemble the ranges and compare SHA-256.

## Connecting an owner-selected GitHub repository

The authenticated Sites owner can connect a GitHub App once and select only
the repositories GPU Control may read. The App must be configured with
Contents: read, Metadata: read, selected-repository installation, Setup URL
https://gpu-control-sites.unjuno.chatgpt.site/github/setup, and OAuth Callback
URL https://gpu-control-sites.unjuno.chatgpt.site/github/oauth/callback.
The Sites Worker needs GITHUB_APP_ID, GITHUB_APP_SLUG,
GITHUB_APP_CLIENT_ID, GITHUB_APP_CLIENT_SECRET,
GITHUB_APP_OAUTH_CALLBACK_URL, and the private key in server-side secret
storage. The install callback alone does not prove who initiated the install:
the owner completes a GitHub user authorization step, and the Worker verifies
that token can read the exact installation before binding it. The temporary
user token is discarded and is never saved. Applying migration 0033 clears
pre-existing GitHub installation bindings because their owner identity was not
verified; reconnect once after that migration. Never put the private key or
installation token in ChatGPT, a training container, repository files, or logs.

In ChatGPT, call `github_connection_status`. If it is disconnected, call
github_connection_start and open its one-time link; install the App with the
specific repository selected, then authorize GPU Control on GitHub to prove
your account can access that installation. Then call github_repositories to
verify the selection and training_register with the repository name. The server pins
the current default-branch commit and creates the registration ID; the user
does not need to find a commit or create an ID. For a run request, continue
directly to `training_prepare`, which validates `.gpu-control/experiment.json`,
its lockfile, and the current runtime, GPU, quote, and budget in one call. Use
`training_inspect` only for a detailed diagnostic or when the user asks to
inspect without running. A per-request token is limited to that single
repository and is not returned to the client.

Example manifest:

```json
{
  "schema_version": 1,
  "task": "train",
  "entrypoint": "src/train.py",
  "python_version": "3.12",
  "dependencies_lock": "requirements.lock",
  "gpu_profiles": ["T4"],
  "outputs": ["checkpoints", "metrics.json"]
}
```

For custom training, write a JSON object of scalar metrics to
`$GPU_CONTROL_CHECKPOINT_DIR/metrics.json`. Declare `metrics.json` in
`outputs`; after completion the bounded values and SHA-256 are returned with
`training_status`. Keep the checkpoint at
`$GPU_CONTROL_CHECKPOINT_DIR/checkpoint.pt`; retrieve it through
`training_checkpoint` in verified chunks. Additional files are exposed only
when listed as an exact relative path under
`artifacts/` (for example, `artifacts/eval/predictions.json`). The completed
status returns each artifact's ID, path, size, and SHA-256; call
`training_artifact` with that ID to retrieve bounded chunks and verify the
assembled file hash. Each declared artifact is limited to 256 MiB and all
declared artifacts together to 512 MiB.

The separate trusted CPU source stager is the only component that receives a
short-lived, selected-repository read token. Its outbound TLS destinations are
limited to `github.com`, `pypi.org`, and `files.pythonhosted.org` for commit and
hash-pinned wheel retrieval. It does not execute repository code. The Modal
domain allowlist is a beta control: DNS itself is unrestricted, and SNI-based
domain filtering does not prevent domain fronting. The training GPU Sandbox
has all network egress blocked and never receives the GitHub token.

At this stage, `training_inspect` validates the manifest and returns structured
compatibility checks. The current branch contains a gated Modal prototype for
fixed CPU source staging followed by a network-blocked GPU Sandbox. It is not
released: admission remains disabled until the runtime image, separate staging
and GPU quotes, budget reservations, checkpoint and metrics verification, cleanup,
security review, and exact-head release gates pass. RunPod custom-repository
execution is not implemented by the fixed RunPod canary. For owner-selected
training, the Worker keeps an owner-scoped dispatch lease until a terminal
provider status explicitly confirms cleanup. A lost submit response,
`uncertain` result, or pending cleanup keeps that lease; the agent must recover
the same run with `training_status` before another run can start.

When the route is released, a user who explicitly asks to run may use ordinary
ChatGPT language such as “Run one small GPU experiment from my registered
`owner/repository` source and show me the result.” The agent prepares the
owner-bound registration with server defaults, then submits the exact returned
plan. ChatGPT's native write confirmation binds the selected commit, GPU,
runtime, and cost ceiling once; there is no per-run Modal login or separate
browser confirmation. The agent then polls the same run and verifies cleanup
and artifacts. Until the route reports ready and admission is enabled, do not
claim that prompt can start compute.

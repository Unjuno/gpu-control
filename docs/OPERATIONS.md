# Current operations: ChatGPT Sites + D1

## Latest operational state — 2026-11-12 13:46 UTC

Production Sites is Version 28, source commit
`237c0bed24277cf7c808f8c0e9946c71d517288c`, environment revision 32, with D1/R2.
The live ChatGPT capability read passed all eight Modal health checks; admission
is disabled. Sites Version 28 accepts the `$0.01` Sandbox-only ceiling and uses
a 15-second bounded Modal request timeout. The one authorized CPU diagnostic
run `e9330c5bb5454f42bb3dabe058091dc0` failed with
`MODAL_WORKLOAD_EXIT_2`; Modal Sandbox
`sb-01M77ZZRFC1090CXA2W3MHDH7V` exited after 247 ms. Its dashboard had no
Sandbox logs, Sites confirmed cleanup, and no inference result or artifact was
produced. The expected bounded preflight line marker was absent, so the exact
failed check remains unknown. Modal Usage remained `$0.05` credits used and
`$0` charges after the run; those totals include prior control/deploy activity
and cannot be attributed to this Sandbox. The `$1` Workspace limit was checked
before execution. Admission was restored to false at environment revision 32;
capabilities report the provider ready but unavailable. Do not retry without a
new exact-run authorization and a useful diagnostic change. RunPod has no Sites
MCP execution route; GPU and paid execution remain parked.

The following paragraph is an earlier operational snapshot, superseded by the
latest state above.

The supported ChatGPT control plane is the public Sites MCP Worker at
`https://gpu-control-sites.unjuno.chatgpt.site`. Its product records are stored
in the Sites-provisioned D1 database and result objects in R2. The live Site is
Version 24 from source commit `c919b0047b203fb0c22b6dd7755934834e899f8f`, with
environment revision 22. Current ChatGPT capabilities report
`provider_ready=true`, `available=false`, and `admission_enabled=false` for
`modal_cpu`. The authenticated Modal endpoint is healthy, but the current Modal
deployment has no accepted inference result. The successful run previously
attributed to Modal was actually executed by the retired local Runner under
Sites Version 16. Two Modal runs failed before the dashboard's v4 deployment;
the UI did not bind v4 to a source commit, and no successful inference has run
after v4. Site Version 24 now records bounded exit-code failure codes without
provider stderr, but this diagnostic has not been observed live. Keep compute
admission closed. Historical CPU results below apply only to their recorded
provider and runtime versions.

## Latest Modal attempt and recovery status — 2026-11-12

Run `599473dcc1ed4034a42d849bcb42e261` was prepared and submitted through
ChatGPT with a 30-second runtime and `$0.00` Site cost ceiling. It failed as
`MODAL_WORKLOAD_FAILED`; D1/Sites reported `cleanup_state=confirmed`. Modal
The earlier Modal app failure logged Sandbox exit `code 2` after 165 ms with
no stdout/stderr logs; the root-dependent launcher was removed in commit
`1c8c30d2270ca2bc7f35f3a988d66b4012be9a27`. Historical run
`eacc26ff2ad54cf69a1ee7665325b197` succeeded in 142 ms and ChatGPT retrieved
its complete 962-byte R2 result, but it used the local Runner, not Modal. Two
Modal runs, `96d7efef9542463d9fc51f47ffbfd5d7` and
`599473dcc1ed4034a42d849bcb42e261`, failed with cleanup confirmed. The Site
discarded their Modal exit codes, and the later Sandbox log filter had no
entries, so their cause remains unknown. Both failures predate the dashboard's
v4 deployment; the dashboard did not expose v4's source commit, and no v4
inference is recorded. Current admission is disabled. The temporary one-hour
deployment API token was revoked and the Modal token list returned zero
entries. Modal showed `$0.01` usage this cycle. Details:
[`Modal and CPU inference chronology`](acceptance/2026-11-12-modal-and-cpu-inference-chronology.md).

Keep all failed runs as failed evidence; do not retry them under the same
idempotency keys. A new bounded smoke needs a new authorization and idempotency
key after the cause is understood and admission is deliberately opened for that
single test; close admission immediately afterward.

The target is a publicly discoverable ChatGPT Site + D1/R2 control plane, Modal
as the first bounded compute integration, and Runpod as the later separately
gated GPU provider. Public discovery does not mean anonymous execution: every
data-bearing or execution tool must require the authenticated Sites user ID and
enforce owner-scoped D1 queries. Vercel, Neon/PostgreSQL, and the macOS Keychain
Runner are retired.
See [`SITES_MODAL_RUNPOD_DELIVERY.md`](SITES_MODAL_RUNPOD_DELIVERY.md) for the
current staged acceptance plan.

## Historical acceptance

The following observations were made before the local Runner was retired. They
are retained as historical evidence and are not current operating instructions.

- ChatGPT can discover and call the Site's experiment tools in the owner's
  connected session.
- One fixed-image CPU checksum smoke completed through ChatGPT → Sites → D1 →
  Runner → D1 → ChatGPT; result retrieval and container cleanup were confirmed.
- One TinyStories 15M inference completed through the same ChatGPT → Sites →
  D1 → Runner → D1 → ChatGPT path. A 24-token result was retrieved, identity
  and checksum validation passed, and container cleanup was confirmed.
- Two more inferences completed after enabling the Site's R2 binding and
  append-only D1 artifact metadata migration. ChatGPT read complete 988-byte and
  991-byte result artifacts; the Worker verified owner/run identity and SHA-256
  before returning each chunk. They used 12 tokens each, took 249 ms and 268 ms,
  and had `$0.00` ceilings.
- Three additional provenance-valid inferences have completed, including one
  post-deploy run. ChatGPT retrieved three complete R2 artifacts and verified
  their recorded SHA-256 values; every accepted run confirmed container cleanup
  and a `$0.00` ceiling. The complete run inventory is in `docs/RELEASE_MATRIX.md`.
- A seventh provenance-valid run (`5447466fe7f9413980d2b47a2b079289`) was
  retrieved through ChatGPT. It generated four tokens in 150 ms, passed identity
  and sandbox checks, and confirmed cleanup at `$0.00`.
- An eighth live recheck (`1fdfe901fda14798a42e33e492edd538`) was prepared,
  submitted, polled, and retrieved through ChatGPT. It generated four tokens in
  155 ms, passed identity/sandbox checks, reported `gpu_used=false`, and
  confirmed cleanup at `$0.00`.
- A fresh run (`a1cdf7e9516b4a00802b6b606f228b08`) completed through the
  currently deployed Sites Version 15. It generated 8 tokens in 227 ms,
  passed registered source/model/parameter and container-isolation checks,
  reported `gpu_used=false`, and confirmed cleanup at `$0.00`. ChatGPT retrieved
  the complete 979-byte R2 result artifact and the Site verified its SHA-256.
- A controlled LaunchAgent stop/start was completed with CPU admission closed
  and no active runs. The old Runner process exited; the LaunchAgent loaded a
  new process and Site heartbeat readiness returned before admission reopened.
  A post-restart ChatGPT run (`6c817aa27a8842eda0bc07c7e5396776`) generated
  eight tokens in 330 ms and passed registered source/model/parameter and
  container-isolation checks. Cleanup was confirmed at `$0.00`; the full
  1,005-byte R2 artifact was retrieved and its SHA-256 matched D1 metadata.
- A separate forced process-loss probe killed the Runner only after the exact
  registered workload container was running. launchd restarted the service;
  after the 180-second D1 lease expired, the recovery path marked run
  `0c3dd2ecf3d34355b6faa63a842d83c7` as `failed` with
  `failure_code=runner_lost_recovered`, `attempt=1`, and
  `cleanup_state=confirmed`. The container was removed, the run was not
  replayed, and the Runner returned to ready. A fresh post-recovery run
  (`aa45b7d899de4c9aaff2ee73fa985cc6`) then succeeded, proving admission slot
  reuse. Its 999-byte R2 artifact was retrieved and SHA-256 verified.
- Repeating the same submission returns the existing run instead of starting
  another container.
- CPU admission is limited to one in-flight run and 30 seconds. The workload
  reports `gpu_used=false`; paid provider execution remains parked.
- A live cancellation probe (`0a61c2b307f14dfbb94d9791ff7d7139`) was submitted
  and cancelled while running. D1 reported `cancelled` with
  `failure_code=caller_cancelled`, `cleanup_state=confirmed`, and no pending
  cancellation. A follow-up capabilities read showed the Runner ready and the
  free CPU admission slot available again. This proves the explicit cancellation
  path for one bounded run; it does not prove forced-process-death recovery.

These checks prove repeated provenance-valid bounded CPU inferences, seven
complete R2 artifact retrievals, one live cancellation/cleanup path, one
planned Runner stop/start, and one forced process-loss/lease-recovery path with
successful post-recovery inference through ChatGPT. They do not prove general
model quality, GPU execution, repeated crash-window reliability, cross-owner
isolation, long-term artifact retention, or backup/restore.

## D1 and R2 recovery boundary

Cloudflare D1 Time Travel is enabled by default for databases on its production
storage backend and can restore to a point within the retention window without
an extra restore fee. As of 2026-11-12, Cloudflare documents seven days of
history on Workers Free and 30 days on Workers Paid. The Sites connector does
not expose the backing mode or account plan, so confirm both before relying on
a specific recovery window.
See [D1 Time Travel and backups](https://developers.cloudflare.com/d1/reference/time-travel/)
and [D1 limits](https://developers.cloudflare.com/d1/platform/limits/).

Time Travel restore overwrites the live database and cancels in-flight queries;
it is recovery, not a safe way to rehearse restoration. Do not run a restore
against the production Site as a test. The restore rehearsal remains open until
it is performed on an isolated scratch D1 database and verifies schema,
owner-scoped run records, leases, and a normal ChatGPT read after restore.

D1 recovery does not restore the separate R2 objects. Reconcile artifact IDs,
object metadata, byte counts, and SHA-256 digests after any D1 recovery; an
unreferenced object must remain inaccessible, and a missing object must not be
reported as a successful result. R2 retention, orphan cleanup, and paired
D1/R2 recovery remain separate acceptance gates. Do not export live D1 rows to a
local file or add them to Git; an export may contain private prompts, owner
identifiers, and run results. Cloudflare documents SQL export through Wrangler
and its API, but that route needs an approved credential and a protected
destination before use: [D1 import and export](https://developers.cloudflare.com/d1/best-practices/import-export-data/).

The Site audience is public. This ChatGPT owner connection successfully called
`experiment_capabilities` and `experiment_list` (29 records: 25 succeeded, 3
failed, 1 cancelled). This does not prove that another ChatGPT account/process
can install or use the plugin. Anonymous HTTP requests returned Cloudflare edge
HTTP 403, so they did not reach the Worker and do not verify its authentication
behavior. The local Runner and Keychain credentials have been removed.

## Operating boundaries

- Keep every stateful MCP tool bound to Sites' authenticated user ID and
  owner-scoped queries. Anonymous and forged-identity requests must fail before
  accessing D1 or any provider. Add per-user and global resource bounds before
  any public compute path is enabled. Cross-account ChatGPT acceptance remains
  open.
- Keep provider credentials out of Site source, MCP arguments, logs, and
  workload containers. The replacement provider must use a scoped runtime
  secret store and must never reintroduce a personal-host Runner token.
- Keep paid execution parked until its separate approval, price, quota,
  authentication, cleanup, and recovery gates pass.
- Do not bring the archived FastAPI/PostgreSQL, Vercel, or Neon stack back into
  the product path. Historical runbook: `archive/OPERATIONS-legacy-postgresql.md`.
- Vercel and Neon are retired from the target runtime. Keep old records as
  historical evidence; do not make either service a deployment or release gate.

## Retired macOS Runner

The Site audience is public; compute remains unavailable until its gates pass.
The former LaunchAgent was unloaded, its local runtime was removed, and the
`runner-bearer` and `sites-service` Keychain entries were deleted. Do not ask
for a macOS password, restore either Keychain item, reinstall the LaunchAgent,
or restart the old Runner. The old endpoint and runtime secret must be removed
from the deployed Site as part of the reviewed provider cutover. Preserve D1/R2
history and historical run evidence.

## Open operational acceptance

1. Verify one authorized inference against the current deployed Modal CPU
   source with idempotent submit, bounded status/collection, and no
   caller-selected code or image. Admission is currently disabled.
2. Exercise ambiguous submission, timeout, cancellation, provider failure, D1
   and R2 write failure, and recovery without duplicate runs or orphan compute.
3. Define R2 artifact retention and orphan cleanup; exercise larger artifacts and
   repeated retrieval beyond the seven accepted complete result objects.
4. Test owner isolation across separate accounts and verify Site access revocation.
5. Document and rehearse scoped provider-secret rotation, D1/R2 backup/restore,
   and incident response before enabling paid providers.

Detailed current state and evidence: `decisions/2026-11-11-sites-d1-architecture-pivot.md`.

## Latest live CPU acceptance — 2026-11-12

This dated record describes a successful run at the time it was performed. It
is superseded for present readiness by the live capability response observed
on 2026-11-12 (`available=false`; local Runner absent; admission disabled).
The next acceptance must use the Modal-backed Sites path.

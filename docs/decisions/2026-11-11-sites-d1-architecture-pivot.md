# Sites + D1 architecture pivot

**Status:** Sites + D1 is the accepted and deployed ChatGPT control-plane direction. A historical free TinyStories inference and artifact retrieval were verified through the now-retired local Runner. Current Modal health is ready, but no successful inference against the current Modal deployment is accepted. Recovery, identity isolation, complete artifact operations, and GPU execution remain open.

## P0 baseline refresh — 2026-11-11 (historical snapshot; superseded below)

- Local source is `codex/gpu-control-current-p5-on-pr58` at `4658552a9bc8f65a6f2623a8642ff39d8aaa081c`; the worktree began clean. PR #60 is still OPEN/DRAFT and mergeable. Its latest GitHub combined commit status surfaced a successful Vercel check only; do not treat that as Sites, ChatGPT, D1, runtime, or end-to-end acceptance. PR #60's own body reports its earlier local full-suite results and explicitly says no deployed ChatGPT tool flow or real GPU/paid provider call was exercised.
- `policies/repository-state.yaml` is `mode: parked`; paid workflow, live paid compute, and RunPod live calls remain disabled. This architecture change does not relax those gates.
- The current repository has no `.openai/hosting.json`, Sites `d1`/`r2` bindings, Wrangler Worker config, or GPU Control Site source. The Sites account inventory returned no existing Site titled GPU Control. Sites+D1 implementation is therefore new work, not a repointing of an existing Site.
- The current Python Gateway hosted path requires PostgreSQL and a persistent filesystem, while the Vercel deployment manifest describes a 30-second FastAPI Function. P1 local Docker and PostgreSQL tests in existing records do not establish a compatible Sites Worker or D1 deployment.
- Existing production/provider state and old source records remain separate from the new Site. The first implementation boundary is a private Sites MCP Worker + D1/R2 smoke, followed by the P1 CPU execution route; the old stack stays parked until replacement evidence exists.

**P0 exit status at that snapshot:** the target had not yet been deployed. The later implementation checkpoints below supersede the hosted status. Preserve all paid/security gates.

## Provider cleanup inventory — initial audit snapshot, 2026-11-12

- **Vercel:** the connected `gpu-control` project has `live: false`, SSO protection enabled, and three Vercel domains. Its newest READY deployment is built from this candidate's `4658552a` commit; a deployment record exists, but this does not prove a live production runtime. The pause-project call returned success; the connector's follow-up project view still reports `live: false` but does not expose a separate paused field, so pause state is not independently confirmed. The local Vercel manifest and client-IP/runtime autodetection have since been removed. The Vercel project/domains still exist; do not present Vercel checks as acceptance evidence.
- **Neon:** the `gpu-control-gateway` project `delicate-smoke-00521013` exists on the free plan. Its `production` branch `br-raspy-cell-b3l93n46` is archived, its single compute is idle/suspended, and the D1 replacement is not connected. The database contains `neon_auth` tables plus `gateway_oauth_*` and `gateway_runs_v1` tables; the branch reports about 31.7 MB logical size and has no Neon snapshot. This is potentially sensitive user/auth/run data. Do not read token rows or delete the Neon project until its data is exported, classified and either migrated to D1 or deliberately confirmed disposable. The dormant branch should incur no active compute while suspended, but verify this before retirement.
- **Sites at initial audit:** the private Site had not yet been published and no D1 migration or runtime secret was installed. This is superseded by the implementation checkpoint below.

These observations are read-only connector inventory, not proof of live application acceptance. They supersede prior assumptions that the Neon project could be removed without an export review.

## Decision summary

Use a ChatGPT Sites-hosted MCP Worker for the user-facing gateway, Cloudflare D1 for durable control-plane state, and R2 for result artifacts. Keep compute in a separately isolated execution service/provider. Vercel and Neon are not target requirements: add no new Vercel/Neon features, and keep their code/configuration out of the supported product path.

PostgreSQL is not an inherent requirement of experiment execution, and the target Sites product does not need it. It is required only by the archived FastAPI implementation and its PostgreSQL-specific tests. The Sites Worker already uses its D1 binding for plans, runs, idempotency, leases, and Runner heartbeats. D1 is the selected control-plane database; its SQLite-compatible binding requires D1-specific prepared statements and atomic batches, not a PostgreSQL URL. Reconsider another database only if measured concurrency, query, or data requirements exceed D1's limits.

Preserve historical acceptance evidence, but keep Vercel and Neon out of the active product path. Vercel runtime config and autodetection have been removed; the old Vercel/PostgreSQL operations procedure has been moved to `docs/archive/`. Retain provider resources only as rollback/export sources until Sites acceptance and required-data export are verified; then retire the resources and unused credentials. Never delete unexported user data or destroy the only rollback copy.

## Why Vercel is not the product requirement

Vercel was inherited from the existing FastAPI deployment (`gateway/vercel.json`): it provided an HTTPS route for that implementation. It was never a product requirement. The existing design also requires asynchronous execution, recovery, durable state, and result storage; adding more Vercel configuration would not complete those capabilities or make the product usable in ChatGPT. Stop extending that path and migrate its required behavior to Sites/D1/R2 plus an execution service.

Sites supports a Worker-backed MCP endpoint and D1/R2 bindings. That aligns the app entry point, ChatGPT tool connection, structured job records, and artifact storage in one hosting path. Sites does not run the current Python/SQLAlchemy/daemon stack unchanged.

## Current code constraints

- `gateway/gpu_gateway/config.py` explicitly requires `postgresql+psycopg://` for hosted deployment.
- `gateway/gpu_gateway/store.py` uses a synchronous SQLAlchemy engine and transaction context manager. SQLite tests rely on `BEGIN IMMEDIATE`; PostgreSQL uses row locking and provider-specific functions/privileges for some operations.
- The current API, execution worker, and recovery supervisor share SQLAlchemy tables and expect transactional lease, idempotency, approval, ownership, and cleanup transitions.
- `ArtifactStore` reads and writes a shared local filesystem. Sites Worker storage is not that persistent filesystem; result bytes should move to R2, with digests and owner-bound metadata in D1.
- The current local CPU backend requires a dedicated Docker-capable worker host. Sites Workers cannot run that host daemon. A Sites-only control plane therefore needs provider-hosted asynchronous compute or a separately operated execution service.

## Proposed target

1. **ChatGPT connection:** publish a private Sites MCP Worker with the existing canonical tools and schemas. Sites supplies the ChatGPT Site/plugin connection; the Worker still enforces owner isolation and every server-side authorization rule.
2. **State:** port run, plan, admission, OAuth/owner mapping, authorization, idempotency, provider-account lease, and recovery state to D1. Use prepared statements and D1 `batch()` transactions for operations that must commit atomically. Replace PostgreSQL-only `SELECT FOR UPDATE`, security-definer functions, role grants, JSONB differences, and SQLAlchemy transaction assumptions with reviewed D1-specific operations.
3. **Artifacts:** put immutable result blobs in R2. Store object key, digest, byte length, run ID, and owner binding in D1. Serve downloads through an authenticated MCP operation that verifies owner and digest before returning bounded content.
4. **Execution:** keep model training outside the Sites Worker. Use an asynchronous provider job API for Modal or RunPod, with provider credentials stored only as server-side Site secrets. Keep paid execution parked until the existing approval, price, quota, and cleanup gates pass.
5. **Recovery:** replace the always-on Python supervisor with a tested durable orchestration path. First verify which scheduled/queue/workflow primitives the Sites publishing surface can bind. If it cannot provide a reliable supervisor-equivalent, use a small separately operated worker service and document that Sites hosts the ChatGPT gateway while that service performs recovery.
6. **Migration:** retain the current Python implementation as a behavioral reference until the D1 version passes parity tests for owner isolation, duplicate submit, concurrent lease claim, approval expiry, cancel/submit races, worker interruption, restart recovery, and artifact integrity.

## Feasibility and constraints

Cloudflare exposes D1 through a Worker environment binding rather than a PostgreSQL connection URL. D1 `batch()` executes statements sequentially and atomically, which can support bounded state transitions when each transition is designed as a batch. Individual D1 databases process queries serially; that is likely acceptable for a single-owner, low-volume control plane, but queue latency, overload handling, and recovery latency must be measured. D1 storage/throughput limits and plan costs must be checked against the user's actual account before choosing the production tier.

The first migration slice should not move every provider or destroy rollback data. It should prove one complete harmless registered run through the Site MCP app, D1, asynchronous compute, status/result retrieval, and owner boundary. Vercel is excluded from the supported target path now; remove residual Vercel/Neon resources after parity and required-data export are verified.

## Long-term task list and acceptance gates

### Implementation checkpoint — 2026-11-12

- [x] Published the Site privately at `https://gpu-control-sites.unjuno.chatgpt.site`; Sites reports an owner-only access policy, MCP readiness, and an already-installed generated plugin. This proves publication, not a successful ChatGPT tool call.
- [x] Published version 3 from Site source commit `9611ce9fc3dd051c759a9b1eb5d51c390872b1b4`. `experiment_capabilities` now reports live-runner readiness separately from execution admission, so parked admission is explicit rather than misreported as a dead Runner.
- [x] Added four Node Worker tests for live/stale/mismatched Runner state and admission gating; all 4 passed. `npm run build`, `npm run validate`, and `git diff --check` also passed before publication.
- [x] After version 3, re-read Sites runtime configuration: environment revision 1 remains active, `CPU_WORKLOAD_ADMISSION_ENABLED=false`, and the Runner bearer remains stored as a masked secret. A fresh D1 heartbeat still matches the registered image and source identity.
- [x] Retired the separate GitHub comment-to-Gateway route that still pointed at the legacy Vercel origin/Neon queue: production policy is disabled with a non-routable origin, its triggering workflow is removed, and `gateway/COMMENT_BRIDGE.md` marks the old route as reference-only. Legacy implementation tests now use explicit test-only opt-in; 82 passed, 1 optional skip.
- [x] Sites provisioned the `DB` D1 binding and applied the initial migration; live table inventory is `plans`, `runs`, and `runner_heartbeats`.
- [x] Registered the fixed CPU image digest/source identity and a fresh Runner bearer secret in Site runtime configuration. `CPU_WORKLOAD_ADMISSION_ENABLED` is explicitly `false`; no run can be submitted until the reviewed runner is ready.
- [x] A local Linux ARM64 isolated run of the exact registered CPU image returned a checksum-validated `cpu-smoke-v1` result and exited cleanly. This is local execution evidence, not a Sites/D1/ChatGPT-originated run.
- [x] Runner endpoint validation now requires a canonical HTTPS origin and refuses redirects; three regression tests cover unsafe origins, redirect rejection, and authentication headers.
- [x] Environment revision 1 and the fixed image registration are active after a successful follow-up private deployment. The Runner bearer is stored as a Site secret; the environment value was confirmed masked on read-back.
- [x] Local Linux/ARM64 Runner authenticated to the private Site and wrote a live D1 heartbeat with the registered image digest and workload source SHA. Admission remains disabled, so no run has been claimed.
- [x] Completed a static security scan of the earlier exact source snapshot. It reported one medium credential-forwarding issue in the then-current Runner; canonical HTTPS-origin validation and redirect rejection were subsequently added and covered by local regression tests. This scan is not an approval of the later live Worker/Runner revision.
- [x] Sent a read-only unauthenticated `tools/call` to the deployed `/mcp` with a forged `oai-authenticated-user-id`; Sites rejected it with HTTP 401. This verifies the public route does not accept that header by itself, but does not replace an authenticated owner-isolation test through the ChatGPT Site plugin.
- [x] Added an initial D1 control-plane schema for owner-scoped plans/runs, idempotency, a single active slot, runner heartbeat and execution lease fields.
- [x] Added a separate Docker runner that polls the Sites Worker, verifies image/source/architecture, applies the fixed isolated CPU profile, validates checksum output, confirms cleanup, and reconciles expired leases without automatic re-execution.
- [x] Added a Worker MCP slice advertising the eight canonical tool names and common schema-v2 envelope; unsupported artifact/cancel operations return explicit blocked responses.
- [x] Bound each prepared plan to the exact image digest in D1; submit and result acceptance compare against that persisted digest. This fixes the low-severity finding in the first exact-source security scan.
- [x] Local build, artifact presence validation, JavaScript syntax check and SQLite-compatible migration parse passed. These checks do not prove hosted Sites/D1/ChatGPT behavior.
- [x] Built the registered CPU smoke image on local Linux ARM64 and executed one deterministic 1,000-iteration run through the new runner's Docker profile; checksum passed and the container was absent after cleanup.
- [x] Follow-up security review of the earlier current snapshot found no reportable findings and noted partial coverage. That snapshot predates the new runner/recovery implementation below and cannot be treated as its security approval.
- [x] Removed `gateway/vercel.json`, the Vercel client-IP mode and runtime autodetection, and the Vercel-specific deployment-SHA variable. The whole legacy FastAPI/PostgreSQL source tree was removed from the working tree on 2026-11-12; its remaining references are historical only.
- [x] Runner heartbeat and authenticated ChatGPT-originated CPU run/result are accepted; cross-owner denial is still unverified and paid execution remains parked.
- [ ] Neon is not retired: its archived project contains auth and gateway run/token tables, with no Neon snapshot. Export/classify those records and obtain a verified D1 or archive copy before project deletion.

### ChatGPT-originated CPU vertical update — 2026-11-12

- [x] Sites version 4 (`appgver_94bc3bac2b1c8191b3863fa75105eca7`) is deployed at the existing owner-only URL. Its first deployment (`appgdep_6af4a41698188191aa281775a574cf85`) reported `succeeded` and `has_mcp=true`. Access policy still lists only the owner and zero external visitors.
- [x] From ChatGPT, `experiment_capabilities` confirmed the exact registered free CPU image, live Runner, 30-second ceiling, one in-flight slot, and `paid_execution=parked`.
- [x] From ChatGPT, prepared, submitted, polled, and separately retrieved run `3f7c1367a1634f919320c767c8e08a36` for repository `Unjuno/gpu-control`, source `4658552a9bc8f65a6f2623a8642ff39d8aaa081c`, image `sha256:c561f8b7054c3b26946841134c76b6f81b8939430613dea9fe8dd5000cefa0fc`, and parameters `{iterations:1000, seed:61112}` at `$0.00`.
- [x] The persisted result is `succeeded` / `passed`; checksum `319a9c3deeffcd3213f907cda9a4c956d3b385cc466f76840a2fdf671e29104d`; all eight reported container checks passed; `gpu_used=false`; `cleanup_state=confirmed`. This is the first ChatGPT-originated Site→D1→Runner→D1→ChatGPT round trip.
- [x] Fixed the admission shutdown claim bypass: when admission is disabled, `/runner/claim` now cancels only queued work before leasing and returns 409. Added a regression test, committed as `4e55378` and pushed to `codex/gpu-control-current-p5-on-pr58`.
- [ ] This run is a checksum smoke, not model inference, GPU execution, cancellation, R2 artifact retrieval, or cross-account owner-isolation evidence. The free CPU admission flag is currently enabled to continue the authorized non-billable vertical; paid providers remain parked.

### TinyStories model-inference update — 2026-11-12

- [x] Published the fixed `tiny-stories-inference-v1` workload to the same owner-private Sites MCP Worker with D1. The public control-plane path remains Sites + D1; no Vercel or Neon runtime was added.
- [x] Corrected workload provenance: image `sha256:87634dc98f196d24deb2f72fe3bb87199dcd860ebd0c69dddd076efdebf685f2` was built with source label `Unjuno/gpu-control` and exact root commit `3cc7a7685c6e9890c9896f6bd77fbb589b89d8e2`, then registered in Sites. The separate Site Worker source commit is `c2ae553dd240c4baf09202ac1e15b64277cb439f`.
- [x] Replaced the Runner bearer with a new random value stored only in Sites secret storage and the live Runner process. Admission remained off while the service was replaced; the new Runner verified Docker and the exact image before reporting readiness.
- [x] Re-enabled free CPU admission only after the exact Runner heartbeat matched the registered source and digest. `paid_execution=parked`, one in-flight run, 30-second maximum, and `$0.00` cost remained in force.
- [x] Through ChatGPT, prepared, submitted, polled, and separately retrieved `tiny-stories-inference-v1` run `a514f038b9e24bed954d0bc7874ba679`. It generated 24 tokens in 420 ms; result/model identity and checksum checks passed, `gpu_used=false`, and cleanup was confirmed.
- [ ] Live forced-restart, cancellation race, cross-account isolation/revocation, R2 artifact retrieval, backup/restore, and extended operational observation remain open. The full evidence is in [`../acceptance/2026-11-12-sites-d1-tinystories-chatgpt-inference.md`](../acceptance/2026-11-12-sites-d1-tinystories-chatgpt-inference.md).

### Workload source SHA correction — 2026-11-12

- The two earlier inference outputs above used `3cc7a7685c6e9890c9896f6bd77fbb589b89d8e2` as the registered source. A direct `git cat-file -t` check showed that value does not exist in the root repository. Those D1 records are retained, but they are excluded from source-provenance acceptance.
- Rebuilt the image from the pushed root commit `3cc7a765cbcbeb7abdfa0d607e8a44e4cdff2288`, confirmed it resolves to a Git commit and the current PR branch, and inspected matching OCI source/revision labels. New digest: `sha256:f0e1bbd44e0bd475dc2f19a548a96e041fc9cb48fc4160d4c0c4de02b0e00541`.
- During replacement, verified all recorded runs were terminal and no labeled containers were running. Disabled admission, deployed the corrected source/digest registration, stopped the mismatched Runner, started a new Runner with the existing Sites service token and newly stored bearer, observed matching readiness, then re-enabled free CPU admission while paid execution stayed parked.
- [x] ChatGPT run `d17dcc650783466088bacb734826bcdb` used the actual root commit and new digest; it generated 24 tokens in 430 ms, passed identity/checksum checks, returned `gpu_used=false`, and was separately retrieved with cleanup confirmed.
- [x] Environment revision 2 was published by the follow-up private deployment `appgdep_6af4a526adf88191a3e50d35acd9371f` (`succeeded`, `has_mcp=true`). A fresh ChatGPT capability call confirms admission enabled, free CPU only, one 30-second slot, and paid execution parked.

### D1 duplicate-submit and legacy Neon refresh — 2026-11-12

- [x] Re-submitting the completed plan through ChatGPT returned the same `run_id`, `state=succeeded`, and `experiment_list` still contains exactly one run. No second container or compute job was created.
- [x] Fixed the submit response to describe the persisted run state even when D1 `batch()` resolves without throwing. Added coverage for both the duplicate-error path and the successful no-op batch path; all 7 Worker tests passed, and `npm run build`, `npm run validate`, and `git diff --check` passed.
- [x] Version 6 (`appgver_8dfd2b8758288191af282215ccf69463`) deployed successfully as `appgdep_6af4a9e52d448191a64f810cf73f6275`. Repeating the ChatGPT submit now reports “この実験は完了しています。” with the same succeeded run ID; `experiment_list` still contains exactly one run.
- [x] Read-only Neon inventory refresh: project `delicate-smoke-00521013`, production branch `br-raspy-cell-b3l93n46` is still primary/default and unprotected; logical size is 31,670,272 bytes. Its only read-write endpoint is idle and suspended, and the project has no Neon snapshots. The database still contains Neon Auth and legacy OAuth/run tables. No secret rows were read and no Neon data was changed.
- [ ] Do not delete Neon until those legacy records are classified and any required data has a verified export or D1/archive copy. There is no active compute now, so the project can remain suspended while the Sites replacement is completed.
- [x] Reorganized operator docs: `docs/CHATGPT_SETUP.md` identifies Sites + D1 as the supported path; the detailed legacy PostgreSQL runbook is under `docs/archive/`, and `docs/OPERATIONS.md` describes current Sites boundaries and open acceptance. Removed Vercel-specific runtime configuration and autodetection from the active path. The old `gateway/README.md` reference in this dated checkpoint is historical; the full `gateway/` source tree was retired on 2026-11-12.
- [x] Refreshed Vercel project `prj_fMufIBiFDlXtWcuJ0bWpAekEMIAp`: `live=false`, latest deployment `BLOCKED`, three Vercel domains remain. The default `gpu-control.vercel.app` health and MCP GETs return 503; the preview URL redirects unauthenticated requests to Vercel SSO. No Vercel application runtime is currently reachable anonymously.
- [ ] The Vercel project and its domains still exist. The connected Vercel deletion flow requires the account owner to review and confirm project deletion; retain the project until final Site acceptance and any needed rollback evidence are resolved.
- [x] Added three local Runner recovery regressions: recovery removes only a container whose run, lease, plan, image, and source labels match; mismatched labels and unconfirmed cleanup fail closed. The focused recovery/security set passed 7 tests, and the root recovery subset passed 3 tests. This is code-level evidence, not a forced restart against the live Site Runner.

### Site source provenance and macOS Runner management — 2026-11-12

- [x] Confirmed production still serves Site Version 11; Version 13 is saved but undeployed. The Site source credential response identifies its source provider as `cloudflare_artifact` on branch `main`.
- [x] Historical check found Version 13's recorded source SHA `52416ec02fcf3b755e1763edc617cd0a67f4ab91` absent from the GitHub checkout; this was not sufficient to determine the separate Cloudflare artifact repository state.
- [x] Fresh authenticated read-only fetch from the configured `cloudflare_artifact` source repository verified `refs/heads/main` at exactly `52416ec02fcf3b755e1763edc617cd0a67f4ab91`. Version 13 provenance is reconciled; this does not by itself authorize or perform deployment.
- [x] Added a macOS Keychain launcher and secret-free LaunchAgent manager. The plist now points at the correct Site checkout, is atomically written with mode `0600`, refuses an unmanaged duplicate Runner, does not force-restart a loaded service, and verifies stop completion.
- [x] Runner tests passed 21/21; Worker tests 24/24; build, artifact validation, `git diff --check`, plist lint, and a Codex Security diff review passed. The review found no reportable vulnerabilities; it did not exercise the live Keychain or launchd service.
- [ ] Install the LaunchAgent only after source and Site secret rotation are reconciled; perform the coordinated cancellation/restart/recovery acceptance with admission closed, then restore only free CPU admission.

### Runner protocol compatibility candidate — 2026-11-12

- [x] Added append-only D1 migration `0003_runner_cancellation_protocol.sql`. Existing heartbeat rows default to protocol 0; only protocol 1 is considered ready and eligible to claim work. The Worker rejects heartbeat payloads with missing, unknown, or extra fields.
- [x] Updated the CPU Runner to declare protocol 1 before recovery/claim. Regression checks prove legacy readiness, heartbeat refresh, and claim attempts fail closed.
- [x] Worker tests passed 24/24; Runner tests passed 12/12; build, packaged artifact validation, and `git diff --check` passed. A Codex Security diff review of the six implementation files completed with zero findings; the review did not exercise live D1 or restart behavior.
- [x] Saved Sites Version 13 from source commit `52416ec02fcf3b755e1763edc617cd0a67f4ab91` with packaged artifact SHA-256 `b43b22033dea244f5680dd1d70ea836a2528254eb2a4facc7247f279f80c952c`. It is saved only; production remains on Version 11 until a coordinated Runner update/restart is ready.
- [x] Revalidated the live ChatGPT route after the previous acceptance: run `1fdfe901fda14798a42e33e492edd538` used the registered source/image and generated four TinyStories tokens in 155 ms. It passed source/model/parameter and sandbox checks, reported `gpu_used=false`, and confirmed cleanup at `$0.00`.
- [x] Superseded by the Version 15 live acceptance below: the coordinated Runner update/restart, zero-cost inference, cancellation, cleanup, and one forced process-loss/lease-expiry recovery have been verified. Repeated crash windows and other listed security/recovery gates remain open.

**Next implementation sequence (refreshed 2026-11-12):** (1) close the outstanding Runner credential-rotation and post-result crash-window checks; (2) rehearse D1 export and restore against an isolated target, then define R2 retention/orphan cleanup; (3) verify owner isolation and revocation using a genuinely separate authenticated Site user; (4) retire external Vercel project/integration and Neon only after residual Neon rows have an explicit data disposition; (5) validate real GPU provider execution through Sites while preserving independent price, quota, cleanup, and authorization gates. Keep paid admission parked until those gates pass. The legacy FastAPI/PostgreSQL source, lockfile, dependencies, and test suite have now been removed from the working tree; the independent Project bridge and reusable tiny-LM workload remain outside `gateway/`.

### User-confirmed platform direction — 2026-11-12

This dated direction preceded the later retirement of the local Runner. The
active target now uses ChatGPT Sites as the control plane with Modal/RunPod as
compute providers; the Runner and its Keychain authentication are retired.
Current status is maintained in `docs/STATUS.md` and `docs/CHATGPT_SETUP.md`.

- ChatGPT Sites is the product interface and control-plane hosting target. Do not add or retain Vercel product features, deployment checks, or runtime assumptions. Remove the external Vercel project and integration after verifying that GitHub required checks, DNS, secrets, and rollback procedures do not depend on it. Historical build and incident evidence may remain in `docs/archive/`.
- Cloudflare D1 is the selected control-plane database. PostgreSQL is **not required** for the Sites product. D1 already persists the live plans, runs, idempotency, leases, and Runner heartbeats. R2 holds result bytes. The separate Runner executes only the fixed registered workload and does not require a PostgreSQL service.
- PostgreSQL-specific locks, migrations, roles, SQLAlchemy paths, and tests existed only because the legacy FastAPI Gateway used them. They were not a reason to keep Postgres in the target architecture. The active source/dependency/test surface is now removed; dated acceptance evidence remains historical.
- Neon is not needed by the current product path. Its external project still contains residual legacy session/auth/control records; do not read token contents or destroy those records until their disposition is explicitly settled. Once that is settled, remove the project and credentials, not just the application's references.
- D1 is appropriate for the present single-owner, bounded, low-volume control plane. Its serialized per-database query execution and D1-specific transaction semantics require explicit concurrency/recovery tests. Reconsider another store only if measured throughput, atomicity, query, or retention needs cannot be met with D1; do not preserve PostgreSQL preemptively.

### Version 15 live cancellation and Runner recovery refresh — 2026-11-12

This section supersedes the Runner deployment/restart/cancellation steps in the
older status notes above; those notes remain as a dated history.

- [x] The private Site is live on Version 15 with D1/R2 and the macOS
  Keychain-backed LaunchAgent. Its running `run.py` and Keychain launcher hashes
  match the published Sites source; plist and installed runtime files are mode
  `0600`.
- [x] A live cancellation request against a running free CPU run converged to
  `cancelled`/`caller_cancelled`, cleanup confirmed, and the free slot ready.
- [x] A planned LaunchAgent stop/start was performed with admission closed and
  no active runs. The new Runner heartbeat was verified before admission was
  reopened; a post-restart ChatGPT inference and R2 artifact retrieval passed.
- [x] A separate free CPU run was interrupted by SIGKILL to the LaunchAgent
  Runner while its exact labeled container was active. launchd restarted the
  Runner. After the 180-second D1 lease expired, recovery removed the stopped
  container and persisted `failed`/`runner_lost_recovered`, attempt 1,
  `cleanup_state=confirmed`, and no result artifact. The run was not replayed.
  A subsequent ChatGPT inference and full R2 artifact read verified slot reuse.
- [x] Live forced Runner loss was accepted at three boundaries: during active
  inference, after container creation but before start, and after container
  exit but before result reporting. Each run expired through its D1 lease,
  became `runner_lost_recovered`, confirmed cleanup without result/replay, and
  was followed by a successful free CPU run. See the dated acceptance records.
- [ ] Test the remaining post-result-persistence/R2-upload window and repeat
  recovery trials. Sanitized Runner logs contained transient
  `SITE_REQUEST_FAILED` retries during earlier observation; diagnose any
  recurrence before increasing admission.
- [ ] Complete D1/R2 backup and restore, artifact retention/orphan cleanup,
  separate-account owner isolation/revocation, Keychain ACL/rotation, and an
  incident runbook. Continue to keep GPU/paid admission parked during these
  gates.
- [ ] Retire Vercel and Neon resources after the legacy code removal and
  required-data disposition. Vercel project deletion still requires owner UI
  action; Neon deletion is pending the owner's explicit choice to discard or
  export its residual auth/session/control rows.

### A. Freeze and map existing behavior

- [ ] Record the exact current tool names/schemas and auth/owner invariants.
- [ ] Map each D1-bound transition in `Store` to a state machine, including its idempotency and crash boundary.
- [ ] Classify provider secrets, artifact data, and existing run/OAuth data for migration or deliberate non-migration.

**Gate:** every public tool and every durable transition has a D1 design and a matching acceptance case; no transition depends on implicit SQLAlchemy or PostgreSQL behavior.

### B. Prove the Sites MCP and D1 vertical

- [x] Build and privately publish the Site MCP Worker; ChatGPT can discover its canonical tools and execute the registered non-billable CPU checksum smoke.
- [x] Create the D1 migration and implement owner-scoped plan/run storage with prepared statements and bounded atomic batches; the end-to-end run and duplicate-submit response are verified.
- [ ] Implement D1 backup/export and restore rehearsal before storing any durable OAuth or run data.

**Gate:** same-owner cross-chat retrieval, cross-owner denial, and a documented D1 export/restore rehearsal remain open.

### C. Replace asynchronous execution and recovery

- [ ] Select and validate the provider-native async job lifecycle for the first execution backend.
- [ ] Implement durable submit intents, external-job ID reconciliation, cancellation, timeouts, and an automated recovery sweep.
- [ ] Prove that duplicate MCP calls do not create duplicate provider jobs and that interruption between D1 commit and provider response is recovered safely.
- [ ] Decide whether the recovery sweep runs through a Sites-supported schedule or a small separately operated worker.

**Gate:** forced interruption, timeout, cancellation race, provider outage, and delayed completion all converge to one truthful terminal state with verified cleanup and no duplicate billable resource.

### D. Move artifacts and harden identity

- [ ] Store immutable results in R2 and validate digest, byte size, run, and owner on retrieval.
- [ ] Bind Sites-authenticated user identity to persisted run ownership; test account changes and revoked access.
- [ ] Move only the secrets required by the selected worker/provider into Site server-side secrets; keep public frontend and tool inputs free of provider credentials.

**Gate:** cross-owner and cross-chat acceptance passes; corrupt/oversized/missing artifacts fail closed; recovery can retrieve and validate provider output after a Worker restart.

### E. Remove Vercel, Neon, and the legacy PostgreSQL Gateway

- [x] Remove Vercel-specific runtime config and environment assumptions from the supported release path; do not add new Vercel feature work.
- [x] Remove the legacy FastAPI/PostgreSQL application, PostgreSQL-only runtime dependencies and tests from the working tree while preserving historical evidence; retain the independent Project bridge and tiny-LM workload outside the retired Gateway tree.
- [ ] Export and verify any required existing run/OAuth state before data migration; otherwise document a deliberate fresh single-owner start.
- [ ] Revoke and rotate credentials that are no longer used.
- [ ] Delete old Vercel/Neon resources only after the D1-backed Site passes the full ChatGPT acceptance and any required data has a verified export.

**Gate:** no release, tool call, recovery process, or secret depends on Vercel or Neon; a documented rollback/export remains available through the agreed retention window.

## Source references

- [Cloudflare D1 binding and `batch()` semantics](https://developers.cloudflare.com/d1/worker-api/d1-database/)
- [Cloudflare D1 limits and single-threaded database behavior](https://developers.cloudflare.com/d1/platform/limits/)
- Existing implementation topology: `docs/decisions/2026-10-28-p3-deployment-topology.md` (historical record; preserve as evidence, supersede its selected-host recommendation only after this proposal is accepted).
- Existing ChatGPT interface contract: `docs/specs/chatgpt-native-experiment-control-plane.md`.

### Legacy source retirement validation — 2026-11-12

- Removed the tracked `gateway/` application tree, including FastAPI/PostgreSQL runtime, deployment manifests, provider/worker implementation, and its Gateway-specific test suite. This retires the unneeded hosted application source from the active checkout; it does not delete the external Vercel project or Neon data.
- Moved the independent GitHub Project bridge to `project_control/` and the reusable tiny-LM workload to `workloads/tiny-lm/`. Updated workflows and imports to the new paths.
- Validation on the candidate: root `uv run --locked pytest -q` passed (one optional skip); `python3 -m unittest discover -s project_control/tests -v` passed 19 tests; the Docker contract smoke and two-step tiny-LM CPU smoke passed; `git diff --check` passed. No live Sites version was changed by this source cleanup.
- PostgreSQL is no longer an application/runtime dependency in the active checkout. D1 remains the Sites control-plane store; R2 remains the artifact store. Neon residual rows and the external Vercel project remain under the retirement gates below.

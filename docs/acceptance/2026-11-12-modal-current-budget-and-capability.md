# Modal budget and Sites capability recheck — 2026-11-12

Checked at 2026-11-12 11:44 UTC through the authenticated ChatGPT Site and
signed-in Modal dashboard.

## Sites state

- Production Site `gpu-control-sites` is public, active, and owned by the
  current account. The Sites API reports Version 25 from source commit
  `c3077a54888bcb07fd0e42238cc677c5d7c17bd8` at
  `https://gpu-control-sites.unjuno.chatgpt.site`.
- Production environment revision 23 contains
  `CPU_WORKLOAD_ADMISSION_ENABLED=true`, the registered source SHA
  `3cc7a765cbcbeb7abdfa0d607e8a44e4cdff2288`, image digest
  `sha256:f0e1bbd44e0bd475dc2f19a548a96e041fc9cb48fc4160d4c0c4de02b0e00541`,
  and fingerprint
  `34c63203d132b0a11c9ac68eebb4e27ad27b570fa36017f3beeb7d4d24e3bae8`.
- A fresh ChatGPT `experiment_capabilities` call returned
  `available=true`, `provider_ready=true`, `admission_enabled=true`, provider
  `modal_cpu`, maximum runtime 30 seconds, maximum inflight 1, and
  `paid_execution=parked`.
- Version 25 currently reports Modal CPU as `free=true` and prepared cost
  `$0.00`. Those fields are inaccurate because Sandbox CPU and memory are
  usage-billed. No workload was submitted in this check.

## Modal state and price evidence

- The Modal `unjuno/main` dashboard shows deployed app version v4; its commit
  field is blank. The latest observed deployment time was Nov 12, 18:06 JST.
- The Usage limit page displayed a provider-set Workspace limit of `$1`, usage
  of `$0.03` in credits, and `$0` in charges. The UI offered adding a payment
  method to raise the limit. This is a rechecked account-level usage ceiling;
  it does not establish a per-run price cap or successful workload execution.
- Modal's [official pricing page](https://modal.com/pricing) lists Sandbox
  non-preemptible CPU at `$0.00003942` per core-second and memory at
  `$0.00000667` per GiB-second. At the configured maximum of 1 core, 0.5 GiB,
  and 30 seconds, the compute estimate is
  `30 * (0.00003942 + 0.5 * 0.00000667) = $0.00128265`, rounded up to `$0.0013`.
  This estimate excludes Modal control-function time, image builds, and any
  provider charges outside Sandbox CPU/memory.

## Code state and acceptance boundary

- Commit `31d7d42` adds a fixed root-to-UID/GID-10001 Sandbox launcher. The
  follow-up currently in the worktree includes that launcher in the workload
  fingerprint, so Site health will require a matching environment update.
- The current live Site is available but the current Modal v4 deployment has
  not been bound to the new launcher. The fixed launcher has not passed a live
  inference check. Do not infer Modal acceptance from the readiness call.
- A narrow parked-mode exception is being added for one authenticated,
  registered CPU run (30 seconds, 1 CPU, 512 MiB, no GPU, blocked egress,
  `$0.01` Sandbox CPU/memory ceiling), requiring a live Workspace usage limit
  no greater than `$1`, current user authorization, and confirmed cleanup.
  Separately billed Modal control-function calls are excluded from that
  ceiling; total charges can be higher. The
  RunPod/GPU and paid-training gates remain parked.
- Review found the live D1 plan schema still enforces a historical `$0.00`
  ceiling. An append-only migration is required before new paid Sandbox plans
  can be inserted; verify it preserves historical plan rows and the `runs` FK
  before deploying it.
- No new Sandbox was created as part of this recheck. The earlier successful
  run under Sites Version 16 used the retired macOS Runner; two prior Modal
  runs failed with cleanup confirmed.

## Follow-up live acceptance — 2026-11-12 12:20 UTC

- Published Sites Version 26 (commit `a9f519f1e48b976e569f5674949a77fa51e16f81`)
  with the corrected Sandbox cost disclosures and append-only D1 migration
  `0004_sandbox_cost_ceiling.sql`. The migration was executed in SQLite with
  foreign keys enabled: historical `0.00` plans and existing runs remained,
  the foreign-key check was clean, and a new `0.01` plan was accepted.
- Deployed Sites Version 27 (commit
  `64d2646815be198b0173877b821264cf3efc10a6`) with non-secret health check
  booleans; all provider health checks passed. The live fingerprint is
  `3a2b0992465a3aac53a41a6f1a9cd6b1812b1beb6f13ca3a59eaeddbece55ddc`.
- Deployed the fixed Sandbox entrypoint to Modal `unjuno/main`. A temporary
  one-hour Workspace API token was used only for this deploy and deleted in
  the Modal UI immediately afterward; the token does not enter the Sandbox.
- Rechecked Modal's current Workspace usage guard before execution: `$1` limit,
  `$0.03` credits used, `$0` charges. ChatGPT prepared one plan for
  `tiny-stories-inference-v1`, prompt `Once`, 16 maximum generated tokens, seed
  `61112`, and a 30-second runtime. Its Sandbox CPU/memory estimate was
  `$0.0013` and its Sandbox-only ceiling was `$0.01`.
- Run `b3380814d0854d93a5d978799d670013` reached Modal through ChatGPT and failed
  with `MODAL_WORKLOAD_EXIT_2`. Modal Sandbox
  `sb-01M77TZXQ0D04PVJ52QG6Y8F0E` showed `Failed (code 2)` and no logs. Sites
  recorded `cleanup_state=confirmed`; no successful inference or artifact was
  produced. The current workload returns exit code 2 without identifying which
  guard failed, so the failure cause remains unknown. No automatic retry was
  made.
- After the attempt, Modal Usage showed `$0.04` in credits, `$0` in charges, and
  the `$1` Workspace limit. The `$0.01` increase includes provider control and
  deployment activity and cannot be attributed solely to this Sandbox.
- Sites environment revision 27 now has
  `CPU_WORKLOAD_ADMISSION_ENABLED=false`. A fresh ChatGPT capability call
  confirmed `provider_ready=true`, all health checks true, and
  `admission_enabled=false`. This one-run authorization is consumed; another
  live Sandbox requires a new current authorization after a useful diagnostic
  fix is ready. RunPod/GPU and paid training remain parked.

## Bounded failure diagnostic prepared — 2026-11-12 12:28 UTC

- The Modal entrypoint now traces only the fixed inference `main()` return path
  and writes a non-sensitive source-line marker when that function returns
  preflight code 2. The Modal control API accepts only this exact bounded
  marker; the Sites Worker records it in `failure_code` without exposing
  provider stderr.
- A local synthetic preflight returned code 2 and emitted the expected source
  line marker. The Site Worker suite passed 21 tests, and build/artifact
  validation passed. No provider was called.
- This diagnostic has not been deployed. The live Site remains on Version 27
  with admission disabled, and the previous one-run authorization is consumed.
  Deploying this diagnostic and performing one bounded inference require a
  new explicit authorization. No new Modal token or Sandbox was created.

## Historical run-list reconciliation — 2026-11-12 12:40 UTC

- A fresh read-only ChatGPT `experiment_list` and `experiment_status` check
  also surfaced run `0f2a3ddaa7da40648600bae21ccd9ed1`, created at
  2026-11-12 11:25 UTC. It is `failed` with `MODAL_WORKLOAD_EXIT_2`,
  `cleanup_state=confirmed`, and no result artifact. Its request was bounded
  to 16 generated tokens. The current read did not establish which deployment
  or authorization was in effect at creation; preserve it as a separate failed
  event without inferring its approval provenance.
- The latest run `b3380814d0854d93a5d978799d670013` remains failed with the same
  exit code and confirmed cleanup. No successful Modal inference is recorded.

# Sites + D1 TinyStories inference acceptance — 2026-11-12

## Scope and result

PASS for one free, owner-authenticated ChatGPT-originated TinyStories CPU
inference whose source label resolves to the exact pushed Git commit. The run
passed through the deployed Sites Worker, D1, and isolated local Runner. It is
a vertical execution proof, not a model quality claim or evidence for GPU,
recovery, cancellation, cross-owner isolation, or artifact retrieval.

## Final deployment identity

- Private Site: `https://gpu-control-sites.unjuno.chatgpt.site`
- Deployment with corrected workload registration and admission enabled:
- Current published deployment: `appgdep_6af4c37d69508191abb84497f8c46a7e`
- The accepted inference run below executed on
  `appgdep_6af4c22815a48191b0c2c798f86dae92`; the later Site source update
  changed only README documentation, not Worker code or runtime configuration.
- Current Site Worker source commit:
  `0226cee8fe6755744d51e6a5ee4d466a7c5b09a9`
- Workload repository: `Unjuno/gpu-control`
- Workload source commit:
  `3cc7a765cbcbeb7abdfa0d607e8a44e4cdff2288`
- The workload source commit exists in the root Git repository and matches the
  remote branch `codex/gpu-control-current-p5-on-pr58`.
- Registered Runner image:
  `sha256:f0e1bbd44e0bd475dc2f19a548a96e041fc9cb48fc4160d4c0c4de02b0e00541`
- Local image inspection reported `arm64` and OCI labels `Unjuno/gpu-control`
  plus the exact source commit above. The Runner verifies these labels and the
  host architecture before sending its ready heartbeat.
- Before the accepted run, live `experiment_capabilities` reported
  `available=true`, `runner_ready=true`, `admission_enabled=true`, `free=true`,
  `max_runtime_seconds=30`, `max_inflight=1`, and `paid_execution=parked`.

## Provenance-valid ChatGPT-originated run

- Run ID: `d17dcc650783466088bacb734826bcdb`
- Workload: `tiny-stories-inference-v1`
- Parameters: prompt `Once upon a time`, `max_new_tokens=24`, `seed=61112`,
  runtime ceiling 30 seconds, maximum cost `$0.00`.
- State: `succeeded`; workload result status: `passed`.
- Generated text: `Once upon a time, there was a little girl named Lily. She loved to play with her toys and eat yummy snacks`
- Runtime: 430 ms; generated tokens: 24; temperature: 0.8.
- Model: `karpathy/tinyllamas@0bd21da7698eaf29a0d7de3992de8a46ef624add/stories15M.bin`
- Model SHA-256:
  `cd590644d963867a2b6e5a1107f51fad663c41d79c149fbecbbb1f95fa81f49a`
- Prompt SHA-256:
  `e286222c229ec73b1bc520d88583191572ae0cbbaa66ea68053994a5e50ac87a`
- Result checksum:
  `37ee4f7a9a814c9333258a29ae4723ae30e0fd4e3cae634f9d4bf2d11dca71e9`
- Passed checks: source identity, parameter bounds, model digest, completed
  inference, non-root execution, no secret environment, no Docker socket,
  read-only root filesystem, and disabled network.
- `gpu_used=false`; `cleanup_state=confirmed`.
- The result was separately retrieved with `experiment_result` after status
  reported success. D1 retained run, plan, source, image, and model identity.

## Provenance correction record

Two earlier ChatGPT runs (`a514f038b9e24bed954d0bc7874ba679` and
`ee5bf84faad040aaabf3743057360824`) generated the same text and completed
cleanup, but their registered source label was
`3cc7a7685c6e9890c9896f6bd77fbb589b89d8e2`. `git cat-file -t` confirmed that
value is not an object in the root repository. The earlier image and runs are
retained in D1 as history but are **not** counted as provenance acceptance.
The image was rebuilt with the actual pushed commit `3cc7a765...`, registered
under its new digest, and the run above repeated successfully. The new full SHA
and image digest are the authoritative values.

## Remaining gates

- One provenance-valid output does not establish statistical quality,
  repeatability across prompts, or useful training performance.
- No injected Runner crash, cancellation race, lease expiry, or restart recovery
  was exercised. The controlled Runner credential/image replacement is not a
  recovery rehearsal.
- Cross-account owner isolation and access revocation remain unverified.
- R2 upload and bounded artifact retrieval have been accepted for three
  artifacts; retention policy, orphan cleanup, larger artifacts, and recovery
  across a Runner restart remain open.
- GPU and paid execution remain parked. No provider was called and no billable
  compute was used.
- The dormant Neon project still contains legacy authentication/run data and
  must not be deleted until an export and retention decision are verified.
- Vercel is not part of this deployed path. Historical Vercel/Neon resources
  have not yet been retired.

## Live rechecks — 2026-11-12

The production Sites deployment is still Version 11 (`appgdep_6af4d87aee20819197c9ff12ed9e81fa`, `succeeded`, MCP enabled). Saved Versions 12 and 13 remain undeployed. Capabilities reported the Runner ready, free CPU admission enabled, one in-flight slot, a 30-second maximum, and paid execution parked.

- Run `6b4cabf7b6aa4aea826c4c8e672705b3` was re-read through the ChatGPT status and result tools. It used the registered source commit and image above, generated 32 tokens in 631 ms, passed identity/sandbox checks, returned `gpu_used=false`, and confirmed cleanup. Its prompt text mentioning cancellation does not mean a cancellation event was exercised.
- Run `5447466fe7f9413980d2b47a2b079289` was prepared, submitted, polled, and retrieved through the ChatGPT tools. It used prompt `A tiny red fox`, seed `61117`, and a four-token limit; it generated four tokens in 150 ms, passed source/model/parameter and container-isolation checks, returned `gpu_used=false`, and confirmed cleanup at a `$0.00` ceiling. Result artifact metadata reports 961 bytes and SHA-256 `3eca2a067a2230b5de6272850eaeac6cc8bf91684293e125a6029c93f0cc456e`; this run's full R2 artifact bytes were not separately fetched.

These rechecks prove more bounded CPU inference on the current Version 11 path. They do not validate Version 13's D1 migration, a live Runner restart, cancellation, cross-owner isolation, or paid/GPU execution.

## Current live refresh — 2026-11-12

The Sites version inventory now shows Version 14 deployed successfully with
MCP enabled at `https://gpu-control-sites.unjuno.chatgpt.site`:

- Deployment: `appgdep_6af5027bff688191b429517650af2496`
- Sites source-repository commit: `1f0a2d49dc0918411cbe1984d5369f365b862839`
- The Sites source commit is distinct from the registered workload source SHA
  below. Version 14 is the currently deployed Sites source; the workload SHA is
  separately registered in D1 as `3cc7a765cbcbeb7abdfa0d607e8a44e4cdff2288`.
- Capabilities recheck reports the fixed TinyStories workload available,
  Runner ready, admission enabled, free local CPU, one in-flight run, 30-second
  maximum, and paid execution parked.

A fresh ChatGPT tool run was prepared, submitted, polled, and retrieved:

- Run ID: `22a28cca6479404aa0dc9206490111de`
- Parameters: prompt `A tiny robot found a blue seed.`, seed `61117`,
  `max_new_tokens=12`, runtime ceiling 30 seconds, cost ceiling `$0.00`.
- Workload source: `3cc7a765cbcbeb7abdfa0d607e8a44e4cdff2288`; image:
  `sha256:f0e1bbd44e0bd475dc2f19a548a96e041fc9cb48fc4160d4c0c4de02b0e00541`.
- State: `succeeded`; result status: `passed`; generated 12 tokens in 310 ms.
- Result: `A tiny robot found a blue seed. He was so happy! He had been looking for a way`
- Checks passed: registered source identity, parameter bounds, model digest,
  inference completion, non-root, no secret environment, no Docker socket,
  read-only root filesystem, and disabled network. `gpu_used=false` and
  `cleanup_state=confirmed`.
- ChatGPT separately retrieved the R2 `result.json` artifact; the tool verified
  its 1,003-byte payload against SHA-256
  `9ff9c340788e6bd4c428c8750a655ceac01d32b55fcbac35cc30d9c18782f119`.

This refresh supersedes the earlier Version 11 live-status snapshot above. It
validates the current free CPU inference and artifact-read path only; it does
not close restart/cancellation recovery, cross-owner isolation, backup/restore,
retention/orphan cleanup, real GPU, or paid-execution gates.

## Version 15 and hardened live Runner refresh — 2026-11-12

The private Site was updated to Version 15, deployment
`appgdep_6af5169fa69c8191b4dca5bb77272c84`, from Sites source commit
`e3cfaf71c5f084c6a6ab40adbae8e189327197ad`. The change hardens macOS Runner
Keychain credential loading and LaunchAgent file handling. The deployed
runtime admission policy was not changed.

The local LaunchAgent was already running. Its `run.py` and Keychain launcher
SHA-256 values match the published source; Keychain items exist without reading
their values, and plist/runtime files have mode `0600`. No restart or
credential rotation was needed for this validation. The partial-coverage static
security review found no actionable finding; it is not a live restart, ACL, or
rotation test.

A new ChatGPT-originated inference completed after deployment:

- Run `a1cdf7e9516b4a00802b6b606f228b08`, prompt `A purple seed appeared.`,
  seed `61118`, eight-token limit; generated eight tokens in 227 ms.
- Registered workload source
  `3cc7a765cbcbeb7abdfa0d607e8a44e4cdff2288`; image
  `sha256:f0e1bbd44e0bd475dc2f19a548a96e041fc9cb48fc4160d4c0c4de02b0e00541`.
- Source, parameter, model digest, inference, non-root, secret-free environment,
  no Docker socket, read-only filesystem, and no-network checks passed.
- `gpu_used=false`, cleanup confirmed, and provider cost `$0.00`.
- ChatGPT retrieved the 979-byte R2 result artifact; SHA-256
  `bb7a05682bfbb1903abd26118cdcc1128bd9aff81b545e72a5e59a805af0311e`.

This remains CPU-only acceptance. Forced restart, interruption/cancellation,
lease expiry/reconciliation, Keychain ACL and rotation, cross-owner isolation,
backup/restore, retention/orphan cleanup, GPU, and paid execution remain open.

## Live cancellation acceptance — 2026-11-12

Run `0a61c2b307f14dfbb94d9791ff7d7139` used the registered CPU workload,
source `3cc7a765cbcbeb7abdfa0d607e8a44e4cdff2288`, image
`sha256:f0e1bbd44e0bd475dc2f19a548a96e041fc9cb48fc4160d4c0c4de02b0e00541`,
and a 32-token maximum with a `$0.00` cost ceiling. The run was observed in
`running` state when cancellation was requested. The status tool subsequently
reported `state=cancelled`, `failure_code=caller_cancelled`,
`cancellation_requested=false`, and `cleanup_state=confirmed`. A separate
capabilities read confirmed the Runner was ready and one-slot CPU admission was
available again. No result artifact was expected for a cancelled run.

This verifies caller-requested cancellation and cleanup on the live free CPU
route. It does not verify forced Runner termination, lease-expiry recovery,
restart reconciliation, cross-owner cancellation denial, or GPU/paid execution.

## Planned Runner restart acceptance — 2026-11-12

Before restarting the local Runner, D1 run inventory showed no queued or active
runs. The owner-private Site's `CPU_WORKLOAD_ADMISSION_ENABLED` was changed to
`false` (environment revision 11), and the same saved Version 15 was deployed
successfully as `appgdep_6af51a366ba481918b161ffda837486e`. Capabilities then
reported `available=false`, `runner_ready=true`, and `admission_enabled=false`.

The LaunchAgent `--stop` returned success. Its status reported `not loaded`,
the previous Runner PID had exited, and no process matching either managed
Runner entrypoint remained. LaunchAgent `--start` returned success and loaded a
new process (PID 72010). While admission remained closed, a fresh capabilities
read reported the Runner ready. Admission was restored to `true` (environment
revision 12) and the same Version 15 was deployed successfully as
`appgdep_6af51a9b39188191851d8d2b0a8eb487`.

A post-restart inference then completed:

- Run `6c817aa27a8842eda0bc07c7e5396776`, prompt
  `A tiny lantern glowed beneath the winter moon.`, seed `719241`, eight-token
  maximum; generated eight tokens in 330 ms.
- The registered source and image identities matched; all nine workload
  provenance and isolation checks passed, `gpu_used=false`, and cleanup was
  confirmed at `$0.00`.
- ChatGPT retrieved the entire 1,005-byte `result.json` artifact. Its locally
  computed SHA-256, `15c464657fe126108c6835e3049ad5d822711d791255ca52909dac121d56473d`,
  matched the D1 artifact metadata.

This proves an orderly admission-gated LaunchAgent stop/start and successful
post-restart work. It does not prove forced process death, crash/lease-expiry
recovery, secret rotation, or owner-isolation behavior.

## Active-run Runner process-loss and lease recovery acceptance — 2026-11-12

Before the probe, Sites capabilities reported the free CPU Runner ready and
admission enabled; D1 listed no active run, and Docker had no containers with
the GPU Control run label. A registered 32-token, 30-second CPU inference was
prepared with a `$0.00` cost ceiling:

- Run `0c3dd2ecf3d34355b6faa63a842d83c7`, source
  `3cc7a765cbcbeb7abdfa0d607e8a44e4cdff2288`, image
  `sha256:f0e1bbd44e0bd475dc2f19a548a96e041fc9cb48fc4160d4c0c4de02b0e00541`.
- A host watcher waited for that exact run's labeled container to be active,
  then sent SIGKILL to the LaunchAgent-owned Runner PID. The observed container
  exited with code 0, while D1 correctly retained the run as `running` under
  its lease because the Runner died before reporting the result.
- launchd automatically restarted the service. The D1 lease was 180 seconds;
  after expiry, Runner recovery found and removed the stopped container, then
  sent its recovery receipt. The authoritative D1 row became `failed`,
  `failure_code=runner_lost_recovered`, `attempt=1`,
  `cleanup_state=confirmed`, and both lease fields were cleared. No result
  artifact was recorded and the run was not automatically retried.
- A Docker inventory query found no container remaining with the run label.
  ChatGPT status confirmed the terminal state, Sites capabilities reported the
  Runner ready and free admission available, and no other run was active.

A new run then proved that admission capacity remained usable:

- Run `aa45b7d899de4c9aaff2ee73fa985cc6`, prompt
  `A little bird found a bright blue feather.`, seed `719243`, eight-token
  maximum; generated eight tokens in 291 ms.
- The registered provenance and all nine isolation checks passed;
  `gpu_used=false`, cleanup confirmed, and cost `$0.00`.
- ChatGPT retrieved the full 999-byte R2 `result.json`. Its locally computed
  SHA-256 `dae639f57be6cd5cadfc78d07b9169dfe2442cc0137c7e63cdf747366e405fc9`
  matched D1 metadata.

This is one live active-run process-loss/lease-expiry recovery acceptance. It
does not establish repeated reliability across every crash window, recovery of
a container that remains active past lease expiry, owner-isolation behavior,
credential rotation, or paid/GPU recovery. Sanitized Runner logs contained
transient `SITE_REQUEST_FAILED` entries during the observation interval; later
Worker logs showed successful heartbeat, recovery, and claim requests (HTTP
200), and the run and container state converged as recorded above. Investigate
the transient transport errors before increasing admission.

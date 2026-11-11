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

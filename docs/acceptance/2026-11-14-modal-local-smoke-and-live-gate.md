# Modal CPU local smoke and live gate — 2026-11-14

## Current hosted state

- The public ChatGPT Site is Version 33 from source commit
  `c85fdf7da994ab59b8a19bbb42b2998bc9814e69`, with environment revision 36.
- The live environment has `CPU_WORKLOAD_ADMISSION_ENABLED=false`, the registered
  image digest `sha256:f0e1bbd44e0bd475dc2f19a548a96e041fc9cb48fc4160d4c0c4de02b0e00541`,
  and fingerprint `8a786eb77ff845ed053ce939a4f4601705c01defb2b6fab7c1dd804ca04b09c5`.
  Capability reads report admission disabled. No post-deployment health call or
  inference has been accepted.
- Modal Usage showed `$0.10` total for the November billing cycle. The Workspace
  usage limit was previously observed at `$1`; recheck both usage and the limit
  before any provider call. The user's authorization is `$1` aggregate for this
  project's testing, not `$1` per execution. Modal control-function usage counts
  toward the Workspace total.
- The Modal Workspace API-token list showed zero active tokens after the
  temporary deploy token was revoked.
- The newest recorded Modal-origin sandbox, `e9330c5bb5454f42bb3dabe058091dc0`,
  was created on November 12. It failed after 247 ms with exit code 2, had no
  Modal logs, and recorded cleanup as confirmed. This run predates the November
  14 deployment and does not establish a failure in that deployment.

## Local reference-container verification

- Built the pinned `tiny_stories_inference` Dockerfile with the repository's
  cached, digest-verified base image, C runner, model, and tokenizer.
- Ran the production `sandbox_entrypoint()` locally in OrbStack with the
  Modal-like constraints: 1 CPU, 512 MiB, read-only root filesystem, network
  disabled, and root startup followed by the bootstrap's UID/GID drop to 10001.
  The registered source SHA, one-token `Once` prompt, and seed 61112 were used;
  local-only run and fingerprint identifiers were synthetic.
- The container exited 0 and returned a valid `tiny-stories-inference-v1`
  result: `Once upon`, one generated token, `gpu_used=false`, and all nine
  declared checks passed. No provider API, Site authorization, or Modal Sandbox
  was used. The temporary local image was removed afterward.
- `PYTHONPATH=src python3 -m pytest tests/test_modal_bootstrap.py -q` passed all
  7 tests. The first invocation without `PYTHONPATH=src` stopped at test
  collection because this checkout was not installed as a package; no
  dependencies were installed.

## Interpretation and remaining acceptance

The pinned model, tokenizer, workload, and fixed bootstrap pass in the local
reference container. The available remote failure is historical and has no
logs, so its cause is not established. Do not change the workload based only on
that failure. A fresh health check and one exact-plan Modal inference are still
needed against the current deployment.

The Site confirmation link currently redirects to OpenAI sign-in. The old exact
plan expired before confirmation. After owner sign-in, create a fresh plan and
confirm its displayed fingerprint and cost on the Site; then check provider
health and run the single bounded inference. Recheck the `$1` aggregate budget
before calling the provider. Keep admission closed except for that authorized
acceptance step, and verify result provenance and cleanup afterward.

The repository-wide Codex Security review remains incomplete at 34 of 335
coverage rows, with no report. No security clearance is claimed. RunPod and GPU
execution remain parked and unconnected to the Site Worker.

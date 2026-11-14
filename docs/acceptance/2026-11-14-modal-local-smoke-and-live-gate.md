# Modal CPU local smoke and live gate — 2026-11-14

## Current hosted state

- The public ChatGPT Site is Version 33 from source commit
  `c85fdf7da994ab59b8a19bbb42b2998bc9814e69`, with environment revision 36.
- The live environment has `CPU_WORKLOAD_ADMISSION_ENABLED=false`, the registered
  image digest `sha256:f0e1bbd44e0bd475dc2f19a548a96e041fc9cb48fc4160d4c0c4de02b0e00541`,
  and fingerprint `8a786eb77ff845ed053ce939a4f4601705c01defb2b6fab7c1dd804ca04b09c5`.
  Capability reads report admission disabled. No post-deployment health call or
  inference has been accepted.
- Modal Usage last showed `$0.10` total for the November billing cycle. The Workspace
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

The Site confirmation link redirects to OpenAI sign-in because the current
browser session is not authenticated to the Site. A fresh exact plan was
prepared, but expired before confirmation; no health call or Sandbox request
was made. After owner sign-in, create another fresh plan and confirm its exact
fingerprint and cost on the Site. The official Modal pricing page was checked
again on November 14; the 30-second, 1-core, 512-MiB Sandbox estimate remains
about `$0.0013`, while control-function charges are separate. Recheck Workspace
usage and its `$1` limit before any provider call. Keep admission closed until
the authorized acceptance step, then verify result provenance and cleanup.

The repository-wide Codex Security review is still incomplete at 45 of 335
files. Its draft has zero confirmed findings so far, but is partial and has no
final report; this is not security clearance. RunPod and GPU execution remain
parked and unconnected to the Site Worker.

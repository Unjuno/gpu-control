# Four-provider resource bootstrap — 2026-11-21

This record covers resource existence only. It does not claim provider
execution, quota availability, credential configuration, ChatGPT end-to-end
acceptance, or cleanup acceptance.

## Architecture boundary

- ChatGPT Sites with D1/R2 remains the public control plane.
- The compute providers are exactly Modal, RunPod, Kaggle, and Hugging Face.
- Railway, Vercel, Neon, and a separately hosted PostgreSQL Gateway are not in
  the execution path.
- Candidate commit `3f2770b` changed the Modal provider-adapter image from a
  copy of the complete legacy Gateway tree to an explicit seven-file provider
  module allowlist. The image no longer packages the Gateway API, OAuth,
  worker, store, migration, or service modules.

## Local fixed-payload verification

The public `Unjuno/orbitune` checkout resolved exactly to
`44a1b806160ab5bc721a370d034a6dfcb28f27a8`. Rebuilding both registered
payloads from that clean detached checkout produced:

- Kaggle staged image digest:
  `sha256:3f764ee4d610edfbe6b07769538ffbae8413b9df47c05af783245d65c7c21bed`
- ZeroGPU Space payload digest:
  `sha256:381d661e4ed646df2e7110df23f80a4dab554af5d3abea333c1c3127bcd9e209`
- Original registered Space contract digest before the upload refresh:
  `sha256:f0c1b097b3ed4a7cc356d77f1d9b8fbaffc8445b9168f02dba2a713741be6537`

The Kaggle digest matched the candidate registry. The exact reviewed Space
root payload was uploaded through the authenticated private-repository UI. The
resulting immutable Space revision is
`2e9df7dcd8815cf3059ae94ce6504315e63a85ab`; the contract digest recomputed
from that revision is
`sha256:5d0757c0c6d35514bdd26618a11e028b635d766612c18404551007b2c168ac68`.
Both values are now pinned in the candidate registry.

## Hugging Face

- `hf auth whoami` identified the CLI session as `Unjuno` without printing a
  token.
- The CLI credential could read identity but received HTTP 403 for repository
  creation, so it was not treated as a deployment credential.
- The authenticated browser account created these resources as private:
  - model repository `Unjuno/gpu-control-orbitune-artifacts`
  - Space `Unjuno/gpu-control-orbitune-zero-gpu`, configured as ZeroGPU Free
- A follow-up settings read confirmed the Space access control is `Private`,
  its current hardware is `ZeroGPU` marked `Free`, and the analytics view has
  no recorded ZeroGPU runs.
- The public Space variable `GPU_CONTROL_HF_ARTIFACT_REPO` exists. The Space
  reports no configured secrets, so it cannot yet read the private artifact
  repository.
- The reviewed app/requirements/README payload is uploaded, the existing
  vendored Orbitune package remains present, and the private Gradio app reached
  `Running on ZERO` with its expected bounded UI. No artifact, provider token,
  or Space secret was uploaded.
- No `/evaluate` request or GPU function was started.

## Kaggle

- The authenticated browser showed account `UnjunoOrg`.
- Its private Code/Notebook list returned `No results found`.
- Therefore the registered resource `UnjunoOrg/orbitune-100-step` does not yet
  have an observed provider object or immutable version.
- No Notebook was created or submitted and no GPU quota was consumed.

## Current blockers

1. Configure distinct read-only Space and worker-only artifact credentials
   without exposing them to ChatGPT, Git, logs, or Kaggle.
2. Create the fixed private Kaggle Notebook from the staged payload and record
   its exact version without submitting a run.
3. Configure the authenticated Modal adapter and re-read four-provider Sites
   capabilities before any owner-confirmed free-quota canary.

Until those steps and the separate one-use execution confirmations are
complete, Kaggle and Hugging Face must remain advertised as unavailable.

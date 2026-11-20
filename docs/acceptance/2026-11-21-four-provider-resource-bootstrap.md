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
- Registered Space contract digest for the pending revision:
  `sha256:f0c1b097b3ed4a7cc356d77f1d9b8fbaffc8445b9168f02dba2a713741be6537`

The Kaggle digest and Space contract digest match the candidate registry. The
Space payload digest is staging evidence; it does not become an approved Space
revision until those exact bytes are uploaded and the resulting immutable Hub
commit is written back to the registry.

## Hugging Face

- `hf auth whoami` identified the CLI session as `Unjuno` without printing a
  token.
- The CLI credential could read identity but received HTTP 403 for repository
  creation, so it was not treated as a deployment credential.
- The authenticated browser account created these resources as private:
  - model repository `Unjuno/gpu-control-orbitune-artifacts`
  - Space `Unjuno/gpu-control-orbitune-zero-gpu`, configured as ZeroGPU Free
- No payload, artifact, provider token, or Space secret was uploaded.
- No evaluation request or GPU function was started.

## Kaggle

- The authenticated browser showed account `UnjunoOrg`.
- Its private Code/Notebook list returned `No results found`.
- Therefore the registered resource `UnjunoOrg/orbitune-100-step` does not yet
  have an observed provider object or immutable version.
- No Notebook was created or submitted and no GPU quota was consumed.

## Current blockers

1. Upload the exact staged Space payload using a write-capable Hub session,
   then replace the placeholder Space revision and recompute the contract
   digest from the observed immutable revision.
2. Configure distinct read-only Space and worker-only artifact credentials
   without exposing them to ChatGPT, Git, logs, or Kaggle.
3. Create the fixed private Kaggle Notebook from the staged payload and record
   its exact version without submitting a run.
4. Configure the authenticated Modal adapter and re-read four-provider Sites
   capabilities before any owner-confirmed free-quota canary.

Until those steps and the separate one-use execution confirmations are
complete, Kaggle and Hugging Face must remain advertised as unavailable.

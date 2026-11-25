# Modal live GPU canary — 2026-11-22

## Scope

This record covers one owner-authorized run of the fixed
`modal-gpu-vector-add-v1` workload through the production ChatGPT Sites MCP
control plane. It does not authorize arbitrary Modal code or a standing GPU
worker.

## Account and project bounds

- Modal Workspace: `unjuno`, environment `main`
- Modal Workspace usage limit observed immediately before planning: `$30.00`
- Billing-period usage observed immediately before planning: `$0.28` in credits
  and `$0.00` in charges
- GPU Control internal Modal GPU monthly ceiling: `$1.00`
- GPU Control per-run ceiling: `$0.01`
- Runtime: 30 seconds maximum
- Hardware: one T4
- Network: blocked
- Secrets attached to workload: none

The provider-account `$30.00` usage limit and the project-internal `$1.00`
ledger are independent. The candidate was corrected at commit `cc27d05` so the
short-lived provider evidence records the actual outer limit while D1 continues
to enforce the stricter internal project ceiling.

## Exact plan

- run ID: `d9df87e10615abbf5edac9acc0ad82be`
- plan fingerprint:
  `866f81dc82d1d5788a815699922f5734866c4a0ee9e327673e2cc238bfbc467d`
- source SHA: `58a24082b73238b982e64a17b7d0624fc2594bab`
- image digest:
  `sha256:b0840d8b2a13e573141e158c50f1f8375a7eb853529172effea49cacfc10c919`
- account-evidence ID:
  `28f06fa35681ffbbd5d3250613418a4aafbe2dff7c9307cc387a7b0ac2f98dfc`

## Result

The authenticated ChatGPT connector returned a terminal `succeeded` result:

- `provider=modal_gpu`
- `gpu_used=true`
- device: `Tesla T4`
- device count: `1`
- CUDA compute capability: `7.5`
- operation: `u32_vector_add_4`
- output SHA-256:
  `012355774c270a50ab691a34a8200062a5c179a8f7021461aa505d47fcc327cb`
- result checksum:
  `4871a94f8d5a098a63b59d5914363f25eca42b506aeb93482c232921d689e345`
- cleanup state: `confirmed`

The evidence proves the bounded production ChatGPT-to-Sites-to-Modal GPU route
for this registered canary. It does not prove Kaggle allocation or Hugging Face
ZeroGPU execution.

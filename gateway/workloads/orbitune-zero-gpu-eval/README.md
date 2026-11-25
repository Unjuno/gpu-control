---
title: GPU Control Orbitune ZeroGPU Evaluation
emoji: 🔒
colorFrom: gray
colorTo: blue
sdk: gradio
sdk_version: 6.32.0
python_version: 3.12.12
app_file: app.py
pinned: false
---

# Orbitune ZeroGPU evaluation Space

This is the reviewed three-endpoint contract consumed by
`HuggingFaceSpaceBackend`. Deploy it only to an allowlisted private Space.
Public visibility would let direct callers bypass Gateway approval and quota
checks and consume the owner's ZeroGPU allocation. Before deployment:

1. Build the upload payload with `stage_orbitune_zero_gpu_space()` from a clean
   checkout at `44a1b806160ab5bc721a370d034a6dfcb28f27a8`; do not vendor a floating tree.
2. Use the checked-in `requirements.txt` with the README `sdk_version`. ZeroGPU
   supplies a supported PyTorch runtime, so do not add an independently floating
   or incompatible PyTorch requirement.
3. Configure ZeroGPU `large`, set `GPU_CONTROL_HF_ARTIFACT_REPO` to the one
   allowlisted private model repository, and set `HF_READ_TOKEN` to a distinct
   read-only token. Never reuse the worker write token.
4. Record the exact Space commit and compute the contract digest with
   `space_contract_digest(space_id, revision)` for the workload registry.
5. Confirm `view_api(return_format="dict")` exposes no unnamed endpoints and
   exactly `/evaluate`, `/status`, and `/cancel`, including the registered input
   labels/components and a single JSON result.

The app does not persist results across a Space restart. A missing request is
reported failed, never re-evaluated automatically.

The `/cancel` endpoint is an idempotent status contract, not proof that an
already allocated GPU function was interrupted. The provider registry therefore
advertises cancellation as unsupported after acceptance.

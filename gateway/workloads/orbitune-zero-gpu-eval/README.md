# Orbitune ZeroGPU evaluation Space

This is the reviewed three-endpoint contract consumed by
`HuggingFaceSpaceBackend`. Before deploying it to an allowlisted private or
public Space:

1. Vendor the `orbitune/` package from commit
   `44a1b806160ab5bc721a370d034a6dfcb28f27a8` into the Space repository.
2. Lock Gradio, `spaces`, `huggingface_hub`, PyTorch and transitive dependencies
   to versions currently supported by ZeroGPU. Do not deploy a floating
   requirements file.
3. Configure ZeroGPU `large`, set `GPU_CONTROL_HF_ARTIFACT_REPO` to the one
   allowlisted private model repository, and set `HF_READ_TOKEN` to a distinct
   read-only token. Never reuse the worker write token.
4. Record the exact Space commit and compute the contract digest with
   `space_contract_digest(space_id, revision)` for the workload registry.
5. Confirm `view_api(return_format="dict")` exposes exactly `/evaluate`,
   `/status`, and `/cancel` with 3, 1, and 1 parameters respectively.

The app does not persist results across a Space restart. A missing request is
reported failed, never re-evaluated automatically.

The `/cancel` endpoint is an idempotent status contract, not proof that an
already allocated GPU function was interrupted. The provider registry therefore
advertises cancellation as unsupported after acceptance.

# Kaggle and Hugging Face Integration Plan

Spec: `/Users/taka/.codex/attachments/25cf9af7-9576-4395-bf71-5759c74a581c/Pasted text.txt`

## Global constraints

- Preserve parked mode and every existing spend, approval, credential, and account-isolation gate.
- Do not submit live Kaggle, ZeroGPU, Hugging Face Jobs, Modal GPU, or RunPod work while parked.
- Restore the deleted Gateway control-plane core without restoring Vercel as a deployment dependency.
- Use only official Kaggle CLI/API and `huggingface_hub`/Gradio APIs.
- Keep MCP semantic tools provider-neutral; add providers through the registry.
- Keep Kaggle and Hugging Face credentials out of submitted workloads and persisted handles.
- Never retry an ambiguous provider-side creation automatically.
- Keep PR #68 Draft; do not merge without explicit owner approval.

## Task 1: Restore and baseline the Gateway core

Restore the deletion-parent Gateway implementation, excluding the duplicate `gateway/project_control` tree. Run its offline test suite and record any pre-existing failures.

## Task 2: Add Kaggle backend offline-first

Add registry wiring and an injectable official-CLI adapter. Test prepare-without-submit, exact argv, quota fail-closed behavior, ambiguous submission reconciliation without duplicate push, immutable owner/kernel/version/source binding, bounded logs/output, restart reconciliation, cleanup, and honest cancellation capability.

## Task 3: Add Hugging Face artifact store

Add an injectable `huggingface_hub` artifact service with private repositories by default, repository allowlisting, checksum verification, immutable revision capture, independent re-download verification, and no token material in Kaggle payloads.

## Task 4: Add Hugging Face Space evaluation backend

Add a short inference/evaluation backend for approved Gradio ZeroGPU Spaces. Test allowlisting, quota introspection and fail-closed overquota behavior, bounded duration/results, reconciliation, and separation from paid Hugging Face Jobs.

## Task 5: Integrate policy, MCP, recovery, and Orbitune workload

Expose capabilities through the existing provider-neutral registry and MCP tools without duplicate provider-specific tool surfaces. Add a trusted Orbitune 100-step workload manifest and tests for evidence fields, checkpoint publication, independent reload/evaluation, recovery, and cleanup state.

## Task 6: Verify and prepare Draft PR evidence

Run the complete relevant Python, worker/Sites, policy, packaging, and security suites. Perform a whole-branch review. Push only after fresh verification, update Draft PR #68, and leave all live provider acceptance items explicitly pending until parked mode and owner action gates are deliberately opened.

# P4 Modal readiness — 2026-10-28

## Scope and disposition

Official Modal Sandbox and pricing documentation were reviewed on 2026-10-28
against the current Gateway adapter. The adapter already has an offline,
worker-only Modal Sandbox integration, but neither a real GPU run nor the
account-specific billing controls have been verified. **Modal is not accepted
as a zero-additional-cost GPU path.** Keep its switch disabled and preserve
`mode: parked`.

## Current code evidence

- `gateway/gpu_gateway/backends.py::ModalSandboxBackend.start` consumes an
  operator-registered workload manifest, looks up an existing Modal app
  (`create_if_missing=False`), uses a prebuilt Modal image ID and fixed argv,
  passes the configured GPU/CPU/memory and runtime limit, and requests
  `block_network=True`. No tool-supplied command, image build, or provider
  credential is accepted.
- Cancellation calls `terminate(wait=True)`. Inspection polls the Sandbox,
  captures bounded output only after it exits, and records its exit code.
  `reconcile` looks up the existing sandbox by its stable name and never
  submits a replacement.
- `GATEWAY_ENABLE_MODAL` defaults to false. The documented Modal SDK credential
  belongs on the worker, not the API or browser deployment.
- Workload metadata supports a provider quote and expiry, but the account's
  actual plan, usage, workspace budget, included credit balance, overage
  behavior, and GPU quota have not been observed. No Modal call was made.

## Current official provider evidence

- Modal's Sandbox guide documents a default five-minute maximum lifetime and a
  configurable maximum of 24 hours. It documents idle timeout, process exit,
  explicit termination, and returned exit codes. The implementation supplies
  a workload-specific timeout and blocks outbound networking; it does not
  configure `idle_timeout`.
- The pricing page currently lists Starter at $0/month with $30/month of
  included compute usage, then pay-as-you-go compute. It describes workspace
  budgets as the way to cap out-of-pocket charges. It also lists storage and
  network-egress rates/allowances separately. Included credit is not proof of
  an account-wide zero-dollar ceiling, and a price listing is not an estimate
  for this workload.
- A workspace budget, account quota, included-credit eligibility, and effective
  hard stop cannot be inferred from public docs. They require read-only review
  of the actual Modal workspace settings by its owner. A budget's behavior and
  scope must be verified before treating it as an enforceable cap.

Official sources:

- [Modal Sandboxes](https://modal.com/docs/guide/sandboxes)
- [Modal sandbox networking](https://modal.com/docs/guide/sandbox-networking)
- [Modal pricing and spend limits](https://modal.com/pricing)

## P4 gaps and next evidence

1. Inspect the selected Modal workspace's plan, included usage, GPU quota,
   budget scope, overage behavior, and hard-stop semantics without launching a
   Sandbox. Do not save or reveal credentials in this record.
2. Add workload capability and cost-selection evidence for CPU, GPU/VRAM,
   architecture, runtime, timeout, network/result collection, and cleanup.
   Distinguish availability from cost class; unknown quota or an unenforceable
   zero-cost requirement must block submission.
3. Bind a current, concrete resource quote and all-in CPU/RAM/GPU/storage/egress
   estimate to the exact registered workload and expiry.
4. Only after the independent cost, authorization, and security gates are
   satisfied, run an approved, bounded GPU smoke and record device/VRAM,
   provider handle, usage, exit status, retrieved result, cancellation, and
   independent cleanup evidence. A self-reported metric is not scientific
   quality evidence.

This record is provider-doc and source review evidence only. It does not prove
account eligibility, live API compatibility, GPU execution, spend prevention,
cleanup, or semantic/model quality. No paid or external compute was started.

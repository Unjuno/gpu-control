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
- Modal now documents two separate controls: a Workspace budget caps total
  usage before credits; a Workspace spend limit caps net out-of-pocket charges.
  At the spend limit, workloads that would incur additional out-of-pocket cost
  stop, while workloads still covered by applicable credits may continue until
  the usage limit is reached. Therefore a zero spend limit can be a hard guard
  against new out-of-pocket charges, but does not prove that a particular run
  has enough eligible remaining credit to finish or that every component
  (especially storage/egress) is covered.
- Public pricing currently lists Starter's $30/month included compute credit
  and separately priced GPU, CPU, memory, volume and egress usage. These public
  rates do not establish the selected workspace's plan, effective limits,
  remaining applicable credit, GPU quota, or an all-in run estimate.
- The current offline core now records gross per-run component estimates and
  explicit, expiring quota evidence with usage headroom, credit balance, and
  eligible component coverage. Its
  selector rejects stale/insufficient balances, uncovered components, and
  missing hard-stop evidence for zero-additional-cost `CREDIT_BACKED` choices.
  Core `revalidate_approved_candidate` also rejects changed/expired
  workload/provider/resource/evidence fingerprints without selecting a
  substitute. Gateway provider-evidence ingestion and calls to this revalidator
  immediately before submit and worker launch are still missing. A spend-limit
  setting alone must never be treated as proof that a particular run is
  credit-covered.
- The workspace's effective budget, spend limit, remaining applicable credit,
  GPU quota, and actual overage behavior still require a read-only owner review.
  Public documentation cannot substitute for those account-specific values.
- Current official SDK reference exposes read-only `Workspace.billing.rates()`,
  resource/time `report()`, and cycle `summary()` operations. The summary
  documents `metered_cost`, `billed_cost`, `adjustments`, and metered-cost
  breakdown; `rates()` returns current cost values; `report()` attributes usage
  by object/time/resource. These APIs can contribute current pricing and
  observed-usage evidence to a future adapter.
- Official-doc refresh on 2026-10-28: Modal's current egress guide says egress
  became billable on October 1, 2026, with plan-specific included allowances;
  Workspace billing summary/report and rates expose egress usage/cost data.
  Reads and writes to Modal Volumes do not count as egress, while transfers
  from a Volume to an external service do. This supersedes any earlier
  assumption that egress evidence was not available through SDK billing APIs.
  The billing summary remains retrospective cost evidence: it does not expose
  remaining eligible credits by component, quota headroom, or a per-run hard
  stop, so it cannot by itself construct `QuotaEvidence` or prove zero
  out-of-pocket risk. See [egress billing](https://modal.com/docs/guide/network-egress-billing),
  [Workspace billing SDK](https://modal.com/docs/sdk/py/latest/Workspace), and
  [budgets and spend limits](https://modal.com/docs/guide/budgets).
- The documented `Workspace.settings.list()` returns `WorkspaceSettings`, but
  the reference does not define fields for current usage headroom, eligible
  remaining credit by charge component, configured workspace/environment
  budgets, net-spend limit, or stop-on-overage state. Billing summaries do not
  document these fields either. Do not infer them from usage totals or public
  plan credits: a future collector must leave `QuotaEvidence` incomplete unless
  it obtains exact current values and provenance for every required field.
  A local read-only collector now exists at `gateway/gpu_gateway/modal_evidence.py`.
  It accepts an injected Workspace object, calls only `billing.rates()` and
  `billing.summary()`, and emits bounded, fingerprinted `billing_only` data
  with `selection_eligible: false` and `quota_evidence:
  NOT_AVAILABLE_FROM_THIS_RESPONSE`. It deliberately does not import Modal,
  obtain credentials, inspect an account, or construct `QuotaEvidence`.
  Twelve offline unit cases cover its input bounds and read-only contract; this
  verifies the adapter behavior against fakes, not live SDK/account behavior.
  Provider evidence ingestion and submit/worker revalidation remain open.
  Until then, zero-additional-cost selection remains blocked. References:
  [Workspace billing API](https://frontend.modal.com/docs/sdk/py/latest/Workspace),
  [Modal budgets and spend limits](https://modal.com/docs/guide/budgets).

Official sources:

- [Modal Sandboxes](https://modal.com/docs/guide/sandboxes)
- [Modal sandbox networking](https://modal.com/docs/guide/sandbox-networking)
- [Modal pricing and spend limits](https://modal.com/pricing)
- [Modal budgets and spend limits](https://modal.com/docs/guide/budgets)

## P4 gaps and next evidence

1. Inspect the selected Modal workspace's plan, included usage, GPU quota,
   budget scope, overage behavior, and hard-stop semantics without launching a
   Sandbox. Do not save or reveal credentials in this record.
2. Connect the current Modal account snapshot to `QuotaEvidence`, preserve the
   separation between gross per-run cost, eligible credit, usage headroom, and
   provider net-spend/usage limits, then wire exact-candidate revalidation into
   prepare/approval/submit and worker launch. Offline stale/insufficient/
   uncovered-credit and no-substitution tests now pass; provider evidence
   ingestion and lifecycle checks remain open.
3. Add workload capability and cost-selection evidence for CPU, GPU/VRAM,
   architecture, runtime, timeout, network/result collection, and cleanup.
   Distinguish availability from cost class; unknown quota or an unenforceable
   zero-cost requirement must block submission.
4. Bind a current, concrete resource quote and all-in CPU/RAM/GPU/storage/egress
   estimate to the exact registered workload and expiry.
5. Only after the independent cost, authorization, and security gates are
   satisfied, run an approved, bounded GPU smoke and record device/VRAM,
   provider handle, usage, exit status, retrieved result, cancellation, and
   independent cleanup evidence. A self-reported metric is not scientific
   quality evidence.

This record is provider-doc and source review evidence only. It does not prove
account eligibility, live API compatibility, GPU execution, spend prevention,
cleanup, or semantic/model quality. No paid or external compute was started.

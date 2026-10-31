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
  before prepare persistence, submit, and worker launch are now wired for the
  signed RunPod catalog path. Modal account quota is not ingested: its billing
  collector remains `billing_only` and cannot construct `QuotaEvidence`. A
  spend-limit setting alone must never be treated as proof that a particular
  run is credit-covered.
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
  Generic signed provider evidence ingestion and exact-plan revalidation are
  wired; Modal-specific quota ingestion and account acceptance remain open.
  Therefore Modal remains ineligible for zero-additional-cost selection.
  References:
  [Workspace billing API](https://frontend.modal.com/docs/sdk/py/latest/Workspace),
  [Modal budgets and spend limits](https://modal.com/docs/guide/budgets).

Official sources:

- [Modal Sandboxes](https://modal.com/docs/guide/sandboxes)
- [Modal sandbox networking](https://modal.com/docs/guide/sandbox-networking)
- [Modal pricing and spend limits](https://modal.com/pricing)
- [Modal budgets and spend limits](https://modal.com/docs/guide/budgets)

## Provider lane comparison refresh — 2026-10-31

The provider implementation order is now explicit: **Modal is the
candidate-bound adapter target; RunPod remains in the P5 paid lane. There is no
currently executable Modal credit-backed lane.** This corrects the earlier
provisional P4-credit-backed direction: Gateway routes `CREDIT_BACKED` plans
through a distinct credit-authority hook. A pure signed-credit verifier and
default-empty issuer/key settings now check current evidence and the exact run
and plan offline. They are not wired into admission, no provider implements the
hook, and Modal quota is still not ingested; therefore no credit-backed lane is
executable. A Modal adapter alone cannot make credit consumption admissible.
This is a code-sequencing decision, not an account selection, spending
authorization, provider registration, or live acceptance.

- The official [Modal Sandbox SDK](https://modal.com/docs/sdk/py/latest/Sandbox)
  exposes requested GPU, CPU, memory, timeout and networking controls, plus
  Sandbox object IDs, attach/poll/log/terminate operations. The existing
  worker-only adapter already uses a pinned image ID, fixed argv, bounded
  runtime, blocked outbound networking, durable object ID and cancellation.
  This makes Modal the shortest implementation path for the P4 candidate-bound
  lifecycle, subject to a separate check that the provider observation and
  receipt can prove the actual allocated device and released resource.
- Current [Modal pricing](https://modal.com/pricing) lists Starter compute
  credits and separately metered GPU, non-preemptible Sandbox CPU/memory,
  volume and egress. [Workspace and Environment budgets](https://modal.com/docs/guide/budgets)
  cap usage, but public documentation does not establish the selected
  workspace's remaining eligible credit or prove a particular run is covered.
  A future credit-backed lane also needs a signed, explicit credit-use
  authorization bound to the complete plan and current quota evidence; balance
  and hard-stop data alone are not consent.
- RunPod's current [Pod management documentation](https://docs.runpod.io/pods/manage-pods)
  says stopping a Pod releases the GPU but volume storage remains billable;
  termination is required when storage should no longer be retained, while a
  Network Volume persists across termination. The Gateway's signed RunPod
  catalog evidence currently supplies GPU model/VRAM, advertised accelerator
  price and datacenter stock only. CPU/RAM/runtime/result/cleanup/quota and
  storage/egress total-cost evidence remain unknown. The existing core RunPod
  adapter requires a `LiveExecutionPermit` and uses paid pricing/occupancy
  gates, so it belongs to P5 and must not be reused as a free or credit-backed
  P4 backend.

The P5 verifier requires `cost_evidence.classification == "PAID"` and rejects
`CREDIT_BACKED`. The registry and worker now classify credit-backed plans into
a separate opt-in and `validate_credit_authorization` hook; there is still no
provider registration or backend that implements that hook. A future authority
must bind a distinct credit-consumption decision (maximum gross credit debit,
zero out-of-pocket ceiling, quota-evidence fingerprint, owner/actor,
run/plan/resource and expiry) or provide a separately reviewed credit permit.
Do not relabel gross credit use as zero cost, silently route it through P4, or
infer consent from the existing Modal workspace balance.

The next offline implementation target remains the candidate-bound Modal
adapter, but its `CREDIT_BACKED` path must fail closed until the authority
contract accepts explicit credit-use consent. A strictly `FREE` or
`FREE_QUOTA` candidate with zero additional cost may follow the P4 path only
when every component and hard-stop condition is evidenced. If no such candidate
exists, P4 cannot perform a real GPU run without the separately authorized P5
path. No provider API call, account inspection, allocation, or test was
performed for this refresh.

### Modal hardware identity evidence boundary — 2026-10-31

The current [Sandbox SDK reference](https://modal.com/docs/sdk/py/latest/Sandbox)
documents the requested GPU reservation, CPU/memory/runtime/network settings,
Sandbox object ID, tags, `poll()` exit code, logs, and `terminate(wait=True)`.
The documented Sandbox object surface does not expose a provider-side physical
GPU identifier or actual allocated GPU model. The repository's
`gateway/examples/gpu_smoke.py` prints a device name from inside the workload;
that is useful execution output but remains workload-produced evidence.

Therefore the future Modal adapter must not label that output as independently
provider-verified hardware identity. A bounded smoke may report
`torch.cuda.get_device_name()` and execute a CUDA operation, but the receipt
must state its evidence source and scope accurately. The adapter still needs a
reviewed method to bind the Modal Sandbox object to the exact requested
resource, authenticate the terminal result, and prove termination/release.
Until that method and a trusted immutable-image/source chain are accepted,
`device_identity_verified` and candidate-bound GPU success must remain
unreachable for Modal. No Modal SDK or account call was made.

## P4 gaps and next evidence

1. Inspect the selected Modal workspace's plan, included usage, GPU quota,
   budget scope, overage behavior, and hard-stop semantics without launching a
   Sandbox. Do not save or reveal credentials in this record.
2. Obtain owner-read Modal account evidence and a supported source for current
   usage headroom, eligible credit coverage, budget/spend caps, and overage stop.
   The generic `QuotaEvidence` model, signed provider observation storage, and
   prepare/submit/worker exact-candidate revalidation already exist. A
   Modal-specific collector must not emit selection-eligible quota data until
   it can populate every required field with provenance. Offline stale/
   insufficient/uncovered-credit and no-substitution cases are covered; live
   Modal evidence and lifecycle checks remain open.
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

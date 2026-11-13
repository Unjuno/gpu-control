# Live Sites, Modal, and budget recheck — 2026-11-14 JST

## ChatGPT Sites access

- The existing `gpu-control-sites` Site is active at its published URL, version
  33, with public Site access and this ChatGPT account as owner.
- From this ChatGPT account, the registered `experiment_capabilities` and
  `experiment_list` tools returned owner-scoped data. The persistent Sites to
  Modal provider configuration is present; capability discovery intentionally
  defers provider health until an exact plan is approved and submitted.
- Direct unauthenticated `POST /mcp` requests returned HTTP 401. A second
  request with a synthetic, non-allowlisted `oai-authenticated-user-id` and no
  Sites bearer credential also returned HTTP 401. This confirms that a
  caller-supplied identity header alone cannot reach the MCP Worker. It does
  not replace a denial test from a separately authenticated ChatGPT account.

## Modal execution and limits

- The owner-scoped run history contains no accepted current Modal inference.
  Its newest Modal Sandbox run failed with `MODAL_WORKLOAD_EXIT_2`; cleanup was
  confirmed and no result artifact was produced. The Modal Sandbox detail page
  showed outbound and inbound networking blocked, CPU request 1 core with no
  CPU limit, memory request 512 MiB with no memory limit, and no Sandbox logs.
- The Sites capability response currently says Modal is configured and
  admission is enabled, while `provider_ready` remains null until an approved
  submit. A minimum one-token plan was prepared during this check but was not
  confirmed, health-checked, or submitted.
- The `$0.01` per-Sandbox ceiling was not an enforced upper bound at this
  recheck: Modal's dashboard showed no CPU or memory hard limits. Modal
  documents `cpu` and `memory` as requests that can burst; tuple values specify
  hard limits. A source fix to set both request and limit is in progress and
  must be published and verified in the live Sandbox details before another
  run.

## Workspace billing

- The logged-in Modal Usage & Billing page showed a `$1` Workspace usage limit,
  `$0.10` in credits used, and `$0` in charges. The page offered “Add payment
  method” to raise the usage limit; no billing setting was changed.
- Modal documents Workspace budgets as a hard cap on gross usage before
  credits, and distinguishes them from net spend limits. Its billing docs also
  describe automatic charges at billing-cycle end and incremental thresholds.
  Therefore, credits alone are not treated as a guarantee against charges; the
  current `$1` usage limit is the verified outer bound for this Workspace.
- References: <https://modal.com/docs/guide/budgets>,
  <https://modal.com/docs/guide/billing>, and <https://modal.com/pricing>.

## Other security scope

- RunPod allocation remains parked and unavailable to live calls. The current
  source tree contains no active macOS Keychain Runner implementation; remaining
  Keychain references are historical documentation or negative checks.
- Repository-wide P0 review remains incomplete. Separate reviews are checking
  RunPod allocation authorization, D1/R2 ownership and recovery, provider
  resource limits, and GitHub workflow token scope. No Modal deployment,
  RunPod API call, billing change, or Sandbox start was performed in this
  recheck.

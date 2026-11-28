# GPU Control provider control plane

## Decision

The authenticated GPU Control API/MCP is the single product control plane.
ChatGPT chat/Work and any compatible MCP client use the same interface when
connected and owner-authenticated. Client choice must not create a second plan,
budget, or run-history system. The current public product integration and all
acceptance claims below remain ChatGPT/Sites-specific unless stated otherwise.

This document describes the fixed-workload provider design as previously
verified; its provider rows are not a fresh live check. The current PR #70
source candidate additionally implements an owner-selected repository lane for
Modal GPU only; it remains unmerged, undispatched under parked policy, and is
not a fifth provider. See [the selected-repository architecture](chatgpt-selected-repository-experiments.md).

The current production ChatGPT path has four compute providers:

1. Modal
2. RunPod
3. Kaggle
4. Hugging Face

Google Colab is a fifth target provider, not a separate completion path. Google
offers a hosted MCP endpoint at `https://colaboratory.googleapis.com/mcp`, but
a user's ChatGPT OAuth connection is not automatically available to the Sites
Worker. A direct ChatGPT-to-Colab app may be used separately for exploration;
its runs are outside the D1 ledger and do not satisfy GPU Control acceptance.
The unified Colab route remains unavailable until GPU Control has its own
owner-scoped Google connection and the common run lifecycle. The published
Colab tools do not expose a compute-unit balance or exact per-run quote, so
the route cannot promise a dollar/CU ceiling until a trusted quota control is
available.

Railway, Vercel, Neon, and a separately hosted PostgreSQL Gateway are not part
of the production execution path.

```text
Authenticated GPU Control client (ChatGPT chat/Work first; other MCP clients
when connected)
  -> ChatGPT Sites MCP
     -> D1: plans, one-use authorization, budgets, run state, provider handles
     -> Modal control API: fixed Modal CPU workload
     -> RunPod REST v2: fixed digest GPU workload
     -> Modal provider adapter
        -> Kaggle: fixed private GPU workload
        -> Hugging Face: fixed private ZeroGPU Space
```

The Modal provider adapter is infrastructure for the Kaggle and Hugging Face
routes; it is not a fifth compute provider. It holds only server-side provider
credentials and exposes only the registered experiment protocol. Chat input
cannot supply a command, image, URL, repository, credential, provider resource,
or arbitrary environment variable.

The deployed adapter image packages only the reviewed provider modules
(`kaggle_backend`, `huggingface_space_backend`, artifact handling, their bounded
workload helpers, and shared validation types). It does not package the legacy
Gateway API, OAuth, worker, PostgreSQL store, migrations, or service modules.

## Trust and persistence boundaries

- Sites authenticates the ChatGPT user and enforces the owner allowlist.
- D1 owns the Sites-facing plan, one-use confirmation, budget reservation,
  owner-visible run state and cleanup evidence for the fixed provider routes.
- Modal endpoints require Modal proxy authentication plus a separate
  Sites-to-adapter HMAC with a short expiry and nonce.
- The PR #70 owner-selected Modal path additionally keeps an atomic dispatch
  claim and execution journal in Modal Dict, with source/checkpoint data in
  Volumes. That journal is required for adapter-side idempotency/recovery but
  is a second durable state store. D1 remains the owner-facing plan, budget and
  cleanup ledger; the exact transition/reconciliation authority when the two
  disagree remains a release-critical contract to finish and test. Do not
  flatten this distinction into “D1 is the only run-state store.”
- Provider credentials are separated by route and are never returned to Sites,
  ChatGPT, logs, artifacts, or model-visible responses.
- Paid execution remains closed unless the exact plan, provider-specific budget,
  one-use confirmation, immutable workload identity, and cleanup path all pass.

## Provider ownership

| Provider | Control path | Credential location | Cost policy |
| --- | --- | --- | --- |
| Modal | Sites -> authenticated Modal control API | Modal proxy token in Sites | shared Sites reservation ceiling of $30/month and $1/run for Modal CPU/GPU compute; not a Modal billing stop |
| RunPod | Sites -> RunPod REST v2 | Sites secret | independent $1/run reservation; no Sites monthly cap; exact Pod termination required |
| Kaggle | Sites -> Modal adapter -> Kaggle | Modal secret | free-first; no paid fallback |
| Hugging Face | Sites -> Modal adapter -> private ZeroGPU Space | Modal secrets and Space secret | free ZeroGPU only; no paid fallback |
| Google Colab (planned fifth provider; unavailable) | ChatGPT -> Sites D1 plan/lease -> owner-scoped Google OAuth -> hosted Colab API MCP | GPU Control Google connection, server-side only | runtime/resource ceiling; exact dollar/CU cap unavailable until a trusted quota/quote is exposed |

The Modal reservation sum covers only Modal CPU/GPU workload compute. It does
not count Modal control-function hosting charges for the Kaggle/Hugging Face
adapters, external-provider costs, unrelated Modal workloads, or actual account
usage outside Sites D1. See [ADR 0005](decisions/0005-shared-modal-compute-budget.md).

## Compatibility rule

Migration `0014_gateway_delegation.sql` and its table names are retained until a
forward-only D1 migration safely copies live rows. Their names are historical
storage identifiers, not authorization to deploy an external Gateway. New
configuration uses only `PROVIDER_ADAPTER_URL`, `PROVIDER_ADAPTER_KEY_ID`, and
`PROVIDER_ADAPTER_HMAC_KEY_B64`; legacy `GATEWAY_*` configuration is rejected.

## Activation acceptance

- No Railway resource or PostgreSQL service is required.
- Google Colab is a target provider, but is reported unavailable until its
  owner-scoped Sites connection, bounded plans, idempotent submission/recovery,
  status, cancellation, result and cleanup evidence exist. Direct Google MCP
  app calls remain outside the Sites ledger and are not product acceptance.
- Sites reports all four registered providers and the real blocker for each.
- Kaggle and Hugging Face calls work through the authenticated Modal adapter.
- RunPod cannot start without an exact price-bound plan and one-use confirmation.
- RunPod also remains disabled until the authenticated completion transport has
  been verified against the live account; provider configuration alone cannot
  enable it.
- Status, result, artifact, cancel, retry, and cleanup survive Site restarts
  because provider handles and state are in D1.
- A real bounded canary is observed for each enabled route; a passing unit test
  or health endpoint alone is not completion evidence.

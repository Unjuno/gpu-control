# Sites four-provider control plane

## Decision

The production ChatGPT path has exactly four compute providers:

1. Modal
2. RunPod
3. Kaggle
4. Hugging Face

Railway, Vercel, Neon, and a separately hosted PostgreSQL Gateway are not part
of the production execution path.

```text
ChatGPT (authenticated user)
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

## Trust and persistence boundaries

- Sites authenticates the ChatGPT user and enforces the owner allowlist.
- D1 is the durable source of truth for plans, one-use confirmations, budgets,
  run state, and opaque provider handles.
- Modal endpoints require Modal proxy authentication plus a separate
  Sites-to-adapter HMAC with a short expiry and nonce.
- Modal storage may be used for bounded staging or reconciliation journals, but
  never as the authoritative run database.
- Provider credentials are separated by route and are never returned to Sites,
  ChatGPT, logs, artifacts, or model-visible responses.
- Paid execution remains closed unless the exact plan, provider-specific budget,
  one-use confirmation, immutable workload identity, and cleanup path all pass.

## Provider ownership

| Provider | Control path | Credential location | Cost policy |
| --- | --- | --- | --- |
| Modal | Sites -> authenticated Modal control API | Modal proxy token in Sites | provider-specific monthly and per-run cap |
| RunPod | Sites -> RunPod REST v2 | Sites secret | per-run cap; exact Pod termination required |
| Kaggle | Sites -> Modal adapter -> Kaggle | Modal secret | free-first; no paid fallback |
| Hugging Face | Sites -> Modal adapter -> private ZeroGPU Space | Modal secrets and Space secret | free ZeroGPU only; no paid fallback |

## Compatibility rule

Migration `0014_gateway_delegation.sql` and its table names are retained until a
forward-only D1 migration safely copies live rows. Their names are historical
storage identifiers, not authorization to deploy an external Gateway. New
configuration uses only `PROVIDER_ADAPTER_URL`, `PROVIDER_ADAPTER_KEY_ID`, and
`PROVIDER_ADAPTER_HMAC_KEY_B64`; legacy `GATEWAY_*` configuration is rejected.

## Activation acceptance

- No Railway resource or PostgreSQL service is required.
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

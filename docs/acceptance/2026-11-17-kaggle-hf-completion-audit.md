# Kaggle and Hugging Face completion audit — 2026-11-17

This audit applies the development directive's actual PASS definition. Code,
mock tests, a green Draft PR, local deployment readiness, or a reachable MCP
endpoint is not substituted for real provider and ChatGPT evidence.

## Authoritative snapshot

- GitHub `main`: `24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e`
- candidate: `codex/sites-modal-runner` at `e2575a66f641cd58964d2cd61ff24d6a2720a7ff`
- Draft PR: #68, stacked on `codex/gpu-control-p1-dcr-v9-review`
- audit PR #43: still open and Draft against `main`
- exact-head checks: seven successful
- repository state: `parked`; paid fallback and RunPod live calls disabled
- live ChatGPT Sites capability read: Modal CPU enabled, RunPod disabled, no
  Kaggle or Hugging Face provider/workload advertised
- browser account state: Kaggle and Hugging Face both showed their login pages;
  no account, token, quota, repository, or Space state was inspected

## Requirement-by-requirement result

| Directive area | Current evidence | Result |
| --- | --- | --- |
| 1. Initial audit | Current main/open PR inventory refreshed; Remote MCP, registry, worker, queue, reconciliation, artifacts, OAuth, policy and provider specifications were inspected. #68 remains stacked rather than merged. | COMPLETE for current code snapshot |
| 2. Kaggle backend | `gateway/gpu_gateway/kaggle_backend.py` uses the official CLI contract, immutable owner/slug/version/source identity, one push after durable intent, no retry after ambiguity, exact-version log/output recovery, explicit unsupported cancellation and quota blocking. Tests inject success, quota, ambiguity and recovery failures. | READY OFFLINE; LIVE BLOCKED |
| 3. Hub artifact store | `huggingface_artifacts.py` restricts writes to allowlisted private model repositories, keeps the write token in the trusted worker, records exact revision/SHA, re-downloads for integrity, and refuses overwrite with different bytes. Kaggle receives no Hub write token. | READY OFFLINE; LIVE BLOCKED |
| 4. ZeroGPU backend | `huggingface_space_backend.py` verifies allowlist, exact commit, Gradio API shape, private visibility, finite included quota, explicit zero overquota use, and bounded results. Paid Jobs and paid quota extension are absent. | READY OFFLINE; LIVE BLOCKED |
| 5. Gateway integration | Registry contains `kaggle` and `huggingface_space`; `huggingface_hub` is an artifact service. Worker lifecycle, receipts and cleanup remain provider-neutral. | COMPLETE OFFLINE |
| 6. ChatGPT MCP semantics | Gateway exposes the eight canonical tools under OAuth. Local Compose rehearsal reached schema v15, worker, supervisor, OAuth discovery, HTTP 200 readiness and HTTP 401 unauthenticated MCP refusal. The connected production Sites tool still lacks Kaggle/HF. | LOCAL PASS; LIVE BLOCKED |
| 7. Orbitune workload | Source is fixed to `44a1b806160ab5bc721a370d034a6dfcb28f27a8`. The Kaggle entrypoint performs forward/loss/backward/step/zero-grad for exactly 100 steps, labels synthetic data, records every loss/device/CUDA/PyTorch/time/checksum, and reloads/evaluates in a separate process. | COMPLETE OFFLINE; REAL GPU UNPROVEN |
| 8. FREE_FIRST selection | Signed provider evidence and workload requirements drive selection. Missing/unsafe quota blocks; no automatic paid fallback exists. Modal, Kaggle and ZeroGPU resources remain independent. | COMPLETE OFFLINE; LIVE QUOTA UNKNOWN |
| 9. Security and authorization | Secrets are worker-only; exact plans require owner approval; public Space/artifacts and arbitrary scripts are rejected; repository remains parked. Final Security Reviews found no actionable source findings. | SOURCE PASS; EXTERNAL STATE UNKNOWN |
| 10. Ordered phases | A-C and offline portions of E/F are complete. D, live E and live F cannot begin without account authentication, quota/resource configuration, a hosted Gateway endpoint, and current one-use owner approval. | BLOCKED AT LIVE PHASE D |
| 11. Acceptance hypothesis | No real Kaggle GPU, 100-step provider run, private Hub roundtrip, private ZeroGPU evaluation, ChatGPT run result, or external cleanup evidence exists. | BLOCKED, not PASS/FAIL |
| 12. Separate-session prompt | The prompt is recorded in `docs/KAGGLE_HUGGINGFACE_RUNBOOK.md`; the current connected Sites schema cannot execute it through Kaggle/HF. | PROMPT READY; EXECUTION BLOCKED |
| 13. Deliverables | Implementations, tests, integration, workloads, quota/cost gates, credential and recovery instructions, Draft PR and blocked audit exist. Real-connection evidence remains absent. | PARTIAL |

## Evidence strength

The following are accepted only for their stated layer:

- unit/fault-injection tests prove deterministic control behavior, not provider
  compatibility or quota;
- the local Compose rehearsal proves the deployment graph and OAuth/MCP
  boundary, not a public ChatGPT connection;
- a live Sites capability response proves only the currently deployed Sites
  registry;
- browser login pages prove authentication is currently unavailable, not that
  the accounts lack quota or eligible resources;
- green PR checks do not prove any real GPU allocation or artifact upload.

## Exact remaining PASS sequence

1. The owner signs in to Kaggle and Hugging Face.
2. Read-only checks establish the Kaggle identity/current included GPU quota and
   the Hub account's private-repository/Space eligibility.
3. Create or select one private model repository and one private ZeroGPU Space;
   pin the exact Space revision and reviewed API contract.
4. Create least-privilege, separable credentials: Kaggle execution credential,
   worker-only Hub write token, and Space read credential. Never expose values
   in ChatGPT, logs, Git, Kaggle or workload output.
5. Deploy the Gateway API, PostgreSQL roles, worker and supervisor behind TLS;
   bootstrap owner OAuth and connect `/mcp` from ChatGPT.
6. Re-read `experiment_capabilities`. If included quota, identity, private
   resources, worker/supervisor readiness or cleanup capacity is unknown, stop.
7. Prepare the exact 100-step plan. Show its immutable identities, free-only
   classification and stop conditions, then obtain a fresh one-use owner
   confirmation.
8. Submit exactly one Kaggle job. Never retry an ambiguous push; reconcile the
   recorded Kernel/version instead.
9. Retrieve the exact output through the trusted worker, upload to the private
   Hub repository, re-download the exact revision and verify SHA-256.
10. If finite included ZeroGPU quota remains with zero overquota use, obtain a
    separate confirmation and run one short private-Space evaluation.
11. From a separate ChatGPT session, retrieve run ID, actual GPU, all losses,
    checkpoint revision/SHA, evaluation, quota classification and cleanup.
12. Confirm provider termination/cleanup and re-close admission. Only then may
    the hypothesis be marked PASS.

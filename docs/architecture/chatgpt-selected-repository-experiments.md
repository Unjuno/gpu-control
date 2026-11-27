# ChatGPT-Selected Repository Experiments

Status: target architecture with a partial source implementation in PR #70.
That PR is open and blocked on required review; owner-selected admission remains
disabled by repository policy. Do not describe this candidate as deployed or
available in ordinary ChatGPT yet.

## Product outcome

From an ordinary ChatGPT chat or Work conversation, the owner can select a
repository available to their connected GitHub account, ask for an experiment,
and have the agent resolve the current immutable commit, inspect the project,
select a supported provider, start a bounded job, monitor it, and retrieve
results. The owner should not need to pre-register every repository as a
control-plane workload or visit a separate browser authorization page for
every run. A user-configured provider budget lease bounds repeated runs.

## Verified boundary in the current source candidate

- GPU Control uses its own read-only GitHub App installation selection. The
  ChatGPT GitHub connector's OAuth token is not passed to the Sites Worker.
  A repository must be selected in the owner's GitHub App installation.
- `training_register` resolves and pins the default-branch SHA when omitted;
  custom private-source reads use a short-lived installation token scoped to
  that selected repository. Registration alone does not authorize compute.
- `training_inspect`/`training_preview` validate
  `.gpu-control/experiment.json`, a hash-locked dependency file, supported GPU
  profile, configured runtime image and quote. `training_prepare` stores an
  exact expiring plan; `training_submit` rechecks it, binds the ChatGPT write
  confirmation, reserves the owner/monthly and single-run limit, then delegates
  to the Modal adapter.
- The candidate includes a trusted source-staging sandbox and a separate
  isolated Modal GPU Sandbox. The workload receives no GitHub/provider token,
  uses the manifest-declared Python entrypoint, and returns bounded metrics,
  checkpoints/artifacts and cleanup evidence.
- This owner-selected implementation currently targets Modal only. The fixed
  RunPod, Kaggle and Hugging Face paths do not mean those providers can execute
  arbitrary owner-selected repositories. Colab is also not connected to the
  shared lifecycle.
- `policies/repository-state.yaml` keeps owner-selected admission disabled and
  repository mode parked. PR #70 has not been merged or deployed as of this
  snapshot; hosted tool schema, migrations, credentials, account limits and an
  end-to-end ChatGPT GPU run still need separate release verification.

## Implementation evidence in PR #70 source

- The implementation surface is `worker/github_app_connection.js`,
  `training_source.js`, `training_contract.js`, `training_plan.js`, the
  `training_*` D1 migrations, and `modal/custom_training_*.py`.
- The source contract is JSON at `.gpu-control/experiment.json`, not the YAML
  alternative described in older target text below. It limits entrypoint,
  Python version, GPU profile, output paths and hash-locked dependencies.
- The API surface supplies owner-scoped connection, repository listing,
  registration, inspection, preview, prepare, submit, status, cancel and
  bounded artifact/checkpoint tools. Ordinary-chat usability still needs a
  fresh published ChatGPT/Work end-to-end acceptance.
- The implementation is more than source inspection but less than a released
  capability. Its policy and admission gates remain closed.

## Target architecture

### 1. Repository discovery and source identity

Use GPU Control's GitHub App tools to list/select repositories and resolve the
chosen branch to a 40-character commit. The ordinary GitHub connector login is
not a credential source for the Sites Worker. Pass only the selected canonical
`owner/repository` and immutable commit to later plan steps. Never copy a
GitHub bearer token into chat, tool arguments, logs or the runner.

For private repositories, add a GitHub App installation flow scoped to
explicitly selected repositories with read-only Contents and Metadata access.
The Sites service stores the installation identity, not a reusable user PAT;
short-lived installation tokens are minted server-side only for source
checkout and are never exposed to the agent or workload. Public repositories
can use unauthenticated, pinned GitHub archive fetches.

### 2. Repository-owned experiment contract

At the selected commit, read the current versioned
`.gpu-control/experiment.json` contract. It declares task, entrypoint, locked
dependencies, Python version, GPU profiles and output paths. The agent does
not invent an unrestricted shell command, image, network policy or provider
credential. Unknown fields and unpinned dependencies fail closed. Keep this
small declared Python protocol as the initial supported product; adding a
general command language would widen both complexity and attack surface.

### 3. Isolated execution

Build or retrieve an immutable image from the pinned source and locked runtime
spec. Run one finite job in an ephemeral provider sandbox with a non-root
workload identity, read-only source, bounded writable output volume, CPU/GPU,
memory, wall-clock, disk, and process limits. Workload code receives no
control-plane, GitHub, provider, or artifact-store credentials. Default
egress is denied; any data download must be an explicitly declared,
allowlisted input. Logs, metadata, checkpoints, and model output remain
untrusted data and cannot change control-plane policy.

### 4. One agent-facing lifecycle across providers

Expose repository discovery/source resolution, preview, execute, status,
cancel, result, and artifact retrieval with the same owner-bound run identity.
The agent should be able to infer and use the sequence from tool descriptions.
Prepare and submit must be idempotent/recoverable; an ambiguous submit resumes
the same run rather than starting another. Provider adapters consume a
validated execution plan, never raw repository instructions.

Provider routing must use current capabilities, quota/pricing, owner policy,
and the requested cost ceiling. Never silently route a free-only request to a
paid provider. Route only to providers whose current contract supports the
declared task, artifact access, runtime, and cleanup semantics.

### 5. Persistent user limits instead of repeated browser ceremonies

Let the owner configure provider-specific monthly and per-run ceilings,
concurrency, allowed repositories/providers, and an optional lease expiry.
Every run checks and atomically reserves that lease. The user's current chat
request supplies intent to run the requested experiment within the lease; the
agent must not ask the same conversational question again after prepare.
The exact plan, source commit, image, provider/resource, runtime, and maximum
charge are still shown in chat. ChatGPT's native write-action confirmation, if
the client requires it, remains a client boundary and cannot be bypassed by
Site code. A request outside the lease is blocked with the specific limit and
the smallest action needed to change it.

## Security boundaries

- GitHub repository access establishes which source may be read; it does not
  authorize spending.
- A persistent budget lease establishes a maximum possible exposure; it does
  not cause a run by itself. A current user request is still required.
- Repository content, agent instructions within that repository, logs, and
  artifacts are untrusted. They cannot grant authorization or expand limits.
- Provider credentials stay in provider adapters and are never mounted in the
  workload container.
- Owner identity, repository installation, source SHA, execution spec, image
  digest, provider, resource, budget lease, and run ID are bound in the saved
  plan and audit record.
- Cross-owner reads, artifact access, status, cancellation, and lease use must
  fail closed.
- This architecture does not make arbitrary workloads intrinsically safe; it
  limits their authority and blast radius through isolation and budgets.

## Delivery sequence

1. Fix misleading product/tool copy and explicitly label the current MAP-only
   route as a specialized acceptance lane.
2. Implement GitHub repository discovery plus an explicit private-repository
   installation binding; prove public and private source selection without
   starting compute.
3. Define and validate the repository experiment contract and image build
   identity at an immutable source SHA.
4. Implement sandbox execution and provider adapters behind the existing
   approved-plan and provider-budget boundaries; preserve all existing fixed
   workloads during migration.
5. Add persistent, provider-specific budget leases and remove the per-run
   `/authorize-training` browser dependency for lease-covered jobs while
   keeping native MCP client confirmation behavior intact.
6. Verify in offline tests, then run only a user-requested, smallest viable
   end-to-end experiment within the configured limits. Verify GPU evidence,
   results/checkpoint hashes, cancellation, cleanup, cross-owner denial, and
   remote ChatGPT/Work tool behavior before calling the product complete.

## Acceptance criteria

- An agent can list only repositories visible to the connected GitHub account,
  select one, resolve its current commit, and explain the chosen source.
- A public repository can be registered and executed without control-plane
  operator pre-registration. A private repository requires an explicitly
  installed, least-privilege GitHub App binding.
- A repository's instructions cannot access secrets, widen budgets, select an
  unapproved provider, or cause another run.
- A normal user request can run a compatible experiment within its existing
  provider-specific lease without a second browser authorization ceremony.
- Every run is owner-bound, immutable-source-bound, resource-bounded,
  idempotent, observable, cancellable, and verifiably cleaned up.
- The agent distinguishes queued, running, succeeded, failed, and cleanup
  states, and never reports a CPU result as a GPU result.
- Modal, RunPod, Kaggle, and Hugging Face appear only for task types their
  current adapters actually support; no paid fallback occurs for a free-only
  request.
- ChatGPT and Work can use the deployed tools without relying on local Codex
  filesystem access or a browser page for each ordinary run.

## Current completion

This file records the required architecture; it is not evidence that the
implementation, deployment, or ChatGPT acceptance criteria have been met.

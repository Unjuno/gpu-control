# Baseline audit: current `main`, PR #43, and the ChatGPT CPU path

**Snapshot:** 2026-10-31 (UTC)

This audit separates the current public default branch from the older release
candidate in PR #43 and from the stacked ChatGPT Gateway work. It records
repository evidence only; it does not certify a production deployment, ChatGPT
account access, GitHub protection settings, or paid-provider readiness.

## Exact references

| Reference | State at audit time | Evidence |
| --- | --- | --- |
| `main` | `24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e` | `git ls-remote origin refs/heads/main` |
| PR #43 base | `a96a24818a5f8bc03b479c35b5e3f957f08dbe04` | `gh pr view 43 --json baseRefOid` |
| PR #43 head | `1699b75df8262023501d41279e83bf429dca1be4` | `gh pr view 43 --json headRefOid` |
| PR #43 | Open, draft, base `main`; not merged | `gh pr view 43 --json state,isDraft,baseRefName` |
| ChatGPT CPU/P3 candidate | PR #59 head `316c1bdd633b2bcc8251544e0b8738af76eb244f`, open and draft | `gh pr view 59`; all listed CI and Vercel checks passed at that head |

The PR #43 head is not an ancestor of current `main`. Its merge base with
current `main` is the PR's old base `a96a248...`. Comparing the two complete
trees shows 100 changed paths and 5,848 deletions, including the removal from
the old PR tree of the Gateway, project-control runner, and their workflows
that exist on current `main`. PR #43 therefore cannot be merged or cherry-
picked as a whole onto the current default branch.

## PR #43 change disposition

The PR contains 35 changed paths relative to its base. The changes fall into
these implementation groups:

| Change group | Files or scope | Disposition for the active ChatGPT objective |
| --- | --- | --- |
| Distribution integrity | `MANIFEST.in`, `scripts/check_distribution.py`, `pyproject.toml`, `uv.lock`, and `.github/workflows/package-check.yml` | Potentially reusable for CLI releases. Current `main` has a newer root lock; the PR-specific package check is absent from current `main`. Review and port it separately if standalone distribution remains a release target. |
| HTTP, source, and input validation | `src/gpu_control/http_security.py`, `policy.py`, `source.py`, `validation.py`, and associated HTTP/source/regression tests | The P1 stack contains a later port of the outbound HTTP/source hardening (for example, commit `48e592a` in the current P1 ancestry). Current `main` does not contain `http_security.py`; the port remains unmerged and needs the normal P1 review/merge path. The Gateway also has its own HTTP/OAuth boundary and must be assessed separately. |
| RunPod transport and reconciliation | `providers/runpod_*`, including price, v1/v2 adapter, Network Volume and recovery changes, plus provider tests | Provider-specific. Defer to the later GPU/paid stage and revalidate against current provider contracts then. PR #43's old branch is not current live-provider evidence. |
| Release and policy records | README/security/setup changes, independent acceptance, parked-mode and release-audit documents | Do not transplant wholesale: current `README.md`, `docs/STATUS.md`, policies and selected workload have advanced since the PR's base. Reconcile facts against current source before reusing wording. |
| pytest development floor | PR #43 changes the floor from pytest `>=8,<9` to `>=9.0.3,<10` and locks pytest `9.0.3` | Not present on current `main`, which still declares `>=8,<9` and pins `8.4.2`. The open P1/P3 candidate has the `>=9.0.3,<10` floor and pins `9.1.1`; this remediation remains unmerged with that candidate. |

The open P1/P3 candidate contains the later outbound HTTP/source hardening
commit `48e592a` in its ancestry; its implementation differs from PR #43's final
tree. This is evidence of a candidate-side port, not evidence that it has landed
on `main` or passed independent GitHub review.

## Current product baseline

- Current `main` includes `gateway/` and `src/gpu_control/`; the PR #43 tree
  predates the current Gateway tree.
- Current `main` declares the development extra as pytest `>=8,<9` and locks
  pytest `8.4.2`. The open ChatGPT candidate updates the floor to `>=9.0.3,<10`
  and locks `9.1.1`, but that change has not landed on `main`.
- Current `docs/STATUS.md` describes an installable offline CLI and offline /
  mock-tested provider contracts. `gateway/README.md` describes an additive
  Modal/RunPod Gateway and explicitly says real ChatGPT/browser-agent
  interoperability is unproven. Neither document establishes that a user can
  initiate and retrieve an experiment from a live ChatGPT conversation.
- The active P1 branch adds a local CPU experiment path that is not part of
  current `main`. Update the release status only after that path is merged and
  the live ChatGPT acceptance evidence is recorded; do not copy candidate
  claims into the current release status prematurely.
- The active user objective for this roadmap is the ChatGPT-facing registered
  experiment path, starting with the local CPU smoke. The repository's parked
  policy separately names an Orbitune RunPod canary for a future GPU stage;
  that workload does not change the CPU-first objective or authorize execution.
- P1/P3 implementation and CI evidence currently live in open draft PRs. In
  particular, PR #59 is draft and has no submitted GitHub review. Its green CI
  proves the tested candidate revision only; it is not a merge or deployment.

## External configuration evidence and gaps

| Requirement | Evidence/status |
| --- | --- |
| Parked mode and paid/live flags | Current `policies/repository-state.yaml` says `mode: parked` and keeps paid workflow, live paid compute, and RunPod calls disallowed. Preserve this. |
| Main branch protection | `docs/STATUS.md` reports that `main` is unprotected. A fresh read-only GitHub protection query returned HTTP 403 rate-limit, so current settings are **unverified** in this audit. |
| ChatGPT custom MCP entitlement and account setup | No account-level evidence was available from the repository or current PR checks. **Unverified**; it requires inspection in the intended ChatGPT account/workspace. |
| Production HTTPS endpoint, OAuth, and persistent runtime | The open candidate has a Vercel Preview result. Preview CI does not verify the production endpoint, ChatGPT OAuth round trip, persistent database, or an independently running worker. **Unverified**. |
| End-user ChatGPT acceptance | No observed ChatGPT-originated `tools/list`, CPU `prepare`/`submit`, second-conversation lookup, or result/artifact retrieval is attached to this audit. **Not accepted**. |

## P0 decision

**P0 is partially complete; keep it open.** Exact repository references and the
PR #43 disposition are recorded. The public account/workspace connection,
production runtime, end-user ChatGPT acceptance, and current GitHub protection
settings still lack authoritative evidence. PR #43's CPU/MCP-relevant code
must proceed through the current P1 stack as a reviewed port; its RunPod
changes remain deferred.

## Next evidence to collect

1. Verify branch protection and required checks from an authorized GitHub
   settings view or a non-rate-limited API response; do not infer it from docs.
2. Verify custom Remote MCP access in the intended ChatGPT account/workspace
   and record its actual OAuth and callback constraints without storing tokens.
3. Review the exact P1 stack head, complete its security and CI gates, and only
   then test the production HTTPS/OAuth/worker configuration.
4. Record a real ChatGPT CPU smoke acceptance with run identity, state,
   cancellation/recovery, second-conversation result lookup, artifact digest,
   and cleanup evidence. Keep GPU and paid acceptance separate.

Until these items pass, keep the repository parked and treat ChatGPT product
readiness as unproven.

# PR #58-based stack reconciliation

Date: 2026-11-02 UTC

## Candidate identity and source snapshots

- Reconciliation branch: `codex/pr58-cpu-vertical-reconcile-20261102`.
- Exact base: public PR #58 head
  `90bd6d8c84e319365d66951ca96c7ccceff40998`, based on PR #57 head
  `cafab7db8a890614c972cfba5a73e0da9f70fa87`.
- Public PR #58 is OPEN/DRAFT, mergeable, and has no submitted human review.
- Source A is preserved at local code candidate `3b0406b59bc96ab5132bf3345f9ac54c227d1730`
  (worktree head `7028cde981e378d705d86862057d5bfe1bd6579d`). Its Gateway
  source/test delta from its recorded base has SHA-256
  `610013d1ff61912be436f1f89449569cef2520e90dcd8524b7d01efb25d8f5d1`.
- Source B is preserved at worktree HEAD
  `d4a44d558d4bd0a927e23dd0a3cc31608215f7b6`. Its 18-path dirty snapshot
  (12 tracked modifications and 6 untracked files) has SHA-256
  `e4189a471b0bd6028d236bd2eee2371e8cb5af2c1c97cc72e7a0fd52a31ddee6`.
  Neither source worktree was modified during this reconciliation.

## Migration lineage conflict

Versions 1–4 appear to implement the same record-version, cleanup/result,
admission, and submission-intent foundations. Versions 5–9 are not compatible
by version number alone:

| Version | Source A: PR #52 local candidate | PR #58 head | Source B: dirty schema-v13 candidate |
| --- | --- | --- | --- |
| 5 | `gateway_control_v1.worker_capabilities` | `gateway_control_v1.supervisor_seen_at` | `gateway_control_v1.supervisor_seen_at` |
| 6 | `gateway_control_v1.worker_capabilities_seen_at` | `gateway_runs_v1.last_observed_at` | `gateway_runs_v1.last_observed_at` |
| 7 | Version marker; per-process heartbeat table is created by Store initialization | OAuth token `grant_id` | OAuth token `grant_id` |
| 8 | Version marker; bounded DB artifact table is created by Store initialization | OAuth client `persistent` field, default false | Provider observation table |
| 9 | `gateway_control_v1.artifact_bytes`, initialized from stored payloads | Reset OAuth client `persistent` to false and require explicit consent | Infer `persistent` from historical token rows |
| 10–13 | Not present | Not present | Provider account leases, lease challenge fields, paid authorization rows, then reset inferred OAuth consent |

Source B's later v13 reset reverses the earlier consent inference after the
intervening schema-v10–v12 additions. This does not make its intermediate
schema-v9 semantics equivalent to PR #58's schema v9. Source A's v7–v9
meanings also conflict directly with PR #58. Never migrate a database between
these histories by comparing only `gateway_schema_version.version`.

For a database created by Source A's disposable/local candidate, rebuild from
the selected base where possible. Do not invent production history migration
without inspecting the actual database and preserving its run, OAuth, and
artifact state. No live database was changed for this reconciliation.

## Feature ownership and safe replay boundaries

| Scope | Current source | Integration note |
| --- | --- | --- |
| Registered CPU container, MCP SDK interoperability, bounded result/artifact retrieval, worker recovery | PR #52 with PRs #53–#55; Source A has matching local evidence | Keep the published lineage. Port only regressions that are absent from the exact candidate; do not replace its migration/store files wholesale with Source A. |
| HTTP/provider boundary and OAuth migration | PRs #56–#58 | PR #58 owns explicit DCR persistence consent and the current schema-v9 migration. Preserve this behavior. |
| Admission-aware readiness and missing-workload fail-closed startup | PR #62 then #65, both siblings based on #57 | Recompute their exact #57-to-head diffs and replay on #58, then rerun affected HTTP/auth/readiness tests. Their public checks do not validate a replayed candidate. |
| Backup generation, paired artifact restore, systemd operations, capacity/retention checks | PR #59, sibling of #58 based on #57 | Recompute the current #57-to-#59 diff and resolve overlaps in `OPERATIONS.md`, Gateway README, protocol, and auth tests on the #58 base. Historical #58-based backup tests refer to older heads. |
| DB runtime-role separation and read-only privilege audit | Source B, schema-v13 candidate | Extract role identities and least-privilege policy as a separate dependency. Its SQL currently names provider/paid tables absent from the CPU-only schema; derive the allowlist from the selected schema and test effective grants before considering deployment. |
| P4/P5 provider lifecycle and paid authorization | PRs #60, #61, #64 | These are outside first ChatGPT CPU acceptance. Do not import them to make the CPU integration appear complete; retain parked mode. |

## Reconciliation order

1. Keep this candidate rooted at exact PR #58 head `90bd6d8`.
2. Inventory PR #62 and #65 path changes and replay them sequentially, then
   verify the resulting source tree and focused P1 tests.
3. Replay PR #59's operations delta, reconcile its backup/artifact model with
   the PR #58 artifact store, and test paired restore on the integrated schema.
4. Port Source B's runtime-role separation against the selected exact schema,
   excluding unrelated P4/P5 tables unless those features are separately
   adopted and reviewed.
5. Port only missing Source A behavior such as its read-only artifact
   consistency verifier after comparing it with PR #59's backup-integrity
   checks. Add a regression for every accepted behavior.
6. Run the exact-candidate Gateway/Core and PostgreSQL/Docker acceptance,
   perform an independent security review, and record the new candidate SHA.
7. Keep publication, hosted DB/secret changes, deployment, ChatGPT OAuth grant,
   and actual ChatGPT run/retrieval as distinct authorization and acceptance
   gates. Keep GPU and paid execution parked.

## External state observed

On 2026-11-02, PRs #52, #55, #57, #58, #59, #62, and #65 were OPEN/DRAFT;
PR #52 reported `REVIEW_REQUIRED`. PRs #51 and #60–#64 contain broader or
later-stage candidate work. The production alias `/readyz` returned HTTP 404.
This local branch has not been pushed and has no GitHub CI or review evidence.

## Readiness replay and current candidate verification

- Replayed the exact PR #57→#62 patch followed by #62→#65 on top of PR #58
  head `90bd6d8`. Both `git apply --check` operations passed; the combined
  replay changes 10 paths. The original PRs remain untouched.
- The CPU image was rebuilt from the source files unchanged at PR #58 base,
  with OCI labels `Unjuno/gpu-control` and revision
  `90bd6d8c84e319365d66951ca96c7ccceff40998`. Image ID:
  `sha256:886c36f28f349781e02099dccefccf672fec2153df0bbe5fe9912912044a2b2a`.
- Focused OAuth/readiness/migration tests: 49 passed on Python 3.14.5.
- Full Gateway suite on Python 3.12.10, disposable PostgreSQL 16 image
  `sha256:9e2cf6287f25c3151f4c9421ccce2b17f3e60061c111a29165e0d2cdd9ff0a97`,
  and the labeled CPU image: 277 passed, 2 skipped (optional Torch and Modal
  dependencies). The run included real CPU container execution, worker
  recovery, MCP result/artifact retrieval, PostgreSQL lifecycle/recovery, and
  OAuth persistence.
- Core suite on Python 3.12.10: 515 passed, 1 skipped.
- A read-only independent Security Review of the #62/#65 replay on this exact
  PR #58 base found no actionable security findings. It did identify a
  functional limitation: external OIDC login requests do not request
  `gateway:ops:read`, while detailed readiness diagnostics require it. Do not
  broaden that scope for all users; define and test explicit operator-scope
  provisioning if external OIDC diagnostics are required.
- The candidate still has no GitHub checks/review and is not deployed. PR #58,
  #62, and #65 green checks belong only to their distinct public heads.
- Gateway source/test patch SHA-256 relative to exact PR #58 base:
  `fdf7cd925880faf1d9d6aec9acac28342d8756b43fad38e3928c618b37cf4b6c`.

# Sites Version 32 and Modal health authorization — 2026-11-13

## Published Site state

- Site: `gpu-control-sites`
- URL: <https://gpu-control-sites.unjuno.chatgpt.site>
- Version: 32
- Site-source commit: `7aacaac46a0111621d450c89a85fde7ce8cca6a2`
- Environment revision: 33
- Deployment ID: `appgdep_6af6fd907b28819199ec3bdb02cd1f5c`
- MCP: enabled
- D1 migration `0008_modal_plan_health_authorization.sql`: applied; live
  overview includes `modal_authorized_health_checks`.

The Site Worker's standalone `experiment_provider_health` tool now requires a
prepared plan's `run_id` and fingerprint. Before its separately billed Modal
GET, it verifies that the authenticated owner confirmed that exact unexpired
plan, that authorization remains unconsumed, and that CPU admission is enabled.
It reserves both the workspace cooldown and a unique per-plan health row before
the request. D1 failures, closed admission, missing authorization, and replay
fail closed.

## Verification

- Sites Worker tests: 36/36 passed.
- Sites build and packaged-artifact validation: passed.
- All D1 migrations 0000–0008 replayed in SQLite memory; foreign-key checks
  passed after each migration.
- Live D1 overview confirms `modal_authorized_health_checks`.
- ChatGPT capabilities reports the provider configured, authorization storage
  ready, and the expected workload fingerprint.
- Capability state still reports `CPU_WORKLOAD_ADMISSION_DISABLED`,
  `provider_ready=null`, and health deferred. No health call or inference was
  made after Version 32.
- Modal app overview shows one inactive CPU control function, zero live calls
  and zero live Sandboxes. Function details do not expose a trusted current OCI
  workload image digest.
- Previous Modal workload attempts failed with exit code 2, confirmed cleanup,
  and no artifact. They predate this Site Version 32 deployment.
- PR #68 is open and Draft at head
  `602457dbe58a90f8f200e067042c015c4e5d73b9`; all six exact-head checks pass.
  The D1 migration list test initially failed because 0008 was not expected;
  commit `602457d` updates the migration contract test, and the targeted test
  passes.

## Security review

The Codex Security diff scan found zero source-level candidate findings for the
Worker authorization change, D1 migration, artifact validator and regression
tests. The scan used a sequential parent review because delegated review was
unavailable. Its coverage is partial, not a full production security
acceptance. It leaves these questions open:

- Verify Sites' authenticated-user-header provenance and cross-account denial.
- Verify the deployed Modal API's authenticated health response and exact
  registered workload image digest.
- Refresh the connected ChatGPT connector's separate provider-health input
  schema if necessary.
- Verify the effective Modal spend limit and payment-method state.

The full scan report is stored at
`~/.codex/state/plugins/codex-security/scans/gpu-control-pr58-current-candidate/d119bd791f26775b9887c79ec7315db7cda9f16a_20261113T121318Z_e9aj3n3p/report.md`.

## Billing snapshot

The Modal Usage & Billing UI showed a $1 Workspace usage limit, $0.10 in
credits used, $0 charges, and an “Add payment method” action. This is a
point-in-time observation, not a guarantee that future usage cannot be charged.
Modal's documentation distinguishes gross usage limits from net spend limits
and documents automatic monthly and incremental billing:
[Budgets](https://modal.com/docs/guide/budgets) and
[Billing](https://modal.com/docs/guide/billing).

## Remaining acceptance

Keep admission disabled until the registered image identity and authenticated
provider readiness can be verified. After that gate, an authorized fresh plan
must complete from ChatGPT through Modal, produce a verified result artifact,
and confirm cleanup. RunPod/GPU execution, paid training, cross-account
identity isolation, and long-term recovery remain separate uncompleted gates.

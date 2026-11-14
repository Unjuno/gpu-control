# Sites and Modal live-state refresh — 2026-11-13

## Repository and review state

- Checkout: `codex/sites-modal-runner` at
  `e2cd227a306a67c9a9f60825411433719b9527ef` before this documentation update.
- PR #68 is open, Draft, mergeable, and points at that exact head.
- Exact-head CI completed successfully: Python 3.11, 3.12, 3.13, trusted
  reference container, and Sites Worker/D1 contract. Project bridge tests also
  completed successfully.
- The last full Codex Security scan was partial. It recorded no confirmed
  findings but left the authenticated identity-header trust boundary
  unresolved. A new repository-wide Deep Security Scan did not start because
  its coordinator requires a managed read-only filesystem profile. This is a
  scan-start blocker, not a clean scan result.

## Sites production state

- Site `gpu-control-sites` is active at Version 31 and the public production
  URL. Version 31 source commit is
  `7be42adca5306a7cd3d7ecd84718af47969dd9b0`; its Worker archive is unchanged
  from Version 30.
- Version 30 was synchronized from candidate commit
  `dbd4089bbe4e480dff283555638ce201cbd3c82e`. Current PR head contains no
  subsequent Worker source changes relative to that commit.
- The live D1 overview lists `authorization_challenges`,
  `human_authorizations`, `modal_health_check_limits`, `plans`, `runs`,
  `runner_heartbeats`, `provider_account_leases`, and
  `provider_account_lease_events`.
- The currently connected ChatGPT plugin tool inventory does not include
  `experiment_provider_health`; schema refresh remains unverified.
- Live `experiment_capabilities` reports `provider_configured=true`,
  `human_authorization_store_ready=true`, `provider_ready=null`,
  `admission_enabled=false`, `available=false`, and
  `CPU_WORKLOAD_ADMISSION_DISABLED`. The registered workload is
  `tiny-stories-inference-v1`, with advertised Sandbox estimate `$0.0013`,
  Sandbox ceiling `$0.01`, and separately billed Modal control-function calls.
  The advertised fingerprint is
  `3bf90f4c3f99ab1bd9ad8f8a7714fbe63f4ccf8f308c729590e86f29c375d577`; image
  digest is
  `sha256:f0e1bbd44e0bd475dc2f19a548a96e041fc9cb48fc4160d4c0c4de02b0e00541`.
- Modal `unjuno/main` shows the `gpu-control-sites` app deployed, no live
  Sandboxes, and zero API tokens at the time of inspection. No new deployment
  was needed for this checkout; the already deployed app was current.

## Actions and remaining acceptance

This refresh did not prepare or submit a run, call the Modal health diagnostic,
change Site environment variables, start provider compute, or change access.
No inference result was created. Keep admission closed.

Next evidence needed: a managed-profile repository-wide P0 scan; authenticated
owner-header spoof testing or an authoritative platform guarantee; refresh and
exercise the connected ChatGPT tool schema and exact-plan confirmation flow;
reconcile the Modal deployed image fingerprint, digest, and source identity;
then request a fresh exact-plan authorization before one bounded inference and
verify its returned artifact and cleanup. RunPod GPU and paid execution remain
separate gates.

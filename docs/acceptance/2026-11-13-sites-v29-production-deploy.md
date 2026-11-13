# Sites Version 29 production deployment — 2026-11-13

## Scope

Reconcile the live `gpu-control-sites` ChatGPT Site with the GitHub candidate
and deploy the exact-plan authorization workflow while keeping workload
admission disabled. This records the Site source history separately from the
GitHub repository history.

## Source and publish evidence

- Site: `gpu-control-sites`, project
  `appgprj_6af482670c2081919ffe27a6faa0f746`.
- Public URL: <https://gpu-control-sites.unjuno.chatgpt.site>.
- GitHub source snapshot synchronized: `Unjuno/gpu-control` commit
  `01dd2a6e9c51795396418c8e77156f4d574c21e3`.
- Site-bound source repository commit: `6144d58acf6de609c8ac42d0b06542e29d89b1ab`.
- Packaged source archive: 102,400 bytes;
  SHA-256 `e1a7a2666e895df1133a7ef1690e8ac1a54fff9ec67cc81c8fd8a0ad21b0092a`.
- Source checks before publishing: `npm test` 30/30 passed, `npm run build`
  passed, and `npm run validate` passed.
- Saved Site version 29:
  `appgprj_6af482670c2081919ffe27a6faa0f746~appgver_fc04b659425c8191b5bd44b6039b08ed`.
- Production deployment:
  `appgdep_6af6d94a59348191a846936c4cbe8e47`; deployment completed with MCP
  enabled. Runtime environment revision remained 32. No runtime variables or
  secrets were changed. Existing public audience/access configuration was
  retained.

## Post-deploy observations

- A fresh ChatGPT `experiment_capabilities` call reported
  `human_authorization_store_ready=true` and
  `explicit_plan_confirmation_required=true`. It also reported
  `admission_enabled=false`, `available=false`, and
  `CPU_WORKLOAD_ADMISSION_DISABLED`; provider health was deferred until an
  authorized submission.
- Read-only D1 schema overview listed `authorization_challenges`,
  `human_authorizations`, `provider_account_leases`, and
  `provider_account_lease_events`, alongside the existing plan/run/heartbeat
  tables. No user rows were read or changed.
- Worker error logs were empty for the observed five-minute window after
  deployment.
- Modal UI showed zero live Sandboxes and zero running control API calls. No
  new provider execution was submitted.

## Limits and remaining acceptance

This deploy proves source synchronization, Site build/validation, deployment,
the authorization schema's presence, and capability advertisement. It does
not prove browser confirmation from an independently authenticated account,
denial for a separate account, current Modal image readiness, or successful
post-deploy inference. The Modal workload Dockerfile correction still needs a
rebuilt OCI digest and matching image fingerprint deployed to Modal and
registered in the Site environment. RunPod remains disabled. Keep CPU and paid
admission closed until those checks and reviews pass.

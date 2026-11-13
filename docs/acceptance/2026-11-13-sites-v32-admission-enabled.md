# Sites Version 32 admission enabled — 2026-11-13

## Production change

- Site: `gpu-control-sites`
- URL: <https://gpu-control-sites.unjuno.chatgpt.site>
- Site Version: 32, source commit
  `7aacaac46a0111621d450c89a85fde7ce8cca6a2`
- Deployment: `appgdep_6af705a0cc18819180d47ba6a9fd79af`
- Runtime environment revision: 34
- MCP: enabled
- Change: `CPU_WORKLOAD_ADMISSION_ENABLED` changed from `false` to `true`.
  All other runtime variables were preserved.

## ChatGPT confirmation

Calls to `experiment_capabilities` and `experiment_list` succeeded from the
connected ChatGPT account. Capabilities reports:

- `available=true`, `provider_configured=true`, and
  `human_authorization_store_ready=true`.
- `admission_enabled=true`; `provider_ready=null` until a plan-authorized
submission runs the authenticated Modal preflight.
- Only `tiny-stories-inference-v1` is enabled, with 30-second maximum runtime,
  one in-flight run, estimated Sandbox cost `$0.0013`, and maximum Sandbox cost
  `$0.01`.
- Modal control-function costs are excluded from the Sandbox ceiling.

`experiment_submit` checks the exact one-use owner authorization, calls the
authenticated Modal health endpoint, and proceeds to the Sandbox only if the
registered identity matches. No authenticated health call or Sandbox was made
as part of this configuration change. A fresh plan was prepared but expired
without confirmation; no provider request has been sent.

## Provider identity and access limits

- Sites advertises source SHA `3cc7a765cbcbeb7abdfa0d607e8a44e4cdff2288`,
  image fingerprint
  `53b5d84a82830a360f1b90bab6087e54723d9db21989ff3fb5440400f3991eec`, and
  image digest
  `sha256:f0e1bbd44e0bd475dc2f19a548a96e041fc9cb48fc4160d4c0c4de02b0e00541`.
- The Modal `unjuno/main` deployment record points to source commit
  `496e28cdb1b257c2a508e56a11fcdb07f6aa8028`. The locally rebuilt image ID is
  `sha256:60ea9d29f70def1ad4577021ac51e2b186b8f8d2c6dee7a2d2d848b441fcbda1`;
  it has not been verified as the deployed Modal OCI digest. Do not treat digest
  parity as proven.
- The Site has public reachability and owner-scoped MCP authorization. Worker
  code enforces the Sites user ID against the stored owner allowlist. A
  separate-account denial test and platform header-provenance verification
  remain open.
- Modal's API-token inventory showed zero tokens. The named main-environment
  Proxy Token remains configured for the Site; its secret value was not read or
  displayed.

## Spend state

The Modal dashboard showed a `$1` Workspace usage limit, `$0.10` in credit
usage, `$0` in charges, and an option to add a payment method to raise the
limit. No payment method or temporary API token was added. Preserve this cap.
The `$0.01` ceiling covers Sandbox CPU and memory only; control-function
charges remain separate. Modal documents usage budgets as gross usage caps
before credits and a separate net spend limit:
[budgets](https://modal.com/docs/guide/budgets),
[billing](https://modal.com/docs/guide/billing).

## Acceptance still open

- Obtain exact-plan owner confirmation and perform one bounded post-deploy
  inference.
- Verify authenticated provider readiness, returned result provenance, R2
  artifact digest, and Sandbox cleanup.
- Reconcile the actual Modal image identity/digest with the Site registry.
- Verify cross-account denial and finish the repository-wide P0 security audit.
- Implement and accept the RunPod GPU route separately; it remains unavailable
  through the Sites MCP Worker.

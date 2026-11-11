# Current operations: ChatGPT Sites + D1

The supported ChatGPT control plane is the owner-private Sites MCP Worker at
`https://gpu-control-sites.unjuno.chatgpt.site`. Its product records are stored
in the Sites-provisioned D1 database. The current free CPU Runner is a separate
Linux process and executes only the exact registered workload image. The Site
Worker does not execute containers or accept caller-selected code, images, or
provider settings.

## Verified now

- ChatGPT can discover and call the private Site's experiment tools.
- One fixed-image CPU checksum smoke completed through ChatGPT → Sites → D1 →
  Runner → D1 → ChatGPT; result retrieval and container cleanup were confirmed.
- Repeating the same submission returns the existing run instead of starting
  another container.
- CPU admission is limited to one in-flight run and 30 seconds. The workload
  reports `gpu_used=false`; paid provider execution remains parked.

These checks do not prove model inference, GPU execution, forced-restart
recovery, cross-owner isolation, or R2 artifact retrieval. Do not use this
candidate to claim those capabilities.

## Operating boundaries

- Keep the Site owner-private. Sites authenticates MCP callers; each tool must
  still enforce persisted owner checks.
- Keep provider credentials out of the Site source, MCP arguments, logs, and
  workload container. Store runtime secrets only through the Sites secret
  controls and the Runner host's protected secret mechanism.
- Keep paid execution parked until its separate approval, price, quota,
  authentication, cleanup, and recovery gates pass.
- Do not bring the archived FastAPI/PostgreSQL, Vercel, or Neon stack back into
  the product path. Historical runbook: `archive/OPERATIONS-legacy-postgresql.md`.
- Do not delete the existing Neon project until its auth/run records are
  classified and any retained data has a verified export. Do not delete Vercel
  rollback resources until Sites acceptance and recovery are complete.

## Open operational acceptance

1. Publish the reviewed exact-commit inference image and verify its generated
   result through ChatGPT. Local candidate inference alone does not close this.
2. Exercise cancellation, Runner interruption/restart, lease expiry, result
   reconciliation, and cleanup against the live Site and Runner.
3. Store immutable artifacts in R2 and verify owner-bound retrieval and digest.
4. Test owner isolation across separate accounts and verify Site access revocation.
5. Add and rehearse a supported Runner start/stop, secret rotation, backup,
   restore, and incident procedure before increasing admission or enabling paid
   providers.

Detailed current state and evidence: `decisions/2026-11-11-sites-d1-architecture-pivot.md`.

# Sites Version 39 Modal asynchronous repeat — 2026-11-15

## Publication

- Site source commit
  `b1e8fb189087c87ded52a21c9ad254382a06426d` was pushed to the
  Site-owned repository and saved as Version 39.
- Saved version:
  `appgprj_6af482670c2081919ffe27a6faa0f746~appgver_f110b4e3f32c8191819070ad123d7614`.
- Production deployment `appgdep_6af95cb013508191b32e539a7b322067`
  succeeded at environment revision 40 with MCP enabled. The existing public
  audience and owner account were preserved.
- Modal `unjuno/main` app `gpu-control-sites` was redeployed from the same
  asynchronous source candidate. The CLI reported `control_api` deployed in
  3.243 seconds. This deployment itself created no Sandbox.
- The first local CLI attempt stopped before deployment because FastAPI was not
  installed in the ephemeral CLI environment. Re-running with the repository's
  pinned FastAPI version succeeded.
- Two one-hour Workspace API tokens were created during recovery of the CLI
  authentication flow: one unused browser-created token and one CLI token used
  for deployment. Both were explicitly deleted. A fresh token-list load showed
  `API tokens 0`.

## Exact repeat run

- run ID: `9f2c52912b234888b709c7a04bdeb707`;
- plan fingerprint:
  `76b20f272b8ba3e8d7d70a24ffcb55e53f9d99d5bc582bb4256b530861aaddb9`;
- source: `Unjuno/gpu-control` at
  `3cc7a765cbcbeb7abdfa0d607e8a44e4cdff2288`;
- prompt `Once`, one generated token, seed `61121`;
- one physical CPU core, 512 MiB, 30 seconds maximum, GPU prohibited;
- estimated maximum Sandbox charge `$0.0013`, Sandbox ceiling `$0.01`,
  separately billed control-function calls excluded.

The owner-confirmed submit returned a normal `pending` response with durable
state `running` and cleanup `pending`; it no longer ended in the earlier
generic host `INTERNAL_ERROR`. The next status call reconciled the same run to
`succeeded`, execution origin `modal_sandbox`, and cleanup `confirmed`.

The result generated `Once upon` in 80 ms, used no GPU, and passed all nine
source, parameter, model, inference, privilege, secret, Docker socket,
read-only-root, and network-isolation checks. Result checksum:
`7f46f255542e6b7627f6cc4afb1425bd0caa973d251630f4bde8c24bc8c9be9f`.

## Artifact, provider, and budget evidence

- The complete 931-byte R2 artifact was retrieved in one bounded chunk.
- Its recorded SHA-256 was
  `ec712f014b4675f829ee4ef96dc8d6fd33cc02359d2c29038167185546ab6b14`.
  Independent local base64 decoding and `shasum -a 256` produced the same
  digest.
- Modal independently displayed Sandbox
  `gpu-control-9f2c52912b234888b709c7a04bdeb707` as `Done`, with 575 ms
  lifetime and zero concurrent Sandboxes.
- The post-run Usage page still displayed `$0.10 in credits`, `$0 in charges`,
  `$0.10 / $1`, and a Workspace usage limit of `$1`. Billing can lag; this is
  a timestamped observation, not a claim of zero eventual control-function
  cost. No payment method or limit was changed.

## Acceptance boundary

This accepts repeatability of the fixed owner-confirmed Sites to Modal CPU
vertical and the asynchronous submit repair. It does not yet accept a forced
live cancellation/restart drill, a separate-account denial/distribution flow,
real GPU execution, or RunPod. Those remain separately gated.


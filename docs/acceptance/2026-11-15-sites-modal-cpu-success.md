# ChatGPT Sites to Modal CPU acceptance — 2026-11-15

## Accepted vertical

The owner-authenticated ChatGPT tool path completed a real registered CPU
inference through ChatGPT Sites, D1, the Modal control function, a bounded Modal
Sandbox, R2 result storage, and cleanup. This accepts that fixed CPU vertical
only; it does not establish GPU or RunPod acceptance.

## Connection repair

- Initial Version 35 submissions failed at Modal health before Sandbox creation.
  Rotating the existing same-scope Proxy Token did not change that result.
- Version 36 added bounded health diagnostics. It returns only allowlisted
  status classes and never response bodies, credentials, URLs, or arbitrary
  exception text.
- Version 37 switched to Modal's documented single
  `Authorization: Bearer <token-id>.<token-secret>` proxy-auth form while
  retaining exact-origin checks and secret-redaction tests.
- Version 38 changed redirect handling from exception mode to manual mode. A
  redirect is never followed and is rejected as a bounded 3xx diagnostic, so
  credentials cannot be forwarded to another origin. Version 38 source commit
  `e8515950bdda0583300ae6b85258a14429527077`, archive hash
  `sha256:381a5c06f8f8802f8736878f5efae98e08e2ec09f718891eefbd93b98bdc4fec`,
  and deployment `appgdep_6af9098cab5881919f443a82f6650f31` published
  successfully with MCP enabled at environment revision 40.

All three Worker changes passed 44/44 tests, build, artifact validation, and
production deployment. The successful submit returned a generic host
`INTERNAL_ERROR` after roughly 22 seconds. The run had nevertheless been
atomically reserved, so the client did not resubmit. Owner-scoped list and
status recovery reconciled that same run to its terminal Modal result. This
also exercises the ambiguous-submit-response recovery path.

## Exact run

- run ID: `245d034977e5471aa7ec6d1f80f6232f`;
- plan fingerprint:
  `0bca9be59c65a2e798408c65586dc12b171f0f1b147010f79ba6f2332cd61bcc`;
- source: `Unjuno/gpu-control` at
  `3cc7a765cbcbeb7abdfa0d607e8a44e4cdff2288`;
- prompt `Once`, one new token, seed `61120`;
- CPU request/limit 1 physical core, memory request/limit 512 MiB, maximum
  runtime 30 seconds, GPU prohibited;
- displayed Sandbox estimate `$0.0013`, Sandbox ceiling `$0.01`, separately
  billed control-function calls excluded.

The terminal result reported state `succeeded`, execution origin
`modal_sandbox`, cleanup `confirmed`, `gpu_used=false`, generated text
`Once upon`, one generated token, and 50 ms inference time. It passed the
expected nine checks: source identity, parameter bounds, model digest,
completed inference, non-root execution, no secret environment, no Docker
socket, read-only root filesystem, and disabled workload networking. The model
digest was `cd590644d963867a2b6e5a1107f51fad663c41d79c149fbecbbb1f95fa81f49a`
and the result checksum was
`938e01b49e498dbfea04e587dbd706b8c7194a0ff34cf00e61b49f5e099c637f`.

## Artifact and cleanup

The owner retrieved the complete 931-byte R2 `result-json-v1` artifact. The
tool verified its owner/run binding and stored digest. Independent local
base64 decoding and SHA-256 calculation produced
`86d88aa2593829f818003288b0d48a86807f2161e88cf6b5dd41af2e582325d7`,
exactly matching the recorded digest.

The Modal dashboard independently showed one Sandbox named
`gpu-control-245d034977e5471aa7ec6d1f80f6232f`, status `Done`, 693 ms lifetime,
and `Concurrent sandboxes 0`. The control-plane terminal state and provider UI
therefore agree that no compute remained live.

## Billing and remaining scope

The post-run Modal Usage limit page still displayed `$0.10 in credits`, `$0 in
charges`, `$0.10 / $1`, with the Workspace limit fixed at `$1`. Billing may be
delayed, so this is a timestamped observation rather than a claim of zero final
cost. No payment method was added and no limit was raised.

This accepts the current fixed Modal CPU vertical. Recovery and operational
stability drills are next. RunPod, real GPU, and broader paid execution remain
parked behind their own authorization, account-lease, result, cleanup, and
budget gates.

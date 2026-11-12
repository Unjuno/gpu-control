# Modal and CPU inference chronology — 2026-11-12

> **Chronology correction:** the successful run recorded below was executed by
> the local macOS Runner under Sites Version 16, as documented in
> [`Runner environment sanitization`](2026-11-12-runner-environment-sanitization.md).
> It was not a Modal run and does not verify the Modal app. The two Modal
> failures below predate the Modal dashboard's v4 deployment at 2026-11-12
> 18:06 JST. No successful inference has been observed after v4; the v4
> dashboard history did not expose a source commit. This record's earlier
> post-fix attribution is superseded.

## Historical successful CPU inference — local Runner

Through the connected `GPU Control — ChatGPT実験管理` tools, run
`eacc26ff2ad54cf69a1ee7665325b197` reached `succeeded` for the registered
`tiny-stories-inference-v1` workload. It used source SHA
`3cc7a765cbcbeb7abdfa0d607e8a44e4cdff2288`, image digest
`sha256:f0e1bbd44e0bd475dc2f19a548a96e041fc9cb48fc4160d4c0c4de02b0e00541`,
prompt `It was a bright morning`, seed `61113`, and a four-token limit. The
Modal result reports 142 ms, `gpu_used=false`, all registered isolation and
identity checks passed, and `cleanup_state=confirmed`.

ChatGPT retrieved the complete `result.json` artifact in one bounded chunk:
962 bytes, EOF true, SHA-256
`39ff3134a0b69d34ea8e4d220a4445583c803eb6382c88593a291486cffb5030`.
The Site reported the matching artifact digest and validated the returned
chunk. The result's inference checksum is
`cd9d86fce2148fddbf96a27107fafcfd2d8a3a378f8d60665a112dc0cceb4623`.

## Modal failures before the current dashboard deployment

Two later runs, `96d7efef9542463d9fc51f47ffbfd5d7` at 08:21 UTC and
`599473dcc1ed4034a42d849bcb42e261` at 08:52 UTC, ended as
`MODAL_WORKLOAD_FAILED`; both reported `cleanup_state=confirmed` and no result
artifact. The Site status response did not preserve the Modal Sandbox exit code
or stderr. The Modal deployment Logs view filtered to the latter Sandbox ID
showed no logs. The exact runtime failure remains undiagnosed. A later
read-only capabilities call at 10:22 UTC reported provider health ready,
`admission_enabled=false`, and `available=false`.

## Sites diagnostic follow-up

Site Version 24, source commit `c919b0047b203fb0c22b6dd7755934834e899f8f`,
was published after adding a bounded failure code derived from the Modal exit
code. It does not expose provider stderr. Post-publish ChatGPT capabilities
still report provider ready, admission disabled, and unavailable; the D1/R2
environment revision remains 22. No new Sandbox was started, so live behavior
of the diagnostic has not been observed.

## Acceptance boundary

The successful local Runner result proves that historical bounded CPU inference
and artifact retrieval through Sites worked at that time. The two failed Modal
runs prove cleanup was reported for those attempts, but they predate the v4
deployment and do not characterize that deployment. Current Modal inference,
cross-account owner isolation, and complete recovery remain unaccepted. Keep
admission closed. Paid execution remains parked.

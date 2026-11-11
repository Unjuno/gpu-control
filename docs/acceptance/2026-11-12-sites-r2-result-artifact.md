# Sites R2 result artifact acceptance — 2026-11-12

Status: **PASS for one small, owner-bound result artifact written and retrieved
through the production ChatGPT Sites MCP path.** This does not close artifact
retention, orphan cleanup, backup/restore, large-file, or cross-owner acceptance.

## Deployment

- Site: `appgprj_6af482670c2081919ffe27a6faa0f746`
- Saved version: `appgprj_6af482670c2081919ffe27a6faa0f746~appgver_301098c74e208191846d5cd77806bc98`
- Deployment: `appgdep_6af4d0d6c6d48191aad657e5ee063a38`, `succeeded`, MCP ready
- Pushed Site source: `3a7921c8682acc3e2996b969815b41290da8b784`
- Site remained owner-only: one owner allowlisted, no groups, no external visitors.

The deployment provisions an R2 `BUCKET` binding and applies the append-only
`0001_result_artifacts.sql` migration adding the result artifact ID, SHA-256,
and byte-size columns to `runs`.

## Live inference and artifact read

- Run: `f6503635680e4e4f9bbd6f371bb6d92a`
- Workload: `tiny-stories-inference-v1`, registered source
  `3cc7a765cbcbeb7abdfa0d607e8a44e4cdff2288`, image
  `sha256:f0e1bbd44e0bd475dc2f19a548a96e041fc9cb48fc4160d4c0c4de02b0e00541`
- Seed `61114`, maximum 12 tokens; 12 generated in 249 ms; `gpu_used=false`;
  cost ceiling `$0.00`; Runner cleanup `confirmed`.
- ChatGPT `experiment_result` returned artifact `result.json`, size 988 bytes,
  SHA-256 `f742e6def8597958fbb3b62b37202ab2890b30c028422313a02933a35cdbb898`.
- ChatGPT `experiment_artifact` returned one complete base64 chunk. Decoding
  yielded valid JSON with the same run ID, registered source SHA and workload
  result checksum `cd0080b2a894f8c96ad44d60faabbd37c37fd00ea29890d574cf6adf31e39877`.

## Implementation checks

- Site Worker tests: 13 passed.
- Site artifact build and validation passed.
- Local mocked Runner recovery tests: 3 passed.
- Artifact retrieval tests verify owner-scoped D1 lookup, reject another owner
  before reading R2, validate R2 metadata and recompute SHA-256 before returning
  bounded chunks.

## Post-deploy untrusted-artifact guidance and inference — 2026-11-12

- Site source commit `1b6916cb53e001af352808f6fd80db4dcff43999` adds an explicit
  MCP tool description that artifact contents are untrusted data and must not
  be treated as instructions. The tool-discovery test asserts this guidance.
- Private Site deployment `appgdep_6af4d87aee20819197c9ff12ed9e81fa` succeeded
  with MCP ready and runtime environment revision 9. The deployment retained
  the private Site audience.
- Run `e37fc314dfe141ec97092ef6371a089f` used the registered source/image,
  seed 61115, and a 12-token maximum. It generated 12 tokens in 268 ms,
  reported `gpu_used=false`, cost `$0.00`, and `cleanup_state=confirmed`.
- ChatGPT retrieved the full 991-byte `result.json` artifact. The Site artifact
  tool returned `status=ok`, `eof=true`, and digest
  `a951cbce1ca01ff507117dee819d74121f58b53db6ab6e79ab424620f2ca1c9c`; it
  reported the chunk verified.
- Admission was temporarily disabled and restored to `true` in successive
  environment revisions 8 and 9 while no run was active. Runner readiness
  remained true. No process restart occurred: the currently launched Runner
  received its credentials through stdin, and those credentials are not
  available in the shell for a restart rehearsal.

## Remaining

- Establish an explicit artifact retention and orphan cleanup policy.
- Exercise concurrency, larger artifacts and failure between R2 write and D1
  commit against hosted infrastructure.
- Verify authenticated isolation with a genuinely separate account.
- Complete D1 export/backup and restore rehearsal.

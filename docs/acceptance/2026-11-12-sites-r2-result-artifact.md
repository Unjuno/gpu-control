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

## Remaining

- Establish an explicit artifact retention and orphan cleanup policy.
- Exercise concurrency, larger artifacts and failure between R2 write and D1
  commit against hosted infrastructure.
- Verify authenticated isolation with a genuinely separate account.
- Complete D1 export/backup and restore rehearsal.

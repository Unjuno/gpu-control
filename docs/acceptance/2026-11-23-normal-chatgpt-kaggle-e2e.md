# Normal ChatGPT Kaggle E2E — 2026-11-23

## Accepted path

A normal ChatGPT conversation issued one request to use the free Kaggle route.
GPU Control completed the owner-bound `prepare -> submit -> status -> result ->
cleanup` lifecycle without asking the user to repeat the plan approval.

- run: `0fb72577bea058b01621e1fc58ce9da1`
- provider: Kaggle
- source: `44a1b806160ab5bc721a370d034a6dfcb28f27a8`
- device: Tesla T4
- execution: `gpu_used=true`, `simulation=false`, exit code 0
- training: 100/100 steps
- validation loss: `5.315847873687744`
- checkpoint SHA-256:
  `b990b1468bc60d8f461c32742bd171349c1463a5d96d4def14442399187db6e0`
- known cost: `$0` (`FREE_QUOTA`)
- cleanup: confirmed

## Artifact finding

The external private ZIP reference was consistent across the run and result:

- revision: `97cbec86cfa60997eef0a4d3d034ef7f2b5461e7`
- path: `runs/0fb72577bea058b01621e1fc58ce9da1/orbitune-output.zip`
- recorded size: 1,737,429 bytes
- recorded SHA-256:
  `4e4ee008812845be511533240698f6fee59794fc9fc4b91135250e744ef7a1e5`

The first deployed MCP exposed only this credential-free reference, so ChatGPT
correctly returned an uncertain result instead of claiming a new hash
calculation. The accepted follow-up keeps the credential inside the Modal
provider adapter, downloads only the allowlisted repository and exact immutable
revision/run path, checks the complete size and SHA-256, and returns at most
24 KiB per owner-bound `experiment_artifact` call.

The updated adapter and Sites Version 79 were deployed on 2026-11-23. A live
read of offsets `0..24575` and `24576..49151` returned two consecutive chunks
for the same run. Before each chunk was returned, the adapter re-downloaded and
verified the complete 1,737,429-byte ZIP at the exact revision. Both responses
reported:

- `full_file_verified=true`
- `verification_method=exact_revision_size_and_sha256`
- SHA-256
  `4e4ee008812845be511533240698f6fee59794fc9fc4b91135250e744ef7a1e5`

Artifact chunk responses are not persisted in D1, so private ZIP bytes do not
replace or enter the stored terminal provider result. This artifact slice is
accepted.

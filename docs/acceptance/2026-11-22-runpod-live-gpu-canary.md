# RunPod live GPU canary acceptance — 2026-11-22

## Accepted scope

The authenticated ChatGPT GPU Control connector prepared and submitted exactly
one owner-bound `runpod-gpu-canary-v1` plan through Sites v65. The run reached a
real RunPod Serverless job, returned an authenticated result for the pinned
source and image, and finished with confirmed cleanup.

| Field | Observed value |
| --- | --- |
| Run ID | `a4284e1e08cf458db708647893e31d71` |
| Provider job ID | `712b3b99-439a-4d9a-80a0-fd95067ffa25-u1` |
| Source SHA | `44cc4501afeb6c1fd2d977859980c05f830f58a1` |
| Image digest | `sha256:0f952ae240e6044bb75ebca29c11dd4c526cd69aeea35decbba76c2d516b1c49` |
| GPU | `NVIDIA RTX 2000 Ada Generation` |
| CUDA compute capability | `8.9` |
| Device count | `1` |
| Total VRAM | `16724066304` bytes |
| Free VRAM | `16624386048` bytes |
| Canary wall time | `0.369781494140625` seconds |
| Result | `gpu_used=true`, `state=succeeded` |
| Cleanup | `confirmed` |

The reviewed plan estimated a worst-window cost of `$0.049139` and enforced a
`$1.00` per-run ceiling.

### Cost wording correction (2026-11-29)

The wording above records what the earlier Sites plan displayed; it is not
evidence of a RunPod-enforced billing cap. The `$1.00` value was GPU Control's
internal reservation ceiling. RunPod bills initialization and may retry queue
jobs, so the earlier displayed estimate did not bound every possible provider
charge. The dashboard's zero balance change for this canary is a separate
observation and does not prove that future attempts are capped. Current source
plans display an estimate with its initialization/TTL/idle assumptions and
explicitly mark `provider_charge_hard_capped: false`.

After completion, the authenticated RunPod endpoint page showed `0` running,
`0` idle and `0` initializing workers, with `0` jobs in progress and `0` queued.
The endpoint's past-hour summary showed one total request, one completed, zero
failed and zero retried. Its billing card displayed total billed `$0.00` and a
`$0.00000/second` spend rate. The dashboard value is rounded provider UI
evidence; this record does not promote it into a sub-cent billing receipt.

## Recovery and migration evidence

Two earlier submissions never obtained a provider job ID. They were not
resubmitted and ended as `RUNPOD_AMBIGUOUS_SUBMIT_TTL_ELAPSED` with confirmed
cleanup. The final candidate fixes both migration boundaries exposed by those
runs:

- native Sites RunPod state takes precedence over a stale delegated-plan row;
- a relay-receipt failure cannot strand an ambiguous run after the fixed
  provider-side five-minute TTL.

The approval window is ten minutes while the provider-side execution TTL
remains five minutes. This changes neither the GPU, image, source, runtime nor
cost ceiling.

## Verification boundary

This proves the RunPod ChatGPT-to-Sites-to-Modal-relay-to-RunPod GPU lifecycle
for the registered canary and this account. It does not prove Kaggle or Hugging
Face execution, cross-account denial, exact provider billing, or arbitrary
workloads.

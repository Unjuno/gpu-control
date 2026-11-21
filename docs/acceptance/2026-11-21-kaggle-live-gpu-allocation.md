# Kaggle live GPU allocation check — 2026-11-21

## Scope

This record covers the ChatGPT Sites -> signed Modal provider adapter -> Kaggle
Kernel path for the registered `orbitune-kaggle-100-step-v1` workload. It is
not acceptance evidence for a successful GPU workload.

The fixed source was `Unjuno/orbitune` commit
`44a1b806160ab5bc721a370d034a6dfcb28f27a8`. Paid fallback remained disabled,
the approved maximum cost was zero, and the workload refused to fall back to
CPU.

## Adapter defect found and fixed

The first live submission attempts failed before provider creation because the
credential-isolated Kaggle subprocess deliberately omitted `PYTHONPATH`, while
the read-only status bridge was invoked with `python -m`. The bridge is now
invoked by its packaged absolute file path. Focused backend, bridge, workload,
and Modal adapter tests passed after the change. The fix was pushed as
`5bf3a16` and deployed to `gpu-control-provider-adapter` in Modal `unjuno/main`.

## Provider observations

| Sites run ID | Kaggle version | Requested shape | Outcome |
| --- | ---: | --- | --- |
| `e9c402d19eb3490b9a47940937263e5d` | 1 | `NvidiaTeslaT4` | Failed closed because `torch.cuda.is_available()` was false |
| `8a5bed2aea58783677feca5161b450da` | 2 | `NvidiaTeslaT4` | Same CPU allocation and fail-closed result |
| `3b6e090cf45e7dfc54ce69dfde78d3f0` | 3 | `NvidiaL4` | Same CPU allocation and fail-closed result |

For version 1, a read-only pull of Kaggle's persisted metadata showed
`enable_gpu=true`, `enable_tpu=false`, and
`machine_shape=NvidiaTeslaT4`. Immediately after the failed attempts, the
official quota endpoint still reported 30.00 GPU hours remaining and 0.00 GPU
hours used. Each Sites result recorded `cleanup_state=confirmed`.

The L4 selection was committed as `f6f9a75` only after the two T4 attempts
reproduced the same provider allocation. L4 did not change the result. No
further automatic retries are permitted until the authenticated Kaggle account
settings are inspected and the provider confirms an accelerator is actually
available to this account.

## Acceptance decision

Kaggle GPU acceptance is **NOT PASSED**. Kernel creation, exact version
tracking, bounded status capture, CPU fail-closed behavior, and cleanup were
observed. Those facts do not prove GPU execution, 100 training steps, artifact
publication, or the downstream Hugging Face ZeroGPU evaluation.

Next acceptance requires all of the following on a new run ID:

1. Kaggle reports a non-CPU accelerator for the committed version.
2. The workload records CUDA device identity and completes exactly 100 steps.
3. The immutable result bundle is uploaded to the allowlisted private Hugging
   Face artifact repository with revision and SHA-256 evidence.
4. Sites returns the provider result and confirms cleanup.


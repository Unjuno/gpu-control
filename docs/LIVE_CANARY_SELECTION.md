# First live GPU canary selection

## Decision

The first paid provider canary should use `Unjuno/orbitune` and its bounded `runpod-training-canary` workload.

This decision is about validating the control-plane/provider path. It is not a claim that Orbitune is the highest-value scientific GPU experiment.

## Why Orbitune is first

At the reviewed candidate it already provides the narrowest useful end-to-end contract:

- public immutable source identity;
- dedicated Dockerfile;
- finite non-interactive PyTorch training;
- deterministic synthetic data with no runtime download;
- no runtime network requirement;
- explicit CUDA requirement and device evidence;
- bounded runtime/cost/training amount;
- bounded result and checkpoint contract;
- source-SHA and image-digest correlation;
- authenticated completion-envelope implementation and CPU smoke coverage.

This removes dataset availability, external model downloads, interactive services, and scientific benchmark ambiguity from the first provider test.

## Candidate comparison

- `Unjuno/orbitune`: best first infrastructure canary because the paid workload contract is already purpose-built and bounded.
- `Unjuno/sync-transformer`: best follow-up scientific GPU experiment. Its documented CUDA extension answers a real unresolved comparison against RAFT, but it introduces external baseline/data/dependency variables that should not be mixed into the first provider-path test.
- `Unjuno/canaria-neural-simplification`: strong reproducibility discipline, but its strongest minimal public experiment is already CPU-viable, so GPU spend has lower immediate information value.
- `Unjuno/resource-conditioned-neural-computation`: current next empirical boundary is physical FPGA/DE0-CV validation rather than commodity cloud-GPU execution.
- `Unjuno/flatness-decoding`: GPU-relevant but large-model caches and model/data dependencies add unnecessary variables for the first paid canary.

## Escalation order

1. Orbitune micro-canary: smallest CUDA/container/provider/completion/cleanup validation that answers whether the live path works.
2. Orbitune bounded training canary only if the micro-canary leaves a material unresolved question.
3. SYNC Transformer CUDA extension as a separately justified scientific execution.

Success at one stage does not authorize the next stage. Each paid stage requires current pricing, current evidence, a fresh DecisionRecord, and exact human authorization.

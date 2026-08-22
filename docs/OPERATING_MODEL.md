# Operating Model

`gpu-control` is designed for a staged experiment workflow. The control plane should reduce uncertainty before it spends money.

## 1. Start in a local container

Use the workload Dockerfile as the first reproducibility boundary. The first question is not whether a large training run succeeds; it is whether the workload starts, imports its dependencies, accepts the intended configuration, writes outputs, and exits correctly.

Use CPU execution when it can validate the code path. If a GPU is available locally, use it before allocating remote compute.

## 2. Minimize the experiment

Reduce the workload to the smallest experiment that can answer the current question:

- small or synthetic/public input;
- few steps or batches;
- one process;
- short timeout;
- no unnecessary services;
- no private data unless the entire path is explicitly designed for it.

A failure at this stage should normally be fixed here rather than escalated to a larger machine.

## 3. Put the workload in its own repository

A GPU workload should live separately from `gpu-control`. The repository is the reproducibility and collaboration boundary.

The baseline contract is:

```text
repository
+ immutable commit SHA
+ Dockerfile
+ locked/reproducible dependencies
+ finite container entrypoint
```

Repository creation, collaborator access, secrets, and write permissions remain explicit human-controlled boundaries. An agent must not infer authorization merely because a repository exists.

The current public MVP accepts public GitHub workload repositories only. Private-repository support requires a separate authorization design rather than merely passing a more powerful token.

## 4. Validate through the control plane

Before paid execution, `gpu-control` validates the request and resource policy and verifies public GitHub source identity.

The gate sequence is:

```text
self-test
  -> request validation
  -> policy validation
  -> repository visibility verification
  -> exact commit SHA verification
  -> Dockerfile-at-SHA verification
  -> isolated container build/smoke test (next milestone)
  -> dry-run
  -> provider price verification
  -> cleanup guarantee
  -> explicit human authorization evidence
  -> ApprovedExecutionPlan
```

A failed gate stops escalation. Source verification is read-only and does not execute repository code.

## 5. Treat container execution as a separate trust boundary

Building or running an arbitrary workload Dockerfile executes untrusted code. It must not be casually inserted into a credential-bearing GitHub Actions job.

The container-verification stage therefore needs its own isolation model, bounded runtime/resources, and threat analysis before it becomes a generic control-plane feature.

Until then, `gpu-control` intentionally stops after source verification and dry-run validation.

## 6. Produce an approved execution plan

Future provider adapters must not accept raw workload requests.

`src/gpu_control/execution.py` produces an immutable `ApprovedExecutionPlan` only when source identity matches the request and the following are all satisfied:

- container verification passed;
- dry-run passed;
- provider price is verified;
- projected worst-case spend fits the requested and policy limits;
- cleanup is guaranteed;
- explicit human authorization is present with an audit reference;
- the current one-GPU MVP policy is satisfied.

Worst-case cost is rounded upward to the nearest cent before approval.

The gate does not authenticate a human by itself. The trusted caller or workflow must establish genuine authorization evidence; an agent must not fabricate it.

## 7. Use RunPod as the final escalation stage

RunPod is the first intended external GPU provider, not the default development environment.

A future RunPod adapter should accept only an `ApprovedExecutionPlan`. It must not allocate resources directly from user-supplied repository, runtime, cost, or GPU values.

Every paid run must use an asynchronous submit/collect lifecycle and cleanup on success, failure, timeout, cancellation, and allocation-related provider errors where possible.

If price, authorization, policy compliance, approved-plan status, or cleanup cannot be established, do not allocate the resource.

## Why the order matters

This ordering keeps debugging signals clean. Local/container failures are usually code or dependency failures. Repository and CI failures are packaging or integration failures. Only after those layers are stable does a remote GPU failure meaningfully indicate a provider, CUDA, VRAM, or GPU-specific problem.

It also prevents an automated agent from treating a connected GPU provider as an unrestricted execution environment.

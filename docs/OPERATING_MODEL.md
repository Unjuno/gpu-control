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

Before paid execution, `gpu-control` validates the request and resource policy. It now also verifies public GitHub source identity before any provider integration is enabled.

The gate sequence is:

```text
self-test
  -> request validation
  -> policy validation
  -> repository visibility verification
  -> exact commit SHA verification
  -> Dockerfile-at-SHA verification
  -> container build/smoke test (next milestone)
  -> dry-run execution plan
```

A failed gate stops escalation. Source verification does not execute repository code.

## 5. Use RunPod as the final escalation stage

RunPod is the first intended external GPU provider, not the default development environment.

Use it only when the experiment requires GPU compute that is not reasonably available in the earlier stages, or when a human explicitly requests the remote GPU run after the gates pass.

Every paid run must be bounded by:

- one GPU by default;
- an explicit GPU profile;
- an explicit runtime ceiling;
- an explicit cost ceiling;
- an immutable workload commit;
- an asynchronous submit/collect lifecycle;
- cleanup on success, failure, timeout, and cancellation.

If price, authorization, policy compliance, or cleanup cannot be established, do not allocate the resource.

## Why the order matters

This ordering keeps debugging signals clean. Local/container failures are usually code or dependency failures. Repository and CI failures are packaging or integration failures. Only after those layers are stable does a remote GPU failure meaningfully indicate a provider, CUDA, VRAM, or GPU-specific problem.

It also prevents an automated agent from treating a connected GPU provider as an unrestricted execution environment.

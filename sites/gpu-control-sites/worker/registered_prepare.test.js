import test from "node:test";
import assert from "node:assert/strict";
import { registeredPrepareArguments } from "./registered_prepare.js";
import { WORKLOADS } from "./workload_registry.js";

const sha = "a".repeat(40);

test("registered CPU ID resolves only pinned repository, source and bounded defaults", () => {
  const workload = WORKLOADS.tiny_stories;
  const result = registeredPrepareArguments({ workload_id: workload.id, idempotency_key: "cpu-idempotency-1" }, {
    CPU_WORKLOAD_REPOSITORY: workload.repository,
    [workload.source_sha_env]: sha,
  });
  assert.deepEqual(result, {
    repository: workload.repository, commit: sha, workload: workload.id,
    parameters: { prompt: "Once", max_new_tokens: 1, seed: 61112 },
    runtime_seconds: workload.runtime_seconds, max_cost_usd: workload.cost_ceiling_usd,
    idempotency_key: "cpu-idempotency-1",
  });
});

test("registered Kaggle ID resolves the immutable zero-cost workload definition", () => {
  const workload = WORKLOADS.kaggle_training;
  const result = registeredPrepareArguments({ workload_id: workload.id, idempotency_key: "kaggle-idempotency-1" }, {});
  assert.deepEqual(result, {
    repository: workload.repository, commit: workload.source_sha, workload: workload.id,
    parameters: {}, runtime_seconds: workload.runtime_seconds, max_cost_usd: "0",
    idempotency_key: "kaggle-idempotency-1",
  });
});

test("registered RunPod ID requires the current pinned source environment", () => {
  const workload = WORKLOADS.runpod_canary;
  assert.equal(registeredPrepareArguments({ workload_id: workload.id }, {}), null);
  const result = registeredPrepareArguments({ workload_id: workload.id, idempotency_key: "runpod-idempotency-1" }, {
    [workload.source_sha_env]: sha,
  });
  assert.equal(result.repository, workload.repository);
  assert.equal(result.commit, sha);
  assert.equal(result.max_cost_usd, workload.cost_ceiling_usd);
});

test("unknown registered workload IDs fail closed", () => {
  assert.equal(registeredPrepareArguments({ workload_id: "unregistered" }, {}), null);
});

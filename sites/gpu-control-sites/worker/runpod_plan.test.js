import assert from "node:assert/strict";
import test from "node:test";
import { prepareRunpodExperiment, validRunpodPrepare } from "./runpod_plan.js";

function environment() {
  const rows = new Map();
  return {
    RUNPOD_API_KEY: "safe-runpod-key-with-enough-bytes",
    RUNPOD_WORKLOAD_IMAGE: `ghcr.io/unjuno/gpu-control-runpod-canary@sha256:${"a".repeat(64)}`,
    RUNPOD_GPU_ID: "NVIDIA RTX 2000 Ada Generation",
    RUNPOD_SERVERLESS_ENDPOINT_ID: "endpoint_test_123",
    RUNPOD_SERVERLESS_HOURLY_PRICE_USD: "0.240000",
    RUNPOD_SERVERLESS_GPU_POOL_ID: "ADA_24",
    RUNPOD_WORKLOAD_SOURCE_SHA: "b".repeat(40),
    DB: { prepare(sql) { return { bind(...values) { return {
      async run() {
        if (sql.includes("INSERT OR IGNORE INTO plans") && !rows.has(values[2])) {
          rows.set(values[2], { id: values[0], fingerprint: values[3], provider_plan_json: values[11],
            state: "prepared", expires_at: values[10] });
        }
        return { meta: { changes: 1 } };
      },
      async first() { return rows.get(values[1]) ?? null; },
    }; } }; } },
  };
}

function args() {
  return { workload: "runpod-gpu-canary-v1", repository: "Unjuno/gpu-control", commit: "b".repeat(40),
    parameters: {}, runtime_seconds: 30, max_cost_usd: "1.00", idempotency_key: "runpod-plan-test-001" };
}

test("prepares one immutable owner-bound Runpod price plan without allocating", async () => {
  const env = environment();
  let offers = 0;
  const client = { async getVerifiedOffer() { offers++; return { gpuId: env.RUNPOD_GPU_ID, cloud: "SERVERLESS",
    gpuCount: 1, hourlyPriceUsd: 0.24, availability: "CONFIGURED", dataCenterId: env.RUNPOD_SERVERLESS_ENDPOINT_ID,
    checkedAt: 1000, validForSeconds: 300, source: "runpod-serverless-endpoint-config" }; } };
  assert.equal(validRunpodPrepare(args(), env), true);
  const result = await prepareRunpodExperiment(env, "owner-1", args(), { client, now: 1000 });
  assert.equal(offers, 1);
  assert.equal(result.provider_approved_plan.estimated_cost_usd, "0.020334");
  assert.equal(result.provider_approved_plan.max_cost_usd, "1.00");
  assert.equal(result.provider_approved_plan.image_digest, `sha256:${"a".repeat(64)}`);
  assert.equal(result.machine_state.state, "prepared");

  const replay = await prepareRunpodExperiment(env, "owner-1", args(), { client, now: 1001 });
  assert.equal(offers, 1, "an idempotent retry must not resample mutable price evidence");
  assert.equal(replay.machine_state.run_id, result.machine_state.run_id);
  assert.equal(replay.plan_fingerprint, result.plan_fingerprint);
  assert.deepEqual(replay.provider_approved_plan, result.provider_approved_plan);
  assert.equal(replay.machine_state.idempotent_replay, true);
});

test("default prepare uses the pinned maximum without management API access", async () => {
  const env = environment();
  const result = await prepareRunpodExperiment(env, "owner-1", {
    ...args(), idempotency_key: "runpod-pinned-maximum-001",
  }, { now: 1000 });
  assert.equal(result.provider_approved_plan.hourly_price_usd, "0.240000");
  assert.equal(result.provider_approved_plan.pricing_source, "sites-operator-pinned-serverless-maximum");
  assert.equal(result.provider_approved_plan.estimated_cost_usd, "0.020334");
  assert.equal(result.provider_approved_plan.pricing_valid_until, 1600);
  assert.equal(result.expires_at, 1600);
  assert.equal(result.authorization_validity_seconds, 600);
  assert.match(result.human_summary, /承認窓は10分/);
});

test("rejects floating images, wrong source, and estimates above the ceiling", async () => {
  const env = environment();
  assert.equal(validRunpodPrepare({ ...args(), commit: "c".repeat(40) }, env), false);
  assert.equal(validRunpodPrepare(args(), { ...env, RUNPOD_WORKLOAD_IMAGE: "image:latest" }), false);
  const client = { async getVerifiedOffer() { return { gpuId: env.RUNPOD_GPU_ID, cloud: "SERVERLESS", gpuCount: 1,
    hourlyPriceUsd: 1000, availability: "CONFIGURED", dataCenterId: env.RUNPOD_SERVERLESS_ENDPOINT_ID, checkedAt: 1000,
    validForSeconds: 300, source: "runpod-serverless-endpoint-config" }; } };
  await assert.rejects(prepareRunpodExperiment(env, "owner-1", args(), { client, now: 1000 }),
    /RUNPOD_ESTIMATED_COST_OUT_OF_BOUNDS/);
});

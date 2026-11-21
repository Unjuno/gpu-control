import assert from "node:assert/strict";
import test from "node:test";
import { RunpodProviderError, RunpodV2Client, runpodConfigured, validateJobStatus, validateSubmittedJob } from "./runpod_provider.js";

const env = { RUNPOD_API_KEY: "secret-api-key-with-enough-bytes",
  RUNPOD_WORKLOAD_IMAGE: `ghcr.io/unjuno/gpu-control-runpod@sha256:${"a".repeat(64)}`,
  RUNPOD_GPU_ID: "NVIDIA RTX 2000 Ada Generation", RUNPOD_SERVERLESS_ENDPOINT_ID: "endpoint_abc123",
  RUNPOD_SERVERLESS_HOURLY_PRICE_USD: "0.240000", RUNPOD_SERVERLESS_GPU_POOL_ID: "ADA_24",
  RUNPOD_WORKLOAD_SOURCE_SHA: "b".repeat(40) };
function jsonResponse(value, status = 200) { return new Response(JSON.stringify(value), { status, headers: { "content-type": "application/json" } }); }

test("configuration requires an immutable image, endpoint, price, and bounded secret", () => {
  assert.equal(runpodConfigured(env), true);
  assert.equal(runpodConfigured({ ...env, RUNPOD_WORKLOAD_IMAGE: "image:latest" }), false);
  assert.equal(runpodConfigured({ ...env, RUNPOD_SERVERLESS_ENDPOINT_ID: ".." }), false);
  assert.equal(runpodConfigured({ ...env, RUNPOD_SERVERLESS_HOURLY_PRICE_USD: "free" }), false);
});

test("submit sends an asynchronous bounded serverless job", async () => {
  let request;
  const client = new RunpodV2Client(env, { fetchImpl: async (url, init) => {
    request = { url, init, body: JSON.parse(init.body) }; return jsonResponse({ id: "job_abc123", status: "IN_QUEUE" });
  } });
  const result = validateSubmittedJob(await client.submitJob({ runId: "1".repeat(32), planFingerprint: "b".repeat(64),
    nonce: "c".repeat(64), completionKeyB64: Buffer.alloc(32, 7).toString("base64"),
    completionKeyId: "d".repeat(32), sourceSha: "e".repeat(40) }));
  assert.deepEqual(result, { id: "job_abc123", status: "IN_QUEUE" });
  assert.equal(request.url, "https://api.runpod.ai/v2/endpoint_abc123/run");
  assert.deepEqual(request.body.policy, { executionTimeout: 30000, ttl: 300000 });
  assert.equal(request.body.input.execution_name, "gpu-control-111111111111");
});

test("offer is accepted only from the exact bounded endpoint configuration", async () => {
  const endpoint = { id: env.RUNPOD_SERVERLESS_ENDPOINT_ID, type: "QUEUE", image: env.RUNPOD_WORKLOAD_IMAGE,
    gpu: { count: 1, pools: [env.RUNPOD_SERVERLESS_GPU_POOL_ID] }, workers: { min: 0, max: 1, idleTimeout: 5 }, timeout: 30000,
    ports: [], networkVolumes: [], mounts: { network: [], global: [] }, args: "", env: {
      GPU_CONTROL_SOURCE_SHA: env.RUNPOD_WORKLOAD_SOURCE_SHA,
      GPU_CONTROL_IMAGE_DIGEST: env.RUNPOD_WORKLOAD_IMAGE.split("@")[1],
    } };
  const client = new RunpodV2Client(env, { fetchImpl: async (url) => {
    assert.equal(url, "https://api.runpod.io/v2/serverless/endpoint_abc123"); return jsonResponse(endpoint);
  } });
  assert.equal((await client.getVerifiedOffer()).cloud, "SERVERLESS");
  const unsafe = new RunpodV2Client(env, { fetchImpl: async () => jsonResponse({ ...endpoint, workers: { min: 1, max: 1, idleTimeout: 5 } }) });
  await assert.rejects(unsafe.getVerifiedOffer(), (error) => error.code === "RUNPOD_ENDPOINT_CONFIGURATION_MISMATCH");
  const costlyIdle = new RunpodV2Client(env, { fetchImpl: async () => jsonResponse({ ...endpoint, workers: { min: 0, max: 1, idleTimeout: 3600 } }) });
  await assert.rejects(costlyIdle.getVerifiedOffer(), (error) => error.code === "RUNPOD_ENDPOINT_CONFIGURATION_MISMATCH");
});

test("status and cancellation are endpoint-scoped and validate job ids", async () => {
  const urls = [];
  const client = new RunpodV2Client(env, { fetchImpl: async (url) => { urls.push(url); return jsonResponse({ id: "job_abc123", status: "CANCELLED" }); } });
  validateJobStatus(await client.getJob("job_abc123"), "job_abc123");
  await client.cancelJob("job_abc123");
  assert.deepEqual(urls, ["https://api.runpod.ai/v2/endpoint_abc123/status/job_abc123", "https://api.runpod.ai/v2/endpoint_abc123/cancel/job_abc123"]);
  assert.throws(() => client.getJob("../../account"), RunpodProviderError);
});

test("cancellation requires the exact terminal receipt", async () => {
  const client = new RunpodV2Client(env, { fetchImpl: async () => jsonResponse({ id: "job_abc123", status: "IN_PROGRESS" }) });
  await assert.rejects(client.cancelJob("job_abc123"), (error) => error.code === "RUNPOD_CANCELLATION_NOT_TERMINAL");
});

test("provider errors do not expose response text and redirects are rejected", async () => {
  const payment = new RunpodV2Client(env, { fetchImpl: async () => jsonResponse({ detail: "add money now" }, 402) });
  await assert.rejects(payment.getJob("job_abc123"), (error) => error.code === "RUNPOD_INSUFFICIENT_BALANCE" && !error.message.includes("add money"));
  const redirect = new RunpodV2Client(env, { fetchImpl: async () => new Response(null, { status: 302, headers: { location: "https://evil.invalid" } }) });
  await assert.rejects(redirect.getJob("job_abc123"), (error) => error.code === "RUNPOD_REDIRECT_REJECTED");
});

test("receipts and status require exact safe shapes", () => {
  assert.throws(() => validateSubmittedJob({ id: "job_abc123", status: "COMPLETED" }), RunpodProviderError);
  assert.throws(() => validateJobStatus({ id: "other_job", status: "COMPLETED" }, "job_abc123"), RunpodProviderError);
});
